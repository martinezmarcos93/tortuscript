"""Política de XP de un ejercicio (informe de integración §5-bis, T3; decisión de Marcos 18/10/2026):
se rechazan las combinaciones incoherentes. Más estrellas con menos XP que lo ya guardado no es una mejora
válida: no se registra nada (ni XP almacenado ni total), y se avisa en el log."""
import copy
import unittest

from tortuscript import progreso


def nuevo():
    return copy.deepcopy(progreso.PROGRESO_INICIAL)


class TestXpDeEjercicio(unittest.TestCase):
    def test_mejora_coherente_se_registra_y_suma_la_diferencia(self):
        p = nuevo()
        self.assertTrue(progreso.registrar_ejercicio(p, 0, 2, 20))
        self.assertTrue(progreso.registrar_ejercicio(p, 0, 3, 30))
        self.assertEqual(p["ejercicios"]["0"], {"estrellas": 3, "xp": 30, "completado": True})
        self.assertEqual(p["xp_total"], 30)

    def test_mas_estrellas_con_menos_xp_se_rechaza_sin_tocar_nada(self):
        p = nuevo()
        progreso.registrar_ejercicio(p, 0, 2, 20)
        antes = copy.deepcopy(p)
        with self.assertLogs("tortuscript.progreso", level="WARNING"):
            self.assertFalse(progreso.registrar_ejercicio(p, 0, 3, 10))
        self.assertEqual(p["ejercicios"], antes["ejercicios"])
        self.assertEqual(p["xp_total"], antes["xp_total"])
        self.assertEqual(p["ejercicios"]["0"]["xp"], 20)

    def test_mismo_xp_con_mas_estrellas_es_coherente(self):
        p = nuevo()
        progreso.registrar_ejercicio(p, 0, 2, 20)
        self.assertTrue(progreso.registrar_ejercicio(p, 0, 3, 20))
        self.assertEqual(p["ejercicios"]["0"]["estrellas"], 3)
        self.assertEqual(p["xp_total"], 20)

    def test_menos_o_igual_estrellas_no_cambia_nada(self):
        for estrellas in (2, 1):
            with self.subTest(estrellas=estrellas):
                p = nuevo()
                progreso.registrar_ejercicio(p, 0, 2, 20)
                self.assertFalse(progreso.registrar_ejercicio(p, 0, estrellas, 99))
                self.assertEqual(p["ejercicios"]["0"], {"estrellas": 2, "xp": 20, "completado": True})
                self.assertEqual(p["xp_total"], 20)

    def test_el_primer_registro_no_tiene_xp_previo_que_contradecir(self):
        p = nuevo()
        self.assertTrue(progreso.registrar_ejercicio(p, 3, 1, 0))
        self.assertEqual(p["ejercicios"]["3"]["xp"], 0)

    def test_xp_negativo_se_rechaza(self):
        p = nuevo()
        with self.assertLogs("tortuscript.progreso", level="WARNING"):
            self.assertFalse(progreso.registrar_ejercicio(p, 0, 1, -5))
        self.assertEqual(p["ejercicios"], {})
        self.assertEqual(p["xp_total"], 0)

    def test_rechazo_no_cuenta_como_actividad_del_dia(self):
        p = nuevo()
        progreso.registrar_ejercicio(p, 0, 2, 20)
        racha, sesion = p["racha"], list(p["sesion_hoy"])
        with self.assertLogs("tortuscript.progreso", level="WARNING"):
            progreso.registrar_ejercicio(p, 0, 3, 10)
        self.assertEqual((p["racha"], p["sesion_hoy"]), (racha, sesion))

    def test_una_estrella_ya_cuenta_como_actividad_del_dia(self):
        p = nuevo()
        progreso.registrar_ejercicio(p, 4, 1, 10)
        self.assertEqual(p["sesion_hoy"], [4])
        self.assertEqual(p["racha"], 1)

    def test_cero_estrellas_no_cuenta_como_actividad(self):
        p = nuevo()
        progreso.registrar_ejercicio(p, 4, 0, 0)
        self.assertEqual(p["sesion_hoy"], [])
        self.assertEqual(p["racha"], 0)


if __name__ == "__main__":
    unittest.main()
