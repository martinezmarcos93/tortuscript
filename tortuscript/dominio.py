"""Modelo de dominio pedagógico V1 (ADR-052, P2): cuánta evidencia de dominio hay por concepto.

Función pura sobre el progreso que ya existe: no guarda nada, no cambia el esquema y no lee la fecha.
Reglas exactas en docs/MODELO_DOMINIO_V1.md. Un dato dañado se ignora; nunca lanza (salvo KeyError por
una unidad que no existe o que no es de tipo 'lecciones').
"""
import json

from . import contenido

ESTADOS = ("sin_evidencia", "visto", "reconocido", "aplicado", "autonomo", "consolidado")
CATEGORIAS = ("reconocimiento", "prediccion", "construccion", "produccion")

_CATEGORIA_POR_TIPO = {
    "elegir": "reconocimiento",
    "predecir": "prediccion",
    "completar": "construccion",
    "ordenar": "construccion",
    "escribir": "produccion",
}
XP_PRIMER_INTENTO = 5      # mismo valor que leccion.XP_PRIMER_INTENTO (no se importa: el modelo no depende del motor)
ESTRELLAS_AUTONOMAS = 3
CAJA_RETENCION = 3
ACIERTOS_RETENCION = 2
MAX_DIGITOS_INDICE = 10


def cargar_mapa():
    """Las `unidades` de contenido/mapa_curricular.json."""
    with open(contenido.CARPETA.parent / "mapa_curricular.json", encoding="utf-8") as f:
        return json.load(f)["unidades"]


def _entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _dict(valor):
    return valor if isinstance(valor, dict) else {}


def _fuerza(tipo, registro):
    """'fuerte' | 'debil' | 'ayudado' según el registro del paso, o None si está dañado."""
    if not isinstance(registro, dict):
        return None
    if tipo == "escribir":
        if "estrellas" in registro:
            estrellas = registro["estrellas"]
            if not _entero(estrellas):
                return None
            if estrellas >= ESTRELLAS_AUTONOMAS:
                return "fuerte"
            return "debil" if estrellas >= 1 else "ayudado"
        return "fuerte" if registro.get("perfecto") is True else "debil"
    xp = registro.get("xp")
    if not _entero(xp):
        return None
    if xp >= XP_PRIMER_INTENTO:
        return "fuerte"
    return "debil" if xp >= 1 else "ayudado"


def _pasos_de_leccion(cursos, curso_id, leccion_id):
    """Pasos de la lección en el curso indicado; [] si el curso o la lección no existen."""
    for curso in cursos if isinstance(cursos, list) else []:
        if not isinstance(curso, dict) or curso.get("id") != curso_id:
            continue
        for seccion in curso.get("secciones") or []:
            for leccion in _dict(seccion).get("lecciones") or []:
                if _dict(leccion).get("id") == leccion_id:
                    pasos = leccion.get("pasos")
                    return pasos if isinstance(pasos, list) else []
    return []


def _hay_retencion(progreso, lecciones):
    """¿Alguna tarjeta de repaso de estas lecciones llegó a la caja 3 con 2 aciertos?"""
    for clave, tarjeta in _dict(progreso.get("repaso")).items():
        if not isinstance(clave, str) or not isinstance(tarjeta, dict):
            continue
        leccion_id, _, indice = clave.rpartition(":")
        if leccion_id not in lecciones or not (indice.isascii() and indice.isdigit()) or len(indice) > MAX_DIGITOS_INDICE:
            continue
        caja, aciertos = tarjeta.get("caja"), tarjeta.get("aciertos")
        if _entero(caja) and _entero(aciertos) and caja >= CAJA_RETENCION and aciertos >= ACIERTOS_RETENCION:
            return True
    return False


def _nivel(disponibles, fuertes, hay_evidencia, retencion):
    """Nivel 0-5 según la tabla de la sección 4 de la especificación."""
    if not disponibles:
        return 0
    if fuertes >= disponibles:
        return 5 if retencion else 4
    if fuertes and len(fuertes) >= min(2, len(disponibles)):
        return 3
    if fuertes:
        return 2
    return 1 if hay_evidencia else 0


def estado_concepto(progreso, cursos, unidad_id, mapa=None):
    """Estado de un concepto (unidad de tipo 'lecciones'). KeyError si no existe o es de otro tipo."""
    unidades = cargar_mapa() if mapa is None else mapa
    unidad = unidades[unidad_id]
    if not isinstance(unidad, dict) or unidad.get("tipo") != "lecciones":
        raise KeyError(unidad_id)
    progreso = _dict(progreso)
    registros = _dict(progreso.get("lecciones"))
    declaradas = unidad.get("lecciones")
    lecciones = [l for l in declaradas if isinstance(l, str)] if isinstance(declaradas, list) else []

    disponibles, fuertes = set(), set()
    evidencias = {}
    for leccion_id in lecciones:
        pasos_registrados = _dict(_dict(registros.get(leccion_id)).get("pasos"))
        for indice, paso in enumerate(_pasos_de_leccion(cursos, unidad.get("curso"), leccion_id)):
            categoria = _CATEGORIA_POR_TIPO.get(_dict(paso).get("tipo"))
            if categoria is None:
                continue
            disponibles.add(categoria)
            cuentas = evidencias.setdefault(categoria, {"fuerte": 0, "debil": 0, "ayudado": 0})
            fuerza = _fuerza(paso["tipo"], pasos_registrados.get(str(indice)))
            if fuerza is not None:
                cuentas[fuerza] += 1
                if fuerza == "fuerte":
                    fuertes.add(categoria)

    retencion = _hay_retencion(progreso, set(lecciones))
    hay_evidencia = any(sum(c.values()) for c in evidencias.values())
    nivel = _nivel(disponibles, fuertes, hay_evidencia, retencion)
    return {
        "unidad": unidad_id,
        "nivel": nivel,
        "estado": ESTADOS[nivel],
        "disponibles": sorted(disponibles),
        "fuertes": sorted(fuertes),
        "evidencias": {c: evidencias[c] for c in sorted(disponibles)},
        "retencion": retencion,
    }


def dominio(progreso, cursos, mapa=None):
    """{unidad_id: estado_concepto(...)} para las unidades de tipo 'lecciones', en el orden del mapa."""
    unidades = cargar_mapa() if mapa is None else mapa
    return {uid: estado_concepto(progreso, cursos, uid, unidades)
            for uid, unidad in unidades.items() if isinstance(unidad, dict) and unidad.get("tipo") == "lecciones"}
