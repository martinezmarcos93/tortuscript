"""
Corre el código del chico en un proceso aparte (tortuscript.worker), con límites:
tiempo real, CPU y memoria. Si algo sale mal, el servidor web no se entera.

En Linux/macOS los límites de CPU y memoria los pone `resource`; en Windows solo
hay límite de tiempo (resource no existe ahí).
"""
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from . import cupos, sandbox_docker
from .error_handler import _explicacion

logger = logging.getLogger("tortuscript.proceso")

RAIZ = Path(__file__).resolve().parent.parent
TIEMPO_MAX = 10           # segundos reales (incluye arrancar Python: un antivirus puede demorarlo).
                          # Los bucles infinitos no llegan acá: los corta el límite de pasos en ~0,1 s.
CPU_MAX = 4               # segundos de CPU
MEMORIA_MAX = 512 * 1024 * 1024


ARCHIVOS_ABIERTOS_MAX = 64
# Lo único del entorno del servidor que ve el proceso del alumno. Todo lo demás (claves SMTP, secretos de
# webhooks, rutas de datos…) no se hereda: el código del chico podía leerlo con "{0.__globals__…}".format(dado).
ENTORNO_PERMITIDO = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE")


def entorno_del_worker():
    entorno = {k: v for k, v in os.environ.items() if k in ENTORNO_PERMITIDO}
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    return entorno


def _limitar():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_MAX, CPU_MAX))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORIA_MAX, MEMORIA_MAX))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))      # no puede escribir archivos
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))       # ni dejar volcados de memoria
    resource.setrlimit(resource.RLIMIT_NOFILE, (ARCHIVOS_ABIERTOS_MAX, ARCHIVOS_ABIERTOS_MAX))
    # El ejecutable instalado (PyInstaller) puede relanzarse a sí mismo al arrancar: ahí no se limita.
    if hasattr(resource, "RLIMIT_NPROC") and not getattr(sys, "frozen", False):
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))  # ni crear procesos o hilos (bomba fork)


def _falla(tipo, detalle=""):
    return {"error": True, "salida": "", "salida_programa": "", "entradas": [],
            "pregunta": None, "tipo": None, "python": "",
            "mensaje": _explicacion(tipo, detalle)}


# ── contrato del trabajo (ADR-033) ──
# Lo que llega del navegador se valida y se acota ANTES de lanzar un proceso. `solucion`, `laberinto`
# y `usar` los pone el servidor desde el contenido del curso; no vienen del cliente.
OPERACIONES = ("ejecutar", "evaluar", "tortuga", "evaluar_tortuga", "juego", "evaluar_juego")
FUENTE_MAX = 20_000            # caracteres de código
ENTRADAS_MAX = 100             # respuestas a preguntar()
ENTRADA_MAX = 1_000            # caracteres por respuesta


class TrabajoInvalido(ValueError):
    """El pedido no cumple el contrato; el mensaje se le puede mostrar al chico."""


def normalizar_pedido(pedido):
    """Devuelve un pedido nuevo que cumple el contrato, o lanza TrabajoInvalido."""
    if not isinstance(pedido, dict) or pedido.get("op") not in OPERACIONES:
        raise TrabajoInvalido("Ese pedido no se entiende.")
    fuente = pedido.get("fuente", "")
    if not isinstance(fuente, str):
        raise TrabajoInvalido("El código tiene que ser texto.")
    if len(fuente) > FUENTE_MAX:
        raise TrabajoInvalido(f"Tu programa es demasiado largo (más de {FUENTE_MAX} letras).")
    if "\x00" in fuente:
        raise TrabajoInvalido("Tu programa tiene un carácter que no se puede usar. Borralo y probá de nuevo.")
    entradas = pedido.get("entradas")
    if entradas is None:
        entradas = []
    if not isinstance(entradas, list) or len(entradas) > ENTRADAS_MAX:
        raise TrabajoInvalido("Las respuestas a las preguntas no son válidas.")
    limpias = []
    for entrada in entradas:
        if isinstance(entrada, bool) or not isinstance(entrada, (str, int, float)):
            raise TrabajoInvalido("Las respuestas a las preguntas no son válidas.")
        entrada = str(entrada)
        if len(entrada) > ENTRADA_MAX:
            raise TrabajoInvalido("Una de las respuestas es demasiado larga.")
        limpias.append(entrada)
    semilla = pedido.get("semilla")
    if isinstance(semilla, bool) or not isinstance(semilla, int) or not 0 <= semilla < 2 ** 31:
        semilla = None                                       # el worker elige una al azar
    limpio = {"op": pedido["op"], "fuente": fuente, "entradas": limpias, "semilla": semilla}
    for clave in ("solucion", "laberinto", "usar"):
        if clave in pedido:
            limpio[clave] = pedido[clave]
    return limpio


