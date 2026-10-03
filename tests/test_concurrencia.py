"""Pedidos simultáneos: el progreso no se pisa (todo pedido espera su turno)."""
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tortuscript import persistencia_local, progreso

try:
    import flask  # noqa: F401
    HAY_FLASK = True
except ImportError:
    HAY_FLASK = False


@unittest.skipUnless(HAY_FLASK, "Flask no instalado")
class TestConcurrencia(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = (persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL)
        persistencia_local.DIRECTORIO = self._dir
        persistencia_local.PERFIL_ACTUAL = "default"
        from web.app import create_app
        self.app = create_app(token="t")
        self.app.config.update(
            TESTING=True,
            ACCOUNT_DB=self._dir / "cuentas.sqlite3",
            ACCOUNT_COOKIE_SECURE=False,
            PROGRESS_DIR=self._dir / "progreso_perfiles",
        )
        self.seed_client = self.app.test_client()
        from fixtures_cuenta import preparar_sesion_educativa
        preparar_sesion_educativa(
            self.app, self.seed_client, email="concurrencia@example.com", nombre="Ana", token="t"
        )
        self.session_cookie = self.seed_client.get_cookie("tortu_session").value
        self.h = {"X-Tortu-Token": "t"}

    def nuevo_cliente(self):
        cliente = self.app.test_client()
        cliente.set_cookie("tortu_session", self.session_cookie)
        return cliente

    def tearDown(self):
        persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL = self._orig
        shutil.rmtree(self._dir)

    def lanzar(self, cantidad, tarea):
        hilos = [threading.Thread(target=tarea, args=(i,)) for i in range(cantidad)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)

    def test_las_secciones_criticas_nunca_se_superponen(self):
        """Con la sección 'cargar → registrar → guardar' lenta, dos pedidos a la vez jamás entran juntos."""
        activos, maximo, lock = [0], [0], threading.Lock()
        from tortuscript.runtime_educativo import RuntimeEducativo
        original = RuntimeEducativo.registrar_paso_leccion

        def lenta(*args, **kwargs):
            with lock:
                activos[0] += 1
                maximo[0] = max(maximo[0], activos[0])
            time.sleep(0.05)
            try:
                return original(*args, **kwargs)
            finally:
                with lock:
                    activos[0] -= 1

        RuntimeEducativo.registrar_paso_leccion = lenta
        try:
            def tarea(i):
                c = self.nuevo_cliente()
                c.post(f"/api/lecciones/hola-mundo/pasos/{1 + i % 4}/comprobar", json={"respuesta": "mostrar"},
                       headers=self.h)
            self.lanzar(8, tarea)
        finally:
            RuntimeEducativo.registrar_paso_leccion = original
        self.assertEqual(maximo[0], 1)

    def test_el_xp_de_pedidos_simultaneos_no_se_pierde(self):
        def tarea(i):
            c = self.nuevo_cliente()
            for paso, resp in ((0, True), (1, "mostrar")):
                c.post(f"/api/lecciones/hola-mundo/pasos/{paso}/comprobar", json={"respuesta": resp},
                       headers=self.h)
        self.lanzar(6, tarea)
        p = self.seed_client.get("/cuenta/progreso").json["progreso"]["data"]
        # El paso 1 (elegir, 5 XP) se completa una sola vez aunque 6 pedidos lo intenten a la vez.
        self.assertEqual(p["xp_total"], 5)
        self.assertEqual(sorted(p["lecciones"]["hola-mundo"]["pasos"]), ["0", "1"])

    def test_las_paginas_estaticas_no_esperan(self):
        """Un pedido lento no bloquea los archivos estáticos."""
        terminado = []

        def lento(*_a, **_k):
            time.sleep(1.5)
            return original(*_a, **_k)

        from tortuscript.runtime_educativo import RuntimeEducativo
        original = RuntimeEducativo.registrar_paso_leccion
        RuntimeEducativo.registrar_paso_leccion = lento
        try:
            hilo = threading.Thread(target=lambda: self.nuevo_cliente().post(
                "/api/lecciones/hola-mundo/pasos/1/comprobar", json={"respuesta": "mostrar"}, headers=self.h))
            hilo.start()
            time.sleep(0.1)
            with self.app.test_client().get("/static/css/tortu.css") as r:
                terminado.append((r.status_code, hilo.is_alive()))          # ¿el pedido lento sigue en curso?
            hilo.join(timeout=10)
        finally:
            RuntimeEducativo.registrar_paso_leccion = original
        self.assertEqual(terminado[0], (200, True))

    def test_un_pedido_rechazado_no_deja_el_turno_tomado(self):
        c = self.nuevo_cliente()
        for _ in range(3):
            self.assertEqual(c.post("/api/lecciones/hola-mundo/pasos/1/comprobar", json={}).status_code, 403)   # sin token
            self.assertEqual(c.get("/", headers={"Host": "malo.com"}).status_code, 403)
        respuesta = []
        hilo = threading.Thread(target=lambda: respuesta.append(self.nuevo_cliente().get("/").status_code))
        hilo.start()
        hilo.join(timeout=10)
        self.assertFalse(hilo.is_alive(), "el turno quedó tomado")
        self.assertEqual(respuesta, [200])

    def test_un_error_del_servidor_tampoco_deja_el_turno_tomado(self):
        from tortuscript.runtime_educativo import RuntimeEducativo
        original = RuntimeEducativo.cargar_datos
        RuntimeEducativo.cargar_datos = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falla"))
        try:
            self.app.config["PROPAGATE_EXCEPTIONS"] = False
            self.assertEqual(self.nuevo_cliente().get("/resumen").status_code, 500)
        finally:
            RuntimeEducativo.cargar_datos = original
        hilo = threading.Thread(target=lambda: self.nuevo_cliente().get("/resumen"))
        hilo.start()
        hilo.join(timeout=10)
        self.assertFalse(hilo.is_alive())


if __name__ == "__main__":
    unittest.main()
