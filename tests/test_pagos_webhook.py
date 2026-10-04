"""Webhook de pagos por HTTP: firma, idempotencia y efecto visible para la familia."""
import hashlib
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from tortuscript import pagos
from tortuscript.auth import AuthRepository
from web.app import create_app

SECRETO = "secreto-de-prueba"
CLAVE = "una-clave-larga-123"
PREMIUM = "tortuscript-premium"


class TestWebhook(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
                               PROGRESS_DIR=self.tmp / "progreso_perfiles",
                               ACCOUNT_EMAIL_SENDER=lambda **payload: None,
                               PAYMENT_WEBHOOK_SECRETS={"prueba": SECRETO})
        self.c = self.app.test_client()
        email = "paga@example.com"
        self.c.post("/cuenta/registrar", data={"email": email, "password": CLAVE, "responsable": "si"})
        self.cuenta_id = "acc_" + hashlib.sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(self.cuenta_id)
        self.c.post("/cuenta/login", data={"email": email, "password": CLAVE})
        csrf = self.c.get_cookie("tortu_csrf").value
        perfil = self.c.post("/cuenta/perfiles", json={"nombre": "Ana"}, headers={"X-Tortu-CSRF": csrf}).json["perfil"]["id"]
        self.c.post("/cuenta/perfil", json={"perfil_id": perfil}, headers={"X-Tortu-CSRF": csrf})
        self.proveedor = self.app.test_client()                    # el proveedor no tiene cookies de nadie
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cuerpo(self, tipo, **cambios):
        self.n += 1
        datos = {"id": f"evt_{self.n}", "tipo": tipo, "cuenta": self.cuenta_id, "producto": PREMIUM,
                 "suscripcion": "sub_1", "ocurrido": f"2026-11-01T12:00:{self.n:02d}Z",
                 "periodo_hasta": "2099-01-01T00:00:00Z"}
        datos.update(cambios)
        return json.dumps(datos).encode()

    def entregar(self, cuerpo, firma=None, proveedor="prueba"):
        firma = pagos.firmar(SECRETO, cuerpo, int(time.time())) if firma is None else firma
        return self.proveedor.post(f"/pagos/webhook/{proveedor}", data=cuerpo,
                                   headers={"X-Tortu-Firma": firma, "Content-Type": "application/json"})

    def premium(self):
        return self.c.get(f"/cuenta/acceso?producto={PREMIUM}").json["permitido"]

    def test_un_pago_firmado_da_acceso_y_se_ve_en_la_cuenta(self):
        self.assertFalse(self.premium())
        r = self.entregar(self.cuerpo("payment_succeeded"))
        self.assertEqual((r.status_code, r.json["estado"]), (200, "aplicado"))
        self.assertTrue(self.premium())
        html = self.c.get("/cuenta/configuracion").get_data(as_text=True)
        self.assertIn("TortuScript Premium", html)
        self.assertIn("activa", html)
        exportado = self.c.get("/cuenta/datos/exportar").json
        self.assertEqual(exportado["suscripciones"][0]["estado"], "active")
        self.assertNotIn("sub_1", json.dumps(exportado))            # la referencia del proveedor no sale

    def test_reenvio_del_mismo_evento_no_repite_efectos(self):
        pago = self.cuerpo("payment_succeeded")
        self.entregar(pago)
        self.entregar(self.cuerpo("refund"))
        self.assertFalse(self.premium())
        r = self.entregar(pago)
        self.assertEqual((r.status_code, r.json["estado"]), (200, "duplicado"))
        self.assertFalse(self.premium())

    def test_sin_firma_valida_no_pasa_nada(self):
        cuerpo = self.cuerpo("payment_succeeded")
        vieja = pagos.firmar(SECRETO, cuerpo, int(time.time()) - 3600)
        for firma in ("", "t=1,v1=00", pagos.firmar("otro-secreto", cuerpo, int(time.time())), vieja):
            with self.subTest(firma=firma[:12]):
                self.assertEqual(self.entregar(cuerpo, firma=firma).status_code, 400)
        alterado = cuerpo.replace(b"sub_1", b"sub_2")
        self.assertEqual(self.entregar(alterado, firma=pagos.firmar(SECRETO, cuerpo, int(time.time()))).status_code, 400)
        self.assertFalse(self.premium())

    def test_el_navegador_no_puede_darse_premium(self):
        # Ni con la sesión del adulto, ni con el token de la app, ni con CSRF: solo vale la firma del proveedor.
        cuerpo = self.cuerpo("payment_succeeded")
        r = self.c.post("/pagos/webhook/prueba", data=cuerpo, headers={
            "X-Tortu-Token": "t", "X-Tortu-CSRF": self.c.get_cookie("tortu_csrf").value,
            "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(self.premium())

    def test_proveedor_desconocido_o_sin_secreto_no_existe(self):
        cuerpo = self.cuerpo("payment_succeeded")
        self.assertEqual(self.entregar(cuerpo, proveedor="otro").status_code, 404)
        self.app.config["PAYMENT_WEBHOOK_SECRETS"] = {}
        self.assertEqual(self.entregar(cuerpo).status_code, 404)
        self.assertEqual(create_app(token="t").config["PAYMENT_WEBHOOK_SECRETS"], {})   # apagado por defecto

    def test_evento_firmado_pero_inconsistente_queda_en_revision(self):
        r = self.entregar(self.cuerpo("payment_succeeded", cuenta="acc_inexistente"))
        self.assertEqual((r.status_code, r.json["estado"]), (200, "revision"))
        self.assertFalse(self.premium())
        self.assertEqual(self.entregar(b"{no json").status_code, 400)
        self.assertEqual(self.entregar(b"x" * (pagos.MAX_CUERPO_WEBHOOK + 1)).status_code, 413)

    def test_cuenta_sin_suscripcion_no_muestra_la_seccion(self):
        self.assertNotIn("Suscripción</h2>", self.c.get("/cuenta/configuracion").get_data(as_text=True))

    def test_el_retorno_de_un_checkout_no_concede_nada(self):
        self.entregar(self.cuerpo("checkout_completed"))
        self.assertFalse(self.premium())
        self.assertIn("pago pendiente", self.c.get("/cuenta/configuracion").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
