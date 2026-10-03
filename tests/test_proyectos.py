"""Mis proyectos: guardar, abrir, duplicar y borrar lo hecho en Experimentar y en la Zona Tortuga."""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tortuscript import persistencia_local, logros, progreso, proyectos
from tortuscript.proyectos import ErrorProyecto

try:
    import flask  # noqa: F401
    HAY_FLASK = True
except ImportError:
    HAY_FLASK = False


class TestProyectos(unittest.TestCase):
    def test_guardar_y_obtener(self):
        p = {}
        id_ = proyectos.guardar(p, "  Mi   estrella ", "tortuga", "repetir 5 veces:", hoy=date(2026, 9, 25))
        guardado = proyectos.obtener(p, id_)
        self.assertEqual((guardado["nombre"], guardado["tipo"], guardado["codigo"]), ("Mi estrella", "tortuga", "repetir 5 veces:"))
        self.assertEqual((guardado["creado"], guardado["actualizado"]), ("2026-09-25", "2026-09-25"))
        self.assertIsNone(proyectos.obtener(p, "nada"))
        self.assertIsNone(proyectos.obtener({}, id_))

    def test_guardar_con_id_actualiza_sin_crear_otro(self):
        p = {}
        id_ = proyectos.guardar(p, "Uno", "experimentar", "a", hoy=date(2026, 9, 1))
        igual = proyectos.guardar(p, "Uno v2", "experimentar", "b", proyecto_id=id_, hoy=date(2026, 9, 2))
        self.assertEqual(igual, id_)
        self.assertEqual(len(p["proyectos"]), 1)
        self.assertEqual((p["proyectos"][id_]["nombre"], p["proyectos"][id_]["codigo"]), ("Uno v2", "b"))
        self.assertEqual((p["proyectos"][id_]["creado"], p["proyectos"][id_]["actualizado"]), ("2026-09-01", "2026-09-02"))

    def test_id_desconocido_crea_uno_nuevo(self):
        p = {}
        id_ = proyectos.guardar(p, "X", "experimentar", "a", proyecto_id="inventado")
        self.assertNotEqual(id_, "inventado")

    def test_validaciones_con_mensajes_para_el_chico(self):
        for args, texto in (((" ", "experimentar", "a"), "nombre"), (("X", "otro", "a"), "tipo"),
                            (("X", "experimentar", "a" * 5001), "largo")):
            with self.subTest(texto=texto), self.assertRaises(ErrorProyecto) as ctx:
                proyectos.guardar({}, *args)
            self.assertIn(texto, str(ctx.exception).lower())

    def test_nombre_largo_se_recorta_y_codigo_vacio_se_permite(self):
        p = {}
        id_ = proyectos.guardar(p, "n" * 100, "experimentar", "")
        self.assertEqual(len(p["proyectos"][id_]["nombre"]), proyectos.MAX_NOMBRE)

    def test_limite_de_proyectos(self):
        p = {}
        for i in range(proyectos.MAX_PROYECTOS):
            proyectos.guardar(p, f"P{i}", "experimentar", "x")
        with self.assertRaises(ErrorProyecto) as ctx:
            proyectos.guardar(p, "uno más", "experimentar", "x")
        self.assertIn("borrá", str(ctx.exception))
        proyectos.guardar(p, "P0 editado", "experimentar", "y", proyecto_id=next(iter(p["proyectos"])))   # editar sí se puede

    def test_duplicar_y_borrar(self):
        p = {}
        id_ = proyectos.guardar(p, "Casa", "tortuga", "avanzar 10")
        copia = proyectos.duplicar(p, id_)
        self.assertNotEqual(copia, id_)
        self.assertEqual((p["proyectos"][copia]["nombre"], p["proyectos"][copia]["codigo"], p["proyectos"][copia]["tipo"]),
                         ("Copia de Casa", "avanzar 10", "tortuga"))
        proyectos.borrar(p, id_)
        self.assertNotIn(id_, p["proyectos"])
        for accion in (proyectos.borrar, proyectos.duplicar):
            with self.assertRaises(ErrorProyecto):
                accion(p, id_)

    def test_listar_los_mas_recientes_primero(self):
        p = {}
        a = proyectos.guardar(p, "Viejo", "experimentar", "1", hoy=date(2026, 9, 1))
        b = proyectos.guardar(p, "Nuevo", "tortuga", "2", hoy=date(2026, 9, 20))
        self.assertEqual([x["id"] for x in proyectos.listar(p)], [b, a])
        self.assertEqual(proyectos.listar({}), [])


class TestLogrosDeProyectos(unittest.TestCase):
    def test_logros_por_proyectos_guardados(self):
        resumen = {"pasos_hechos": 0, "hechas_ids": set(), "perfectas": 0, "cursos": {}, "estrellas3": 0, "nivel": 1, "proyectos": 1}
        self.assertIn("primer-proyecto", logros.cumplidos({}, resumen))
        self.assertNotIn("cinco-proyectos", logros.cumplidos({}, resumen))
        self.assertIn("cinco-proyectos", logros.cumplidos({}, dict(resumen, proyectos=5)))


