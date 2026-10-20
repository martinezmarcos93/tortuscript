"""Mapa de cobertura pedagógica (P1, docs/ESPECIFICACION_P1_P6.md).

Para cada unidad del mapa curricular cuenta qué tipos de paso tiene y qué categorías de evidencia
(reconocimiento, predicción, construcción, producción) se pueden practicar con ellos. Puro: no toca disco.
"""
from . import dominio
from .contenido import TIPOS

_ROTULOS = {"reconocimiento": "Reconocimiento", "prediccion": "Predicción",
            "construccion": "Construcción", "produccion": "Producción"}


def _lecciones_por_id(cursos, curso_id):
    for curso in cursos if isinstance(cursos, list) else []:
        if isinstance(curso, dict) and curso.get("id") == curso_id:
            return {lec.get("id"): lec for sec in curso.get("secciones", []) if isinstance(sec, dict)
                    for lec in sec.get("lecciones", []) if isinstance(lec, dict)}
    return {}


def cobertura(cursos, mapa):
    """{unidad_id: {curso, lecciones, pasos, tipos, categorias, faltan}} para las unidades de tipo «lecciones»."""
    salida = {}
    for uid, unidad in mapa.items():
        if not isinstance(unidad, dict) or unidad.get("tipo") != "lecciones":
            continue
        por_id = _lecciones_por_id(cursos, unidad.get("curso"))
        tipos = {tipo: 0 for tipo in TIPOS}
        total = 0
        for leccion_id in unidad.get("lecciones", []):
            for paso in (por_id.get(leccion_id) or {}).get("pasos", []):
                tipo = paso.get("tipo") if isinstance(paso, dict) else None
                if tipo in tipos:
                    tipos[tipo] += 1
                    total += 1
        presentes = {dominio._CATEGORIA_POR_TIPO[t] for t, n in tipos.items() if n and t in dominio._CATEGORIA_POR_TIPO}
        salida[uid] = {
            "curso": unidad.get("curso"),
            "lecciones": list(unidad.get("lecciones", [])),
            "pasos": total,
            "tipos": tipos,
            "categorias": [c for c in dominio.CATEGORIAS if c in presentes],
            "faltan": [c for c in dominio.CATEGORIAS if c not in presentes],
        }
    return salida


def resumen(cob):
    """Unidades con una sola categoría, sin producción y con las cuatro (en el orden del mapa)."""
    return {
        "unidades": len(cob),
        "con_una_categoria": [u for u, d in cob.items() if len(d["categorias"]) == 1],
        "sin_produccion": [u for u, d in cob.items() if "produccion" not in d["categorias"]],
        "completas": [u for u, d in cob.items() if not d["faltan"]],
    }


def tabla_markdown(cob):
    filas = ["| Unidad | Curso | Pasos | " + " | ".join(_ROTULOS[c] for c in dominio.CATEGORIAS) + " | Faltan |",
             "|---|---|---|" + "---|" * len(dominio.CATEGORIAS) + "---|"]
    for uid, d in cob.items():
        marcas = " | ".join("✅" if c in d["categorias"] else "—" for c in dominio.CATEGORIAS)
        faltan = ", ".join(_ROTULOS[c] for c in d["faltan"]) or "—"
        filas.append(f"| `{uid}` | {d['curso']} | {d['pasos']} | {marcas} | {faltan} |")
    return "\n".join(filas) + "\n"
