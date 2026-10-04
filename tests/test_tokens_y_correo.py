"""Barrido 6 — vencimiento y uso único de los enlaces de cuenta, y la prueba de entrega de correo."""
import contextlib
import io
import shutil
import smtplib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from herramientas import probar_correo
from tortuscript import auth as auth_mod
from tortuscript.auth import AuthError, AuthRepository
from tortuscript.cuentas import CuentaRepository

CLAVE = "una-clave-larga-123"
NUEVA = "otra-clave-larga-456"


class TestEnlacesDeCuenta(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "cuentas.sqlite3"
        self.cuentas = CuentaRepository(self.db)
        self.cuentas.ensure_schema()
        self.auth = AuthRepository(self.db)
        self.auth.ensure_schema()
        self.cuenta = self.cuentas.crear_account("familia@example.com").id
        self.auth.set_password(self.cuenta, CLAVE)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def vencer_tokens(self):
        pasado = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("UPDATE account_tokens SET expires_at=?", (pasado,))

    def test_los_plazos_son_los_documentados(self):
        ahora = datetime.now(timezone.utc)
        _, vence_verificacion = self.auth.create_verification_token(self.cuenta)
        _, vence_recuperacion = self.auth.create_recovery_token("familia@example.com")
        self.assertAlmostEqual((vence_verificacion - ahora).total_seconds(), auth_mod.VERIFICATION_HOURS * 3600, delta=30)
        self.assertAlmostEqual((vence_recuperacion - ahora).total_seconds(), auth_mod.RECOVERY_HOURS * 3600, delta=30)

    def test_un_enlace_de_verificacion_vencido_no_verifica(self):
        token, _ = self.auth.create_verification_token(self.cuenta)
        self.vencer_tokens()
        with self.assertRaises(AuthError):
            self.auth.verify_email_token(token)
        with self.assertRaises(AuthError):                             # la cuenta sigue sin verificar
            self.auth.verify_password("familia@example.com", CLAVE)

    def test_un_enlace_de_recuperacion_vencido_no_cambia_la_clave(self):
        self.auth.marcar_verificada(self.cuenta)
        token, _ = self.auth.create_recovery_token("familia@example.com")
        self.vencer_tokens()
        with self.assertRaises(AuthError):
            self.auth.reset_password(token, NUEVA)
        self.assertEqual(self.auth.verify_password("familia@example.com", CLAVE)["id"], self.cuenta)

    def test_cada_enlace_sirve_una_sola_vez(self):
        token, _ = self.auth.create_verification_token(self.cuenta)
        self.auth.verify_email_token(token)
        with self.assertRaises(AuthError):
            self.auth.verify_email_token(token)
        recuperacion, _ = self.auth.create_recovery_token("familia@example.com")
        self.auth.reset_password(recuperacion, NUEVA)
        with self.assertRaises(AuthError):
            self.auth.reset_password(recuperacion, CLAVE)
        self.assertEqual(self.auth.verify_password("familia@example.com", NUEVA)["id"], self.cuenta)

    def test_pedir_otro_enlace_anula_el_anterior(self):
        viejo, _ = self.auth.create_recovery_token("familia@example.com")
        nuevo, _ = self.auth.create_recovery_token("familia@example.com")
        with self.assertRaises(AuthError):
            self.auth.reset_password(viejo, NUEVA)
        self.auth.reset_password(nuevo, NUEVA)

    def test_un_enlace_de_un_tipo_no_sirve_para_el_otro(self):
        verificacion, _ = self.auth.create_verification_token(self.cuenta)
        with self.assertRaises(AuthError):
            self.auth.reset_password(verificacion, NUEVA)
        recuperacion, _ = self.auth.create_recovery_token("familia@example.com")
        with self.assertRaises(AuthError):
            self.auth.verify_email_token(recuperacion)

    def test_restablecer_la_clave_cierra_las_sesiones_abiertas(self):
        self.auth.marcar_verificada(self.cuenta)
        sesion, _, _ = self.auth.create_session(self.cuenta)
        token, _ = self.auth.create_recovery_token("familia@example.com")
        self.auth.reset_password(token, NUEVA)
        self.assertIsNone(self.auth.get_session(sesion))

    def test_el_token_no_se_guarda_en_claro(self):
        token, _ = self.auth.create_recovery_token("familia@example.com")
        with closing(sqlite3.connect(self.db)) as con:
            self.assertNotIn(token, "\n".join(con.iterdump()))


class ServidorFalso:
    enviados = []
    falla = None

    def __init__(self, host, puerto, timeout=None, context=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, usuario, clave):
        pass

    def send_message(self, mensaje):
        if ServidorFalso.falla:
            raise ServidorFalso.falla
        ServidorFalso.enviados.append(mensaje)


SMTP = {"TORTU_EMAIL_MODO": "smtp", "TORTU_SMTP_HOST": "smtp.example", "TORTU_SMTP_PUERTO": "587",
        "TORTU_EMAIL_REMITENTE": "TortuScript <no-responder@tortu.example>", "TORTU_URL_BASE": "https://tortu.example"}


class TestProbarCorreo(unittest.TestCase):
    def setUp(self):
        ServidorFalso.enviados, ServidorFalso.falla = [], None

    def correr(self, argumentos, entorno):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida), \
                patch.object(smtplib, "SMTP", ServidorFalso):
            return probar_correo.main(argumentos, entorno=entorno), salida.getvalue()

    def test_envia_un_correo_igual_al_de_una_familia(self):
        codigo, texto = self.correr(["adulto@example.com", "--tipo", "recovery"], SMTP)
        self.assertEqual(codigo, 0)
        self.assertIn("aceptó el mensaje", texto)
        (mensaje,) = ServidorFalso.enviados
        self.assertEqual(mensaje["To"], "adulto@example.com")
        self.assertIn("https://tortu.example/cuenta/restablecer-password?token=token-de-prueba-sin-validez",
                      mensaje.get_content())

    def test_si_el_servidor_lo_rechaza_sale_con_error(self):
        ServidorFalso.falla = smtplib.SMTPRecipientsRefused({"adulto@example.com": (550, b"no existe")})
        codigo, texto = self.correr(["adulto@example.com"], SMTP)
        self.assertEqual(codigo, 1)
        self.assertIn("rechazó el envío", texto)

    def test_sin_correo_configurado_o_mal_configurado_no_intenta_nada(self):
        for entorno in ({}, {"TORTU_EMAIL_MODO": "smtp", "TORTU_URL_BASE": "https://tortu.example"},
                        {"TORTU_EMAIL_MODO": "paloma"}):
            with self.subTest(entorno=entorno):
                self.assertEqual(self.correr(["adulto@example.com"], entorno)[0], 2)
        self.assertEqual(self.correr(["sin-arroba"], SMTP)[0], 2)
        self.assertEqual(ServidorFalso.enviados, [])

    def test_en_modo_consola_no_se_envia_nada(self):
        codigo, texto = self.correr(["adulto@example.com"], {"TORTU_EMAIL_MODO": "consola", "TORTU_URL_BASE": "http://127.0.0.1:5057"})
        self.assertEqual(codigo, 0)
        self.assertIn("no se envió ningún correo", texto)
        self.assertEqual(ServidorFalso.enviados, [])


if __name__ == "__main__":
    unittest.main()
