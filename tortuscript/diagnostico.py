"""
Prueba de nivel del diagnóstico (ADR-004, segunda versión).

Seis preguntas, una por sección del curso 1 (contenido/diagnostico.json). La corrige el servidor: el navegador nunca
recibe las respuestas correctas. Recomienda empezar al comienzo de la primera sección donde hubo un error; si todo
está bien, en *Desafíos*. No hay caminos personalizados: solo un punto de entrada, con las mismas reglas de las
lecciones salteadas de la primera versión.
"""
import json
import random
from functools import lru_cache
from pathlib import Path

from . import contenido, progreso

ARCHIVO = Path(__file__).resolve().parent.parent / "contenido" / "diagnostico.json"


@lru_cache(maxsize=None)
def cargar():
    with open(ARCHIVO, encoding="utf-8") as f:
        return json.load(f)


def inicios_de_seccion():
    """Primera lección de cada sección del curso 1, en orden."""
    return [s["lecciones"][0]["id"] for s in contenido.cargar_curso()["secciones"]]


def entradas_permitidas(experiencia):
    """Dónde puede empezar cada experiencia: "un poquito", en Variables; "bastante", al comienzo de cualquier sección
    después de Mostrar (es lo que puede recomendar la prueba)."""
    if not isinstance(experiencia, str):
        return set()
    if experiencia == "bastante":
        return set(inicios_de_seccion()[1:])
    fija = progreso.PUNTOS_DE_ENTRADA.get(experiencia)
    return {fija} if fija else set()


def preguntas_publicas():
    """Las preguntas para el navegador: sin la respuesta correcta y con las opciones mezcladas siempre igual."""
    datos = cargar()
    salida = []
    for i, p in enumerate(datos["preguntas"]):
        opciones = list(p["opciones"])
        random.Random(f"diagnostico:{i}").shuffle(opciones)
        salida.append({"pregunta": p["pregunta"], "codigo": p.get("codigo"), "opciones": opciones})
    return {"intro": datos["intro"], "preguntas": salida}


def recomendar(respuestas):
    """La lección de entrada recomendada según las respuestas (textos de las opciones, en orden)."""
    datos = cargar()
    if not isinstance(respuestas, list) or len(respuestas) != len(datos["preguntas"]):
        raise ValueError("Contestá todas las preguntas.")
    for p, r in zip(datos["preguntas"], respuestas):
        if r != p["opciones"][p["correcta"]]:
            return p["seccion"]
    return datos["si_acierta_todo"]
