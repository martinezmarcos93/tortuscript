"""Correo transaccional: mensaje, enlace, SMTP (con un servidor de mentira) y configuración por entorno."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from tortuscript import correo

VENCE = datetime(2026, 10, 4, 15, 30, tzinfo=timezone.utc)
BASE = "https://tortu.example"


class ServidorFalso:
    instancias = []

    def __init__(self, host, puerto, timeout=None, context=None):
        self.host, self.puerto, self.timeout = host, puerto, timeout
        self.pasos, self.mensajes = [], []
        ServidorFalso.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.pasos.append("quit")
        return False

    def starttls(self, context=None):
        self.pasos.append("starttls")

    def login(self, usuario, clave):
        self.pasos.append(("login", usuario, clave))

    def send_message(self, mensaje):
        self.pasos.append("send")
        self.mensajes.append(mensaje)


class TestMensaje(unittest.TestCase):
    def test_enlace_de_cada_tipo_apunta_a_la_pantalla_que_no_consume_el_token(self):
        self.assertEqual(correo.enlace("verification", "abc", BASE + "/"),
                         "https://tortu.example/cuenta/verificar-email?token=abc")
        self.assertEqual(correo.enlace("recovery", "a b&c=/", BASE),
                         "https://tortu.example/cuenta/restablecer-password?token=a%20b%26c%3D%2F")

    def test_los_enlaces_existen_como_rutas_get_de_la_app(self):
        from web.app import create_app
        reglas = {r.rule for r in create_app(token="t").url_map.iter_rules() if "GET" in r.methods}
        for ruta in correo.RUTAS.values():
            self.assertIn(ruta, reglas)

    def test_tipo_desconocido_o_base_invalida_se_rechazan(self):
        with self.assertRaises(correo.CorreoError):
            correo.enlace("otro", "t", BASE)
        for base in ("", "tortu.example", "javascript:alert(1)", "ftp://x"):
            with self.subTest(base=base), self.assertRaises(correo.CorreoError):
                correo.enlace("recovery", "t", base)

    def test_mensaje_tiene_enlace_vencimiento_y_cabeceras(self):
        m = correo.construir_mensaje("recovery", "ana@example.com", "tok", VENCE, BASE, "TortuScript <no-responder@tortu.example>")
        cuerpo = m.get_content()
        self.assertEqual(m["To"], "ana@example.com")
        self.assertIn("contraseña", m["Subject"])
        self.assertIn("https://tortu.example/cuenta/restablecer-password?token=tok", cuerpo)
        self.assertIn("04/10/2026 a las 15:30 UTC", cuerpo)
        self.assertEqual(m["Auto-Submitted"], "auto-generated")
        self.assertIn("@tortu.example>", m["Message-ID"])

    def test_no_se_pueden_inyectar_cabeceras_por_el_destinatario(self):
        with self.assertRaises(ValueError):
            correo.construir_mensaje("recovery", "ana@example.com\nBcc: otro@example.com", "t", VENCE, BASE, "a@b.c")


class TestSMTP(unittest.TestCase):
    def setUp(self):
        ServidorFalso.instancias = []

    def test_starttls_con_login_envia_un_mensaje(self):
        enviar = correo.EnviadorSMTP("smtp.example", 587, "a@tortu.example", BASE, usuario="u", clave="c")
        with patch.object(correo.smtplib, "SMTP", ServidorFalso):
            enviar(tipo="verification", email="ana@example.com", token="tok", expires=VENCE)
        servidor = ServidorFalso.instancias[0]
        self.assertEqual((servidor.host, servidor.puerto, servidor.timeout), ("smtp.example", 587, 15))
        self.assertEqual(servidor.pasos, ["starttls", ("login", "u", "c"), "send", "quit"])
        self.assertIn("verificar-email?token=tok", servidor.mensajes[0].get_content())

    def test_ssl_usa_conexion_cifrada_desde_el_inicio(self):
        enviar = correo.EnviadorSMTP("smtp.example", 465, "a@tortu.example", BASE, seguridad="ssl")
        with patch.object(correo.smtplib, "SMTP_SSL", ServidorFalso), \
                patch.object(correo.smtplib, "SMTP", side_effect=AssertionError("no debe usarse")):
            enviar(tipo="recovery", email="ana@example.com", token="tok", expires=VENCE)
        self.assertEqual(ServidorFalso.instancias[0].pasos, ["send", "quit"])

    def test_el_fallo_del_servidor_se_propaga_a_la_ruta(self):
        enviar = correo.EnviadorSMTP("smtp.example", 587, "a@tortu.example", BASE)
        with patch.object(correo.smtplib, "SMTP", side_effect=OSError("sin red")), self.assertRaises(OSError):
            enviar(tipo="recovery", email="ana@example.com", token="tok", expires=VENCE)

    def test_no_se_registra_token_ni_direccion(self):
        enviar = correo.EnviadorSMTP("smtp.example", 587, "a@tortu.example", BASE)
        with patch.object(correo.smtplib, "SMTP", ServidorFalso), self.assertLogs(correo.logger, "INFO") as logs:
            enviar(tipo="recovery", email="ana@example.com", token="tok-secreto", expires=VENCE)
        texto = "\n".join(logs.output)
        self.assertNotIn("tok-secreto", texto)
        self.assertNotIn("ana@example.com", texto)

    def test_configuraciones_inseguras_o_incompletas_se_rechazan(self):
        with self.assertRaises(correo.CorreoError):
            correo.EnviadorSMTP("smtp.example", 25, "a@b.c", BASE, usuario="u", clave="c", seguridad="ninguna")
        with self.assertRaises(correo.CorreoError):
            correo.EnviadorSMTP("", 587, "a@b.c", BASE)
        with self.assertRaises(correo.CorreoError):
            correo.EnviadorSMTP("smtp.example", 587, "a@b.c", BASE, seguridad="tls1")


class TestEntorno(unittest.TestCase):
    def test_sin_modo_no_hay_enviador(self):
        self.assertIsNone(correo.desde_entorno({}))
        self.assertIsNone(correo.desde_entorno({"TORTU_SMTP_HOST": "smtp.example"}))

    def test_modo_consola_muestra_el_enlace_local(self):
        lineas = []
        enviar = correo.desde_entorno({"TORTU_EMAIL_MODO": "consola"}, url_base="http://127.0.0.1:5057/")
        self.assertIsInstance(enviar, correo.EnviadorConsola)
        enviar.salida = lineas.append
        enviar(tipo="verification", email="ana@example.com", token="tok", expires=VENCE)
        self.assertIn("http://127.0.0.1:5057/cuenta/verificar-email?token=tok", lineas[0])

    def test_modo_smtp_lee_todo_del_entorno(self):
        enviar = correo.desde_entorno({
            "TORTU_EMAIL_MODO": "SMTP", "TORTU_SMTP_HOST": "smtp.example", "TORTU_SMTP_PUERTO": "465",
            "TORTU_SMTP_SEGURIDAD": "ssl", "TORTU_SMTP_USUARIO": "u", "TORTU_SMTP_CLAVE": "c",
            "TORTU_EMAIL_REMITENTE": "a@tortu.example", "TORTU_URL_BASE": BASE,
        })
        self.assertEqual((enviar.host, enviar.puerto, enviar.seguridad, enviar.usuario, enviar.url_base),
                         ("smtp.example", 465, "ssl", "u", BASE))

    def test_configuracion_a_medias_es_un_error_explicito(self):
        casos = (
            {"TORTU_EMAIL_MODO": "paloma"},
            {"TORTU_EMAIL_MODO": "consola"},                                  # sin URL base
            {"TORTU_EMAIL_MODO": "smtp", "TORTU_URL_BASE": BASE},              # sin host ni remitente
            {"TORTU_EMAIL_MODO": "smtp", "TORTU_URL_BASE": BASE, "TORTU_SMTP_HOST": "h",
             "TORTU_EMAIL_REMITENTE": "a@b.c", "TORTU_SMTP_PUERTO": "abc"},
        )
        for entorno in casos:
            with self.subTest(entorno=entorno), self.assertRaises(correo.CorreoError):
                correo.desde_entorno(entorno)


if __name__ == "__main__":
    unittest.main()
