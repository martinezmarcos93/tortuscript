"""Motor de proyectos integradores V1.

Los proyectos son datos curriculares y su estado vive dentro del progreso del perfil.
No ejecuta código del alumno al validar: comprueba artefactos y criterios declarados.
La ejecución local del proyecto exportado ocurre fuera de TortuScript.
"""
import ast
import json
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "contenido" / "proyectos" / "catalogo.json"

BLOQUES_CURSO = {
    "python": "python-real",
    "web": "web-esencial",
    "sql": "sql-fundamentos",
}
MAX_ARCHIVOS = 20
MAX_ARCHIVO_BYTES = 120_000
MAX_PROYECTOS_INTEGRADORES = 20
MAX_AYUDAS_VISTAS = 50


class ErrorProyectoIntegrador(ValueError):
    """Error corregible por el alumno."""


def cargar_catalogo():
    with CATALOGO.open(encoding="utf-8") as f:
        datos = json.load(f)
    return datos["proyectos"]


def obtener_proyecto(proyecto_id):
    return next((p for p in cargar_catalogo() if p["id"] == proyecto_id), None)


def _curso_completo(progreso, curso_id):
    lecciones = progreso.get("lecciones") or {}
    prefijo = {
        "python-real": ("py-",),
        "web-esencial": ("web-",),
        "sql-fundamentos": ("sql-",),
    }.get(curso_id)
    if not prefijo:
        return False
    ids = [i for i in lecciones if any(i.startswith(x) for x in prefijo)]
    return bool(ids) and all(lecciones[i].get("completada") for i in ids)


def bloques_completados(progreso):
    return {bloque for bloque, curso in BLOQUES_CURSO.items() if _curso_completo(progreso, curso)}


def contexto(progreso):
    nivel = 1
    try:
        from .progreso import calcular_nivel
        nivel = calcular_nivel(progreso.get("xp_total", 0))[0]
    except (TypeError, ValueError) as e:
        # XP mal tipado en un progreso viejo: se sigue con el nivel inicial, pero queda registrado.
        logger.error("No se pudo calcular el nivel para los proyectos integradores: %s", e, exc_info=True)
    return {
        "bloques": sorted(bloques_completados(progreso)),
        "nivel": nivel,
        "experiencia": (progreso.get("config") or {}).get("experiencia"),
        "franja_edad": (progreso.get("config") or {}).get("franja_edad"),
    }


def _franja_perfil(progreso):
    franja = (progreso.get("config") or {}).get("franja_edad")
    if franja in {"exploradores", "constructores", "creadores", "desarrolladores"}:
        return franja
    return None


def _adaptacion(proyecto, progreso):
    franja = _franja_perfil(progreso)
    adaptaciones = proyecto.get("adaptaciones") or {}
    datos = adaptaciones.get(franja) or adaptaciones.get("default") or {}
    return {
        "franja": franja,
        "dificultad": datos.get("dificultad", proyecto.get("dificultad", "media")),
        "ayudas_maximas": int(datos.get("ayudas_maximas", MAX_AYUDAS_VISTAS)),
        "descripcion": datos.get("descripcion"),
    }


def disponibles(progreso):
    """Proyectos desbloqueados por currículo y compatibles con la franja, si existe."""
    hechos = bloques_completados(progreso)
    salida = []
    for p in cargar_catalogo():
        requeridos = set(p["bloques"])
        franja = _franja_perfil(progreso)
        compatibles = not franja or not p.get("franjas_edad") or franja in p["franjas_edad"]
        if len(requeridos & hechos) >= 2 and compatibles:
            salida.append({**p, "desbloqueado": True, "adaptacion": _adaptacion(p, progreso)})
        else:
            faltan = sorted(requeridos - hechos)
            motivo = "franja" if len(requeridos & hechos) >= 2 and not compatibles else "curriculo"
            salida.append({**p, "desbloqueado": False, "faltan_bloques": faltan, "motivo_bloqueo": motivo})
    return salida


def _limpiar_archivo(nombre):
    nombre = str(nombre or "").replace("\\", "/").strip().lstrip("/")
    partes = [p for p in nombre.split("/") if p not in ("", ".", "..")]
    if not partes or len(partes) > 4:
        raise ErrorProyectoIntegrador("Ese nombre de archivo no es válido.")
    limpio = "/".join(partes)
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", limpio):
        raise ErrorProyectoIntegrador("El nombre del archivo tiene caracteres que no usamos.")
    return limpio


def _normalizar_archivos(archivos):
    if not isinstance(archivos, dict):
        raise ErrorProyectoIntegrador("Los archivos del proyecto no son válidos.")
    if len(archivos) > MAX_ARCHIVOS:
        raise ErrorProyectoIntegrador("El proyecto tiene demasiados archivos.")
    salida = {}
    for nombre, codigo in archivos.items():
        nombre = _limpiar_archivo(nombre)
        codigo = str(codigo or "")
        if len(codigo.encode("utf-8")) > MAX_ARCHIVO_BYTES:
            raise ErrorProyectoIntegrador(f"El archivo {nombre} es demasiado grande.")
        salida[nombre] = codigo
    return salida


