"""Barrido 4 — lo que el adulto puede hacer con los datos de su familia: acceso, rectificación,
archivo de perfiles, cambio de contraseña y registro de consentimiento."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaError, CuentaRepository, MAX_CHILD_PROFILES
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot
from web.app import create_app

CLAVE = "una-clave-larga-123"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
                               PROGRESS_DIR=self.tmp / "progreso_perfiles",
                               ACCOUNT_EMAIL_SENDER=lambda **payload: None)
        self.c = self.app.test_client()
        self.cuentas = CuentaRepository(self.tmp / "cuentas.sqlite3")
        self.cuentas.ensure_schema()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _cuenta(self, email, cliente=None):
        """Registra, verifica e inicia sesión. Devuelve (cliente, id de cuenta)."""
        cliente = cliente or self.c
        r = cliente.post("/cuenta/registrar", data={"email": email, "password": CLAVE, "responsable": "si"})
        self.assertEqual(r.status_code, 202)
        cuenta_id = "acc_" + hashlib.sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)
        self.assertEqual(cliente.post("/cuenta/login", data={"email": email, "password": CLAVE}).status_code, 302)
        return cliente, cuenta_id

    def _csrf(self, cliente=None):
        return (cliente or self.c).get_cookie("tortu_csrf").value

    def _perfil(self, nombre, cliente=None):
        cliente = cliente or self.c
        r = cliente.post("/cuenta/perfiles", json={"nombre": nombre}, headers={"X-Tortu-CSRF": self._csrf(cliente)})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.json["perfil"]["id"]

    def _form(self, ruta, cliente=None, **datos):
        cliente = cliente or self.c
        return cliente.post(ruta, data={"csrf": self._csrf(cliente), **datos})


class TestConsentimiento(Base):
    def test_el_registro_exige_y_registra_la_declaracion_del_adulto(self):
        sin = self.c.post("/cuenta/registrar", data={"email": "a@example.com", "password": CLAVE})
        self.assertEqual(sin.status_code, 400)
        self.assertIn("persona adulta responsable", sin.get_data(as_text=True))
        self.assertIn('value="a@example.com"', sin.get_data(as_text=True))          # no hay que reescribir el correo
        self.assertIsNone(self.cuentas.obtener_account_por_email("a@example.com"))  # sin declaración no hay cuenta

        _, cuenta_id = self._cuenta("a@example.com")
        historial = self.cuentas.listar_consentimientos(cuenta_id)
        self.assertEqual([(c.finalidad, c.otorgado) for c in historial], [("responsable_adulto", True)])
        self.assertTrue(historial[0].version)
        self.assertTrue(self.cuentas.tiene_consentimiento(cuenta_id, "responsable_adulto"))

    def test_una_finalidad_no_habilita_otra_y_sin_registro_no_hay_consentimiento(self):
        _, cuenta_id = self._cuenta("b@example.com")
        for finalidad in ("analitica", "tutor_ia", "sincronizacion"):
            self.assertFalse(self.cuentas.tiene_consentimiento(cuenta_id, finalidad))

    def test_revocar_agrega_una_fila_y_vale_la_ultima_decision(self):
        _, cuenta_id = self._cuenta("c@example.com")
        self.cuentas.registrar_consentimiento(cuenta_id, "tutor_ia", "v1", True)
        self.assertTrue(self.cuentas.tiene_consentimiento(cuenta_id, "tutor_ia"))
        self.cuentas.registrar_consentimiento(cuenta_id, "tutor_ia", "v1", False)
        self.assertFalse(self.cuentas.tiene_consentimiento(cuenta_id, "tutor_ia"))
        self.cuentas.registrar_consentimiento(cuenta_id, "tutor_ia", "v2", True)
        self.assertTrue(self.cuentas.tiene_consentimiento(cuenta_id, "tutor_ia"))
        del_tutor = [c for c in self.cuentas.listar_consentimientos(cuenta_id) if c.finalidad == "tutor_ia"]
        self.assertEqual([(c.version, c.otorgado) for c in del_tutor], [("v1", True), ("v1", False), ("v2", True)])

    def test_decisiones_invalidas_se_rechazan(self):
        _, cuenta_id = self._cuenta("d@example.com")
        for args in ((cuenta_id, "publicidad", "v1", True), (cuenta_id, "tutor_ia", "", True),
                     (cuenta_id, "tutor_ia", "v1", 1), (cuenta_id, "tutor_ia", "x" * 41, True),
                     ("acc_inexistente", "tutor_ia", "v1", True)):
            with self.subTest(args=args), self.assertRaises(CuentaError):
                self.cuentas.registrar_consentimiento(*args)


class TestPerfiles(Base):
    def test_renombrar_conserva_identidad_y_progreso(self):
        self._cuenta("e@example.com")
        ana = self._perfil("Ana")
        ProgresoChildProfile(self.tmp / "progreso_perfiles").guardar(nuevo_snapshot(ana, {"xp_total": 40}))
        r = self._form(f"/cuenta/perfiles/{ana}/renombrar", nombre="  Anita  ")
        self.assertEqual(r.status_code, 302)
        self.assertIn("ok=renombrado", r.headers["Location"])
        self.assertIn("El nombre del perfil se cambió", self.c.get(r.headers["Location"]).get_data(as_text=True))
        perfiles = self.c.get("/cuenta/me").json["perfiles"]
        self.assertEqual(perfiles, [{"id": ana, "nombre": "Anita"}])
        self.assertEqual(ProgresoChildProfile(self.tmp / "progreso_perfiles").cargar(ana).data["xp_total"], 40)

    def test_renombrar_rechaza_duplicados_equivalentes_y_nombres_invalidos(self):
        self._cuenta("f@example.com")
        ana, _bruno = self._perfil("Ana"), self._perfil("Bruno")
        for nombre in ("BRUNO", "", "x" * 31):
            with self.subTest(nombre=nombre):
                r = self._form(f"/cuenta/perfiles/{ana}/renombrar", nombre=nombre)
                self.assertEqual(r.status_code, 400)
        self.assertEqual(self._form(f"/cuenta/perfiles/{ana}/renombrar", nombre="ANA").status_code, 302)   # el propio
        r = self.c.post(f"/cuenta/perfiles/{ana}/renombrar", json={"nombre": ["x"]},
                        headers={"X-Tortu-CSRF": self._csrf()})
        self.assertEqual(r.status_code, 400)

    def test_archivar_saca_el_perfil_de_uso_sin_borrar_su_progreso_y_restaurar_lo_devuelve(self):
        self._cuenta("g@example.com")
        ana, bruno = self._perfil("Ana"), self._perfil("Bruno")
        store = ProgresoChildProfile(self.tmp / "progreso_perfiles")
        store.guardar(nuevo_snapshot(ana, {"xp_total": 40}))
        self.c.post("/cuenta/perfil", json={"perfil_id": ana}, headers={"X-Tortu-CSRF": self._csrf()})
        self.assertEqual(self.c.get("/api/estado", headers={"X-Tortu-Token": "t"}).status_code, 200)

        self.assertEqual(self._form(f"/cuenta/perfiles/{ana}/archivar").status_code, 302)
        # Ya no se puede usar ni elegir, y la sesión que lo tenía activo vuelve al selector.
        self.assertEqual(self.c.get("/api/estado", headers={"X-Tortu-Token": "t"}).status_code, 401)
        self.assertIn("/cuenta/seleccionar-perfil", self.c.get("/mapa").headers["Location"])
        self.assertEqual([p["id"] for p in self.c.get("/cuenta/me").json["perfiles"]], [bruno])
        selector = self.c.get("/cuenta/seleccionar-perfil").get_data(as_text=True)
        self.assertNotIn(ana, selector)
        r = self.c.post("/cuenta/perfil", json={"perfil_id": ana}, headers={"X-Tortu-CSRF": self._csrf()})
        self.assertEqual(r.status_code, 403)
        # El progreso sigue en disco y aparece como archivado en la configuración.
        self.assertEqual(store.cargar(ana).data["xp_total"], 40)
        self.assertIn("Perfiles archivados", self.c.get("/cuenta/configuracion").get_data(as_text=True))

        self.assertEqual(self._form(f"/cuenta/perfiles/{ana}/restaurar").status_code, 302)
        self.assertEqual(self.c.post("/cuenta/perfil", json={"perfil_id": ana},
                                     headers={"X-Tortu-CSRF": self._csrf()}).status_code, 200)
        self.assertEqual(self.c.get("/api/estado", headers={"X-Tortu-Token": "t"}).json["xp"], 40)

    def test_archivar_libera_un_lugar_y_restaurar_respeta_el_limite(self):
        self._cuenta("h@example.com")
        ids = [self._perfil(f"Perfil {i}") for i in range(MAX_CHILD_PROFILES)]
        self._form(f"/cuenta/perfiles/{ids[0]}/archivar")
        self._perfil("Nuevo")
        r = self._form(f"/cuenta/perfiles/{ids[0]}/restaurar")
        self.assertEqual(r.status_code, 400)
        self.assertIn("como máximo", r.get_data(as_text=True))

    def test_nadie_gestiona_perfiles_de_otra_familia_ni_sin_csrf(self):
        self._cuenta("i@example.com")
        ana = self._perfil("Ana")
        otra, _ = self._cuenta("j@example.com", self.app.test_client())
        for accion in ("renombrar", "archivar", "restaurar"):
            with self.subTest(accion=accion):
                ajeno = self._form(f"/cuenta/perfiles/{ana}/{accion}", otra, nombre="Robado")
                self.assertEqual(ajeno.status_code, 400)
                sin_csrf = self.c.post(f"/cuenta/perfiles/{ana}/{accion}", data={"nombre": "X"})
                self.assertEqual(sin_csrf.status_code, 403)
                anonimo = self.app.test_client().post(f"/cuenta/perfiles/{ana}/{accion}", data={"nombre": "X"})
                self.assertEqual(anonimo.status_code, 401)
        self.assertEqual(self.c.get("/cuenta/me").json["perfiles"], [{"id": ana, "nombre": "Ana"}])


class TestPassword(Base):
    def test_cambio_exige_la_actual_y_cierra_las_demas_sesiones(self):
        _, cuenta_id = self._cuenta("k@example.com")
        otro_dispositivo = self.app.test_client()
        otro_dispositivo.post("/cuenta/login", data={"email": "k@example.com", "password": CLAVE})
        self.assertEqual(otro_dispositivo.get("/cuenta/me").status_code, 200)
        nueva = "otra-clave-larga-456"

        casos = (({"actual": "no-es-la-clave!", "nueva": nueva, "nueva2": nueva}, "actual no es correcta"),
                 ({"actual": CLAVE, "nueva": "corta", "nueva2": "corta"}, "12 caracteres"),
                 ({"actual": CLAVE, "nueva": nueva, "nueva2": nueva + "x"}, "no coinciden"))
        for datos, mensaje in casos:
            with self.subTest(mensaje=mensaje):
                r = self._form("/cuenta/password", **datos)
                self.assertEqual(r.status_code, 400)
                self.assertIn(mensaje, r.get_data(as_text=True))
        self.assertEqual(otro_dispositivo.get("/cuenta/me").status_code, 200)       # los fallos no cierran nada

        r = self._form("/cuenta/password", actual=CLAVE, nueva=nueva, nueva2=nueva)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/cuenta/me").status_code, 200)                 # esta sesión sigue
        self.assertEqual(otro_dispositivo.get("/cuenta/me").status_code, 401)       # las otras no
        limpio = self.app.test_client()
        self.assertEqual(limpio.post("/cuenta/login", data={"email": "k@example.com", "password": CLAVE}).status_code, 401)
        self.assertEqual(limpio.post("/cuenta/login", data={"email": "k@example.com", "password": nueva}).status_code, 302)

    def test_el_cambio_invalida_enlaces_de_recuperacion_pendientes(self):
        correos = []
        self.app.config["ACCOUNT_EMAIL_SENDER"] = lambda **payload: correos.append(payload)
        self._cuenta("l@example.com")
        self.c.post("/cuenta/recuperar", data={"email": "l@example.com"})
        token = [m for m in correos if m["tipo"] == "recovery"][-1]["token"]
        nueva = "otra-clave-larga-456"
        self._form("/cuenta/password", actual=CLAVE, nueva=nueva, nueva2=nueva)
        r = self.c.post("/cuenta/restablecer-password", json={"token": token, "password": "tercera-clave-larga-789"})
        self.assertEqual(r.status_code, 400)

    def test_sin_csrf_o_sin_sesion_no_se_cambia(self):
        self._cuenta("m@example.com")
        self.assertEqual(self.c.post("/cuenta/password", data={"actual": CLAVE, "nueva": "otra-clave-larga-456"}).status_code, 403)
        self.assertEqual(self.app.test_client().post("/cuenta/password", data={}).status_code, 401)


class TestExportacion(Base):
    def test_el_adulto_descarga_todo_lo_suyo_y_nada_secreto_ni_ajeno(self):
        _, cuenta_id = self._cuenta("n@example.com")
        ana, bruno = self._perfil("Ana"), self._perfil("Bruno")
        store = ProgresoChildProfile(self.tmp / "progreso_perfiles")
        store.guardar(nuevo_snapshot(ana, {"xp_total": 40, "proyectos": {"a1": {"nombre": "Mi dibujo"}}}))
        self._form(f"/cuenta/perfiles/{bruno}/archivar")
        otra, _ = self._cuenta("o@example.com", self.app.test_client())
        ajeno = self._perfil("Zoe", otra)
        store.guardar(nuevo_snapshot(ajeno, {"xp_total": 999}))

        r = self.c.get("/cuenta/datos/exportar")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        d = r.json
        self.assertEqual(d["cuenta"]["correo"], "n@example.com")
        self.assertEqual({p["nombre"]: p["en_uso"] for p in d["perfiles"]}, {"Ana": True, "Bruno": False})
        de_ana = next(p for p in d["perfiles"] if p["nombre"] == "Ana")
        self.assertEqual(de_ana["progreso"]["datos"]["xp_total"], 40)
        self.assertEqual(de_ana["progreso"]["datos"]["proyectos"]["a1"]["nombre"], "Mi dibujo")
        self.assertIsNone(next(p for p in d["perfiles"] if p["nombre"] == "Bruno")["progreso"])
        self.assertEqual(d["consentimientos"][0]["finalidad"], "responsable_adulto")
        self.assertEqual(len(d["sesiones_abiertas"]), 1)

        texto = json.dumps(d)
        for secreto in ("scrypt", "password", "hash", self.c.get_cookie("tortu_session").value, self._csrf(),
                        "o@example.com", "Zoe", ajeno, "999"):
            self.assertNotIn(secreto, texto)

    def test_sin_sesion_no_hay_exportacion(self):
        self.assertEqual(self.c.get("/cuenta/datos/exportar").status_code, 401)

    def test_un_progreso_danado_no_impide_descargar_el_resto(self):
        self._cuenta("p@example.com")
        ana, bruno = self._perfil("Ana"), self._perfil("Bruno")
        store = ProgresoChildProfile(self.tmp / "progreso_perfiles")
        store.guardar(nuevo_snapshot(ana, {"xp_total": 40}))
        store.guardar(nuevo_snapshot(bruno, {"xp_total": 5}))
        (self.tmp / "progreso_perfiles" / f"progreso_{bruno}.json").write_text("{roto", encoding="utf-8")
        d = self.c.get("/cuenta/datos/exportar").json
        self.assertEqual(next(p for p in d["perfiles"] if p["nombre"] == "Ana")["progreso"]["datos"]["xp_total"], 40)
        self.assertIn("error", next(p for p in d["perfiles"] if p["nombre"] == "Bruno")["progreso"])
        # Exportar es solo lectura: no aparta ni repara archivos.
        self.assertFalse(list((self.tmp / "progreso_perfiles").glob("*.corrupto-*")))


class TestPaginaDeConfiguracion(Base):
    def test_muestra_todo_y_sin_sesion_vuelve_despues_de_ingresar(self):
        r = self.c.get("/cuenta/configuracion")
        self.assertEqual(r.status_code, 302)
        self.assertIn("next=", r.headers["Location"])
        self._cuenta("q@example.com")
        self._perfil("Ana")
        html = self.c.get("/cuenta/configuracion").get_data(as_text=True)
        for texto in ("q@example.com", 'value="Ana"', "Guardar nombre", "Archivar", "Cambiar contraseña",
                      "Descargar mis datos", "Soy la persona adulta responsable"):
            self.assertIn(texto, html)
        self.assertNotIn("<script", html)


if __name__ == "__main__":
    unittest.main()
