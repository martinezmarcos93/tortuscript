"""Sandbox de contenedores (ADR-033): pruebas de aislamiento REALES, con código hostil arbitrario.

Se saltean si no hay Docker o no está construida la imagen:
    docker build -f despliegue/sandbox/Dockerfile -t tortuscript-sandbox:1 .
Aquí el código corre SIN el validador de TortuScript (como si alguien lo hubiera burlado): lo que
se comprueba es el aislamiento del sistema operativo, no el del lenguaje.
"""
import os
import shutil
import subprocess
import unittest
from unittest import mock

from tortuscript import proceso, sandbox_docker


def _imagen_disponible():
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "image", "inspect", sandbox_docker.IMAGEN_POR_DEFECTO],
                           capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


HAY_SANDBOX = _imagen_disponible()
SECRETO = "secreto-del-servidor-456"


def hostil(codigo, tiempo=20):
    """Ejecuta Python arbitrario dentro del sandbox, con las mismas restricciones que un trabajo."""
    return sandbox_docker.ejecutar("", tiempo, extra=["--entrypoint", "python"], argumentos=["-c", codigo])


class TestConfiguracion(unittest.TestCase):
    def test_apagado_por_defecto_y_se_activa_solo_con_docker(self):
        self.assertFalse(sandbox_docker.activo({}))
        self.assertFalse(sandbox_docker.activo({"TORTU_SANDBOX": "si"}))
        self.assertTrue(sandbox_docker.activo({"TORTU_SANDBOX": " Docker "}))
        self.assertEqual(sandbox_docker.imagen({}), sandbox_docker.IMAGEN_POR_DEFECTO)
        self.assertEqual(sandbox_docker.imagen({"TORTU_SANDBOX_IMAGEN": "registro/img:2"}), "registro/img:2")

    def test_el_comando_lleva_todas_las_restricciones_de_la_adr_033(self):
        orden = " ".join(sandbox_docker.comando("tortu-x"))
        for exigido in ("--rm", "--network none", "--read-only", "--tmpfs /tmp:rw,noexec", "--memory 256m",
                        "--memory-swap 256m", "--cpus 1", "--pids-limit", "--cap-drop ALL",
                        "--security-opt no-new-privileges", "--user 65534:65534", "--ulimit cpu=", "--ulimit nofile=",
                        "--ipc none", "--log-driver none"):
            self.assertIn(exigido, orden)
        # Nada del host se monta ni se publica, y no hay privilegios.
        for prohibido in (" -v ", "--volume", "--mount", "--privileged", "--publish", " -p ", "--pid host",
                          "--network host", "--cap-add", "--device"):
            self.assertNotIn(prohibido, orden + " ")

    def test_si_el_sandbox_esta_pedido_y_falla_no_se_ejecuta_en_el_host(self):
        roto = subprocess.CompletedProcess([], 125, "", "docker: no such image")
        with mock.patch.dict(os.environ, {"TORTU_SANDBOX": "docker"}), \
                mock.patch.object(sandbox_docker, "ejecutar", return_value=roto), \
                mock.patch.object(proceso.subprocess, "run", side_effect=AssertionError("no debe correr local")), \
                self.assertLogs("tortuscript.proceso", "ERROR"):
            r = proceso.correr({"op": "ejecutar", "fuente": "mostrar 1"})
        self.assertTrue(r["error"])
        with mock.patch.dict(os.environ, {"TORTU_SANDBOX": "docker"}), \
                mock.patch.object(sandbox_docker, "ejecutar", side_effect=FileNotFoundError("docker")), \
                mock.patch.object(proceso.subprocess, "run", side_effect=AssertionError("no debe correr local")), \
                self.assertLogs("tortuscript.proceso", "ERROR"):
            self.assertTrue(proceso.correr({"op": "ejecutar", "fuente": "mostrar 1"})["error"])


