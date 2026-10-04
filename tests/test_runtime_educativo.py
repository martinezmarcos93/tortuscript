"""Pruebas de la fachada del runtime educativo autenticado."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript.acceso import AccesoProducto
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from tortuscript.perfil_educativo import PerfilEducativoService, ContextoEducativoError
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot
from tortuscript.runtime_educativo import RuntimeEducativo


class RuntimeEducativoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        db = self.tmp / "cuentas.sqlite3"
        self.cuentas = CuentaRepository(db)
        self.cuentas.ensure_schema()
        self.auth = AuthRepository(db)
        self.auth.ensure_schema()
        cuenta = self.cuentas.crear_account("adulto@example.com")
        self.auth.set_password(cuenta.id, "una-clave-larga-123")
        self.auth.marcar_verificada(cuenta.id)
        perfil = self.cuentas.crear_child_profile(cuenta.id, "Ana")
        self.session, _, _ = self.auth.create_session(cuenta.id)
        self.auth.select_profile(self.session, perfil.id)
        self.perfil = perfil
        self.service = PerfilEducativoService(
            self.cuentas,
            self.auth,
            ProgresoChildProfile(self.tmp / "progress"),
            AccesoProducto(self.cuentas),
        )
        self.runtime = RuntimeEducativo(self.service)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_runtime_resuelve_contexto_y_progreso_por_perfil(self):
        snapshot = nuevo_snapshot(self.perfil.id, {"xp_total": 42})
        self.runtime.guardar(self.session, snapshot)
        publico = self.runtime.snapshot_publico(self.session)
        self.assertEqual(publico["perfil"]["id"], self.perfil.id)
        self.assertEqual(publico["progreso"]["data"]["xp_total"], 42)
        self.assertEqual(publico["progreso"]["profile_id"], self.perfil.id)

    def test_runtime_no_permita_sesion_sin_perfil(self):
        self.auth.clear_profile(self.session)
        with self.assertRaises(ContextoEducativoError):
            self.runtime.snapshot_publico(self.session)

    def test_snapshot_parcial_o_de_esquema_anterior_se_completa_al_leerlo(self):
        # El esquema es aditivo: un snapshot sin campos nuevos no puede romper las páginas.
        from tortuscript import progreso as legado
        self.service.guardar_progreso(self.session, nuevo_snapshot(self.perfil.id, {"xp_total": 40}))
        datos = self.runtime.cargar_datos(self.session)
        self.assertEqual(datos["xp_total"], 40)
        for campo in legado.PROGRESO_INICIAL:
            self.assertIn(campo, datos)
        self.assertEqual(datos["version"], legado.VERSION_ESQUEMA)


if __name__ == "__main__":
    unittest.main()
