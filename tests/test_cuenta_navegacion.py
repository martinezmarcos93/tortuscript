"""Navegación de las páginas de cuenta: destino `next`, formularios HTML y CSP."""
import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript.auth import AuthRepository
from web.app import create_app

CLAVE = "una-clave-larga-123"


class CuentaNavegacionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app(token="test-token")
        self.app.config.update(
            TESTING=True,
            ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
            PROGRESS_DIR=self.tmp / "progreso_perfiles",
            ACCOUNT_EMAIL_SENDER=lambda **payload: None,
        )
        self.client = self.app.test_client()
        self.email = f"nav-{self.tmp.name.lower()}@example.com"
        registro = self.client.post("/cuenta/registro", json={"email": self.email, "password": CLAVE})
        self.assertEqual(registro.status_code, 202)
        cuenta_id = "acc_" + hashlib.sha256(self.email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _login_form(self, **extra):
        return self.client.post("/cuenta/login", data={"email": self.email, "password": CLAVE, **extra})

    def _csrf(self):
        return self.client.get_cookie("tortu_csrf").value

    def test_el_destino_pedido_sobrevive_login_y_creacion_de_perfil(self):
        # Sin sesión, una página educativa manda al login recordando a dónde se iba.
        inicio = self.client.get("/logros")
        self.assertEqual(inicio.status_code, 302)
        self.assertIn("next=", inicio.headers["Location"])
        pagina = self.client.get(inicio.headers["Location"])
        self.assertIn('name="next" value="/logros?"', pagina.get_data(as_text=True))

        login = self._login_form(next="/logros")
        self.assertEqual(login.status_code, 302)
        self.assertIn("/cuenta/seleccionar-perfil", login.headers["Location"])
        self.assertIn("next=/logros", login.headers["Location"].replace("%2F", "/"))

        selector = self.client.get(login.headers["Location"]).get_data(as_text=True)
        # Tanto elegir como crear un perfil conservan el destino.
        self.assertEqual(selector.count('name="next" value="/logros"'), 1)
        creado = self.client.post("/cuenta/perfiles", data={
            "nombre": "Ana", "csrf": self._csrf(), "next": "/logros",
        })
        self.assertEqual(creado.status_code, 302)
        self.assertEqual(creado.headers["Location"], "/logros")

    def test_login_no_redirige_a_un_destino_externo(self):
        for destino in ("https://evil.example", "//evil.example", "/\\evil.example"):
            with self.subTest(destino=destino):
                cliente = self.app.test_client()
                login = cliente.post("/cuenta/login", data={
                    "email": self.email, "password": CLAVE, "next": destino,
                })
                self.assertEqual(login.status_code, 302)
                self.assertNotIn("evil", login.headers["Location"])
                pagina = cliente.get("/cuenta/ingresar?next=" + destino)
                self.assertNotIn("evil", pagina.headers.get("Location", "") + pagina.get_data(as_text=True))

    def test_con_sesion_ingresar_lleva_al_selector_conservando_destino(self):
        self._login_form()
        respuesta = self.client.get("/cuenta/ingresar?next=/mapa")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("seleccionar-perfil", respuesta.headers["Location"])
        self.assertIn("mapa", respuesta.headers["Location"])

    def test_error_al_crear_perfil_por_formulario_conserva_destino(self):
        self._login_form()
        csrf = self._csrf()
        self.client.post("/cuenta/perfiles", data={"nombre": "Ana", "csrf": csrf})
        repetido = self.client.post("/cuenta/perfiles", data={"nombre": "ANA", "csrf": csrf, "next": "/mapa"})
        self.assertEqual(repetido.status_code, 400)
        html = repetido.get_data(as_text=True)
        self.assertIn("Ya existe un perfil con ese nombre", html)
        self.assertIn('name="next" value="/mapa"', html)

    def test_seleccion_invalida_por_formulario_muestra_pagina_con_error(self):
        self._login_form()
        csrf = self._csrf()
        ajeno = self.client.post("/cuenta/perfil", data={"perfil_id": "child_inexistente", "csrf": csrf})
        self.assertEqual(ajeno.status_code, 403)
        self.assertNotIn("Location", ajeno.headers)
        self.assertIn("no está disponible", ajeno.get_data(as_text=True))
        vacio = self.client.post("/cuenta/perfil", data={"csrf": csrf, "next": "/"})
        self.assertEqual(vacio.status_code, 400)
        self.assertIn("<h1>", vacio.get_data(as_text=True))

    def test_seleccion_con_perfil_id_no_textual_no_es_error_interno(self):
        self._login_form()
        for valor in ([], {}, 7, True, ["child_x"]):
            with self.subTest(valor=valor):
                r = self.client.post("/cuenta/perfil", json={"perfil_id": valor},
                                     headers={"X-Tortu-CSRF": self._csrf()})
                self.assertEqual(r.status_code, 400)

    def test_verificacion_con_token_no_textual_no_es_error_interno(self):
        for valor in ([], {}, 7, ["x"]):
            with self.subTest(valor=valor):
                r = self.client.post("/cuenta/verificar-email", json={"token": valor},
                                     headers={"Accept": "application/json"})
                self.assertEqual(r.status_code, 400)

    def test_login_por_formulario_limitado_responde_pagina_y_retry_after(self):
        ultimo = None
        for _ in range(11):
            ultimo = self.client.post("/cuenta/login", data={"email": self.email, "password": "mala-clave-larga"})
        self.assertEqual(ultimo.status_code, 429)
        self.assertIn("Retry-After", ultimo.headers)
        self.assertIn("<h1>", ultimo.get_data(as_text=True))

    def test_paginas_de_cuenta_no_usan_scripts_en_linea(self):
        # La CSP (script-src 'self') bloquea cualquier <script> sin src: sería código muerto y un error de consola.
        self._login_form()
        self.client.post("/cuenta/perfiles", data={"nombre": "Ana", "csrf": self._csrf()})
        for ruta in ("/cuenta/registrar", "/cuenta/seleccionar-perfil", "/cuenta/configuracion",
                     "/cuenta/verificar-email?token=x"):
            with self.subTest(ruta=ruta):
                html = self.client.get(ruta).get_data(as_text=True)
                self.assertFalse(re.search(r"<script(?![^>]*\bsrc=)", html), ruta)
                self.assertNotRegex(html, r"\son[a-z]+=\"")

    def test_el_selector_respeta_el_limite_de_perfiles_del_dominio(self):
        from tortuscript.cuentas import MAX_CHILD_PROFILES
        self._login_form()
        csrf = self._csrf()
        for i in range(MAX_CHILD_PROFILES):
            self.assertIn('id="nombre"', self.client.get("/cuenta/seleccionar-perfil").get_data(as_text=True))
            r = self.client.post("/cuenta/perfiles", json={"nombre": f"Perfil {i}"}, headers={"X-Tortu-CSRF": csrf})
            self.assertEqual(r.status_code, 201)
        self.assertNotIn('id="nombre"', self.client.get("/cuenta/seleccionar-perfil").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