def iniciar(progreso, proyecto_id, hoy=None):
    proyecto = obtener_proyecto(proyecto_id)
    if not proyecto:
        raise ErrorProyectoIntegrador("Ese proyecto no existe.")
    if not any(p["id"] == proyecto_id and p["desbloqueado"] for p in disponibles(progreso)):
        raise ErrorProyectoIntegrador("Todavía necesitás completar más bloques para empezar este proyecto.")
    estados = progreso.setdefault("proyectos_integradores", {})
    if proyecto_id in estados:
        return proyecto_id
    if len(estados) >= MAX_PROYECTOS_INTEGRADORES:
        raise ErrorProyectoIntegrador("Ya tenés demasiados proyectos integradores guardados.")
    hoy = str(hoy or date.today())
    estados[proyecto_id] = {
        "creado": hoy,
        "actualizado": hoy,
        "archivos": _normalizar_archivos(proyecto.get("archivos_iniciales", {})),
        "etapas": {},
        "etapa_actual": 0,
        "ayudas_vistas": [],
        "completado": False,
    }
    return proyecto_id


def estado(progreso, proyecto_id):
    proyecto = obtener_proyecto(proyecto_id)
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id)
    if not proyecto or not datos:
        return None
    etapas = []
    for i, etapa in enumerate(proyecto["etapas"]):
        hecho = bool((datos.get("etapas") or {}).get(etapa["id"]))
        etapas.append({**etapa, "completada": hecho, "numero": i + 1})
    return {
        "id": proyecto_id,
        "titulo": proyecto["titulo"],
        "icono": proyecto.get("icono", "🧩"),
        "descripcion": proyecto["descripcion"],
        "bloques": proyecto["bloques"],
        "objetivo": proyecto["objetivo"],
        "archivos": dict(datos.get("archivos") or {}),
        "etapas": etapas,
        "etapa_actual": datos.get("etapa_actual", 0),
        "completado": bool(datos.get("completado")),
        "exportable": bool(datos.get("completado")),
        "contexto": contexto(progreso),
        "adaptacion": _adaptacion(proyecto, progreso),
    }


def guardar_archivo(progreso, proyecto_id, nombre, codigo, hoy=None):
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id)
    if not datos:
        raise ErrorProyectoIntegrador("Primero abrí el proyecto.")
    archivos = dict(datos.get("archivos") or {})
    nombre = _limpiar_archivo(nombre)
    codigo = str(codigo or "")
    if len(codigo.encode("utf-8")) > MAX_ARCHIVO_BYTES:
        raise ErrorProyectoIntegrador("Ese archivo es demasiado grande.")
    archivos[nombre] = codigo
    if len(archivos) > MAX_ARCHIVOS:
        raise ErrorProyectoIntegrador("El proyecto tiene demasiados archivos.")
    datos["archivos"] = archivos
    datos["actualizado"] = str(hoy or date.today())


def _criterio_ok(archivos, criterio):
    codigo = archivos.get(criterio.get("archivo"), "")
    if criterio.get("contiene"):
        return all(fragmento in codigo for fragmento in criterio["contiene"])
    if criterio.get("min_caracteres") is not None:
        return len(codigo) >= int(criterio["min_caracteres"])
    if criterio.get("python_valido"):
        try:
            ast.parse(codigo)
        except SyntaxError:
            return False
        return True
    return False


def validar_etapa(progreso, proyecto_id, etapa_id, hoy=None):
    proyecto = obtener_proyecto(proyecto_id)
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id)
    if not proyecto or not datos:
        raise ErrorProyectoIntegrador("Primero abrí el proyecto.")
    etapa = next((e for e in proyecto["etapas"] if e["id"] == etapa_id), None)
    if not etapa:
        raise ErrorProyectoIntegrador("Esa etapa no existe.")
    indice = next(i for i, e in enumerate(proyecto["etapas"]) if e["id"] == etapa_id)
    actual = int(datos.get("etapa_actual", 0))
    if indice > actual:
        return {"ok": False, "mensaje": "Primero completá la etapa anterior."}
    if not all(_criterio_ok(datos.get("archivos") or {}, c) for c in etapa["criterios"]):
        return {"ok": False, "mensaje": "Todavía falta algo para completar esta etapa."}
    datos.setdefault("etapas", {})[etapa_id] = True
    datos["etapa_actual"] = max(datos.get("etapa_actual", 0), indice + 1)
    if datos["etapa_actual"] >= len(proyecto["etapas"]):
        datos["completado"] = True
    datos["actualizado"] = str(hoy or date.today())
    return {"ok": True, "completado": datos["completado"]}


