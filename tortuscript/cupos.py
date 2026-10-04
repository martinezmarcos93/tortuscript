"""Tope de ejecuciones simultáneas del código de los chicos, con una cola acotada (ADR-033).

Cada ejecución lanza un proceso (o un contenedor) con hasta `CPU_MAX` segundos de CPU y cientos de MB
de memoria. Sin un tope, un aula entera apretando «Probar» a la vez —o un abuso— multiplica eso por la
cantidad de pedidos. Acá se reparte una cantidad fija de cupos:

- el que encuentra un cupo libre corre;
- el que no, espera en la cola hasta `espera` segundos;
- si la cola ya está llena, o se cansó de esperar, recibe `Ocupado` y la app le pide que pruebe de nuevo.

Los cupos valen para toda la máquina, no solo para este proceso: además del semáforo en memoria se toma
un candado de archivo por cupo (`fcntl`), así varios procesos web comparten el mismo tope. En Windows no
hay `fcntl`; ahí la app es local y de un solo proceso, y alcanza con el semáforo.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:                                            # Windows
    fcntl = None

CUPOS_MIN, CUPOS_MAX = 1, 64
ESPERA_POR_DEFECTO = 8.0          # segundos en la cola antes de rendirse
COLA_POR_CUPO = 4                 # cuántos pueden esperar por cada cupo


class Ocupado(RuntimeError):
    """No hay cupo: la cola está llena o se agotó la espera."""


def cupos_desde_entorno(entorno=None) -> int:
    """`TORTU_EJECUCIONES_MAX`, o la cantidad de núcleos (entre 2 y 8) si no está o está mal escrito."""
    entorno = os.environ if entorno is None else entorno
    valor = (entorno.get("TORTU_EJECUCIONES_MAX") or "").strip()
    if valor:
        try:
            return max(CUPOS_MIN, min(CUPOS_MAX, int(valor)))
        except ValueError:
            logger.error("TORTU_EJECUCIONES_MAX no es un número (%r): se usa el valor por defecto.", valor)
    return max(2, min(8, os.cpu_count() or 2))


class Cupos:
    def __init__(self, cantidad: int, carpeta: Path | str | None = None, espera: float = ESPERA_POR_DEFECTO,
                 cola: int | None = None):
        self.cantidad = max(CUPOS_MIN, min(CUPOS_MAX, int(cantidad)))
        self.espera = espera
        self.cola_max = self.cantidad * COLA_POR_CUPO if cola is None else cola
        self.carpeta = Path(carpeta) if carpeta is not None else Path(tempfile.gettempdir()) / "tortuscript-cupos"
        self._semaforo = threading.BoundedSemaphore(self.cantidad)
        self._guardia = threading.Lock()
        self._esperando = 0

    def _candado_de_archivo(self, limite: float):
        """Un cupo libre entre todos los procesos de la máquina, o None si no hay `fcntl` (no hace falta)."""
        if fcntl is None:
            return None
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Sin carpeta compartida el tope queda por proceso: peor, pero no impide ejecutar.
            logger.error("No se pudo usar la carpeta de cupos %s: %s", self.carpeta, e)
            return None
        while True:
            for i in range(self.cantidad):
                archivo = open(self.carpeta / f"cupo-{i}.lock", "a")
                try:
                    fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return archivo
                except OSError:
                    archivo.close()
            if time.monotonic() >= limite:
                raise Ocupado("no hay cupo libre en la máquina")
            time.sleep(0.05)

    @contextmanager
    def tomar(self):
        """Contexto que ocupa un cupo. Lanza `Ocupado` si no lo consigue a tiempo."""
        limite = time.monotonic() + self.espera
        with self._guardia:
            if self._esperando >= self.cola_max:
                raise Ocupado("la cola de ejecuciones está llena")
            self._esperando += 1
        try:
            if not self._semaforo.acquire(timeout=max(0.0, limite - time.monotonic())):
                raise Ocupado("se agotó la espera por un cupo")
        finally:
            with self._guardia:
                self._esperando -= 1
        archivo = None
        try:
            archivo = self._candado_de_archivo(limite)
            yield
        finally:
            if archivo is not None:
                archivo.close()                                # cerrar el archivo suelta el candado
            self._semaforo.release()
