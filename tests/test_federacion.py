"""Contratos con Croco-Script (ADR-037): token de autorización, vectores publicados y transición por HTTP."""
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tortuscript import federacion
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from tortuscript.federacion import FederacionError
from web.app import create_app

RAIZ = Path(__file__).resolve().parent.parent
VECTORES = json.loads((RAIZ / "docs" / "contratos" / "authorization-v1.vectores.json").read_text(encoding="utf-8"))
CLAVE = "x" * 40
T = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


class TestToken(unittest.TestCase):
    def emitir(self, **cambios):
        datos = dict(clave=CLAVE, kid="k1", destino="croco-script", cuenta_id="acc_1", perfil_id="child_1", ahora=T)
        datos.update(cambios)
        return federacion.emitir_autorizacion(**datos)

    def test_ida_y_vuelta(self):
        datos = federacion.validar_autorizacion(self.emitir(), {"k1": CLAVE}, "croco-script", ahora=T + timedelta(seconds=30))
        self.assertEqual((datos["sub"], datos["acc"], datos["aud"], datos["iss"]), ("child_1", "acc_1", "croco-script", "tortuscript"))
        self.assertEqual(datos["exp"] - datos["iat"], 60)

    def test_solo_lleva_identificadores_opacos(self):
        datos = federacion.validar_autorizacion(self.emitir(), {"k1": CLAVE}, "croco-script", ahora=T)
        self.assertEqual(set(datos), {"v", "iss", "aud", "sub", "acc", "ent", "iat", "exp", "jti"})

    def test_vence_al_minuto_y_es_de_un_solo_uso(self):
        token = self.emitir()
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=T + timedelta(seconds=61))
        usados = set()

        def ya_usado(jti):
            visto = jti in usados
            usados.add(jti)
            return visto

        federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=T, ya_usado=ya_usado)
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=T, ya_usado=ya_usado)

    def test_cada_token_tiene_un_jti_distinto(self):
        jtis = {federacion.validar_autorizacion(self.emitir(), {"k1": CLAVE}, "croco-script", ahora=T)["jti"] for _ in range(20)}
        self.assertEqual(len(jtis), 20)

    def test_rotacion_de_claves(self):
        viejo = self.emitir()
        nuevo = self.emitir(clave="y" * 40, kid="k2")
        ambas = {"k1": CLAVE, "k2": "y" * 40}
        federacion.validar_autorizacion(viejo, ambas, "croco-script", ahora=T)
        federacion.validar_autorizacion(nuevo, ambas, "croco-script", ahora=T)
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(viejo, {"k2": "y" * 40}, "croco-script", ahora=T)   # la vieja ya se retiró

    def test_no_se_emite_con_clave_debil_ni_para_destinos_desconocidos(self):
        with self.assertRaises(FederacionError):
            self.emitir(clave="corta")
        with self.assertRaises(FederacionError):
            self.emitir(destino="otro-producto")

    def test_basura_no_provoca_excepciones_inesperadas(self):
        for token in (None, 7, "", "a.b", "a.b.c", "....", "é.é.é", "e30.e30.x", "W10.W10.x"):
            with self.subTest(token=token), self.assertRaises(FederacionError):
                federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=T)


class TestVectoresPublicados(unittest.TestCase):
    """Los vectores de docs/contratos/ son el contrato que implementa Croco-Script: no pueden desviarse del código."""

    def setUp(self):
        self.claves = {VECTORES["kid"]: VECTORES["clave"]}
        self.ahora = datetime.fromisoformat(VECTORES["momento_de_validacion"])

    def test_el_vector_valido_se_acepta_y_coincide_con_lo_documentado(self):
        datos = federacion.validar_autorizacion(VECTORES["valido"]["token"], self.claves, VECTORES["destino"], ahora=self.ahora)
        self.assertEqual(datos, VECTORES["valido"]["datos"])

    def test_el_emisor_actual_genera_exactamente_el_vector_valido(self):
        d = VECTORES["valido"]["datos"]
        token = federacion.emitir_autorizacion(
            VECTORES["clave"], VECTORES["kid"], d["aud"], d["acc"], d["sub"],
            ahora=datetime.fromtimestamp(d["iat"], timezone.utc), jti=d["jti"])
        self.assertEqual(token, VECTORES["valido"]["token"])

    def test_todos_los_invalidos_se_rechazan(self):
        self.assertGreaterEqual(len(VECTORES["invalidos"]), 15)
        for vector in VECTORES["invalidos"]:
            with self.subTest(motivo=vector["motivo"]), self.assertRaises(FederacionError):
                federacion.validar_autorizacion(vector["token"], self.claves, VECTORES["destino"], ahora=self.ahora)


