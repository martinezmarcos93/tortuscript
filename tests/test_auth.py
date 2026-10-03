"""Pruebas de las primitivas de autenticación y sesión server-side."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript.cuentas import CuentaRepository
from tortuscript.auth import AuthError, AuthRepository


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "cuentas.sqlite3"
        self.cuentas = CuentaRepository(self.db)
        self.cuentas.ensure_schema()
        self.auth = AuthRepository(self.db)
        self.auth.ensure_schema()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_password_se_guarda_como_hash_y_exige_verificacion(self):
        cuenta = self.cuentas.crear_account("adulto@example.com")
        self.auth.set_password(cuenta.id, "una-clave-larga-123")
        with self.assertRaises(AuthError):
            self.auth.verify_password("adulto@example.com", "una-clave-larga-123")
        self.auth.marcar_verificada(cuenta.id)
        fila = self.auth.verify_password("adulto@example.com", "una-clave-larga-123")
        self.assertEqual(fila["id"], cuenta.id)
        with self.assertRaises(AuthError):
            self.auth.verify_password("adulto@example.com", "incorrecta")
        with self.auth._db() as db:
            hash_guardado = db.execute("SELECT password_hash FROM accounts WHERE id=?", (cuenta.id,)).fetchone()[0]
        self.assertNotEqual(hash_guardado, "una-clave-larga-123")
        self.assertTrue(hash_guardado.startswith("scrypt:"))

    def test_sesion_expone_token_solo_al_crearla_y_se_revoca(self):
        cuenta = self.cuentas.crear_account("adulto@example.com")
        sesion, csrf, _ = self.auth.create_session(cuenta.id)
        self.assertIsNotNone(self.auth.get_session(sesion))
        self.assertTrue(self.auth.csrf_ok(sesion, csrf))
        self.assertFalse(self.auth.csrf_ok(sesion, "otro-token"))
        self.auth.revoke(sesion)
        self.assertIsNone(self.auth.get_session(sesion))

    def test_sesion_expirada_no_se_considera_autenticada(self):
        cuenta = self.cuentas.crear_account("expirada@example.com")
        sesion, csrf, _ = self.auth.create_session(cuenta.id)
        with self.auth._db() as db:
            db.execute(
                "UPDATE sessions SET expires_at=? WHERE id_hash=?",
                ("2000-01-01T00:00:00+00:00", __import__("hashlib").sha256(sesion.encode()).hexdigest()),
            )
        self.assertIsNone(self.auth.get_session(sesion))
        self.assertFalse(self.auth.csrf_ok(sesion, csrf))

    def test_sesion_con_expiracion_corrupta_no_rompe_la_autenticacion(self):
        cuenta = self.cuentas.crear_account("corrupta@example.com")
        sesion, _, _ = self.auth.create_session(cuenta.id)
        with self.auth._db() as db:
            db.execute(
                "UPDATE sessions SET expires_at=? WHERE id_hash=?",
                ("no-es-una-fecha", __import__("hashlib").sha256(sesion.encode()).hexdigest()),
            )
        self.assertIsNone(self.auth.get_session(sesion))

    def test_no_se_puede_seleccionar_perfil_con_sesion_expirada(self):
        cuenta = self.cuentas.crear_account("perfil-expirado@example.com")
        perfil = self.cuentas.crear_child_profile(cuenta.id, "Ana")
        sesion, _, _ = self.auth.create_session(cuenta.id)
        with self.auth._db() as db:
            db.execute(
                "UPDATE sessions SET expires_at=? WHERE id_hash=?",
                ("2000-01-01T00:00:00+00:00", __import__("hashlib").sha256(sesion.encode()).hexdigest()),
            )
        with self.assertRaises(AuthError):
            self.auth.select_profile(sesion, perfil.id)

    def test_revocar_todas_las_sesiones_de_una_cuenta_no_afecta_a_otra(self):
        una = self.cuentas.crear_account("una@example.com")
        otra = self.cuentas.crear_account("otra@example.com")
        sesion_una_1, _, _ = self.auth.create_session(una.id)
        sesion_una_2, _, _ = self.auth.create_session(una.id)
        sesion_otra, _, _ = self.auth.create_session(otra.id)
        self.auth.revoke_all(una.id)
        self.assertIsNone(self.auth.get_session(sesion_una_1))
        self.assertIsNone(self.auth.get_session(sesion_una_2))
        self.assertIsNotNone(self.auth.get_session(sesion_otra))

    def test_el_hash_de_sesion_no_es_el_token(self):
        cuenta = self.cuentas.crear_account("adulto@example.com")
        sesion, _, _ = self.auth.create_session(cuenta.id)
        with self.auth._db() as db:
            guardado = db.execute("SELECT id_hash FROM sessions").fetchone()[0]
        self.assertNotEqual(guardado, sesion)
        self.assertEqual(len(guardado), 64)



    def test_verificacion_de_correo_es_de_un_solo_uso(self):
        cuenta = self.cuentas.crear_account("adulto@example.com")
        token, _ = self.auth.create_verification_token(cuenta.id)
        self.auth.verify_email_token(token)
        with self.assertRaises(AuthError):
            self.auth.verify_email_token(token)
        fila = self.cuentas.obtener_account(cuenta.id)
        self.assertEqual(fila.email, "adulto@example.com")

    def test_password_invalida_no_consumo_token_recuperacion(self):
        cuenta = self.cuentas.crear_account("recuperar@example.com")
        self.auth.set_password(cuenta.id, "una-clave-larga-123")
        self.auth.marcar_verificada(cuenta.id)
        token, _ = self.auth.create_recovery_token(cuenta.email)
        with self.assertRaisesRegex(AuthError, "al menos 12 caracteres"):
            self.auth.reset_password(token, "corta")
        self.assertEqual(
            self.auth.verify_password(cuenta.email, "una-clave-larga-123")["id"],
            cuenta.id,
        )
        self.auth.reset_password(token, "otra-clave-larga-456")
        self.assertEqual(
            self.auth.verify_password(cuenta.email, "otra-clave-larga-456")["id"],
            cuenta.id,
        )

    def test_recuperacion_cambia_password_y_revoca_sesiones(self):
        cuenta = self.cuentas.crear_account("adulto@example.com")
        self.auth.set_password(cuenta.id, "una-clave-larga-123")
        self.auth.marcar_verificada(cuenta.id)
        session, _, _ = self.auth.create_session(cuenta.id)
        token, _ = self.auth.create_recovery_token(cuenta.email)
        self.auth.reset_password(token, "otra-clave-larga-456")
        with self.assertRaises(AuthError):
            self.auth.verify_password(cuenta.email, "una-clave-larga-123")
        self.assertEqual(self.auth.verify_password(cuenta.email, "otra-clave-larga-456")["id"], cuenta.id)
        self.assertIsNone(self.auth.get_session(session))
        with self.assertRaises(AuthError):
            self.auth.reset_password(token, "tercera-clave-larga-789")

if __name__ == "__main__":
    unittest.main()
