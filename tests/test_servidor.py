"""Modo servidor: no arranca inseguro, y arrancado aplica host, proxy, cookies seguras y HSTS."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript import correo
from web.servidor import ConfiguracionInvalida, crear_aplicacion_servidor


class TestModoServidor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.entorno = {
            "TORTU_HOSTS": "tortu.example, www.tortu.example", "TORTU_URL_BASE": "https://tortu.example",
            "TORTUSCRIPT_DATOS": str(self.tmp / "datos"), "TORTU_SANDBOX": "docker",
            "TORTU_EMAIL_MODO": "smtp", "TORTU_SMTP_HOST": "smtp.example", "TORTU_EMAIL_REMITENTE": "a@tortu.example",
        }

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def app(self, **cambios):
        entorno = {**self.entorno, **cambios}
        return crear_aplicacion_servidor({k: v for k, v in entorno.items() if v is not None})

    def test_no_arranca_si_falta_o_es_insegura_una_configuracion(self):
        casos = {
            "sin hosts": {"TORTU_HOSTS": None},
            "host con comodín": {"TORTU_HOSTS": "*"},
            "host con esquema": {"TORTU_HOSTS": "https://tortu.example"},
            "url sin https": {"TORTU_URL_BASE": "http://tortu.example"},
            "url de otro host": {"TORTU_URL_BASE": "https://otro.example"},
            "sin carpeta de datos": {"TORTUSCRIPT_DATOS": None},
            "sin sandbox": {"TORTU_SANDBOX": None},
            "sin correo": {"TORTU_EMAIL_MODO": None},
            "correo de consola": {"TORTU_EMAIL_MODO": "consola"},
            "correo a medias": {"TORTU_SMTP_HOST": None},
            "token corto": {"TORTU_TOKEN": "corto"},
            "proxies no numérico": {"TORTU_PROXIES": "muchos"},
            "demasiados proxies": {"TORTU_PROXIES": "50"},
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre), self.assertRaises(ConfiguracionInvalida):
                self.app(**cambio)
        self.assertFalse((self.tmp / "datos").exists())             # un arranque rechazado no crea nada

    def test_configuracion_completa(self):
        app = self.app(TORTU_TOKEN="t" * 40)
        self.assertEqual(app.config["HOSTS_PERMITIDOS"], {"tortu.example", "www.tortu.example"})
        self.assertTrue(app.config["ACCOUNT_COOKIE_SECURE"])
        self.assertIsInstance(app.config["ACCOUNT_EMAIL_SENDER"], correo.EnviadorSMTP)
        self.assertEqual(app.config["ACCOUNT_EMAIL_SENDER"].url_base, "https://tortu.example")
        self.assertEqual(app.config["ACCOUNT_DB"], self.tmp / "datos" / "instance" / "cuentas.sqlite3")
        self.assertEqual(app.config["TOKEN"], "t" * 40)
        self.assertIsNone(app.config["TUTOR_PROVEEDOR"])
        self.assertEqual(app.config["PAYMENT_WEBHOOK_SECRETS"], {})

    def test_solo_atiende_sus_hosts_y_manda_hsts_y_cookies_seguras(self):
        app = self.app()
        app.config["TESTING"] = True
        c = app.test_client()
        propio = {"Host": "interno:8000", "X-Forwarded-Host": "tortu.example", "X-Forwarded-Proto": "https",
                  "X-Forwarded-For": "203.0.113.7"}
        r = c.get("/cuenta/ingresar", headers=propio)
        self.assertEqual(r.status_code, 200)
        self.assertIn("max-age=31536000", r.headers["Strict-Transport-Security"])
        for ajeno in ("evil.example", "127.0.0.1", "localhost"):
            with self.subTest(host=ajeno):
                self.assertEqual(c.get("/cuenta/ingresar", headers={**propio, "X-Forwarded-Host": ajeno}).status_code, 403)

        # Una sesión creada detrás del proxy lleva cookies Secure y redirige con https.
        app.config["ACCOUNT_EMAIL_SENDER"] = lambda **payload: None
        import hashlib
        from tortuscript.auth import AuthRepository
        email = "servidor@example.com"
        c.post("/cuenta/registrar", data={"email": email, "password": "una-clave-larga-123", "responsable": "si"}, headers=propio)
        AuthRepository(app.config["ACCOUNT_DB"]).marcar_verificada("acc_" + hashlib.sha256(email.encode()).hexdigest()[:24])
        login = c.post("/cuenta/login", data={"email": email, "password": "una-clave-larga-123"},
                       headers={**propio, "Origin": "https://tortu.example"})
        self.assertEqual(login.status_code, 302)
        cookies = login.headers.getlist("Set-Cookie")
        self.assertTrue(all("Secure" in cookie for cookie in cookies), cookies)
        self.assertTrue(any("HttpOnly" in cookie for cookie in cookies))
        # El origen propio (https, host público) se acepta; el interno del proxy no.
        mal = c.post("/cuenta/login", data={"email": email, "password": "x" * 12},
                     headers={**propio, "Origin": "http://interno:8000"})
        self.assertEqual(mal.status_code, 403)

    def test_el_limite_de_intentos_usa_la_ip_del_cliente_y_no_la_del_proxy(self):
        app = self.app()
        app.config["TESTING"] = True
        c = app.test_client()

        def intento(ip):
            return c.post("/cuenta/login", data={"email": "nadie@example.com", "password": "una-clave-larga-123"},
                          headers={"X-Forwarded-Host": "tortu.example", "X-Forwarded-Proto": "https", "X-Forwarded-For": ip})

        for _ in range(10):
            self.assertEqual(intento("203.0.113.7").status_code, 401)
        self.assertEqual(intento("203.0.113.7").status_code, 429)
        self.assertEqual(intento("203.0.113.8").status_code, 401)   # otra familia no queda bloqueada
        # Un cliente no puede esquivar el límite inventando la cabecera: vale la que agrega el proxy propio.
        self.assertEqual(intento("198.51.100.1, 203.0.113.7").status_code, 429)

    def test_sin_modo_servidor_la_app_local_no_manda_hsts(self):
        from web.app import create_app
        r = create_app(token="t").test_client().get("/cuenta/ingresar")
        self.assertNotIn("Strict-Transport-Security", r.headers)


if __name__ == "__main__":
    unittest.main()