@unittest.skipUnless(HAY_FLASK, "Flask no instalado")
class TestWebProyectos(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = (persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL)
        persistencia_local.DIRECTORIO = self._dir
        persistencia_local.PERFIL_ACTUAL = "default"
        from web.app import create_app
        self.app = create_app(token="t")
        self.app.config.update(
            TESTING=True,
            ACCOUNT_DB=self._dir / "cuentas.sqlite3",
            ACCOUNT_COOKIE_SECURE=False,
            PROGRESS_DIR=self._dir / "progreso_perfiles",
        )
        self.c = self.app.test_client()
        self.h = {"X-Tortu-Token": "t"}
        from fixtures_cuenta import preparar_sesion_educativa
        preparar_sesion_educativa(self.app, self.c, email="proyectos@example.com", nombre="Ana", token="t")

    def tearDown(self):
        persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL = self._orig
        shutil.rmtree(self._dir)

    def post(self, ruta, datos=None):
        return self.c.post(ruta, json=datos or {}, headers=self.h)

    def guardar(self, nombre="Mi dibujo", tipo="tortuga", codigo="avanzar 50", **extra):
        return self.post("/api/proyectos", {"nombre": nombre, "tipo": tipo, "codigo": codigo, **extra}).get_json()

    def progreso_cuenta(self):
        respuesta = self.c.get("/cuenta/progreso")
        if respuesta.status_code != 200 or not respuesta.json.get("progreso"):
            raise AssertionError(f"no se pudo leer el progreso comercial: {respuesta.status_code} {respuesta.get_data(as_text=True)}")
        return respuesta.json["progreso"]["data"]

    def test_guardar_abrir_y_editar(self):
        r = self.guardar()
        self.assertTrue(r["ok"])
        id_ = r["id"]
        self.assertEqual([a["id"] for a in r["avisos"] if a["tipo"] == "logro"], ["primer-proyecto"])
        html = self.c.get(f"/tortuga?proyecto={id_}").get_data(as_text=True)
        self.assertIn("avanzar 50", html)
        self.assertIn("Mi dibujo", html)
        self.assertEqual(self.guardar(nombre="Mi dibujo 2", codigo="avanzar 99", id=id_)["id"], id_)
        self.assertEqual(self.progreso_cuenta()["proyectos"][id_]["codigo"], "avanzar 99")
        self.assertEqual(self.guardar(id=id_)["avisos"], [])                            # el logro no se repite

    def test_un_proyecto_se_abre_en_su_pagina(self):
        id_ = self.guardar(tipo="experimentar", codigo='mostrar "hola"')["id"]
        self.assertEqual(self.c.get(f"/experimentar?proyecto={id_}").status_code, 200)
        r = self.c.get(f"/tortuga?proyecto={id_}")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith(f"/experimentar?proyecto={id_}"))
        r = self.c.get("/experimentar?proyecto=noexiste")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/experimentar"))

    def test_lista_duplicar_y_borrar(self):
        id_ = self.guardar(nombre="Casa")["id"]
        copia = self.post(f"/api/proyectos/{id_}/duplicar").get_json()
        self.assertTrue(copia["ok"])
        self.assertEqual(copia["total"], 2)
        html = self.c.get("/proyectos").get_data(as_text=True)
        self.assertIn("Casa", html)
        self.assertIn("Copia de Casa", html)
        self.assertEqual(self.post(f"/api/proyectos/{id_}/borrar").get_json()["total"], 1)
        self.assertEqual(self.post(f"/api/proyectos/{id_}/borrar").status_code, 400)       # ya no existe

    def test_errores_que_el_chico_puede_corregir_vuelven_como_400_con_mensaje(self):
        r = self.post("/api/proyectos", {"nombre": "", "tipo": "tortuga", "codigo": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("nombre", r.get_json()["mensaje"])
        self.assertEqual(self.post("/api/proyectos", {"nombre": "X", "tipo": "raro", "codigo": "x"}).status_code, 400)
        self.assertEqual(self.c.post("/api/proyectos", json={}).status_code, 403)              # sin token

    def test_pagina_vacia_y_texto_escapado(self):
        self.assertIn("Todavía no guardaste nada", self.c.get("/proyectos").get_data(as_text=True))
        self.guardar(nombre="<b>x</b>", codigo="<script>alert(1)</script>")
        html = self.c.get("/proyectos").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("<b>x</b>", html)
        proyecto_id = next(iter(self.progreso_cuenta()["proyectos"]))
        pagina = self.c.get("/tortuga?proyecto=" + proyecto_id).get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", pagina)                                 # va como JSON, no como HTML


if __name__ == "__main__":
    unittest.main()
