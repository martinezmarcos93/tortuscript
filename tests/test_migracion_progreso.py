"""Pruebas de migración explícita del progreso local al ChildProfile."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript.acceso import AccesoProducto
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from tortuscript.perfil_educativo import PerfilEducativoService, ContextoEducativoError
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso import PROGRESO_INICIAL
from tortuscript import persistencia_local
from tortuscript.progreso_contrato import nuevo_snapshot
from tortuscript.migracion_progreso import MigracionProgresoError, MigracionProgresoLocal


class MigracionProgresoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "cuentas.sqlite3"
        self.cuentas = CuentaRepository(self.db)
        self.cuentas.ensure_schema()
        self.auth = AuthRepository(self.db)
        self.auth.ensure_schema()
        self.cuenta = self.cuentas.crear_account("adulto@example.com")
        self.auth.set_password(self.cuenta.id, "una-clave-larga-123")
        self.auth.marcar_verificada(self.cuenta.id)
        self.perfil = self.cuentas.crear_child_profile(self.cuenta.id, "Ana")
        self.session, _, _ = self.auth.create_session(self.cuenta.id)
        self.auth.select_profile(self.session, self.perfil.id)
        self.local = self.tmp / "local"
        self.local.mkdir()
        self.old_cwd = Path.cwd()
        # El módulo legado usa su raíz de proyecto; parcheamos únicamente su directorio durante la prueba.
        self.progreso = persistencia_local
        self.old_dir = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self.local
        self.service = PerfilEducativoService(
            self.cuentas, self.auth, ProgresoChildProfile(self.tmp / "commercial"), AccesoProducto(self.cuentas)
        )
        self.migracion = MigracionProgresoLocal(self.service)

    def tearDown(self):
        persistencia_local.DIRECTORIO = self.old_dir
        shutil.rmtree(self.tmp)

    def test_importacion_expresa_copia_al_perfil_activo(self):
        datos = dict(PROGRESO_INICIAL)
        datos["xp_total"] = 123
        datos["config"] = dict(PROGRESO_INICIAL["config"])
        datos["_perfil"] = "ana"
        self.progreso.guardar_progreso(datos)
        snapshot = self.migracion.importar_local(self.session, "ana")
        self.assertEqual(snapshot.profile_id, self.perfil.id)
        self.assertEqual(snapshot.data["xp_total"], 123)

    def test_rechaza_nombre_de_perfil_no_textual_sin_error_500(self):
        for nombre in (None, [], {}, 17):
            with self.subTest(nombre=nombre):
                with self.assertRaises(MigracionProgresoError):
                    self.migracion.importar_local(self.session, nombre)

    def test_rechaza_perfil_local_inexistente(self):
        with self.assertRaises(MigracionProgresoError):
            self.migracion.importar_local(self.session, "perfil_que_no_existe")
        self.assertIsNone(self.service.cargar_progreso(self.session))

    def test_rechaza_progreso_local_ilegible_sin_persistirlo_ni_apartarlo(self):
        archivo = self.local / "progreso_ana.json"
        for contenido in ("{no es json", "[]", '{"ejercicios": []}'):
            with self.subTest(contenido=contenido):
                archivo.write_text(contenido, encoding="utf-8")
                with self.assertRaises(MigracionProgresoError):
                    self.migracion.importar_local(self.session, "ana")
                self.assertIsNone(self.service.cargar_progreso(self.session))
                # La migración no debe apartar ni reescribir el archivo de origen.
                self.assertEqual(archivo.read_text(encoding="utf-8"), contenido)
                self.assertFalse(list(self.local.glob("*.corrupto-*")))

    def test_normaliza_campos_anidados_mal_tipados_y_conserva_lo_valido(self):
        archivo = self.local / "progreso_ana.json"
        archivo.write_text(
            '{"ejercicios": {}, "config": [], "xp_total": 41}',
            encoding="utf-8",
        )
        snapshot = self.migracion.importar_local(self.session, "ana")
        self.assertEqual(snapshot.data["xp_total"], 41)
        self.assertIsInstance(snapshot.data["config"], dict)
        self.assertIsInstance(snapshot.data["config"]["ajustes"], dict)

    def test_no_reemplaza_progreso_comercial_sin_confirmacion(self):
        self.service.guardar_progreso(self.session, nuevo_snapshot(self.perfil.id, {"xp_total": 999}))
        with self.assertRaises(MigracionProgresoError):
            self.migracion.importar_local(self.session, "ana")

    def test_reemplazo_debe_ser_explicito(self):
        datos = dict(PROGRESO_INICIAL)
        datos["xp_total"] = 123
        datos["_perfil"] = "ana"
        self.progreso.guardar_progreso(datos)
        self.service.guardar_progreso(self.session, nuevo_snapshot(self.perfil.id, {"xp_total": 999}))
        snapshot = self.migracion.importar_local(self.session, "ana", reemplazar=True)
        self.assertEqual(snapshot.data["xp_total"], 123)

    def test_sesion_sin_perfil_no_puede_migrar(self):
        self.auth.clear_profile(self.session)
        with self.assertRaises(ContextoEducativoError):
            self.migracion.listar_locales(self.session)


if __name__ == "__main__":
    unittest.main()