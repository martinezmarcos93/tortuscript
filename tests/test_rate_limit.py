"""Pruebas del limitador de intentos para endpoints sensibles."""
import unittest
from unittest.mock import patch

from tortuscript.rate_limit import RateLimiter


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


if __name__ == "__main__":
    unittest.main()
