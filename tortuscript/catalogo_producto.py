"""Capa de producto V1: catálogo, competencias, progreso curricular y acceso.

No procesa pagos ni depende de una implementación SaaS. El catálogo curricular
sigue siendo la fuente conceptual; este módulo agrega el adaptador operativo.
"""
import json
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "docs" / "catalogo_curricular_v1.json"
MAPA = RAIZ / "contenido" / "mapa_curricular.json"

ESTADOS_ACCESO = (
    "gratuito",
    "premium",
    "prueba",
    "bloqueado_por_prerrequisito",
    "no_publicado",
)

# Estado comercial intencionalmente separado: mientras no exista decisión comercial,
# ninguna unidad se asigna a premium por código.
ESTADO_COMERCIAL_POR_DEFINIR = "por_definir"

SEGMENTOS_PRODUCTO = {
    "gratis": {
        "nombre": "Gratis",
        "descripcion": "Contenido que puede publicarse sin una decisión de suscripción.",
        "estado_acceso": "gratuito",
        "itinerarios": ["alfabetizacion-tecnologica"],
    },
    "premium": {
        "nombre": "Premium",
        "descripcion": "Segmento reservado; no asigna cursos todavía.",
        "estado_acceso": "premium",
        "itinerarios": [],
    },
    "en_desarrollo": {
        "nombre": "En desarrollo",
        "descripcion": "Contenido todavía no publicado como producto.",
        "estado_acceso": "no_publicado",
        "itinerarios": [],
    },
    "avanzados": {
        "nombre": "Avanzados",
        "descripcion": "Fuentes curriculares avanzadas previstas para una fase posterior.",
        "estado_acceso": "no_publicado",
        "itinerarios": ["nivel-avanzado"],
    },
}


def cargar_catalogo():
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def cargar_mapa():
    return json.loads(MAPA.read_text(encoding="utf-8"))


def _indice_unidades():
    indice = {}
    for itinerario in cargar_catalogo()["itinerarios"]:
        for unidad in itinerario.get("unidades", []):
            indice[unidad["id"]] = {**unidad, "itinerario": itinerario["id"]}
    return indice


def validar_modelo():
    datos = cargar_catalogo()
    mapa = cargar_mapa()
    ids = []
    for itinerario in datos["itinerarios"]:
        for unidad in itinerario.get("unidades", []):
            uid = unidad["id"]
            if uid in ids:
                raise ValueError(f"unidad curricular duplicada: {uid}")
            ids.append(uid)
            if not unidad.get("competencias"):
                raise ValueError(f"unidad sin competencias: {uid}")
            if uid not in mapa["unidades"]:
                raise ValueError(f"unidad sin adaptador operativo: {uid}")
            if unidad.get("estado_acceso") and unidad["estado_acceso"] not in ESTADOS_ACCESO:
                raise ValueError(f"estado de acceso inválido: {uid}")
    return True


def _evidencia_lecciones(progreso, unidad_id):
    evidencia = cargar_mapa()["unidades"].get(unidad_id)
    if not evidencia or evidencia.get("tipo") != "lecciones":
        return {"estudiada": False, "completada": False, "repasar": False, "lecciones": []}
    datos = progreso.get("lecciones") or {}
    lecciones = evidencia["lecciones"]
    estados = [datos.get(i, {}) for i in lecciones]
    estudiada = any(bool(e) for e in estados)
    completada = bool(estados) and all(e.get("completada") for e in estados)
    repaso = progreso.get("repaso") or {}
    claves = {f"{evidencia['curso']}:{i}" for i in lecciones}
    repasar = any(
        item.get("proximo") and item.get("proximo") <= str(date.today())
        for clave, item in repaso.items()
        if clave in claves
    )
    return {
        "estudiada": estudiada,
        "completada": completada,
        "repasar": repasar,
        "lecciones": lecciones,
    }


def _evidencia_proyecto(progreso, unidad_id):
    evidencia = cargar_mapa()["unidades"].get(unidad_id)
    proyecto_id = (evidencia or {}).get("proyecto")
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id, {})
    return {
        "estudiada": bool(datos),
        "completada": bool(datos.get("completado")),
        "repasar": False,
        "proyecto": proyecto_id,
    }


def _itinerario_completo(itinerario_id, progreso, indice):
    unidades = [u for u in indice.values() if u["itinerario"] == itinerario_id]
    return bool(unidades) and all(
        estado_unidad(u["id"], progreso, _indice=indice)["completada"] for u in unidades
    )


