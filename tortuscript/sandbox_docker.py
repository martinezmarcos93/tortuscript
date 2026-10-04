"""Sandbox efímero para el código del alumno (ADR-033): un contenedor nuevo por ejecución.

Se activa con `TORTU_SANDBOX=docker` (por defecto NO se usa: el modo local sigue con el subproceso
de `proceso.py`). Cada trabajo corre en un contenedor que:

- no tiene red (`--network none`);
- no contiene secretos ni datos: la imagen solo trae Python y el paquete `tortuscript`, y el
  contenedor no hereda el entorno del servidor ni monta ningún directorio del host;
- tiene el sistema de archivos en solo lectura y un /tmp en memoria, chico y sin ejecución;
- tiene tope de memoria, CPU, procesos, archivos abiertos y tiempo;
- corre sin privilegios (usuario `nobody`, sin capabilities, sin escalar privilegios);
- se destruye al terminar (`--rm`) y, si se pasa del tiempo, se mata por nombre;
- no ve el host ni otros trabajos (namespaces propios de PID, red, IPC y montaje).

Si Docker o la imagen no están disponibles la ejecución FALLA: nunca se vuelve en silencio al
subproceso local, porque quien configuró el sandbox espera aislamiento.
"""
from __future__ import annotations

import logging
import os
import secrets
import subprocess

logger = logging.getLogger(__name__)

IMAGEN_POR_DEFECTO = "tortuscript-sandbox:1"
MEMORIA = "256m"
MEMORIA_VIRTUAL_BYTES = 512 * 1024 * 1024       # RLIMIT_AS: Python alcanza a explicar el MemoryError
CPU_SEGUNDOS = 4
PROCESOS_MAX = 16
ARCHIVOS_ABIERTOS_MAX = 64
ARRANQUE_SEGUNDOS = 20                          # margen para crear el contenedor, además del tiempo del trabajo


def activo(entorno=None) -> bool:
    entorno = os.environ if entorno is None else entorno
    return (entorno.get("TORTU_SANDBOX") or "").strip().lower() == "docker"


def imagen(entorno=None) -> str:
    entorno = os.environ if entorno is None else entorno
    return (entorno.get("TORTU_SANDBOX_IMAGEN") or IMAGEN_POR_DEFECTO).strip()


def comando(nombre: str, imagen_: str | None = None, extra: list[str] | None = None) -> list[str]:
    """La línea de `docker run` de un trabajo. `extra` (solo pruebas) va después de la imagen."""
    return [
        "docker", "run", "--rm", "--interactive", "--name", nombre,
        # Con --init el worker no es el PID 1 (que ignora las señales sin manejador, como SIGXCPU).
        "--init",
        "--network", "none",
        "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m",
        "--memory", MEMORIA, "--memory-swap", MEMORIA,
        "--cpus", "1", "--pids-limit", str(PROCESOS_MAX),
        # Límite blando antes que el duro: llega SIGXCPU (se informa «tardó demasiado») y no un SIGKILL,
        # que no se distinguiría del corte por memoria del contenedor.
        "--ulimit", f"cpu={CPU_SEGUNDOS}:{CPU_SEGUNDOS + 1}",
        # Docker no admite el ulimit de memoria virtual: lo aplica el worker al arrancar (ver worker.main).
        "--env", f"TORTU_MEMORIA_MAX={MEMORIA_VIRTUAL_BYTES}",
        "--ulimit", f"nofile={ARCHIVOS_ABIERTOS_MAX}:{ARCHIVOS_ABIERTOS_MAX}",
        "--ulimit", "core=0:0",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "65534:65534", "--ipc", "none", "--log-driver", "none",
        "--hostname", "sandbox",
        *(extra or []),
        imagen_ or imagen(),
    ]


def nombre_de_trabajo() -> str:
    return "tortu-trabajo-" + secrets.token_hex(8)


def ejecutar(entrada: str, tiempo_max: float, extra: list[str] | None = None,
             argumentos: list[str] | None = None) -> subprocess.CompletedProcess:
    """Corre un trabajo y devuelve el proceso terminado (returncode, stdout, stderr).
    Lanza subprocess.TimeoutExpired si se pasó del tiempo (el contenedor ya quedó eliminado)
    y OSError si no se pudo invocar a Docker."""
    nombre = nombre_de_trabajo()
    orden = comando(nombre, extra=extra) + (argumentos or [])
    # A `docker` (el cliente) solo se le pasa PATH: el contenedor no recibe ninguna variable del servidor.
    entorno = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    for clave in ("DOCKER_HOST", "DOCKER_CONTEXT", "HOME", "XDG_RUNTIME_DIR"):
        if clave in os.environ:
            entorno[clave] = os.environ[clave]
    try:
        return subprocess.run(orden, input=entrada, capture_output=True, text=True, encoding="utf-8",
                              timeout=tiempo_max + ARRANQUE_SEGUNDOS, env=entorno)
    except subprocess.TimeoutExpired:
        # subprocess mató al cliente `docker`, no al contenedor: hay que eliminarlo por nombre.
        try:
            subprocess.run(["docker", "kill", nombre], capture_output=True, timeout=15, env=entorno)
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.error("No se pudo eliminar el contenedor %s tras el tiempo límite: %s", nombre, e)
        raise
