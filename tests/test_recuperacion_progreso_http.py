"""Un archivo de progreso dañado no deja al perfil con error 500 permanente (Barrido 5)."""
import logging
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript import persistencia_local
from web.app import create_app

try:
    from fixtures_cuenta import preparar_sesion_educativa
except ImportError:
    from tests.fixtures_cuenta import preparar_sesion_educativa


class TestRecuperacionProgresoHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self.tmp
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
                               PROGRESS_DIR=self.tmp / "progreso_perfiles")
        self.c = self.app.test_client()
        self.fx = preparar_sesion_educativa(self.app, self.c, email="recupera@example.com", token="t")
        self.h = {"X-Tortu-Token": "t"}
        self.archivo = self.tmp / "progreso_perfiles" / f"progreso_{self.fx['perfil_id']}.json"
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self.tmp)

    def test_con_respaldo_el_alumno_sigue_con_su_progreso(self):
        self.assertEqual(self.c.post("/api/config", json={"meta_min": 5}, headers=self.h).status_code, 200)
        self.assertEqual(self.c.post("/api/config", json={"meta_min": 10}, headers=self.h).status_code, 200)
        self.archivo.write_text("{se cortó la luz", encoding="utf-8")
        pagina = self.c.get("/", headers=self.h)
        self.assertEqual(pagina.status_code, 200)
        estado = self.c.get("/api/estado", headers=self.h).json
        self.assertEqual(estado["meta_min"], 5)                    # el respaldo es el guardado anterior
        self.assertEqual(len(list(self.archivo.parent.glob("*.corrupto-*"))), 1)

    def test_sin_respaldo_vuelve_a_la_bienvenida_en_vez_de_un_error(self):
        self.archivo.write_text("{se cortó la luz", encoding="utf-8")
        for respaldo in self.archivo.parent.glob("*.bak"):
            respaldo.unlink()
        pagina = self.c.get("/", headers=self.h)
        self.assertEqual(pagina.status_code, 302)
        self.assertIn("/bienvenida", pagina.headers["Location"])
        self.assertEqual(self.c.get("/bienvenida", headers=self.h).status_code, 200)
        self.assertEqual(len(list(self.archivo.parent.glob("*.corrupto-*"))), 1)


if __name__ == "__main__":
    unittest.main()
