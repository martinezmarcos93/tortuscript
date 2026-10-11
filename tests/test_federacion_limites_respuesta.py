"""Límites defensivos del transporte de operaciones federadas."""

import json
import tempfile
import unittest
from pathlib import Path

from tortuscript.federacion_operaciones import (
    RESPUESTA_EXPORTACION_MAXIMA,
    RESPUESTA_MAXIMA,
    OperacionesCroco,
)


class Respuesta:
    def __init__(self, cuerpo):
        self.status = 200
        self.cuerpo = cuerpo

    def read(self, limite=-1):
        return self.cuerpo[:limite] if limite >= 0 else self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestLimitesRespuestaFederada(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def operaciones(self, cuerpo):
        return OperacionesCroco(
            {"url": "https://croco.example/entrar", "clave": "x" * 40, "kid": "k1"},
            Path(self.tmp.name),
            abrir=lambda *args, **kwargs: Respuesta(cuerpo),
        )

    def test_exportacion_superior_al_limite_operativo_se_acepta(self):
        datos = {"contrato": "Supresion.v1", "accion": "exportar_perfil",
                 "datos": {"historial": "x" * (RESPUESTA_MAXIMA + 1024)}}
        cuerpo = json.dumps(datos).encode("utf-8")
        estado, recibido = self.operaciones(cuerpo)._enviar("exportar_perfil", "acc_1", "p1")
        self.assertEqual(estado, 200)
        self.assertEqual(recibido, datos)

    def test_exportacion_que_supera_el_limite_defensivo_se_rechaza(self):
        cuerpo = b" " * (RESPUESTA_EXPORTACION_MAXIMA + 1)
        with self.assertRaisesRegex(OSError, "demasiado grande"):
            self.operaciones(cuerpo)._enviar("exportar_perfil", "acc_1", "p1")

    def test_respuestas_operativas_conservan_el_limite_pequeno(self):
        cuerpo = b" " * (RESPUESTA_MAXIMA + 1)
        with self.assertRaisesRegex(OSError, "demasiado grande"):
            self.operaciones(cuerpo)._enviar("suprimir_perfil", "acc_1", "p1")


if __name__ == "__main__":
    unittest.main()