def ayudas(progreso, proyecto_id):
    proyecto = obtener_proyecto(proyecto_id)
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id)
    if not proyecto or not datos:
        return []
    nivel = contexto(progreso)["nivel"]
    limite = _adaptacion(proyecto, progreso)["ayudas_maximas"]
    vistas = set(datos.get("ayudas_vistas") or [])
    salida = []
    for ayuda in proyecto.get("ayudas", []):
        desbloqueada = nivel >= int(ayuda.get("min_nivel", 1))
        salida.append({**ayuda, "desbloqueada": desbloqueada, "vista": ayuda["id"] in vistas})
    return salida


def ver_ayuda(progreso, proyecto_id, ayuda_id):
    proyecto = obtener_proyecto(proyecto_id)
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id)
    if not proyecto or not datos:
        raise ErrorProyectoIntegrador("Primero abrí el proyecto.")
    ayuda = next((a for a in proyecto.get("ayudas", []) if a["id"] == ayuda_id), None)
    if not ayuda:
        raise ErrorProyectoIntegrador("Esa ayuda no existe.")
    if contexto(progreso)["nivel"] < int(ayuda.get("min_nivel", 1)):
        raise ErrorProyectoIntegrador("Esa ayuda todavía no está desbloqueada.")
    vistas = datos.setdefault("ayudas_vistas", [])
    limite = _adaptacion(proyecto, progreso)["ayudas_maximas"]
    if ayuda_id not in vistas:
        if len(vistas) >= limite:
            raise ErrorProyectoIntegrador("Ya usaste muchas ayudas en este proyecto.")
        vistas.append(ayuda_id)
    return ayuda["texto"]


def resumen_catalogo(progreso):
    hechos = bloques_completados(progreso)
    return [
        {
            "id": p["id"], "titulo": p["titulo"], "icono": p.get("icono", "🧩"),
            "descripcion": p["descripcion"], "bloques": p["bloques"],
            "desbloqueado": len(set(p["bloques"]) & hechos) >= 2,
            "iniciado": p["id"] in (progreso.get("proyectos_integradores") or {}),
            "completado": bool((progreso.get("proyectos_integradores") or {}).get(p["id"], {}).get("completado")),
            "adaptacion": _adaptacion(p, progreso),
        }
        for p in cargar_catalogo()
    ]


def exportar(progreso, proyecto_id):
    """Genera el ZIP del proyecto terminado en memoria. No ejecuta ninguno de sus archivos."""
    import io
    import zipfile
    proyecto = obtener_proyecto(proyecto_id)
    datos = (progreso.get("proyectos_integradores") or {}).get(proyecto_id)
    if not proyecto or not datos:
        raise ErrorProyectoIntegrador("Primero abrí el proyecto.")
    if not datos.get("completado"):
        raise ErrorProyectoIntegrador("Terminá todas las etapas antes de descargar el proyecto.")
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for nombre, codigo in (datos.get("archivos") or {}).items():
            z.writestr(nombre, codigo)
        z.writestr("TORTUSCRIPT_PROYECTO.txt",
                   "Proyecto creado con TortuScript.\n"
                   "Abrilo en una carpeta y seguí las instrucciones de README.md si existe.\n")
    return salida.getvalue(), proyecto["id"] + ".zip"


def validar_catalogo():
    """Valida la integridad estructural del catálogo sin ejecutar código de alumnos."""
    errores = []
    ids = set()
    for proyecto in cargar_catalogo():
        pid = proyecto.get("id")
        if not pid or pid in ids:
            errores.append(f"id de proyecto duplicado o vacío: {pid!r}")
        ids.add(pid)
        if len(set(proyecto.get("bloques", []))) < 2:
            errores.append(f"{pid}: necesita al menos dos bloques")
        if not proyecto.get("franjas_edad"):
            errores.append(f"{pid}: faltan franjas_edad")
        archivos = proyecto.get("archivos_iniciales") or {}
        try:
            _normalizar_archivos(archivos)
        except ErrorProyectoIntegrador as exc:
            errores.append(f"{pid}: archivos iniciales inválidos: {exc}")
        etapas = proyecto.get("etapas") or []
        if not etapas:
            errores.append(f"{pid}: no tiene etapas")
        for i, etapa in enumerate(etapas):
            if not etapa.get("id") or not etapa.get("criterios"):
                errores.append(f"{pid}: etapa {i + 1} incompleta")
            for criterio in etapa.get("criterios", []):
                if criterio.get("archivo") not in archivos:
                    errores.append(f"{pid}: criterio referencia archivo inexistente {criterio.get('archivo')!r}")
        adaptaciones = proyecto.get("adaptaciones") or {}
        for franja, datos in adaptaciones.items():
            if franja != "default" and franja not in proyecto.get("franjas_edad", []):
                errores.append(f"{pid}: adaptación para franja incompatible {franja}")
            if int(datos.get("ayudas_maximas", 0)) < 0:
                errores.append(f"{pid}: ayudas_maximas inválido para {franja}")
    return errores
