"""Cada pedido asegura el esquema, valida la sesión y lee el progreso una sola vez (Barrido 5).

Antes una página hacía ~12 migraciones de esquema, 7 lecturas del progreso y ~80 transacciones SQLite.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tortuscript import persistencia_local
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from tortuscript.perfil_educativo import PerfilEducativoService
from tortuscript.progreso_childprofile import ProgresoChildProfile
from web.app import create_app

try:
    from fixtures_cuenta import preparar_sesion_educativa
except ImportError:
    from tests.fixtures_cuenta import preparar_sesion_educativa


class TestCostoPorPedido(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self.tmp
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
                               PROGRESS_DIR=self.tmp / "progreso_perfiles")
        self.c = self.app.test_client()
        self.fx = preparar_sesion_educativa(self.app, self.c, email="costo@example.com", token="t")
        self.h = {"X-Tortu-Token": "t"}

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self.tmp)

    def test_el_esquema_no_se_vuelve_a_asegurar_en_cada_pedido(self):
        with mock.patch.object(CuentaRepository, "ensure_schema") as cuentas, \
                mock.patch.object(AuthRepository, "ensure_schema") as auth:
            for ruta in ("/", "/mapa", "/logros", "/cuenta/me"):
                self.assertEqual(self.c.get(ruta, headers=self.h).status_code, 200)
        cuentas.assert_not_called()
        auth.assert_not_called()

    def test_si_se_reemplaza_la_base_el_esquema_se_asegura_de_nuevo(self):
        base = Path(self.app.config["ACCOUNT_DB"])
        copia = base.with_name("copia.sqlite3")
        shutil.copy2(base, copia)
        base.unlink()
        copia.rename(base)                                          # otro inodo, misma ruta (como una restauración)
        with mock.patch.object(CuentaRepository, "ensure_schema", autospec=True,
                               side_effect=CuentaRepository.ensure_schema) as cuentas:
            self.assertEqual(self.c.get("/cuenta/me").status_code, 200)
            self.assertEqual(self.c.get("/cuenta/me").status_code, 200)
        self.assertEqual(cuentas.call_count, 1)

    def test_una_pagina_valida_la_sesion_y_lee_el_progreso_una_sola_vez(self):
        self.c.get("/", headers=self.h)                             # la primera visita cierra la semana de la liga y guarda
        with mock.patch.object(PerfilEducativoService, "contexto", autospec=True,
                               side_effect=PerfilEducativoService.contexto) as contexto, \
                mock.patch.object(ProgresoChildProfile, "cargar", autospec=True,
                                  side_effect=ProgresoChildProfile.cargar) as cargar:
            self.assertEqual(self.c.get("/", headers=self.h).status_code, 200)
        # contexto: una vez la puerta de entrada y otra al leer el progreso (cargar_progreso revalida el dueño).
        self.assertLessEqual(contexto.call_count, 2)
        self.assertEqual(cargar.call_count, 1)

    def test_tras_escribir_el_mismo_pedido_ve_el_progreso_nuevo(self):
        # /api/config guarda y devuelve el estado calculado después: no puede salir de la lectura memorizada.
        r = self.c.post("/api/config", json={"meta_min": 5}, headers=self.h)
        self.assertEqual((r.status_code, r.json["estado"]["meta_min"]), (200, 5))
        r = self.c.post("/api/config", json={"meta_min": 15}, headers=self.h)
        self.assertEqual(r.json["estado"]["meta_min"], 15)
        self.assertEqual(self.c.get("/api/estado", headers=self.h).json["meta_min"], 15)

    def test_quien_recibe_el_progreso_no_puede_alterar_lo_memorizado(self):
        # Un helper que modifica su copia sin guardar no debe contaminar lecturas posteriores del mismo pedido.
        r = self.c.post("/api/config", json={"meta_min": 999}, headers=self.h)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.c.get("/api/estado", headers=self.h).json["meta_min"], 15)


if __name__ == "__main__":
    unittest.main()
