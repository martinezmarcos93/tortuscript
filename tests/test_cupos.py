"""Tope de ejecuciones simultáneas y cola acotada (ADR-033, barrido 8)."""
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tortuscript import cupos, proceso


class TestCupos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_nunca_corren_mas_que_los_cupos(self):
        c = cupos.Cupos(2, self.tmp, espera=5)
        corriendo, maximo, guardia = [0], [0], threading.Lock()

        def trabajo():
            with c.tomar():
                with guardia:
                    corriendo[0] += 1
                    maximo[0] = max(maximo[0], corriendo[0])
                time.sleep(0.05)
                with guardia:
                    corriendo[0] -= 1

        hilos = [threading.Thread(target=trabajo) for _ in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(maximo[0], 2)

    def test_sin_cupo_a_tiempo_se_informa_ocupado(self):
        c = cupos.Cupos(1, self.tmp, espera=0.1)
        with c.tomar():
            inicio = time.monotonic()
            with self.assertRaises(cupos.Ocupado):
                with c.tomar():
                    self.fail("no debería entrar")
            self.assertLess(time.monotonic() - inicio, 2)
        with c.tomar():                                            # liberado: vuelve a haber cupo
            pass

    def test_la_cola_llena_rechaza_sin_esperar(self):
        c = cupos.Cupos(1, self.tmp, espera=5, cola=0)
        inicio = time.monotonic()
        with self.assertRaises(cupos.Ocupado):
            with c.tomar():
                pass
        self.assertLess(time.monotonic() - inicio, 1)

    @unittest.skipIf(cupos.fcntl is None, "sin fcntl el tope es por proceso")
    def test_el_tope_se_comparte_entre_procesos(self):
        # Dos instancias con la misma carpeta se comportan como dos procesos web de la misma máquina.
        uno, otro = cupos.Cupos(1, self.tmp, espera=0.1), cupos.Cupos(1, self.tmp, espera=0.1)
        with uno.tomar():
            with self.assertRaises(cupos.Ocupado):
                with otro.tomar():
                    self.fail("el otro proceso no debería conseguir cupo")
        with otro.tomar():
            pass

    def test_un_error_adentro_libera_el_cupo(self):
        c = cupos.Cupos(1, self.tmp, espera=0.1)
        with self.assertRaises(ValueError):
            with c.tomar():
                raise ValueError("se rompió el trabajo")
        with c.tomar():
            pass

    def test_cupos_desde_el_entorno(self):
        self.assertEqual(cupos.cupos_desde_entorno({"TORTU_EJECUCIONES_MAX": "3"}), 3)
        self.assertEqual(cupos.cupos_desde_entorno({"TORTU_EJECUCIONES_MAX": "0"}), cupos.CUPOS_MIN)
        self.assertEqual(cupos.cupos_desde_entorno({"TORTU_EJECUCIONES_MAX": "9999"}), cupos.CUPOS_MAX)
        self.assertTrue(2 <= cupos.cupos_desde_entorno({}) <= 8)
        with self.assertLogs(level="ERROR"):
            self.assertTrue(2 <= cupos.cupos_desde_entorno({"TORTU_EJECUCIONES_MAX": "muchos"}) <= 8)


class TestProcesoConCupos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_sin_cupo_el_chico_recibe_un_mensaje_claro_y_no_se_lanza_nada(self):
        lleno = cupos.Cupos(1, self.tmp, espera=0.05)
        with mock.patch.object(proceso, "_CUPOS", lleno), mock.patch("subprocess.run") as lanzar, lleno.tomar(), \
                self.assertLogs("tortuscript.proceso", level="WARNING"):
            r = proceso.correr({"op": "ejecutar", "fuente": 'mostrar "hola"', "entradas": []})
        self.assertTrue(r["error"])
        self.assertIn("muchos programas corriendo", r["mensaje"])
        self.assertNotIn("Para curiosos", r["mensaje"])
        lanzar.assert_not_called()

    def test_con_cupo_corre_normal(self):
        with mock.patch.object(proceso, "_CUPOS", cupos.Cupos(2, self.tmp)):
            r = proceso.correr({"op": "ejecutar", "fuente": 'mostrar "hola"', "entradas": []})
        self.assertFalse(r["error"])
        self.assertIn("hola", r["salida"])


if __name__ == "__main__":
    unittest.main()
