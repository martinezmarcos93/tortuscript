"""Pruebas del boundary HTTP de cuenta adulta."""
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from web.app import create_app
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository


class CuentaRoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app(token="test-token")
        self.app.config.update(
            TESTING=True,
            ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
            ACCOUNT_COOKIE_SECURE=False,
            PROGRESS_DIR=self.tmp / "progreso_perfiles",
        )
        self.emails = []
        self.app.config["ACCOUNT_EMAIL_SENDER"] = lambda **payload: self.emails.append(payload)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_migracion_local_legada_desactivada_por_defecto(self):
        listado = self.client.get("/cuenta/progreso/locales")
        importacion = self.client.post(
            "/cuenta/progreso/importar-local",
            json={"perfil_local": "ana"},
        )
        self.assertEqual(listado.status_code, 404)
        self.assertEqual(importacion.status_code, 404)

    def test_migracion_local_legada_solo_se_habilita_explicita(self):
        self.app.config["ENABLE_LOCAL_PROGRESS_MIGRATION"] = True
        listado = self.client.get("/cuenta/progreso/locales")
        # La capacidad queda habilitada, pero sigue requiriendo sesión con perfil.
        self.assertEqual(listado.status_code, 401)

    def test_api_valida_token_antes_de_resolver_la_sesion_educativa(self):
        # El token de la app local y la sesión de cuenta son controles distintos.
        # Sin token, la petición debe rechazarse por el gateway; con token pero sin
        # sesión, debe rechazarse por identidad educativa.
        sin_token = self.client.get("/api/estado")
        self.assertEqual(sin_token.status_code, 403)

        con_token_sin_sesion = self.client.get(
            "/api/estado", headers={"X-Tortu-Token": "test-token"}
        )
        self.assertEqual(con_token_sin_sesion.status_code, 401)

    def test_gateway_web_redirige_al_login_y_perfil(self):
        inicio = self.client.get("/", follow_redirects=False)
        self.assertEqual(inicio.status_code, 302)
        self.assertIn("/cuenta/ingresar", inicio.headers["Location"])

        login_page = self.client.get("/cuenta/ingresar")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Ingresar a TortuScript", login_page.get_data(as_text=True))

        registro_page = self.client.get("/cuenta/registrar")
        self.assertEqual(registro_page.status_code, 200)
        self.assertIn("Crear cuenta adulta", registro_page.get_data(as_text=True))

    def test_registro_y_recuperacion_fallan_cerrado_sin_sender_email(self):
        self.app.config["ACCOUNT_EMAIL_SENDER"] = None

        registro = self.client.post("/cuenta/registro", json={
            "email": "sin-correo@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(registro.status_code, 503)
        self.assertEqual(registro.json["codigo"], "envio_email_no_configurado")

        registro_html = self.client.post("/cuenta/registrar", data={
            "email": "sin-correo-html@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(registro_html.status_code, 503)

        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        self.assertIsNone(repo.obtener_account_por_email("sin-correo@example.com"))
        self.assertIsNone(repo.obtener_account_por_email("sin-correo-html@example.com"))

        recuperacion = self.client.post(
            "/cuenta/recuperar",
            json={"email": "cualquiera@example.com"},
        )
        self.assertEqual(recuperacion.status_code, 503)
        self.assertEqual(recuperacion.json["codigo"], "envio_email_no_configurado")

        reenvio = self.client.post(
            "/cuenta/reenviar-verificacion",
            json={"email": "cualquiera@example.com"},
        )
        self.assertEqual(reenvio.status_code, 503)
        self.assertEqual(reenvio.json["codigo"], "envio_email_no_configurado")

    def test_registro_password_invalida_no_reserva_email(self):
        invalido = self.client.post("/cuenta/registro", json={
            "email": "reintento@example.com",
            "password": "corta",
        })
        self.assertEqual(invalido.status_code, 400)
        valido = self.client.post("/cuenta/registro", json={
            "email": "reintento@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(valido.status_code, 202)
        self.assertEqual(valido.json["estado"], "pendiente_verificacion")

    def test_fallo_de_proveedor_no_rompe_registro_y_se_puede_reintentar(self):
        def proveedor_roto(**payload):
            raise RuntimeError("fallo simulado del proveedor")

        self.app.config["ACCOUNT_EMAIL_SENDER"] = proveedor_roto
        registro = self.client.post("/cuenta/registro", json={
            "email": "reintento-correo@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(registro.status_code, 503)
        self.assertEqual(registro.json["codigo"], "envio_email_fallido")

        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta = repo.obtener_account_por_email("reintento-correo@example.com")
        self.assertIsNotNone(cuenta)
        auth = AuthRepository(self.tmp / "cuentas.sqlite3")
        with auth._db() as db:
            row = db.execute(
                "SELECT password_hash,verified_at FROM accounts WHERE id=?", (cuenta.id,)
            ).fetchone()
        self.assertTrue(row["password_hash"])
        self.assertIsNone(row["verified_at"])

        self.app.config["ACCOUNT_EMAIL_SENDER"] = lambda **payload: self.emails.append(payload)
        reenvio = self.client.post("/cuenta/reenviar-verificacion", json={
            "email": "REINTENTO-CORREO@example.com",
        })
        self.assertEqual(reenvio.status_code, 202)
        self.assertEqual(reenvio.json["estado"], "solicitud_recibida")
        self.assertEqual(len(self.emails), 1)
        self.assertEqual(self.emails[0]["tipo"], "verification")
        verificado = self.client.post("/cuenta/verificar-email", json={
            "token": self.emails[0]["token"],
        }, headers={"Accept": "application/json"})
        self.assertEqual(verificado.status_code, 200)
        self.assertEqual(verificado.json["estado"], "correo_verificado")

    def test_reenvio_aplica_limite_por_ip(self):
        for _ in range(5):
            respuesta = self.client.post("/cuenta/reenviar-verificacion", json={
                "email": "ausente@example.com",
            })
            self.assertEqual(respuesta.status_code, 202)
        bloqueado = self.client.post("/cuenta/reenviar-verificacion", json={
            "email": "otro@example.com",
        })
        self.assertEqual(bloqueado.status_code, 429)
        self.assertIn("Retry-After", bloqueado.headers)

    def test_reenvio_no_revela_si_correo_existe_o_ya_esta_verificado(self):
        email = "ya-verificada@example.com"
        creado = self.client.post("/cuenta/registro", json={
            "email": email, "password": "una-clave-larga-123",
        })
        self.assertEqual(creado.status_code, 202)
        cuenta_id = "acc_" + __import__("hashlib").sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)
        self.emails.clear()

        desconocido = self.client.post("/cuenta/reenviar-verificacion", json={
            "email": "no-existe@example.com",
        })
        verificado = self.client.post("/cuenta/reenviar-verificacion", json={
            "email": email,
        })
        self.assertEqual(desconocido.status_code, 202)
        self.assertEqual(verificado.status_code, 202)
        self.assertEqual(desconocido.json, verificado.json)
        self.assertEqual(self.emails, [])

    def test_fallo_de_proveedor_en_recuperacion_no_filtra_estado_de_cuenta(self):
        email = "recuperar-correo@example.com"
        self.client.post("/cuenta/registro", json={
            "email": email, "password": "una-clave-larga-123",
        })
        cuenta_id = "acc_" + __import__("hashlib").sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)

        def proveedor_roto(**payload):
            raise RuntimeError("fallo simulado del proveedor")

        self.app.config["ACCOUNT_EMAIL_SENDER"] = proveedor_roto
        recuperacion = self.client.post("/cuenta/recuperar", json={"email": email})
        desconocido = self.client.post(
            "/cuenta/recuperar", json={"email": "ausente@example.com"}
        )
        self.assertEqual(recuperacion.status_code, 202)
        self.assertEqual(desconocido.status_code, 202)
        self.assertEqual(recuperacion.json, desconocido.json)

    def test_registro_aplica_rate_limit_por_ip_y_devuelve_retry_after(self):
        for indice in range(5):
            respuesta = self.client.post("/cuenta/registro", json={
                "email": f"registro-{indice}@example.com",
                "password": "una-clave-larga-123",
            })
            self.assertEqual(respuesta.status_code, 202)

        bloqueado = self.client.post("/cuenta/registro", json={
            "email": "registro-extra@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(bloqueado.status_code, 429)
        self.assertIn("Retry-After", bloqueado.headers)

        # Las rutas HTML y JSON comparten el mismo límite por IP.
        bloqueado_html = self.client.post("/cuenta/registrar", data={
            "email": "registro-html@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(bloqueado_html.status_code, 429)

    def test_registro_queda_pendiente_de_verificacion(self):
        r = self.client.post("/cuenta/registro", json={
            "email": "adulto@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json["estado"], "pendiente_verificacion")

        login = self.client.post("/cuenta/login", json={
            "email": "adulto@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 401)

    def test_seleccion_perfil_rechaza_redireccion_externa(self):
        email = "redirect@example.com"
        self.client.post("/cuenta/registro", json={
            "email": email, "password": "una-clave-larga-123",
        })
        cuenta_id = "acc_" + __import__("hashlib").sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)
        login = self.client.post("/cuenta/login", json={
            "email": email, "password": "una-clave-larga-123",
        })
        csrf = login.json["csrf"]
        creado = self.client.post("/cuenta/perfiles", json={"nombre": "Ana"},
                                  headers={"X-Tortu-CSRF": csrf})
        self.assertEqual(creado.status_code, 201)

        pagina = self.client.get("/cuenta/seleccionar-perfil?next=https://evil.example")
        self.assertEqual(pagina.status_code, 200)
        self.assertNotIn("evil.example", pagina.get_data(as_text=True))

        seleccion = self.client.post("/cuenta/perfil", data={
            "perfil_id": creado.json["perfil"]["id"],
            "csrf": csrf,
            "next": "https://evil.example",
        })
        self.assertEqual(seleccion.status_code, 302)
        self.assertTrue(seleccion.headers["Location"].startswith("/"))
        self.assertNotIn("evil.example", seleccion.headers["Location"])

    def test_login_html_no_revela_si_la_cuenta_existe_o_esta_verificada(self):
        self.client.post("/cuenta/registro", json={
            "email": "pendiente@example.com",
            "password": "una-clave-larga-123",
        })
        existente = self.client.post("/cuenta/login", data={
            "email": "pendiente@example.com",
            "password": "una-clave-larga-123",
        })
        inexistente = self.client.post("/cuenta/login", data={
            "email": "no-existe@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(existente.status_code, 401)
        self.assertEqual(inexistente.status_code, 401)
        self.assertEqual(existente.get_data(as_text=True), inexistente.get_data(as_text=True))

    def test_login_tiene_limite_agregado_por_ip_al_rotar_correos(self):
        for indice in range(30):
            respuesta = self.client.post("/cuenta/login", json={
                "email": f"rotacion-{indice}@example.com",
                "password": "clave-incorrecta",
            })
            self.assertEqual(respuesta.status_code, 401)
        bloqueado = self.client.post("/cuenta/login", json={
            "email": "rotacion-final@example.com",
            "password": "clave-incorrecta",
        })
        self.assertEqual(bloqueado.status_code, 429)
        self.assertIn("Retry-After", bloqueado.headers)

    def test_recuperacion_limita_tambien_solicitudes_malformadas(self):
        for _ in range(5):
            respuesta = self.client.post("/cuenta/recuperar", json={})
            self.assertEqual(respuesta.status_code, 202)
        bloqueado = self.client.post("/cuenta/recuperar", json={})
        self.assertEqual(bloqueado.status_code, 429)
        self.assertIn("Retry-After", bloqueado.headers)

    def test_limites_por_ip_en_login_verificacion_y_restablecimiento(self):
        for _ in range(10):
            login = self.client.post("/cuenta/login", json={
                "email": "ausente@example.com", "password": "clave-incorrecta",
            })
            self.assertEqual(login.status_code, 401)
        login_bloqueado = self.client.post("/cuenta/login", json={
            "email": "ausente@example.com", "password": "clave-incorrecta",
        })
        self.assertEqual(login_bloqueado.status_code, 429)
        self.assertIn("Retry-After", login_bloqueado.headers)

        for _ in range(10):
            verificacion = self.client.post("/cuenta/verificar-email", json={
                "token": "token-invalido",
            })
            self.assertEqual(verificacion.status_code, 400)
        verificacion_bloqueada = self.client.post("/cuenta/verificar-email", json={
            "token": "otro-token-invalido",
        })
        self.assertEqual(verificacion_bloqueada.status_code, 429)

        for _ in range(10):
            restablecimiento = self.client.post("/cuenta/restablecer-password", json={
                "token": "token-invalido", "password": "una-clave-larga-123",
            })
            self.assertEqual(restablecimiento.status_code, 400)
        restablecimiento_bloqueado = self.client.post("/cuenta/restablecer-password", json={
            "token": "otro-token-invalido", "password": "una-clave-larga-123",
        })
        self.assertEqual(restablecimiento_bloqueado.status_code, 429)

    def test_login_cookie_me_csrf_perfil_y_logout(self):
        self.client.post("/cuenta/registro", json={
            "email": "adulto@example.com",
            "password": "una-clave-larga-123",
        })
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta = repo.obtener_account("acc_" + __import__("hashlib").sha256("adulto@example.com".encode()).hexdigest()[:24])
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta.id)

        login = self.client.post("/cuenta/login", json={
            "email": "adulto@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]
        cookies = "\\n".join(login.headers.getlist("Set-Cookie"))
        self.assertIn("tortu_session=", cookies)
        self.assertIn("tortu_csrf=", cookies)

        me = self.client.get("/cuenta/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json["cuenta"]["email"], "adulto@example.com")
        self.assertEqual(me.json["perfiles"], [])

        bad = self.client.post("/cuenta/perfiles", json={"nombre": "Ana"})
        self.assertEqual(bad.status_code, 403)

        created = self.client.post(
            "/cuenta/perfiles",
            json={"nombre": "Ana"},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["perfil"]["nombre"], "Ana")

        me2 = self.client.get("/cuenta/me")
        self.assertEqual([p["nombre"] for p in me2.json["perfiles"]], ["Ana"])

        selected = self.client.post(
            "/cuenta/perfil",
            json={"perfil_id": created.json["perfil"]["id"]},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json["perfil_activo"], created.json["perfil"]["id"])

        perfiles_api = self.client.get("/api/perfiles", headers={"X-Tortu-Token": "test-token"})
        self.assertEqual(perfiles_api.status_code, 200)
        self.assertEqual(perfiles_api.json["modo"], "cuenta")
        self.assertEqual(perfiles_api.json["perfiles"][0]["id"], created.json["perfil"]["id"])

        me3 = self.client.get("/cuenta/me")
        self.assertEqual(me3.json["perfil_activo"], created.json["perfil"]["id"])

        progress = {
            "contract_version": 1,
            "profile_id": created.json["perfil"]["id"],
            "updated_at": "2026-09-30T12:00:00+00:00",
            "data": {"xp_total": 25000},
        }
        saved = self.client.put(
            "/cuenta/progreso",
            json=progress,
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(saved.status_code, 410)
        self.assertEqual(saved.json["codigo"], "escritura_no_autoritativa")

        loaded = self.client.get("/cuenta/progreso")
        self.assertEqual(loaded.status_code, 200)
        self.assertIsNone(loaded.json["progreso"])

        acceso = self.client.get("/cuenta/acceso?producto=tortuscript-premium")
        self.assertEqual(acceso.status_code, 200)
        self.assertFalse(acceso.json["permitido"])

        repo.establecer_entitlement(cuenta.id, "tortuscript-premium", True, "payment")
        acceso2 = self.client.get("/cuenta/acceso?producto=tortuscript-premium")
        self.assertTrue(acceso2.json["permitido"])

        # Un snapshot de otro perfil no puede escribirse sobre el perfil activo.
        otro = self.client.post(
            "/cuenta/perfiles",
            json={"nombre": "Beto"},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(otro.status_code, 201)
        bad_progress = dict(progress, profile_id=otro.json["perfil"]["id"])
        rejected = self.client.put(
            "/cuenta/progreso",
            json=bad_progress,
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(rejected.status_code, 410)
        self.assertEqual(rejected.json["codigo"], "escritura_no_autoritativa")

        logout = self.client.post("/cuenta/logout", headers={"X-Tortu-CSRF": csrf})
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/cuenta/me").status_code, 401)



    def test_cuenta_perfil_activo_abre_onboarding_y_progreso_persiste(self):
        # Recorrido integrado mínimo del producto actual: cuenta adulta, perfil,
        # sesión educativa, primera página y persistencia asociada al perfil.
        registro = self.client.post("/cuenta/registro", json={
            "email": "flujo@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(registro.status_code, 202)

        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta_id = "acc_" + __import__("hashlib").sha256(
            "flujo@example.com".encode()
        ).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)

        login = self.client.post("/cuenta/login", json={
            "email": "flujo@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]

        creado = self.client.post(
            "/cuenta/perfiles",
            json={"nombre": "Perfil de prueba"},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(creado.status_code, 201)
        perfil_id = creado.json["perfil"]["id"]

        seleccionado = self.client.post(
            "/cuenta/perfil",
            json={"perfil_id": perfil_id},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(seleccionado.status_code, 200)

        inicio = self.client.get("/", follow_redirects=False)
        self.assertEqual(inicio.status_code, 302)
        self.assertIn("/bienvenida", inicio.headers["Location"])
        bienvenida = self.client.get("/bienvenida")
        self.assertEqual(bienvenida.status_code, 200)

        guardado = self.client.post(
            "/api/onboarding",
            json={"nombre": "Perfil de prueba", "experiencia": "nunca", "meta_min": 5},
            headers={"X-Tortu-Token": "test-token"},
        )
        self.assertEqual(guardado.status_code, 200, guardado.get_data(as_text=True))

        recuperado = self.client.get("/cuenta/progreso")
        self.assertEqual(recuperado.status_code, 200)
        self.assertEqual(recuperado.json["perfil"]["id"], perfil_id)
        self.assertEqual(recuperado.json["progreso"]["data"]["config"]["nombre"], "Perfil de prueba")
        self.assertEqual(recuperado.json["progreso"]["data"]["xp_total"], 0)

    def test_aislamiento_entre_cuentas_para_perfiles_y_progreso(self):
        for email in ("a@example.com", "b@example.com"):
            respuesta = self.client.post("/cuenta/registro", json={
                "email": email,
                "password": "una-clave-larga-123",
            })
            self.assertEqual(respuesta.status_code, 202)

        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        auth = AuthRepository(self.tmp / "cuentas.sqlite3")
        for email in ("a@example.com", "b@example.com"):
            cuenta = repo.obtener_account(
                "acc_" + __import__("hashlib").sha256(email.encode()).hexdigest()[:24]
            )
            auth.marcar_verificada(cuenta.id)

        cliente_a = self.app.test_client()
        cliente_b = self.app.test_client()
        login_a = cliente_a.post("/cuenta/login", json={
            "email": "a@example.com",
            "password": "una-clave-larga-123",
        })
        login_b = cliente_b.post("/cuenta/login", json={
            "email": "b@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login_a.status_code, 200)
        self.assertEqual(login_b.status_code, 200)
        csrf_a = login_a.json["csrf"]
        csrf_b = login_b.json["csrf"]

        perfil_a = cliente_a.post(
            "/cuenta/perfiles",
            json={"nombre": "Perfil A"},
            headers={"X-Tortu-CSRF": csrf_a},
        )
        perfil_b = cliente_b.post(
            "/cuenta/perfiles",
            json={"nombre": "Perfil B"},
            headers={"X-Tortu-CSRF": csrf_b},
        )
        self.assertEqual(perfil_a.status_code, 201)
        self.assertEqual(perfil_b.status_code, 201)
        pid_a = perfil_a.json["perfil"]["id"]
        pid_b = perfil_b.json["perfil"]["id"]

        seleccionado_b = cliente_b.post(
            "/cuenta/perfil",
            json={"perfil_id": pid_b},
            headers={"X-Tortu-CSRF": csrf_b},
        )
        self.assertEqual(seleccionado_b.status_code, 200)

        seleccionado_a = cliente_a.post(
            "/cuenta/perfil",
            json={"perfil_id": pid_a},
            headers={"X-Tortu-CSRF": csrf_a},
        )
        self.assertEqual(seleccionado_a.status_code, 200)

        cruzado = cliente_a.post(
            "/cuenta/perfil",
            json={"perfil_id": pid_b},
            headers={"X-Tortu-CSRF": csrf_a},
        )
        self.assertEqual(cruzado.status_code, 403)

        snapshot = {
            "contract_version": 1,
            "profile_id": pid_b,
            "updated_at": "2026-09-30T12:00:00+00:00",
            "data": {"xp_total": 999},
        }
        escritura_cruzada = cliente_a.put(
            "/cuenta/progreso",
            json=snapshot,
            headers={"X-Tortu-CSRF": csrf_a},
        )
        self.assertEqual(escritura_cruzada.status_code, 410)

        acceso_b = cliente_b.get("/cuenta/acceso?producto=tortuscript-premium")
        self.assertEqual(acceso_b.status_code, 200)
        self.assertFalse(acceso_b.json["permitido"])

        repo.establecer_entitlement(
            "acc_" + __import__("hashlib").sha256("b@example.com".encode()).hexdigest()[:24],
            "tortuscript-premium",
            True,
            "payment",
        )
        acceso_b_premium = cliente_b.get("/cuenta/acceso?producto=tortuscript-premium")
        self.assertTrue(acceso_b_premium.json["permitido"])

        # La sesión de A no puede observar el entitlement de B porque no puede seleccionar su perfil.
        acceso_a = cliente_a.get("/cuenta/acceso?producto=tortuscript-premium")
        self.assertFalse(acceso_a.json["permitido"])

    def test_runtime_educativo_registra_xp_leccion_practica_y_proyecto(self):
        self.client.post("/cuenta/registro", json={
            "email": "runtime@example.com",
            "password": "una-clave-larga-123",
        })
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta = repo.obtener_account("acc_" + __import__("hashlib").sha256("runtime@example.com".encode()).hexdigest()[:24])
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta.id)
        login = self.client.post("/cuenta/login", json={
            "email": "runtime@example.com",
            "password": "una-clave-larga-123",
        })
        csrf = login.json["csrf"]
        perfil = self.client.post("/cuenta/perfiles", json={"nombre": "Ana"}, headers={"X-Tortu-CSRF": csrf})
        pid = perfil.json["perfil"]["id"]
        self.client.post("/cuenta/perfil", json={"perfil_id": pid}, headers={"X-Tortu-CSRF": csrf})

        ejercicio = self.client.post("/cuenta/runtime/ejercicio", json={
            "indice": 0, "estrellas": 3, "xp_ganado": 10
        }, headers={"X-Tortu-CSRF": csrf})
        self.assertEqual(ejercicio.status_code, 410)
        self.assertEqual(ejercicio.json["codigo"], "evaluacion_requerida")

        leccion = self.client.post("/cuenta/runtime/leccion/paso", json={
            "leccion_id": "leccion-runtime", "indice": 0, "xp": 5000,
            "perfecto": True, "total_pasos": 1, "estrellas": 3
        }, headers={"X-Tortu-CSRF": csrf})
        self.assertEqual(leccion.status_code, 410)
        self.assertEqual(leccion.json["codigo"], "evaluacion_requerida")

        practica = self.client.post("/cuenta/runtime/practica", json={
            "leccion_id": "leccion-runtime", "paso": 0, "acierto": True
        }, headers={"X-Tortu-CSRF": csrf})
        self.assertEqual(practica.status_code, 410)
        self.assertEqual(practica.json["codigo"], "comprobacion_requerida")

        proyecto = self.client.post("/cuenta/runtime/proyectos", json={
            "nombre": "Mi proyecto", "tipo": "experimentar", "codigo": "print('hola')"
        }, headers={"X-Tortu-CSRF": csrf})
        self.assertEqual(proyecto.status_code, 200)

        listado = self.client.get("/cuenta/runtime/proyectos")
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(len(listado.json["proyectos"]), 1)

        progreso = self.client.get("/cuenta/runtime/progreso")
        self.assertEqual(progreso.status_code, 200)
        # Las peticiones de puntuación falsificada no deben mutar el progreso.
        self.assertEqual(progreso.json["progreso"]["data"]["xp_total"], 0)
        self.assertNotIn("leccion-runtime", progreso.json["progreso"]["data"]["lecciones"])
        self.assertEqual(len(progreso.json["progreso"]["data"]["proyectos"]), 1)


    def test_pantallas_educativas_usan_childprofile_activo(self):
        self.client.post("/cuenta/registro", json={
            "email": "pantallas@example.com",
            "password": "una-clave-larga-123",
        })
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta = repo.obtener_account("acc_" + __import__("hashlib").sha256(
            "pantallas@example.com".encode()
        ).hexdigest()[:24])
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta.id)

        login = self.client.post("/cuenta/login", json={
            "email": "pantallas@example.com",
            "password": "una-clave-larga-123",
        })
        csrf = login.json["csrf"]
        perfil = self.client.post(
            "/cuenta/perfiles", json={"nombre": "Ana"},
            headers={"X-Tortu-CSRF": csrf},
        )
        pid = perfil.json["perfil"]["id"]
        self.client.post(
            "/cuenta/perfil", json={"perfil_id": pid},
            headers={"X-Tortu-CSRF": csrf},
        )

        api_headers = {"X-Tortu-Token": "test-token"}
        estado = self.client.get("/api/estado", headers=api_headers)
        self.assertEqual(estado.status_code, 200)
        self.assertEqual(estado.json["nombre"], "Ana")

        proyecto = self.client.post(
            "/api/proyectos",
            json={"nombre": "Proyecto UI", "tipo": "experimentar", "codigo": "print(1)"},
            headers=api_headers,
        )
        self.assertEqual(proyecto.status_code, 200)

        snapshot = self.client.get("/cuenta/progreso")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json["perfil"]["nombre"], "Ana")
        data = snapshot.json["progreso"]["data"]
        self.assertEqual(len(data["proyectos"]), 1)

        archivos = list((self.tmp / "progreso_perfiles").glob("progreso_*.json"))
        self.assertEqual(len(archivos), 1)
        self.assertIn(pid, archivos[0].name)


    def test_gateway_educativo_llega_a_bienvenida_despues_de_seleccionar_perfil(self):
        self.client.post("/cuenta/registro", json={
            "email": "gateway@example.com",
            "password": "una-clave-larga-123",
        })
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta = repo.obtener_account("acc_" + __import__("hashlib").sha256(
            "gateway@example.com".encode()
        ).hexdigest()[:24])
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta.id)

        login = self.client.post("/cuenta/login", json={
            "email": "gateway@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]

        perfil = self.client.post(
            "/cuenta/perfiles",
            json={"nombre": "Ana"},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(perfil.status_code, 201)

        selected = self.client.post(
            "/cuenta/perfil",
            json={"perfil_id": perfil.json["perfil"]["id"]},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(selected.status_code, 200)

        inicio = self.client.get("/", follow_redirects=False)
        self.assertEqual(inicio.status_code, 302)
        self.assertIn("/bienvenida", inicio.headers["Location"])


    def test_onboarding_web_persiste_en_el_childprofile_activo(self):
        self.client.post("/cuenta/registro", json={
            "email": "onboarding@example.com",
            "password": "una-clave-larga-123",
        })
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta = repo.obtener_account("acc_" + __import__("hashlib").sha256(
            "onboarding@example.com".encode()
        ).hexdigest()[:24])
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta.id)

        login = self.client.post("/cuenta/login", json={
            "email": "onboarding@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]

        perfil = self.client.post(
            "/cuenta/perfiles",
            json={"nombre": "Ana"},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(perfil.status_code, 201)
        pid = perfil.json["perfil"]["id"]

        selected = self.client.post(
            "/cuenta/perfil",
            json={"perfil_id": pid},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(selected.status_code, 200)

        onboarding = self.client.post(
            "/api/onboarding",
            json={"nombre": "Marcos", "experiencia": "nunca", "meta_min": 5},
            headers={"X-Tortu-Token": "test-token"},
        )
        self.assertEqual(onboarding.status_code, 200, onboarding.get_data(as_text=True))
        self.assertTrue(onboarding.json["ok"])

        progreso = self.client.get("/cuenta/progreso")
        self.assertEqual(progreso.status_code, 200)
        data = progreso.json["progreso"]["data"]
        self.assertTrue(data["config"]["onboarding"])
        self.assertEqual(data["config"]["nombre"], "Marcos")
        self.assertEqual(data["config"]["experiencia"], "nunca")
        self.assertEqual(data["config"]["meta_min"], 5)

        inicio = self.client.get("/")
        self.assertEqual(inicio.status_code, 200)


    def test_verificacion_y_recuperacion_http_no_exponen_token(self):
        registro = self.client.post("/cuenta/registro", json={
            "email": "seguridad@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(registro.status_code, 202)
        self.assertNotIn("token", registro.json)
        self.assertEqual(self.emails[0]["tipo"], "verification")
        token = self.emails[0]["token"]

        verificado = self.client.get("/cuenta/verificar-email", query_string={"token": token})
        self.assertEqual(verificado.status_code, 200)
        self.assertIn("Confirmar correo", verificado.get_data(as_text=True))

        # Un GET de escáner no debe consumir el token.
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        cuenta = repo.obtener_account_por_email("seguridad@example.com")
        auth_repo = AuthRepository(self.tmp / "cuentas.sqlite3")
        with auth_repo._db() as db:
            self.assertIsNone(db.execute(
                "SELECT verified_at FROM accounts WHERE id=?", (cuenta.id,)
            ).fetchone()[0])

        confirmado = self.client.post("/cuenta/verificar-email", data={"token": token})
        self.assertEqual(confirmado.status_code, 200)
        with auth_repo._db() as db:
            self.assertIsNotNone(db.execute(
                "SELECT verified_at FROM accounts WHERE id=?", (cuenta.id,)
            ).fetchone()[0])

        login = self.client.post("/cuenta/login", json={
            "email": "seguridad@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)

        recovery = self.client.post("/cuenta/recuperar", json={"email": "seguridad@example.com"})
        self.assertEqual(recovery.status_code, 202)
        self.assertEqual(self.emails[-1]["tipo"], "recovery")
        recovery_token = self.emails[-1]["token"]

        reset = self.client.post("/cuenta/restablecer-password", json={
            "token": recovery_token,
            "password": "otra-clave-larga-456",
        })
        self.assertEqual(reset.status_code, 200)

        login2 = self.client.post("/cuenta/login", json={
            "email": "seguridad@example.com",
            "password": "otra-clave-larga-456",
        })
        self.assertEqual(login2.status_code, 200)

        reused = self.client.post("/cuenta/restablecer-password", json={
            "token": recovery_token,
            "password": "tercera-clave-larga-789",
        })
        self.assertEqual(reused.status_code, 400)


    def test_login_aplica_rate_limit_y_devuelve_retry_after(self):
        self.client.post("/cuenta/registro", json={
            "email": "limit@example.com",
            "password": "una-clave-larga-123",
        })
        for _ in range(10):
            respuesta = self.client.post("/cuenta/login", json={
                "email": "limit@example.com",
                "password": "incorrecta-larga",
            })
            self.assertEqual(respuesta.status_code, 401)
        bloqueado = self.client.post("/cuenta/login", json={
            "email": "limit@example.com",
            "password": "incorrecta-larga",
        })
        self.assertEqual(bloqueado.status_code, 429)
        self.assertIn("Retry-After", bloqueado.headers)

    def test_cambiar_perfil_mantiene_progreso_independiente_por_perfil(self):
        self.client.post("/cuenta/registro", json={
            "email": "aislamiento@example.com",
            "password": "una-clave-larga-123",
        })
        repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        repo.ensure_schema()
        cuenta_id = "acc_" + __import__("hashlib").sha256(
            "aislamiento@example.com".encode()
        ).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)
        login = self.client.post("/cuenta/login", json={
            "email": "aislamiento@example.com",
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]
        headers = {"X-Tortu-CSRF": csrf}

        perfiles = []
        for nombre in ("Ana", "Beto"):
            respuesta = self.client.post(
                "/cuenta/perfiles", json={"nombre": nombre}, headers=headers
            )
            self.assertEqual(respuesta.status_code, 201)
            perfiles.append(respuesta.json["perfil"]["id"])

        def seleccionar_y_guardar(pid, xp, timestamp):
            seleccionado = self.client.post(
                "/cuenta/perfil", json={"perfil_id": pid}, headers=headers
            )
            self.assertEqual(seleccionado.status_code, 200)
            guardado = self.client.post("/api/onboarding", json={
                "nombre": f"Perfil-{xp}",
                "experiencia": "nunca",
                "meta_min": 5,
            }, headers={"X-Tortu-Token": "test-token"})
            self.assertEqual(guardado.status_code, 200, guardado.get_data(as_text=True))
            cargado = self.client.get("/cuenta/progreso")
            self.assertEqual(cargado.status_code, 200)
            self.assertEqual(cargado.json["progreso"]["data"]["config"]["nombre"], f"Perfil-{xp}")
            self.assertEqual(cargado.json["progreso"]["data"]["xp_total"], 0)

        seleccionar_y_guardar(perfiles[0], 11, "2026-10-02T12:00:00+00:00")
        seleccionar_y_guardar(perfiles[1], 22, "2026-10-02T12:01:00+00:00")
        seleccionar_y_guardar(perfiles[0], 11, "2026-10-02T12:00:00+00:00")
        seleccionar_y_guardar(perfiles[1], 22, "2026-10-02T12:01:00+00:00")


    def test_evaluacion_canonica_persiste_y_aisla_xp_entre_perfiles(self):
        # Recorrido autenticado completo: cuenta → perfiles → onboarding →
        # evaluación canónica en servidor → persistencia → cambio y recuperación.
        email = "evaluacion-integrada@example.com"
        self.client.post("/cuenta/registro", json={
            "email": email,
            "password": "una-clave-larga-123",
        })
        cuenta_id = "acc_" + __import__("hashlib").sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)

        login = self.client.post("/cuenta/login", json={
            "email": email,
            "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]
        headers = {"X-Tortu-CSRF": csrf, "X-Tortu-Token": "test-token"}

        perfiles = {}
        for nombre in ("Ana", "Beto"):
            creado = self.client.post(
                "/cuenta/perfiles", json={"nombre": nombre}, headers=headers
            )
            self.assertEqual(creado.status_code, 201, creado.get_data(as_text=True))
            perfiles[nombre] = creado.json["perfil"]["id"]

        def seleccionar(perfil_id):
            respuesta = self.client.post(
                "/cuenta/perfil", json={"perfil_id": perfil_id},
                headers={"X-Tortu-CSRF": csrf},
            )
            self.assertEqual(respuesta.status_code, 200, respuesta.get_data(as_text=True))

        def completar_onboarding(nombre):
            respuesta = self.client.post("/api/onboarding", json={
                "nombre": nombre, "experiencia": "nunca", "meta_min": 5,
            }, headers={"X-Tortu-Token": "test-token"})
            self.assertEqual(respuesta.status_code, 200, respuesta.get_data(as_text=True))

        seleccionar(perfiles["Ana"])
        completar_onboarding("Ana")
        evaluacion = self.client.post(
            "/api/ejercicios/1/evaluar",
            json={"codigo": 'mostrar "Hola mundo"'},
            headers={"X-Tortu-Token": "test-token"},
        )
        self.assertEqual(evaluacion.status_code, 200, evaluacion.get_data(as_text=True))
        self.assertEqual(evaluacion.json["evaluacion"]["estado"], "correcto")
        self.assertEqual(evaluacion.json["premio"]["xp"], 30)

        # La ruta canónica de lección debe evaluar el mismo paso sin crear
        # una segunda recompensa ni divergir del progreso del ejercicio.
        evaluacion_leccion = self.client.post(
            "/api/lecciones/hola-mundo/pasos/5/evaluar",
            json={"codigo": 'mostrar "Hola mundo"'},
            headers={"X-Tortu-Token": "test-token"},
        )
        self.assertEqual(
            evaluacion_leccion.status_code, 200,
            evaluacion_leccion.get_data(as_text=True),
        )
        self.assertEqual(evaluacion_leccion.json["evaluacion"]["estado"], "correcto")

        progreso_ana = self.client.get("/cuenta/progreso")
        self.assertEqual(progreso_ana.status_code, 200)
        self.assertEqual(progreso_ana.json["perfil"]["id"], perfiles["Ana"])
        self.assertEqual(progreso_ana.json["progreso"]["data"]["xp_total"], 30)

        seleccionar(perfiles["Beto"])
        completar_onboarding("Beto")
        progreso_beto = self.client.get("/cuenta/progreso")
        self.assertEqual(progreso_beto.status_code, 200)
        self.assertEqual(progreso_beto.json["perfil"]["id"], perfiles["Beto"])
        self.assertEqual(progreso_beto.json["progreso"]["data"]["xp_total"], 0)
        self.assertEqual(
            progreso_beto.json["progreso"]["data"]["config"]["nombre"], "Beto"
        )

        seleccionar(perfiles["Ana"])
        recuperado = self.client.get("/cuenta/progreso")
        self.assertEqual(recuperado.status_code, 200)
        self.assertEqual(recuperado.json["perfil"]["id"], perfiles["Ana"])
        self.assertEqual(recuperado.json["progreso"]["data"]["xp_total"], 30)
        self.assertEqual(
            recuperado.json["progreso"]["data"]["config"]["nombre"], "Ana"
        )


    def test_practica_canonica_autenticada_persiste_en_perfil_activo(self):
        email = "practica-integrada@example.com"
        self.client.post("/cuenta/registro", json={
            "email": email, "password": "una-clave-larga-123",
        })
        cuenta_id = "acc_" + __import__("hashlib").sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)
        login = self.client.post("/cuenta/login", json={
            "email": email, "password": "una-clave-larga-123",
        })
        self.assertEqual(login.status_code, 200)
        csrf = login.json["csrf"]
        creado = self.client.post(
            "/cuenta/perfiles", json={"nombre": "Practica"},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(creado.status_code, 201)
        perfil_id = creado.json["perfil"]["id"]
        seleccionado = self.client.post(
            "/cuenta/perfil", json={"perfil_id": perfil_id},
            headers={"X-Tortu-CSRF": csrf},
        )
        self.assertEqual(seleccionado.status_code, 200)

        onboarding = self.client.post("/api/onboarding", json={
            "nombre": "Practica", "experiencia": "nunca", "meta_min": 5,
        }, headers={"X-Tortu-Token": "test-token"})
        self.assertEqual(onboarding.status_code, 200, onboarding.get_data(as_text=True))

        # Completar los pasos rápidos crea tarjetas vencidas cuando avanzamos
        # el reloj de la aplicación de prueba dos días, sin tocar el reloj real.
        respuestas = {
            0: True,
            1: "mostrar",
            2: ["mostrar"],
            3: ['mostrar "Hola"', 'mostrar "Chau"'],
            4: "Buen día",
        }
        for indice, respuesta in respuestas.items():
            comprobado = self.client.post(
                f"/api/lecciones/hola-mundo/pasos/{indice}/comprobar",
                json={"respuesta": respuesta},
                headers={"X-Tortu-Token": "test-token"},
            )
            self.assertEqual(
                comprobado.status_code, 200,
                f"paso {indice}: {comprobado.get_data(as_text=True)}",
            )
            self.assertTrue(comprobado.json["ok"])

        progreso_antes = self.client.get("/cuenta/progreso")
        self.assertEqual(progreso_antes.status_code, 200)
        xp_antes = progreso_antes.json["progreso"]["data"]["xp_total"]

        fecha_real = __import__("datetime").date
        delta = __import__("datetime").timedelta

        class FechaFutura(fecha_real):
            @classmethod
            def today(cls):
                return fecha_real.today() + delta(days=2)

        with patch("web.app.date", FechaFutura):
            pagina = self.client.get("/practica")
            self.assertEqual(pagina.status_code, 200, pagina.get_data(as_text=True))
            respuesta = self.client.post(
                "/api/practica/comprobar",
                json={"leccion": "hola-mundo", "paso": 1, "respuesta": "mostrar"},
                headers={"X-Tortu-Token": "test-token"},
            )
        self.assertEqual(respuesta.status_code, 200, respuesta.get_data(as_text=True))
        self.assertTrue(respuesta.json["ok"])

        progreso_despues = self.client.get("/cuenta/progreso")
        self.assertEqual(progreso_despues.status_code, 200)
        self.assertEqual(progreso_despues.json["perfil"]["id"], perfil_id)
        self.assertEqual(
            progreso_despues.json["progreso"]["data"]["xp_total"], xp_antes + 2
        )
        tarjeta = progreso_despues.json["progreso"]["data"]["repaso"]["hola-mundo:1"]
        self.assertEqual(tarjeta["aciertos"], 1)

if __name__ == "__main__":
    unittest.main()
