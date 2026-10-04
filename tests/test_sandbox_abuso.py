"""Barrido 8 — pruebas de abuso del proceso que corre el código del alumno (ADR-033, tanda «24–30/11»).

No certifican aislamiento ante un atacante en un servidor público (para eso hace falta el sandbox
del sistema operativo de ADR-033): fijan lo que el proceso local SÍ garantiza hoy y evitan regresiones.
"""
import os
import subprocess
import sys
import unittest
from unittest import mock

from tortuscript import proceso
from tortuscript.proceso import correr

SECRETO = "secreto-que-no-debe-salir-123"
UNIX = sys.platform != "win32"


def ejecutar(fuente, op="ejecutar", **extra):
    return correr({"op": op, "fuente": fuente, "entradas": [], **extra})


def texto(r):
    return " ".join(str(r.get(k) or "") for k in ("salida", "salida_programa", "mensaje", "python"))


class TestSecretosDelServidor(unittest.TestCase):
    def test_el_entorno_del_servidor_no_llega_al_codigo_del_alumno(self):
        # Antes: "{0.__globals__[sys].modules[os].environ}".format(dado) mostraba la clave SMTP del .env.
        intentos = (
            'print("{0.__globals__[sys].modules[os].environ}".format(dado))',
            'print("{0.__globals__[sys].modules[os].environ}".format_map({"0": dado}))',
            'f = "{0.__globals__[sys].modules[os].environ}"\nprint(f.format(dado))',
            'mostrar "{0.__globals__}".format(dado)',
        )
        with mock.patch.dict(os.environ, {"TORTU_SMTP_CLAVE": SECRETO, "OTRA_CLAVE": SECRETO}):
            for fuente in intentos:
                for op in ("ejecutar", "tortuga", "evaluar", "juego"):
                    with self.subTest(fuente=fuente[:40], op=op):
                        r = ejecutar(fuente, op=op, solucion='mostrar "x"')
                        self.assertNotIn(SECRETO, texto(r))
                        self.assertNotIn("environ(", texto(r))

    def test_el_worker_arranca_solo_con_el_entorno_permitido(self):
        with mock.patch.dict(os.environ, {"TORTU_SMTP_CLAVE": SECRETO, "TORTUSCRIPT_DATOS": "/datos", "HOME": "/home/x"}):
            entorno = proceso.entorno_del_worker()
        self.assertNotIn(SECRETO, entorno.values())
        self.assertLessEqual(set(entorno), set(proceso.ENTORNO_PERMITIDO) | {"PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE"})
        # Y aunque alguien se lo pase, el worker lo borra antes de ejecutar nada.
        r = subprocess.run(proceso.comando_worker(), input='{"op": "ejecutar", "fuente": "mostrar 1"}',
                           capture_output=True, text=True, cwd=str(proceso.RAIZ),
                           env={**proceso.entorno_del_worker(), "FILTRADO": SECRETO}, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_format_se_rechaza_con_un_mensaje_para_chicos(self):
        r = ejecutar('print("{}".format(1))')
        self.assertTrue(r["error"])
        self.assertIn("No se puede usar «.format»", r["mensaje"])


class TestEscapes(unittest.TestCase):
    def test_puertas_clasicas_cerradas(self):
        intentos = (
            "import os", "from os import system", "__import__('os')", "print(().__class__.__base__.__subclasses__())",
            "print(open('/etc/passwd').read())", "eval('1+1')", "exec('x = 1')", "compile('1', 'a', 'eval')",
            "print(globals())", "print(locals())", "print(vars())", "print(dir())", "getattr(1, 'real')",
            "print(dado.__globals__)", "x = lambda: 0\nprint(x.__code__)", "breakpoint()", "help()",
            "print(type.__subclasses__(type))", "print(print.__self__)", "input.__call__", "print(__builtins__)",
            "class A: pass\nprint(A.__mro__)", "print(str.__dict__)", "memoryview(b'x')", "print(__name__)",
        )
        for fuente in intentos:
            with self.subTest(fuente=fuente):
                r = ejecutar(fuente)
                self.assertTrue(r["error"], texto(r))
                self.assertNotIn("root:", texto(r))

    def test_el_juego_usa_su_propio_interprete_y_tampoco_filtra(self):
        with mock.patch.dict(os.environ, {"TORTU_SMTP_CLAVE": SECRETO}):
            r = ejecutar('h es heroe("{0.__class__}", 10, 1)\nmostrar h.nombre', op="juego")
        self.assertNotIn(SECRETO, texto(r))
        self.assertNotIn("<class", texto(r))


class TestRecursos(unittest.TestCase):
    def test_bucle_infinito_se_corta_rapido_y_con_explicacion(self):
        for fuente in ("mientras True:\n    x es 1", "while True: pass", "repetir 999999999 veces:\n    x es 1"):
            with self.subTest(fuente=fuente[:20]):
                r = ejecutar(fuente)
                self.assertTrue(r["error"])
                self.assertTrue(r["mensaje"])

    def test_un_try_del_alumno_no_puede_tragarse_el_corte(self):
        r = ejecutar("while True:\n    try:\n        x = 1\n    except Exception:\n        pass")
        self.assertTrue(r["error"])

    def test_salida_gigante_se_corta(self):
        r = ejecutar('while True:\n    print("x" * 1000)')
        self.assertTrue(r["error"])
        self.assertLess(len(r.get("salida") or ""), 30_000)

    def test_bomba_de_memoria_termina_con_explicacion_y_no_tumba_al_servidor(self):
        for fuente in ('x = "a" * 10000000000', "x = [0] * 10 ** 10", "x = list(range(10 ** 10))"):
            with self.subTest(fuente=fuente):
                r = ejecutar(fuente)
                self.assertTrue(r["error"])
                self.assertTrue(r["mensaje"])

    def test_calculo_interminable_en_una_sola_linea_lo_corta_el_limite_de_cpu(self):
        # No hay "pasos" que contar: una sola línea. Lo frena RLIMIT_CPU (o el tiempo real en Windows).
        r = ejecutar("x = 9 ** 9 ** 9")
        self.assertTrue(r["error"])

    def test_recursion_sin_fin_se_explica(self):
        r = ejecutar("def f():\n    return f()\nf()")
        self.assertTrue(r["error"])

    def test_tras_cada_abuso_el_servidor_sigue_atendiendo(self):
        ejecutar('x = "a" * 10000000000')
        r = ejecutar('mostrar "sigo vivo"')
        self.assertFalse(r["error"])
        self.assertIn("sigo vivo", r["salida"])


@unittest.skipUnless(UNIX, "los límites de resource solo existen en Linux/macOS")
class TestLimitesDelProceso(unittest.TestCase):
    """Los límites que pone el padre valen para CUALQUIER código que corra en el worker, no solo el validado."""

    def _en_el_worker(self, codigo):
        return subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=30,
                              preexec_fn=proceso._limitar, env=proceso.entorno_del_worker())

    def test_no_puede_crear_procesos(self):
        r = self._en_el_worker("import os\ntry:\n    os.fork()\n    print('FORK')\nexcept OSError:\n    print('bloqueado')")
        self.assertIn("bloqueado", r.stdout)
        self.assertNotIn("FORK", r.stdout)
        r = self._en_el_worker("import subprocess\ntry:\n    subprocess.run(['echo', 'x'])\n    print('EXEC')\n"
                               "except OSError:\n    print('bloqueado')")
        self.assertIn("bloqueado", r.stdout)

    def test_no_puede_crear_hilos(self):
        r = self._en_el_worker("import threading\ntry:\n    t = threading.Thread(target=print)\n    t.start()\n"
                               "    print('HILO')\nexcept RuntimeError:\n    print('bloqueado')")
        self.assertIn("bloqueado", r.stdout)

    def test_no_puede_escribir_archivos(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            destino = os.path.join(d, "robado.txt")
            r = self._en_el_worker(f"f = open({destino!r}, 'w')\nf.write('x' * 100)\nf.close()\nprint('ESCRITO')")
            self.assertNotIn("ESCRITO", r.stdout)
            self.assertFalse(os.path.exists(destino) and os.path.getsize(destino) > 0)

    def test_no_puede_abrir_cientos_de_archivos(self):
        r = self._en_el_worker("abiertos = []\ntry:\n    for _ in range(500):\n        abiertos.append(open('/dev/null'))\n"
                               "    print('ABIERTOS')\nexcept OSError:\n    print('bloqueado', len(abiertos))")
        self.assertIn("bloqueado", r.stdout)

    def test_memoria_y_cpu_tienen_tope(self):
        r = self._en_el_worker("try:\n    x = bytearray(2 * 1024 ** 3)\n    print('MEMORIA')\nexcept MemoryError:\n    print('bloqueado')")
        self.assertIn("bloqueado", r.stdout)
        r = self._en_el_worker("while True:\n    pass")
        self.assertLess(r.returncode, 0)                           # lo mata SIGXCPU


if __name__ == "__main__":
    unittest.main()
