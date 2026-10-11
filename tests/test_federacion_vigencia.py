"""Regresiones de vigencia para tokens Authorization.v1."""
import base64
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timezone

from tortuscript import federacion
from tortuscript.federacion import FederacionError

CLAVE = "x" * 40
AHORA = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def token_firmado(cambios):
    cabecera = {"alg": "HS256", "typ": "JWT", "kid": "k1"}
    cuerpo = {
        "v": 1, "iss": "tortuscript", "aud": "croco-script",
        "sub": "child_1", "acc": "acc_1",
        "ent": {"producto": "croco-script", "activo": True},
        "iat": int(AHORA.timestamp()), "exp": int(AHORA.timestamp()) + 60,
        "jti": "jti-prueba",
    }
    cuerpo.update(cambios)

    def codificar(valor):
        return base64.urlsafe_b64encode(
            json.dumps(valor, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).rstrip(b"=").decode("ascii")

    mensaje = f"{codificar(cabecera)}.{codificar(cuerpo)}"
    firma = base64.urlsafe_b64encode(
        hmac.new(CLAVE.encode("utf-8"), mensaje.encode("ascii"), hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")
    return f"{mensaje}.{firma}"


class TestVigenciaEstricta(unittest.TestCase):
    def test_rechaza_expiracion_anterior_a_emision(self):
        iat = int(AHORA.timestamp())
        token = token_firmado({"iat": iat, "exp": iat - 1})
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=AHORA)

    def test_rechaza_version_booleana(self):
        token = token_firmado({"v": True})
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=AHORA)

    def test_rechaza_vigencia_cero(self):
        iat = int(AHORA.timestamp())
        token = token_firmado({"iat": iat, "exp": iat})
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(token, {"k1": CLAVE}, "croco-script", ahora=AHORA)


if __name__ == "__main__":
    unittest.main()
