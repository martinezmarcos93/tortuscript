"""El paquete instalable: lleva la app y nunca el progreso ni la basura de desarrollo."""
import hashlib
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "herramientas"))

import crear_paquete  # noqa: E402
from tortuscript import contenido  # noqa: E402


def arbol(base):
    """Un mini proyecto con cosas que van y cosas que NO tienen que ir."""
    archivos = {
        "tortuscript/__init__.py": "", "tortuscript/motor.py": "x = 1",
        "tortuscript/__pycache__/motor.cpython-39.pyc": "basura",
        "web/templates/base.html": "<html>", "web/static/css/tortu.css": "a{}",
        "contenido/cursos/curso.json": "{}", "docs/guia.md": "# guia",
        "lanzadores/iniciar.sh": "#!/bin/sh", "herramientas/h.py": "print(1)",
        "iniciar_web.py": "", "requirements.txt": "Flask==3.1.3", "README.md": "# r", "CHANGELOG.md": "# c",
        # privado / desarrollo: NO
        "progreso_lua.json": "{}", "progreso_lua.json.bak": "{}", "progreso_lua.json.corrupto-2026": "{}",
        "config_tortuscript.json": "{}", "logs/tortuscript.log": "log",
        "tests/test_algo.py": "", ".venv/lib/x.py": "", ".git/config": "", "dist/viejo.zip": "zip",
        ".claude/settings.json": "{}", "web/static/js/tmp.tmp": "t",
    }
    for rel, contenido in archivos.items():
        ruta = Path(base) / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")


class TestQueEntra(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        arbol(self.raiz)

    def tearDown(self):
        self._tmp.cleanup()

    def test_lleva_la_app_y_deja_afuera_lo_privado(self):
        hallados = {p.as_posix() for p in crear_paquete.archivos_del_paquete(self.raiz)}
        for debe in ("tortuscript/__init__.py", "tortuscript/motor.py", "web/templates/base.html", "web/static/css/tortu.css",
                     "contenido/cursos/curso.json", "iniciar_web.py", "requirements.txt", "README.md", "CHANGELOG.md",
                     "lanzadores/iniciar.sh", "docs/guia.md", "herramientas/h.py"):
            self.assertIn(debe, hallados)
        for no_debe in hallados:
            self.assertNotRegex(no_debe, r"progreso_|config_tortuscript|logs/|tests/|\.venv|\.git|dist/|__pycache__|\.pyc|\.claude|\.tmp")

    def test_esta_ordenado_y_no_repite(self):
        hallados = crear_paquete.archivos_del_paquete(self.raiz)
        self.assertEqual(hallados, sorted(set(hallados)))

    def test_carpetas_inexistentes_no_rompen(self):
        with tempfile.TemporaryDirectory() as vacio:
            self.assertEqual(crear_paquete.archivos_del_paquete(vacio), [])


class TestElZip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name) / "proyecto"
        arbol(self.raiz)
        self.salida = Path(self._tmp.name) / "salida"

    def tearDown(self):
        self._tmp.cleanup()

    def crear(self, **kw):
        return crear_paquete.crear_paquete(self.raiz, self.salida, hoy=date(2026, 9, 25), **kw)

    def test_nombre_estructura_y_extras(self):
        ruta = self.crear()
        self.assertEqual(ruta.name, "TortuScript-20260925.zip")
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            self.assertTrue(all(n.startswith("TortuScript/") for n in nombres))
            for extra in ("INSTALAR.txt", "instalar.bat", "instalar.sh", "VERSION.txt"):
                self.assertIn(f"TortuScript/{extra}", nombres)
            self.assertIn("TortuScript/iniciar_web.py", nombres)
            self.assertFalse([n for n in nombres if "progreso_" in n or "tests/" in n or "__pycache__" in n])
            self.assertIn("25/09/2026", z.read("TortuScript/VERSION.txt").decode("utf-8"))

    def test_con_lock_los_instaladores_verifican_hashes_y_lo_incluyen(self):
        (self.raiz / "requirements.lock").write_text("Flask==3.1.3 \\\n    --hash=sha256:abc\n", encoding="utf-8")
        with zipfile.ZipFile(self.crear()) as z:
            bat = z.read("TortuScript/instalar.bat").decode("utf-8")
            sh = z.read("TortuScript/instalar.sh").decode("utf-8")
            self.assertIn("TortuScript/requirements.lock", z.namelist())
        self.assertIn("-m pip install --require-hashes -r requirements.lock", bat)
        self.assertIn(".venv/bin/python -m pip install --require-hashes -r requirements.lock", sh)

    def test_los_instaladores_instalan_flask_y_cada_uno_con_su_fin_de_linea(self):
        with zipfile.ZipFile(self.crear()) as z:
            bat = z.read("TortuScript/instalar.bat").decode("utf-8")
            sh = z.read("TortuScript/instalar.sh").decode("utf-8")
        self.assertIn("-m pip install -r requirements.txt", bat)
        self.assertIn("\r\n", bat)
        self.assertNotIn("--no-index", bat)
        self.assertIn(".venv/bin/python -m pip install -r requirements.txt", sh)
        self.assertNotIn("\r", sh)
        self.assertIn("{", sh)                      # las llaves de sh quedaron bien escapadas
        self.assertNotIn("{{", sh)

    def test_huella_sha256(self):
        ruta = self.crear()
        linea = (self.salida / (ruta.name + ".sha256")).read_text(encoding="utf-8").split()
        self.assertEqual(linea[0], hashlib.sha256(ruta.read_bytes()).hexdigest())
        self.assertEqual(linea[1], ruta.name)

    def test_con_ruedas_instala_sin_internet(self):
        def falsa(destino, raiz):
            (Path(destino) / "Flask-3.1.3-py3-none-any.whl").write_bytes(b"rueda")
        with mock.patch.object(crear_paquete, "_descargar_ruedas", side_effect=falsa):
            ruta = self.crear(con_ruedas=True)
        with zipfile.ZipFile(ruta) as z:
            self.assertIn("TortuScript/wheels/Flask-3.1.3-py3-none-any.whl", z.namelist())
            self.assertIn("--no-index --find-links wheels", z.read("TortuScript/instalar.bat").decode("utf-8"))
            self.assertIn("--no-index --find-links wheels", z.read("TortuScript/instalar.sh").decode("utf-8"))
            self.assertIn("sin internet", z.read("TortuScript/INSTALAR.txt").decode("utf-8"))

    def test_sin_ruedas_no_baja_nada(self):
        with mock.patch.object(crear_paquete, "_descargar_ruedas") as descargar:
            self.crear()
        descargar.assert_not_called()


