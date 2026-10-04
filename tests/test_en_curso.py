"""El estado «en curso» (pistas, intentos, práctica, colas) vive en disco por perfil, no en el proceso."""
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tortuscript import en_curso, persistencia_local
from tortuscript.en_curso import EnCurso
from web.app import create_app

try:
    from fixtures_cuenta import preparar_sesion_educativa
except ImportError:
    from tests.fixtures_cuenta import preparar_sesion_educativa

try:
    import fcntl
except ImportError:
    fcntl = None

PERFIL = "child_0123456789abcdef01234567"


class TestAlmacen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = EnCurso(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ida_y_vuelta_y_perfil_sin_archivo(self):
        self.assertEqual(self.store.cargar(PERFIL), en_curso.vacio())
        datos = {"pistas": {"hola|5": 2}, "intentos": {"hola|1": {"errores": 3, "revelado": True}},
                 "practica": {"dia": "2026-10-04", "pasos": [("hola", 1), ("chau", 2)]}, "colas": {"todos|7": [3, 1, 2]}}
        self.store.guardar(PERFIL, datos)
        self.assertEqual(self.store.cargar(PERFIL), datos)           # los pasos vuelven como tuplas

    def test_archivo_danado_o_con_basura_se_reinicia_sin_romper(self):
        archivo = self.tmp / f"en_curso_{PERFIL}.json"
        for contenido in ("{roto", "[]", '"texto"', json.dumps({"pistas": {"a|1": 99, "b|2": "3", "c|3": 1},
                                                                 "intentos": {"a|1": {"errores": -4}, "b|2": 7},
                                                                 "practica": {"dia": 5, "pasos": "x"},
                                                                 "colas": {"x": ["a"], "y": [1, 2]}, "extra": 1})):
            archivo.write_text(contenido, encoding="utf-8")
            datos = self.store.cargar(PERFIL)
            self.assertEqual(set(datos), {"pistas", "intentos", "practica", "colas"})
        self.assertEqual(datos, {"pistas": {"c|3": 1}, "intentos": {}, "practica": None, "colas": {"y": [1, 2]}})

    def test_el_tamano_esta_acotado_y_se_conserva_lo_mas_nuevo(self):
        datos = en_curso.vacio()
        datos["pistas"] = {f"l|{n}": 1 for n in range(en_curso.ENTRADAS_MAX + 50)}
        datos["colas"] = {f"todos|{n}": [n] for n in range(en_curso.COLAS_MAX + 4)}
        self.store.guardar(PERFIL, datos)
        guardado = self.store.cargar(PERFIL)
        self.assertEqual(len(guardado["pistas"]), en_curso.ENTRADAS_MAX)
        self.assertIn(f"l|{en_curso.ENTRADAS_MAX + 49}", guardado["pistas"])
        self.assertNotIn("l|0", guardado["pistas"])
        self.assertEqual(list(guardado["colas"]), [f"todos|{n}" for n in range(4, en_curso.COLAS_MAX + 4)])

    def test_solo_identificadores_internos(self):
        for malo in ("Ana", "../../etc/passwd", "child_x", None):
            with self.assertRaises(ValueError):
                self.store.cargar(malo)


class TestEntreProcesos(unittest.TestCase):
    """Dos aplicaciones sobre los mismos datos equivalen a dos procesos web (o a un reinicio)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self.tmp
        self.a = self._app()
        self.ca = self.a.test_client()
        self.fx = preparar_sesion_educativa(self.a, self.ca, email="encurso@example.com", token="t")
        self.b = self._app()
        self.cb = self.b.test_client()
        self.cb.set_cookie("tortu_session", self.ca.get_cookie("tortu_session").value)
        self.h = {"X-Tortu-Token": "t"}

    def _app(self):
        app = create_app(token="t")
        app.config.update(TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3", PROGRESS_DIR=self.tmp / "progreso_perfiles")
        return app

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self.tmp)

    def test_las_pistas_pedidas_en_un_proceso_cuentan_en_el_otro(self):
        ruta = "/api/lecciones/hola-mundo/pasos/5"
        self.assertEqual(self.ca.post(ruta + "/pista", headers=self.h).json["nivel"], 1)
        self.assertEqual(self.cb.post(ruta + "/pista", headers=self.h).json["nivel"], 2)      # sigue la cuenta
        r = self.ca.post(ruta + "/evaluar", json={"codigo": 'mostrar "Hola mundo"'}, headers=self.h).json
        self.assertEqual(r["premio"]["estrellas"], 1)                                          # dos pistas: una estrella

    def test_los_errores_de_un_paso_sobreviven_a_un_reinicio(self):
        ruta = "/api/lecciones/hola-mundo/pasos/1"
        self.assertEqual(self.ca.post(ruta + "/respuesta", headers=self.h).status_code, 403)   # todavía no intentó
        self.ca.post(ruta + "/comprobar", json={"respuesta": "escribir"}, headers=self.h)
        self.ca.post(ruta + "/comprobar", json={"respuesta": "pantalla"}, headers=self.h)
        self.assertEqual(self.cb.post(ruta + "/respuesta", headers=self.h).status_code, 200)   # otro proceso lo sabe

    def test_la_cola_de_repaso_fijada_en_un_proceso_la_ve_el_otro(self):
        self.ca.post("/api/ejercicios/1/evaluar", json={"codigo": 'mostrar "Hola mundo"'}, headers=self.h)
        inicio = self.ca.get("/repaso/todos?s=7")
        self.assertEqual(inicio.status_code, 302)
        self.assertEqual(self.cb.get(inicio.headers["Location"]).status_code, 200)

    def test_abrir_la_leccion_reinicia_pistas_en_todos_los_procesos(self):
        ruta = "/api/lecciones/hola-mundo/pasos/5/pista"
        self.ca.post(ruta, headers=self.h)
        self.cb.get("/leccion/hola-mundo")
        self.assertEqual(self.ca.post(ruta, headers=self.h).json["nivel"], 1)

    def test_el_estado_en_curso_no_es_progreso(self):
        self.ca.post("/api/lecciones/hola-mundo/pasos/5/pista", headers=self.h)
        self.assertTrue(list((self.tmp / "progreso_perfiles").glob("en_curso_child_*.json")))
        exportado = json.dumps(self.ca.get("/cuenta/datos/exportar").json)
        self.assertNotIn("en_curso", exportado)
        from tortuscript import respaldo_datos
        self.tmp.joinpath("instance").mkdir()
        shutil.copy2(self.tmp / "cuentas.sqlite3", self.tmp / "instance" / "cuentas.sqlite3")
        shutil.copytree(self.tmp / "progreso_perfiles", self.tmp / "instance" / "progreso_perfiles")
        carpeta = respaldo_datos.crear(self.tmp / "instance", self.tmp / "respaldos")
        nombres = [p.name for p in carpeta.rglob("*") if p.is_file()]
        self.assertFalse([n for n in nombres if "en_curso" in n or "candado" in n], nombres)

    @unittest.skipIf(fcntl is None, "sin fcntl (Windows)")
    def test_un_pedido_espera_si_otro_proceso_tiene_el_candado_del_perfil(self):
        self.ca.get("/api/estado", headers=self.h)                   # crea el archivo de candado
        candado = self.tmp / "progreso_perfiles" / f".candado_{self.fx['perfil_id']}"
        self.assertTrue(candado.exists())
        terminado = []

        def pedir():
            terminado.append(self.cb.get("/api/estado", headers=self.h).status_code)

        with open(candado, "a") as ajeno:
            fcntl.flock(ajeno, fcntl.LOCK_EX)                        # «otro proceso» está en su sección crítica
            hilo = threading.Thread(target=pedir)
            hilo.start()
            time.sleep(0.4)
            self.assertEqual(terminado, [])                          # el pedido espera
        hilo.join(timeout=10)
        self.assertEqual(terminado, [200])

    def test_otro_perfil_no_espera(self):
        otro = self.a.test_client()
        preparar_sesion_educativa(self.a, otro, email="otra-familia@example.com", nombre="Bruno", token="t")
        if fcntl is None:
            self.skipTest("sin fcntl (Windows)")
        candado = self.tmp / "progreso_perfiles" / f".candado_{self.fx['perfil_id']}"
        self.ca.get("/api/estado", headers=self.h)
        with open(candado, "a") as ajeno:
            fcntl.flock(ajeno, fcntl.LOCK_EX)
            self.assertEqual(otro.get("/api/estado", headers=self.h).status_code, 200)   # no comparte candado


if __name__ == "__main__":
    unittest.main()
