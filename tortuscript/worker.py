"""
Proceso hijo que ejecuta UN pedido y termina. Lo lanza tortuscript.proceso.

Lee un JSON por stdin y escribe un JSON por stdout. Así el código del chico corre
aislado del servidor web, con límites de tiempo y memoria puestos por el padre.

Pedido:
  {"op": "ejecutar", "fuente": "...", "entradas": [...]}
  {"op": "evaluar",  "fuente": "...", "entradas": [...], "solucion": "..."}
  {"op": "tortuga",  "fuente": "...", "entradas": [...]}   → agrega "ordenes"
  {"op": "evaluar_tortuga", "fuente": "...", "entradas": [...], "solucion": "..."}
                                                                → "ordenes" + "evaluacion" del dibujo
  (con "laberinto": {...} y "usar": [...] se evalúa el laberinto en vez de comparar con la solución;
   "ordenes" llega entonces solo hasta el choque, si lo hubo)
"""
import json
import sys

import secrets

from . import tortugame
from .evaluacion import SEMILLA_EVALUACION, evaluar, evaluar_dibujo, evaluar_laberinto
from .limites import limitar_memoria_windows
from .executor import ejecutar_codigo
from .tortuga import Registro
from .translator import TraductorTortuScript, detectar_tipo


def _python_de(fuente):
    tipo = detectar_tipo(fuente)
    python = fuente if tipo == "python" else TraductorTortuScript().traducir_codigo(fuente)
    return tipo, python


def _palabras_de(fuente, tipo):
    """Palabras de TortuScript que usa el programa del chico (para los pasos que exigen alguna)."""
    if tipo == "python":
        return set()
    traductor = TraductorTortuScript()
    traductor.traducir_codigo(fuente)
    return set(traductor.ultimas_palabras)


def semilla_del_pedido(pedido):
    """Evaluar usa siempre la semilla fija (el chico no la elige); jugar usa la que manda el navegador para
    re-ejecutar con las respuestas a preguntar() o, la primera vez, una nueva al azar."""
    if pedido.get("op") in ("evaluar", "evaluar_tortuga", "evaluar_juego"):
        return SEMILLA_EVALUACION
    semilla = pedido.get("semilla")
    if isinstance(semilla, int) and not isinstance(semilla, bool) and 0 <= semilla < 2 ** 31:
        return semilla
    return secrets.randbelow(2 ** 31)


def atender_juego(pedido):
    """TortuGame con la implementación de referencia: jugar (op "juego") o evaluar contra la solución."""
    semilla = semilla_del_pedido(pedido)
    entradas = list(pedido.get("entradas") or [])
    r = tortugame.correr_juego(pedido.get("fuente", ""), semilla, entradas)
    respuesta = {**r, "semilla": semilla, "salida": "", "salida_programa": "", "entradas": entradas}
    if pedido.get("op") == "evaluar_juego" and not r["error"] and r["pregunta"] is None:
        esperado = tortugame.correr_juego(pedido.get("solucion", ""), semilla, entradas, completar_con_vacio=True)
        respuesta["evaluacion"] = tortugame.comparar(r["eventos"], esperado["eventos"])
    return respuesta


def atender(pedido):
    if pedido.get("op") in ("juego", "evaluar_juego"):
        return atender_juego(pedido)
    tipo, python = _python_de(pedido.get("fuente", ""))
    semilla = semilla_del_pedido(pedido)
    detalles = {}
    registro = Registro() if pedido.get("op") in ("tortuga", "evaluar_tortuga") else None
    entradas = list(pedido.get("entradas") or [])
    # Una evaluación web sin respuestas todavía debe detenerse en la primera pregunta.
    # `[]` se reserva para la segunda ejecución, cuando ya llegaron respuestas.
    entradas_fijas = entradas if entradas else None
    salida, hay_error, mensaje = ejecutar_codigo(
        python, entradas_fijas=entradas_fijas,
        detalles=detalles, completar_con_vacio=False,
        extra_globals=registro.globales() if registro else None,
        callback_linea=registro.callback_linea if registro else None, semilla=semilla)
    respuesta = {
        "tipo": tipo, "python": python, "semilla": semilla,
        "salida": salida, "error": hay_error, "mensaje": mensaje,
        "salida_programa": detalles.get("salida_programa", ""),
        "entradas": detalles.get("entradas", []),
        "pregunta": detalles.get("pregunta_pendiente"),
    }
    if registro is not None:
        respuesta["ordenes"] = registro.ordenes       # aunque haya error: se dibuja lo hecho
    if pedido.get("op") == "evaluar_tortuga" and pedido.get("laberinto") and not hay_error \
            and respuesta["pregunta"] is None:
        palabras = _palabras_de(pedido.get("fuente", ""), tipo)
        ev = evaluar_laberinto(registro.ordenes, pedido["laberinto"], palabras, pedido.get("usar") or [])
        respuesta["ordenes"] = ev.pop("ordenes")
        respuesta["evaluacion"] = ev
    elif pedido.get("op") == "evaluar_tortuga" and not hay_error and respuesta["pregunta"] is None:
        respuesta["evaluacion"] = evaluar_dibujo(pedido.get("solucion", ""), registro.ordenes,
                                                 respuesta["entradas"], semilla)
    if pedido.get("op") == "evaluar" and not hay_error and respuesta["pregunta"] is None:
        respuesta["evaluacion"] = evaluar(pedido.get("solucion", ""), detalles, semilla)
    return respuesta


def main():
    limitar_memoria_windows()               # en Linux/macOS lo pone el padre (proceso.py)
    import os
    os.environ.clear()                      # el padre ya lo recorta; acá no queda nada que leer
    for flujo in (sys.stdin, sys.stdout):   # Windows abre los pipes en cp1252
        flujo.reconfigure(encoding="utf-8")
    salida_real = sys.stdout            # el código del alumno escribe en otro buffer
    pedido = json.load(sys.stdin)
    respuesta = atender(pedido)
    salida_real.write(json.dumps(respuesta, ensure_ascii=False))
    salida_real.flush()


if __name__ == "__main__":
    main()