def _cumple_prerrequisito(requisito, progreso, indice):
    if isinstance(requisito, str):
        if requisito in indice:
            return estado_unidad(requisito, progreso, _indice=indice)["completada"]
        competencias_ids = {c for u in indice.values() for c in u.get("competencias", [])}
        if requisito in competencias_ids:
            return any(
                requisito in u.get("competencias", [])
                and estado_unidad(u["id"], progreso, _indice=indice)["completada"]
                for u in indice.values()
            )
        raise ValueError(f"prerrequisito desconocido: {requisito}")
    if isinstance(requisito, dict):
        if "itinerario" in requisito:
            return _itinerario_completo(requisito["itinerario"], progreso, indice)
        if "uno_de_itinerarios" in requisito:
            opciones = requisito["uno_de_itinerarios"]
            return any(_itinerario_completo(i, progreso, indice) for i in opciones)
        raise ValueError("prerrequisito estructurado desconocido")
    raise ValueError("prerrequisito inválido")


def _cumple_prerrequisitos(unidad, progreso, indice):
    return all(
        _cumple_prerrequisito(r, progreso, indice)
        for r in unidad.get("prerrequisitos") or []
    )


def estado_unidad(unidad_id, progreso, _indice=None):
    indice = _indice or _indice_unidades()
    unidad = indice[unidad_id]
    evidencia = (
        _evidencia_proyecto(progreso, unidad_id)
        if cargar_mapa()["unidades"][unidad_id].get("tipo") == "proyecto"
        else _evidencia_lecciones(progreso, unidad_id)
    )
    return {
        "id": unidad_id,
        "titulo": unidad["titulo"],
        "itinerario": unidad["itinerario"],
        "competencias": list(unidad.get("competencias", [])),
        "nivel": unidad.get("nivel"),
        "dificultad": unidad.get("dificultad"),
        "estado": (
            "completada" if evidencia["completada"]
            else "en_progreso" if evidencia["estudiada"]
            else "pendiente"
        ),
        "estudiada": evidencia["estudiada"],
        "completada": evidencia["completada"],
        "repasar": evidencia["repasar"],
        "prerrequisitos_cumplidos": _cumple_prerrequisitos(unidad, progreso, indice),
    }


def _publicado(unidad):
    return unidad["itinerario"] != "nivel-avanzado"


def estado_acceso(unidad_id, progreso, _indice=None):
    indice = _indice or _indice_unidades()
    unidad = indice[unidad_id]
    if not _publicado(unidad):
        return "no_publicado"
    if not _cumple_prerrequisitos(unidad, progreso, indice):
        return "bloqueado_por_prerrequisito"
    declarado = unidad.get("estado_acceso")
    if declarado:
        return declarado
    for segmento in SEGMENTOS_PRODUCTO.values():
        if unidad["itinerario"] in segmento["itinerarios"]:
            return segmento["estado_acceso"]
    # La decisión comercial queda deliberadamente fuera del motor.
    return ESTADO_COMERCIAL_POR_DEFINIR


def competencias(progreso):
    indice = _indice_unidades()
    salida = {}
    for uid, unidad in indice.items():
        estado = estado_unidad(uid, progreso, indice)
        for competencia in unidad.get("competencias", []):
            actual = salida.setdefault(competencia, {
                "id": competencia,
                "unidades": [],
                "estudiada": False,
                "dominada": False,
                "repasar": False,
            })
            actual["unidades"].append(uid)
            actual["estudiada"] = actual["estudiada"] or estado["estudiada"]
            actual["dominada"] = actual["dominada"] or estado["completada"]
            actual["repasar"] = actual["repasar"] or estado["repasar"]
    return salida


def resumen(progreso):
    indice = _indice_unidades()
    unidades = [estado_unidad(uid, progreso, indice) for uid in indice]
    accesos = {uid: estado_acceso(uid, progreso, indice) for uid in indice}
    comps = competencias(progreso)
    return {
        "version": 1,
        "segmentos_producto": SEGMENTOS_PRODUCTO,
        "estado_comercial": ESTADO_COMERCIAL_POR_DEFINIR,
        "unidades": unidades,
        "competencias": list(comps.values()),
        "accesos": accesos,
    }


def progreso_para_mostrar(progreso):
    """Contrato pequeño para UI: evita exponer reglas internas o datos de perfil."""
    r = resumen(progreso)
    return {
        "segmentos_producto": r["segmentos_producto"],
        "unidades": [
            {
                "id": u["id"],
                "titulo": u["titulo"],
                "itinerario": u["itinerario"],
                "estado": u["estado"],
                "repasar": u["repasar"],
                "acceso": r["accesos"][u["id"]],
            }
            for u in r["unidades"]
        ],
        "competencias": r["competencias"],
    }


def curriculo_publicado():
    """El documento Curriculum.v1 de TortuScript (ADR-037): itinerarios con unidades y sus identificadores.
    Los itinerarios que todavía no tienen unidades propias (el nivel avanzado, que vive en Croco-Script) no figuran."""
    from tortuscript import federacion
    catalogo = cargar_catalogo()
    itinerarios = [{"id": it["id"], "unidades": [u["id"] for u in it["unidades"]]}
                   for it in catalogo["itinerarios"] if it.get("unidades")]
    return federacion.curriculo_v1("tortuscript", catalogo["version"], itinerarios)