class TestElProyectoReal(unittest.TestCase):
    def test_lo_esencial_esta_y_lo_privado_no(self):
        hallados = {p.as_posix() for p in crear_paquete.archivos_del_paquete(RAIZ)}
        for debe in ("iniciar_web.py", "requirements.txt", "web/templates/base.html", "web/static/css/tortu.css",
                     "web/static/img/tortuscript.svg", "contenido/cursos/primeros-pasos.json", "contenido/referencia.json",
                     "tortuscript/leccion.py", "lanzadores/Iniciar TortuScript.bat", "docs/CONTENIDO.md"):
            self.assertIn(debe, hallados)
        self.assertFalse([
            h for h in hallados
            if h.startswith(("tests/", "logs/", ".venv", ".git"))
            or (Path(h).name.startswith("progreso_") and Path(h).suffix != ".py")
        ])

    def test_los_cursos_y_las_fuentes_viajan_completos(self):
        hallados = {p.as_posix() for p in crear_paquete.archivos_del_paquete(RAIZ)}
        self.assertEqual({h for h in hallados if h.startswith("contenido/cursos/")},
                         {f"contenido/cursos/{n}.json" for n in contenido.ORDEN_CURSOS})
        self.assertGreaterEqual(len([h for h in hallados if h.startswith("web/static/fonts/")]), 6)
        self.assertGreaterEqual(len([h for h in hallados if h.startswith("web/static/vendor/")]), 7)



class TestLockDelProyecto(unittest.TestCase):
    def test_leer_lock(self):
        import auditar_dependencias as ad
        texto = "# comentario\nFlask==3.1.3 \\\n    --hash=sha256:aa \\\n    --hash=sha256:bb\nJinja2==3.1.6 \\\n    --hash=sha256:cc\n"
        self.assertEqual(ad.leer_lock(texto), [("Flask", "3.1.3"), ("Jinja2", "3.1.6")])

    def test_el_lock_real_fija_flask_como_requirements_y_todo_con_hashes(self):
        import auditar_dependencias as ad
        lock = (RAIZ / "requirements.lock").read_text(encoding="utf-8")
        paquetes = dict(ad.leer_lock(lock))
        flask = next(l for l in (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines() if l.startswith("Flask=="))
        self.assertEqual(paquetes["Flask"], flask.split("==")[1])
        self.assertTrue({"Werkzeug", "Jinja2", "MarkupSafe", "itsdangerous", "click", "blinker"} <= set(paquetes))
        bloques = [b for b in lock.split("\n") if ad._LINEA.match(b)]
        self.assertEqual(len(bloques), len(paquetes))
        self.assertGreaterEqual(lock.count("--hash=sha256:"), len(paquetes))       # al menos un hash por paquete


if __name__ == "__main__":
    unittest.main()
