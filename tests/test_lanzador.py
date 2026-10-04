"""El lanzador: puerto libre, mensajes claros y un servidor que de verdad arranca."""
import contextlib
import io
import socket
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import iniciar_web

try:
    import flask  # noqa: F401
    HAY_FLASK = True
except ImportError:
    HAY_FLASK = False


class TestPuerto(unittest.TestCase):
    def test_salta_los_puertos_ocupados(self):
        with socket.socket() as ocupado:
            ocupado.bind(("127.0.0.1", 0))
            ocupado.listen()
            puerto = ocupado.getsockname()[1]
            elegido = iniciar_web.puerto_libre(puerto, 5)
            self.assertNotEqual(elegido, puerto)
            self.assertGreater(elegido, puerto)

    def test_si_no_hay_ninguno_libre_lo_dice(self):
        with mock.patch.object(socket.socket, "connect_ex", return_value=0):
            with self.assertRaises(RuntimeError) as ctx:
                iniciar_web.puerto_libre(6000, 3)
        self.assertIn("puerto libre", str(ctx.exception))


class TestArgumentos(unittest.TestCase):
    def test_por_defecto_abre_el_navegador(self):
        a = iniciar_web.leer_argumentos([])
        self.assertFalse(a.sin_navegador)
        self.assertIsNone(a.puerto)

    def test_opciones(self):
        a = iniciar_web.leer_argumentos(["--sin-navegador", "--puerto", "8123"])
        self.assertTrue(a.sin_navegador)
        self.assertEqual(a.puerto, 8123)


class TestEntorno(unittest.TestCase):
    def test_entorno_correcto(self):
        self.assertIsNone(iniciar_web.verificar_entorno() if HAY_FLASK else None)

    def test_python_viejo_se_avisa_en_español(self):
        with mock.patch.object(sys, "version_info", (3, 7, 0)):
            self.assertIn("necesita Python 3.9", iniciar_web.verificar_entorno())

    def test_sin_flask_dice_como_instalarlo(self):
        with mock.patch.dict(sys.modules, {"flask": None}):
            mensaje = iniciar_web.verificar_entorno()
        self.assertIn("Falta Flask", mensaje)
        self.assertIn("pip install -r requirements.txt", mensaje)

    def test_main_con_entorno_roto_devuelve_1_sin_arrancar_nada(self):
        with mock.patch.object(iniciar_web, "verificar_entorno", return_value="falta algo"), \
                mock.patch.object(iniciar_web, "crear_servidor") as crear:
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                self.assertEqual(iniciar_web.main(["--sin-navegador"]), 1)
            self.assertIn("falta algo", salida.getvalue())
            crear.assert_not_called()


class TestEnv(unittest.TestCase):
    def test_lee_claves_sin_pisar_el_entorno_ni_fallar_si_falta(self):
        with tempfile.TemporaryDirectory() as d:
            archivo = Path(d) / ".env"
            self.assertEqual(iniciar_web.cargar_env(archivo), [])
            archivo.write_text(
                "# comentario\n\nTORTU_PRUEBA_A=uno\nTORTU_PRUEBA_B = \"dos tres\"\nTORTU_PRUEBA_C=\nsin_igual\n",
                encoding="utf-8")
            with mock.patch.dict("os.environ", {"TORTU_PRUEBA_A": "ya-estaba"}, clear=False):
                import os
                agregadas = iniciar_web.cargar_env(archivo)
                self.assertEqual(agregadas, ["TORTU_PRUEBA_B", "TORTU_PRUEBA_C"])
                self.assertEqual(os.environ["TORTU_PRUEBA_A"], "ya-estaba")
                self.assertEqual(os.environ["TORTU_PRUEBA_B"], "dos tres")
                self.assertEqual(os.environ["TORTU_PRUEBA_C"], "")


@unittest.skipUnless(HAY_FLASK, "Flask no instalado")
class TestAplicacion(unittest.TestCase):
    def test_cuentas_y_progreso_viven_en_la_carpeta_de_datos(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {}, clear=False) as entorno:
            entorno.pop("TORTU_EMAIL_MODO", None)
            app = iniciar_web.crear_aplicacion(Path(d), "http://127.0.0.1:5057/")
            self.assertEqual(app.config["ACCOUNT_DB"], Path(d) / "instance" / "cuentas.sqlite3")
            self.assertEqual(app.config["PROGRESS_DIR"], Path(d) / "instance" / "progreso_perfiles")
            # Sin configuración explícita el correo queda deshabilitado (las rutas fallan cerradas).
            self.assertIsNone(app.config["ACCOUNT_EMAIL_SENDER"])

    def test_desde_el_codigo_fuente_coincide_con_la_carpeta_instance_de_flask(self):
        from tortuscript import rutas
        from web.app import create_app
        self.assertEqual(rutas.carpeta_de_cuentas(rutas.RAIZ), Path(create_app(token="t").instance_path))

    def test_modo_consola_arma_enlaces_con_la_url_local(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {"TORTU_EMAIL_MODO": "consola"}):
            app = iniciar_web.crear_aplicacion(Path(d), "http://127.0.0.1:5099/")
            self.assertEqual(app.config["ACCOUNT_EMAIL_SENDER"].url_base, "http://127.0.0.1:5099")

    def test_correo_mal_configurado_impide_arrancar_con_mensaje_claro(self):
        salida = io.StringIO()
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict("os.environ", {"TORTU_EMAIL_MODO": "smtp", "TORTUSCRIPT_DATOS": d}), \
                mock.patch.object(iniciar_web, "configurar_logs"), \
                mock.patch.object(iniciar_web, "crear_servidor") as crear, \
                contextlib.redirect_stdout(salida):
            self.assertEqual(iniciar_web.main(["--sin-navegador", "--puerto", "5098"]), 1)
            crear.assert_not_called()
        self.assertIn("No pude arrancar", salida.getvalue())


class TestLogs(unittest.TestCase):
    def test_crea_la_carpeta_y_el_archivo(self):
        import logging
        raiz = logging.getLogger("tortuscript")
        antes = list(raiz.handlers)
        with tempfile.TemporaryDirectory() as tmp:
            iniciar_web.configurar_logs(Path(tmp) / "logs")
            nuevos = [h for h in raiz.handlers if h not in antes]
            try:
                self.assertTrue((Path(tmp) / "logs" / "tortuscript.log").exists())
            finally:
                for h in nuevos:
                    h.close()
                    raiz.removeHandler(h)

    def test_sin_permisos_no_rompe(self):
        with mock.patch.object(Path, "mkdir", side_effect=OSError("solo lectura")):
            iniciar_web.configurar_logs(Path("/no/se/puede"))                       # no levanta


@unittest.skipUnless(HAY_FLASK, "Flask no instalado")
class TestServidorReal(unittest.TestCase):
    def test_arranca_responde_y_se_apaga(self):
        puerto = iniciar_web.puerto_libre(5300, 50)
        servidor = iniciar_web.crear_servidor(puerto)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/static/css/tortu.css", timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn("--violeta", r.read().decode("utf-8"))
        finally:
            servidor.shutdown()
            servidor.server_close()
            hilo.join(timeout=5)
        self.assertFalse(hilo.is_alive())

    def test_solo_escucha_en_la_compu_local(self):
        puerto = iniciar_web.puerto_libre(5400, 50)
        servidor = iniciar_web.crear_servidor(puerto)
        try:
            self.assertEqual(servidor.server_address[0], "127.0.0.1")
        finally:
            servidor.server_close()


if __name__ == "__main__":
    unittest.main()
