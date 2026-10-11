"""Los conflictos de propiedad en Supresion.v1 no se cuentan como borrados confirmados."""
import json
import tempfile
import unittest
from pathlib import Path

from tortuscript.federacion_operaciones import OperacionesCroco

CONFIG = {"url": "https://croco.example/entrar", "clave": "x" * 40, "kid": "k1"}


class Respuesta:
    status = 409

    def read(self, limite=-1):
        return b'{"error":"perfil_de_otra_cuenta"}'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestConflictoSupresion(unittest.TestCase):
    def test_409_se_conserva_y_no_se_reporta_como_confirmado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ops = OperacionesCroco(CONFIG, Path(carpeta), abrir=lambda *a, **k: Respuesta())
            self.assertFalse(ops.solicitar("suprimir_perfil", "acc_1", "child_1"))
            cola = ops.pendientes()
            self.assertEqual(len(cola), 1)
            self.assertEqual(cola[0]["estado"], "conflicto_409")
            self.assertEqual(cola[0]["ultimo_error"], "perfil_de_otra_cuenta")
            self.assertEqual(ops.reintentar_pendientes(), 0)
            self.assertEqual(ops.pendientes(), cola)

    def test_409_durante_reintento_pasa_a_revision_manual(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ops = OperacionesCroco(CONFIG, Path(carpeta), abrir=lambda *a, **k: Respuesta())
            archivo = Path(carpeta) / "operaciones_pendientes.json"
            archivo.write_text(json.dumps([{
                "accion": "suprimir_perfil", "cuenta": "acc_1", "perfil": "child_1",
                "intentos": 1, "creada": "2026-10-11T00:00:00+00:00"
            }]), encoding="utf-8")
            self.assertEqual(ops.reintentar_pendientes(), 0)
            cola = ops.pendientes()
            self.assertEqual(cola[0]["estado"], "conflicto_409")
            self.assertEqual(cola[0]["intentos"], 1)


if __name__ == "__main__":
    unittest.main()
