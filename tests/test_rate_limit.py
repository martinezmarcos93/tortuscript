"""Pruebas del limitador de intentos para endpoints sensibles."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tortuscript.rate_limit import RateLimiter, SQLiteRateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_aplica_limite_por_clave_y_calcula_reintento(self):
        limiter = RateLimiter()
        with patch("tortuscript.rate_limit.monotonic", side_effect=[1.0, 2.0, 3.0]):
            self.assertEqual(limiter.allow("login:ip:correo", 2, 10), (True, 0))
            self.assertEqual(limiter.allow("login:ip:correo", 2, 10), (True, 0))
            permitido, retry_after = limiter.allow("login:ip:correo", 2, 10)
        self.assertFalse(permitido)
        self.assertEqual(retry_after, 8)

    def test_limpia_claves_expiradas_generadas_por_identificadores_unicos(self):
        limiter = RateLimiter()
        tiempos = [0.0] * 127 + [10.0]
        with patch("tortuscript.rate_limit.monotonic", side_effect=tiempos):
            for i in range(127):
                self.assertTrue(limiter.allow(f"login:ip:email-{i}", 10, 5)[0])
            self.assertTrue(limiter.allow("trigger", 10, 5)[0])
        self.assertEqual(set(limiter._events), {"trigger"})
        self.assertEqual(set(limiter._windows), {"trigger"})

    def test_sqlite_comparte_el_limite_entre_instancias(self):
        with tempfile.TemporaryDirectory() as temporal:
            db = Path(temporal) / "rate-limit.sqlite3"
            primero = SQLiteRateLimiter(db)
            segundo = SQLiteRateLimiter(db)
            with patch("tortuscript.rate_limit.time", side_effect=[100.0, 101.0, 102.0]):
                self.assertEqual(primero.allow("login:ip:correo", 2, 10), (True, 0))
                self.assertEqual(segundo.allow("login:ip:correo", 2, 10), (True, 0))
                permitido, retry_after = primero.allow("login:ip:correo", 2, 10)
            self.assertFalse(permitido)
            self.assertEqual(retry_after, 8)

    def test_sqlite_no_guarda_la_clave_original_en_claro(self):
        with tempfile.TemporaryDirectory() as temporal:
            db = Path(temporal) / "rate-limit.sqlite3"
            limiter = SQLiteRateLimiter(db)
            limiter.allow("login:192.0.2.4:persona@example.com", 2, 60)
            import sqlite3
            with sqlite3.connect(db) as con:
                bucket = con.execute("SELECT bucket FROM rate_limit_events").fetchone()[0]
            self.assertNotIn("persona@example.com", bucket)
            self.assertRegex(bucket, r"^[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