@unittest.skipUnless(HAY_SANDBOX, "sin Docker o sin la imagen tortuscript-sandbox:1")
class TestTrabajosEnElSandbox(unittest.TestCase):
    def correr(self, fuente, **extra):
        with mock.patch.dict(os.environ, {"TORTU_SANDBOX": "docker", "TORTU_SMTP_CLAVE": SECRETO}):
            return proceso.correr({"op": "ejecutar", "fuente": fuente, **extra})

    def test_el_mismo_contrato_que_el_proceso_local(self):
        r = self.correr('n es preguntar("¿Nombre? ")\nmostrar "Hola " + n', entradas=["Ana"])
        self.assertFalse(r["error"], r.get("mensaje"))
        self.assertIn("Hola Ana", r["salida"])
        with mock.patch.dict(os.environ, {"TORTU_SANDBOX": "docker"}):
            dibujo = proceso.correr({"op": "tortuga", "fuente": "avanzar 50\ngirar_der 90"})
            evaluado = proceso.correr({"op": "evaluar", "fuente": "mostrar 2", "solucion": "mostrar 1 + 1"})
        self.assertTrue(dibujo["ordenes"])
        self.assertEqual(evaluado["evaluacion"]["estado"], "correcto")

    def test_los_abusos_terminan_con_la_misma_explicacion(self):
        self.assertIn("no termina nunca", self.correr("while True: pass")["mensaje"])
        self.assertIn("demasiada memoria", self.correr('x = "a" * 10000000000')["mensaje"])
        # Una sola línea que no termina: no hay pasos que contar, la corta el límite de CPU del contenedor.
        self.assertIn("tardó demasiado", self.correr("x = sum(range(10 ** 12))")["mensaje"])

    def test_no_queda_ningun_contenedor_despues_de_los_trabajos(self):
        self.correr("mostrar 1")
        self.correr("x = 9 ** 9 ** 9")
        vivos = subprocess.run(["docker", "ps", "-aq", "--filter", "name=tortu-trabajo-"],
                               capture_output=True, text=True, timeout=20).stdout.split()
        self.assertEqual(vivos, [])

    def test_un_trabajo_que_no_termina_se_elimina_por_nombre(self):
        with mock.patch.object(sandbox_docker, "ARRANQUE_SEGUNDOS", 0), self.assertRaises(subprocess.TimeoutExpired):
            sandbox_docker.ejecutar("", 3, extra=["--entrypoint", "python"],
                                    argumentos=["-c", "import time\nwhile True: time.sleep(1)"])
        vivos = subprocess.run(["docker", "ps", "-q", "--filter", "name=tortu-trabajo-"],
                               capture_output=True, text=True, timeout=20).stdout.split()
        self.assertEqual(vivos, [])