class TestDocumentos(unittest.TestCase):
    def test_identidad_y_acceso_no_llevan_datos_personales(self):
        self.assertEqual(federacion.identidad_v1("acc_1", "child_1"),
                         {"contrato": "Identity.v1", "cuenta": "acc_1", "perfil": "child_1"})
        self.assertEqual(federacion.acceso_v1("croco-script", 1, "2026-11-01T12:00:00+00:00")["activo"], True)

    def test_progreso_normaliza_y_descarta_campos_ajenos(self):
        p = federacion.progreso_v1("child_1", "croco-script", "2026.1", [{
            "curso": "python-datos", "lecciones_completadas": ["b", "a"], "ejercicios_completados": "3",
            "evaluaciones": [{"id": 1, "aprobada": 1, "nota_interna": "x"}], "nombre_del_chico": "Ana"}], "2026-11-01T12:00:00+00:00")
        self.assertEqual(p["cursos"], [{"curso": "python-datos", "lecciones_completadas": ["a", "b"],
                                        "ejercicios_completados": 3, "proyectos": 0,
                                        "evaluaciones": [{"id": "1", "aprobada": True}]}])
        self.assertNotIn("Ana", json.dumps(p))


class TestTransicionHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app(token="t")
        self.app.config.update(
            TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3", PROGRESS_DIR=self.tmp / "progreso_perfiles",
            ACCOUNT_EMAIL_SENDER=lambda **payload: None,
            FEDERACION={"croco-script": {"url": "https://croco.example/entrar", "clave": CLAVE, "kid": "k1"}})
        self.c = self.app.test_client()
        self.email = "croco@example.com"
        self.c.post("/cuenta/registrar", data={"email": self.email, "password": "una-clave-larga-123", "responsable": "si"})
        self.cuenta_id = "acc_" + hashlib.sha256(self.email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(self.cuenta_id)
        self.c.post("/cuenta/login", data={"email": self.email, "password": "una-clave-larga-123"})
        csrf = self.c.get_cookie("tortu_csrf").value
        self.perfil = self.c.post("/cuenta/perfiles", json={"nombre": "Ana"}, headers={"X-Tortu-CSRF": csrf}).json["perfil"]["id"]
        self.c.post("/cuenta/perfil", json={"perfil_id": self.perfil}, headers={"X-Tortu-CSRF": csrf})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_sin_acceso_no_hay_token(self):
        r = self.c.get("/cuenta/ir/croco-script")
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("Location", r.headers)
        self.assertNotIn("autorizacion=", r.get_data(as_text=True))

    def test_con_acceso_redirige_con_un_token_valido_y_sin_datos_personales(self):
        CuentaRepository(self.tmp / "cuentas.sqlite3").establecer_entitlement(self.cuenta_id, "croco-script", True, "prueba")
        r = self.c.get("/cuenta/ir/croco-script")
        self.assertEqual(r.status_code, 302)
        destino = urlsplit(r.headers["Location"])
        self.assertEqual((destino.scheme, destino.netloc, destino.path), ("https", "croco.example", "/entrar"))
        self.assertEqual(r.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        token = parse_qs(destino.query)["autorizacion"][0]
        datos = federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script")
        self.assertEqual((datos["sub"], datos["acc"]), (self.perfil, self.cuenta_id))
        self.assertNotIn(self.email, r.headers["Location"])
        self.assertNotIn("Ana", r.headers["Location"])
        self.assertNotIn(CLAVE, r.headers["Location"])

    def test_el_acceso_a_premium_no_abre_croco(self):
        CuentaRepository(self.tmp / "cuentas.sqlite3").establecer_entitlement(self.cuenta_id, "tortuscript-premium", True, "prueba")
        self.assertEqual(self.c.get("/cuenta/ir/croco-script").status_code, 403)

    def test_sin_sesion_o_sin_perfil_va_a_ingresar_y_vuelve(self):
        r = self.app.test_client().get("/cuenta/ir/croco-script")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/cuenta/ingresar", r.headers["Location"])
        self.assertIn("croco-script", r.headers["Location"])

    def test_producto_no_configurado_no_existe(self):
        self.assertEqual(self.c.get("/cuenta/ir/otro").status_code, 404)
        self.assertEqual(create_app(token="t").config["FEDERACION"], {})

    def test_configuracion_con_clave_debil_no_emite(self):
        self.app.config["FEDERACION"]["croco-script"]["clave"] = "corta"
        CuentaRepository(self.tmp / "cuentas.sqlite3").establecer_entitlement(self.cuenta_id, "croco-script", True, "prueba")
        with self.assertLogs("web.cuenta_routes", "ERROR"):
            self.assertEqual(self.c.get("/cuenta/ir/croco-script").status_code, 503)


if __name__ == "__main__":
    unittest.main()