def comando_worker():
    """Cómo lanzar el worker: con Python (`-m tortuscript.worker`) o, si la app está instalada como ejecutable
    (PyInstaller, ADR-015), el mismo ejecutable con `--worker` (no hay otro Python para lanzar)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker"]
    return [sys.executable, "-m", "tortuscript.worker"]


_CUPOS = None
_CUPOS_GUARDIA = threading.Lock()


def cupos_de_ejecucion():
    """Los cupos de esta máquina (se crean una vez por proceso; ver `cupos.py` y `TORTU_EJECUCIONES_MAX`)."""
    global _CUPOS
    with _CUPOS_GUARDIA:
        if _CUPOS is None:
            _CUPOS = cupos.Cupos(cupos.cupos_desde_entorno())
        return _CUPOS


def correr(pedido):
    """Ejecuta el pedido en un proceso hijo y devuelve el dict de respuesta."""
    try:
        pedido = normalizar_pedido(pedido)
    except TrabajoInvalido as e:
        return _falla("CodigoNoPermitido", str(e))             # sin lanzar ningún proceso
    try:
        with cupos_de_ejecucion().tomar():
            return _correr_con_cupo(pedido)
    except cupos.Ocupado as e:
        logger.warning("Ejecución rechazada por falta de cupo: %s", e)
        return _falla("Ocupado")


def _correr_con_cupo(pedido):
    entrada = json.dumps(pedido, ensure_ascii=False)
    try:
        if sandbox_docker.activo():
            # ADR-033: contenedor efímero sin red. Si falla, no se recurre al subproceso local.
            r = sandbox_docker.ejecutar(entrada, TIEMPO_MAX)
            if r.returncode in (125, 126, 127):                # docker no pudo crear o iniciar el contenedor
                logger.error("El sandbox no pudo iniciar (código %s): %s", r.returncode, r.stderr[-300:])
                return _falla("Interno")
            if r.returncode == 137 and not r.stdout.strip():   # eliminado por el tope de memoria del contenedor
                return _falla("SinMemoria")
        else:
            opciones = {}
            if sys.platform != "win32":
                opciones["preexec_fn"] = _limitar
            r = subprocess.run(
                comando_worker(), input=entrada, capture_output=True,
                text=True, encoding="utf-8", timeout=TIEMPO_MAX, cwd=str(RAIZ), env=entorno_del_worker(),
                **opciones)
    except subprocess.TimeoutExpired:
        return _falla("TardoDemasiado")
    except OSError as e:
        logger.error("No se pudo lanzar el proceso del alumno: %s", e, exc_info=True)
        return _falla("Interno")
    if r.returncode != 0 or not r.stdout.strip():
        # Muerto por límite de CPU (SIGXCPU) o de memoria, o un error interno
        logger.warning("worker terminó con código %s: %s", r.returncode, r.stderr[-500:])
        if "MemoryError" in r.stderr:
            return _falla("SinMemoria")
        # Señal en el proceso local (negativo) o en el contenedor (128 + señal).
        return _falla("TardoDemasiado" if r.returncode < 0 or r.returncode > 128 else "Interno")
    try:
        return json.loads(r.stdout)
    except ValueError:
        logger.error("respuesta ilegible del worker: %r", r.stdout[-300:])
        return _falla("Interno")