@unittest.skipUnless(HAY_SANDBOX, "sin Docker o sin la imagen tortuscript-sandbox:1")
class TestAislamientoAnteCodigoHostil(unittest.TestCase):
    def test_sin_red(self):
        r = hostil("import socket\n"
                   "for destino in (('1.1.1.1', 53), ('127.0.0.1', 5057), ('172.17.0.1', 22)):\n"
                   "    try:\n        socket.create_connection(destino, timeout=2); print('CONECTO', destino)\n"
                   "    except OSError: print('sin red')\n"
                   "try:\n    socket.gethostbyname('example.com'); print('DNS')\nexcept OSError: print('sin dns')")
        self.assertNotIn("CONECTO", r.stdout)
        self.assertNotIn("DNS", r.stdout)
        self.assertEqual(r.stdout.count("sin red"), 3)

    def test_no_recibe_el_entorno_ni_secretos_del_servidor(self):
        with mock.patch.dict(os.environ, {"TORTU_SMTP_CLAVE": SECRETO, "TORTU_PAGOS_SECRETO": SECRETO}):
            r = hostil("import os; print(dict(os.environ))")
        self.assertNotIn(SECRETO, r.stdout)
        self.assertNotIn("TORTU_SMTP", r.stdout)

    def test_sistema_de_archivos_de_solo_lectura_y_sin_datos_del_host(self):
        r = hostil("import os\n"
                   "for ruta in ('/app/x', '/x', '/etc/x', '/app/tortuscript/worker.py', '/var/tmp/x', '/home/x'):\n"
                   "    try:\n        open(ruta, 'w').write('x'); print('ESCRIBIO', ruta)\n"
                   "    except OSError: print('solo lectura')\n"
                   "print('instance' in os.listdir('/app'), bool(os.listdir('/media')), os.path.exists('/app/.env'))\n"
                   "print(sorted(os.listdir('/app')))")
        self.assertNotIn("ESCRIBIO", r.stdout)
        self.assertIn("False False False", r.stdout)
        self.assertIn("['tortuscript']", r.stdout)                 # ni cursos, ni cuentas, ni progreso de nadie

    def test_tmp_es_efimero_chico_y_sin_ejecucion(self):
        r = hostil("import os, subprocess\n"
                   "open('/tmp/a', 'w').write('x'); print('tmp ok')\n"
                   "try:\n    open('/tmp/grande', 'wb').write(b'x' * (64 * 1024 * 1024)); print('LLENO')\n"
                   "except OSError: print('tope de tmp')\n"
                   "open('/tmp/s.sh', 'w').write('#!/bin/sh\\necho EJECUTO')\nos.chmod('/tmp/s.sh', 0o755)\n"
                   "try:\n    print(subprocess.run(['/tmp/s.sh'], capture_output=True, text=True).stdout)\n"
                   "except OSError: print('noexec')")
        self.assertIn("tmp ok", r.stdout)
        self.assertIn("tope de tmp", r.stdout)
        self.assertIn("noexec", r.stdout)
        self.assertNotIn("EJECUTO", r.stdout)
        otro = hostil("import os; print(os.listdir('/tmp'))")       # el siguiente trabajo no ve nada del anterior
        self.assertEqual(otro.stdout.strip(), "[]")

    def test_sin_privilegios_ni_forma_de_escalar(self):
        r = hostil("import os\nprint('uid', os.getuid(), 'gid', os.getgid())\n"
                   "estado = open('/proc/self/status').read()\n"
                   "print([l for l in estado.splitlines() if l.startswith(('CapEff', 'NoNewPrivs'))])\n"
                   "try:\n    os.setuid(0); print('ROOT')\nexcept OSError: print('no escala')")
        self.assertIn("uid 65534 gid 65534", r.stdout)
        self.assertIn("CapEff:\\t0000000000000000", r.stdout)
        self.assertIn("NoNewPrivs:\\t1", r.stdout)
        self.assertNotIn("ROOT", r.stdout)

    def test_no_ve_procesos_del_host_ni_de_otros_trabajos(self):
        r = hostil("import os\nfor p in sorted(int(p) for p in os.listdir('/proc') if p.isdigit()):\n"
                   "    print(p, open(f'/proc/{p}/comm').read().strip())")
        procesos = [linea.split()[1] for linea in r.stdout.splitlines()]
        self.assertEqual(procesos, ["docker-init", "python"])       # solo el init del contenedor y este trabajo

    def test_bomba_de_procesos_acotada(self):
        r = hostil("import os, time\nhijos = 0\n"
                   "try:\n    for _ in range(200):\n        if os.fork() == 0:\n            time.sleep(3); os._exit(0)\n        hijos += 1\n"
                   "except OSError: pass\nprint('hijos', hijos)")
        hijos = int(r.stdout.split("hijos")[-1])
        self.assertLess(hijos, sandbox_docker.PROCESOS_MAX)

    def test_memoria_acotada_por_el_contenedor(self):
        r = hostil("b = []\ntry:\n    while True: b.append(bytearray(32 * 1024 * 1024))\n"
                   "except MemoryError: print('MemoryError con', len(b) * 32, 'MB')")
        self.assertTrue(r.returncode == 137 or "MemoryError" in r.stdout, (r.returncode, r.stdout))
        usados = [int(x) for x in r.stdout.split() if x.isdigit()]
        self.assertTrue(not usados or usados[0] <= 512)


if __name__ == "__main__":
    unittest.main()
