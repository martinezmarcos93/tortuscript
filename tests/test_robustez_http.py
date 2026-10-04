"""Ninguna ruta debe responder 500 ante un cuerpo mal tipado (Barrido 1).

Recorre TODAS las reglas registradas en la app, así una ruta nueva queda cubierta sin
tocar este archivo. El barrido completo original (18.442 pedidos) encontró errores
internos en /api/onboarding, /api/traducir, /cuenta/perfil, /cuenta/perfiles y
/cuenta/verificar-email; esta versión reducida conserva los valores que los disparaban.
"""
import logging
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript import contenido, persistencia_local

try:
    from fixtures_cuenta import preparar_sesion_educativa      # unittest discover -s tests
except ImportError:
    from tests.fixtures_cuenta import preparar_sesion_educativa
from web.app import create_app

CAMPOS = ("codigo entradas semilla respuesta respuestas nombre tipo id experiencia meta_min entrada leccion paso "
          "omitir email password password2 token perfil_id perfil_local reemplazar proyecto_id next "
          "tam contraste movimiento letra voz velocidad").split()
VALORES = (None, True, -1, 1e308, 2 ** 70, "", "\u0000", "x" * 5000, [], [[]], ["a", 1, None], {}, {"a": {"b": []}})
# Estos estados son respuestas deliberadas, no errores internos.
ESPERADOS_5XX = {503}


class Libre:
    """Limitador que nunca corta: aquí se prueban tipos, no límites de intentos."""

    def allow(self, *args, **kwargs):
        return True, 0


class TestRobustezHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._orig = (persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL)
        persistencia_local.DIRECTORIO = cls.tmp
        cls.app = create_app(token="t")
        cls.app.config.update(
            TESTING=True, ACCOUNT_DB=cls.tmp / "cuentas.sqlite3", PROGRESS_DIR=cls.tmp / "progreso_perfiles",
            ENABLE_LOCAL_PROGRESS_MIGRATION=True,
        )
        cls.app.extensions["tortu_rate_limiter"] = Libre()
        cls.c = cls.app.test_client()
        cls.fx = preparar_sesion_educativa(cls.app, cls.c, email="robustez@example.com", token="t")
        cls.h = {"X-Tortu-Token": "t", "X-Tortu-CSRF": cls.fx["csrf"]}
        leccion = contenido.lecciones(contenido.cargar_curso())[0][1]
        tipos = {}
        for i, paso in enumerate(leccion["pasos"]):
            tipos.setdefault(paso["tipo"], str(i))                # un paso de cada tipo alcanza
        cls.parametros = {
            "<leccion_id>": [leccion["id"]], "<int:i>": sorted(set(tipos.values())) + ["99"],
            "<int:n>": ["1"], "<int:pos>": ["1"], "<modo>": ["todo"], "<curso_id>": ["x"],
            "<proyecto_id>": ["x"], "<etapa_id>": ["x"], "<ayuda_id>": ["x"], "<encuesta_id>": ["curso-terminado"],
        }

    @classmethod
    def tearDownClass(cls):
        persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL = cls._orig
        shutil.rmtree(cls.tmp)

    def _urls(self, regla):
        urls = [regla]
        for marca, valores in self.parametros.items():
            if marca in regla:
                urls = [u.replace(marca, v) for u in urls for v in valores]
        self.assertFalse(any("<" in u for u in urls), f"parámetro de ruta sin valor de prueba: {regla}")
        return urls

    def _pedir(self, metodo, url, **kw):
        respuesta = self.c.open(url, method=metodo, headers=self.h, **kw)
        respuesta.close()
        return respuesta.status_code

    def test_ningun_cuerpo_mal_tipado_provoca_error_interno(self):
        logging.disable(logging.CRITICAL)                          # los 500, si aparecen, se informan abajo
        self.addCleanup(logging.disable, logging.NOTSET)
        fallos, pedidos = [], 0
        reglas = sorted((r.rule, tuple(sorted(r.methods - {"HEAD", "OPTIONS", "GET"})))
                        for r in self.app.url_map.iter_rules()
                        if r.endpoint not in ("static", "cuenta.logout"))
        for regla, metodos in reglas:
            for url in self._urls(regla):
                for metodo in metodos:
                    cuerpos = [{"json": {k: v for k in CAMPOS}} for v in VALORES]
                    cuerpos += [{"json": v} for v in ([], "x", 7, None)]
                    cuerpos += [{"data": "{mal", "content_type": "application/json"},
                                {"data": {k: "x" for k in CAMPOS}},
                                {"data": b"\xff\xfe=\xff", "content_type": "application/x-www-form-urlencoded"}]
                    for cuerpo in cuerpos:
                        estado = self._pedir(metodo, url, **cuerpo)
                        pedidos += 1
                        if estado >= 500 and estado not in ESPERADOS_5XX:
                            fallos.append(f"{metodo} {url} → {estado} con {str(cuerpo)[:90]}")
                    # Un cuerpo pudo cambiar el perfil activo: se restaura para la ruta siguiente.
                    self.c.post("/cuenta/perfil", json={"perfil_id": self.fx["perfil_id"]}, headers=self.h)
        self.assertGreater(pedidos, 500)
        self.assertEqual(fallos, [], "\n".join(fallos[:40]))

    def test_ninguna_consulta_get_hostil_provoca_error_interno(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        consultas = ("", "?proyecto=x&s=abc&next=//evil.example&token=%00&producto[]=1",
                     "?s=99999999999999999999&proyecto=" + "x" * 3000, "?next=%ff%fe&token=&producto=")
        fallos = []
        for regla in sorted(r.rule for r in self.app.url_map.iter_rules()
                            if "GET" in r.methods and r.endpoint != "static"):
            for url in self._urls(regla):
                for consulta in consultas:
                    estado = self._pedir("GET", url + consulta)
                    if estado >= 500 and estado not in ESPERADOS_5XX:
                        fallos.append(f"GET {url}{consulta[:60]} → {estado}")
        self.assertEqual(fallos, [], "\n".join(fallos[:40]))


if __name__ == "__main__":
    unittest.main()
