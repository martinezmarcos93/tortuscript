"""Selección adaptativa de tarjetas de repaso, sin cambiar su programación."""
import logging
import os
from math import ceil

from . import dominio, practica

logger = logging.getLogger(__name__)

VARIABLE = "TORTU_PLANIFICADOR"
MAX_POR_CONCEPTO = 2
NIVEL_SIN_CONCEPTO = 3
ORDEN_ACTIVIDADES = ("reconocimiento", "prediccion", "construccion", "produccion")


def activo(entorno=None):
    entorno = os.environ if entorno is None else entorno
    valor = entorno.get(VARIABLE, "")
    return isinstance(valor, str) and valor.strip().lower() == "adaptativo"


def elegir(progreso, cursos, hoy, mapa=None, cantidad=practica.POR_SESION):
    if cantidad <= 0:
        return []
    unidades = dominio.cargar_mapa() if mapa is None else mapa
    conceptos = {}
    for uid, unidad in unidades.items():
        if isinstance(unidad, dict) and unidad.get("tipo") == "lecciones":
            for leccion_id in unidad.get("lecciones", []):
                conceptos.setdefault(leccion_id, uid)
    niveles = {uid: estado["nivel"] for uid, estado in dominio.dominio(progreso, cursos, unidades).items()}

    grupos = {}
    for tarjeta in practica.candidatos(progreso, cursos, hoy):
        leccion = tarjeta["leccion"]
        concepto = conceptos.get(leccion)
        grupo = concepto if concepto is not None else (None, leccion)
        nivel = niveles.get(concepto, NIVEL_SIN_CONCEPTO)
        prioridad = (nivel, -tarjeta["vencido"], tarjeta["caja"], leccion, tarjeta["paso"])
        grupos.setdefault(grupo, []).append((prioridad, leccion, tarjeta["paso"]))
    for lista in grupos.values():
        lista.sort(key=lambda item: item[0])
    orden = sorted(grupos, key=lambda grupo: grupos[grupo][0][0])
    elegidas = []
    por_leccion = {}
    por_grupo = {grupo: 0 for grupo in orden}

    def rondas(limite, limite_leccion=practica.MAX_POR_LECCION):
        while len(elegidas) < cantidad:
            hubo_avance = False
            for grupo in orden:
                if por_grupo[grupo] >= limite or len(elegidas) >= cantidad:
                    continue
                for _, leccion, paso in grupos[grupo]:
                    if (leccion, paso) not in elegidas and por_leccion.get(leccion, 0) < limite_leccion:
                        elegidas.append((leccion, paso))
                        por_leccion[leccion] = por_leccion.get(leccion, 0) + 1
                        por_grupo[grupo] += 1
                        hubo_avance = True
                        break
            if not hubo_avance:
                break

    rondas(MAX_POR_CONCEPTO)
    if len(elegidas) < cantidad:
        # Con pocas lecciones vencidas se aflojan los dos topes, como en practica.elegir.
        lecciones = {leccion for lista in grupos.values() for _, leccion, _ in lista}
        rondas(max(MAX_POR_CONCEPTO, ceil(cantidad / max(1, len(orden)))),
               max(practica.MAX_POR_LECCION, ceil(cantidad / max(1, len(lecciones)))))
    return elegidas


def elegir_sesion(progreso, cursos, hoy, mapa=None, entorno=None, cantidad=practica.POR_SESION):
    if not activo(entorno):
        return practica.elegir(progreso, cursos, hoy, cantidad)
    try:
        return elegir(progreso, cursos, hoy, mapa, cantidad)
    except Exception:
        logger.error("Falló el planificador adaptativo; se usa el repaso anterior", exc_info=True)
        return practica.elegir(progreso, cursos, hoy, cantidad)


def recomendar(estado):
    if not estado.get("disponibles"):
        return None
    fuertes = set(estado.get("fuertes", []))
    disponibles = set(estado["disponibles"])
    for actividad in ORDEN_ACTIVIDADES:
        if actividad in disponibles and actividad not in fuertes:
            return actividad
    if estado.get("estado") == "consolidado":
        return None
    if not estado.get("retencion"):
        return "repaso"
    return None
