"""
Práctica del día: repaso espaciado (cajas de Leitner) e intercalado (se mezclan lecciones).

Cada paso rápido de una lección terminada (elegir, predecir, completar, ordenar) es una "tarjeta"
que se vuelve a ver cada vez más espaciada mientras se responda bien al primer intento:
caja 0 (nuevo) → 1 → 2 → 3 → 4 → 5, con INTERVALOS de días entre repasos. Un error la manda de
vuelta a la caja 1 (mañana). Sin castigos: solo se reprograma.

Todo es puro: recibe `hoy` y los cursos, no toca disco.

Registros dañados (JSON válido con datos internos mal formados): se AISLAN. Una tarjeta o un paso que no se
puede interpretar con seguridad no se ofrece, no se «corrige» ni recibe un vencimiento inventado; lo sano de al
lado sigue funcionando y nada se reescribe al leer (ver `diagnosticar` y docs/audits/ROBUSTEZ_REGISTROS_PROGRESO.md).
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

INTERVALOS = (1, 2, 4, 8, 16)          # días de espera al pasar a la caja 1..5
MAX_CAJA = len(INTERVALOS)
TIPOS = ("elegir", "predecir", "completar", "ordenar")
POR_SESION = 6
MAX_POR_LECCION = 2
XP_ACIERTO = 2                          # XP por acertar al primer intento en la práctica
XP_MAXIMO_DIARIO = 12


def clave(leccion_id, paso):
    return f"{leccion_id}:{paso}"


_SIN_TARJETA = object()                 # centinela: «no hay tarjeta guardada» (distinto de una tarjeta guardada como None)


def _fecha_iso(valor):
    """date si `valor` es una cadena AAAA-MM-DD canónica y real; None en cualquier otro caso (sin excepciones)."""
    if not isinstance(valor, str):
        return None
    try:
        fecha = date.fromisoformat(valor)
    except ValueError:
        return None
    return fecha if fecha.isoformat() == valor else None      # rechaza formas que Python acepta pero no escribimos


def _caja_valida(caja):
    return isinstance(caja, int) and not isinstance(caja, bool) and 0 <= caja <= MAX_CAJA


def _contador_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def _indice_de_paso(indice_s):
    """Índice de paso (>= 0) si la clave es la forma canónica que escribimos ("0", "1", ...); None si no."""
    # Los índices de pasos son pequeños; evitar int() para claves arbitrariamente largas.
    if isinstance(indice_s, str) and len(indice_s) <= 10 and indice_s.isascii() and indice_s.isdigit() and str(int(indice_s)) == indice_s:
        return int(indice_s)
    return None


def fecha_programada(tarjeta):
    """Fecha `proximo` de una tarjeta de repaso, o None si no hay una válida (no es objeto, falta o está dañada)."""
    return _fecha_iso(tarjeta.get("proximo")) if isinstance(tarjeta, dict) else None


def _analizar(progreso, cursos, hoy):
    """([candidatos], [defectos]). Un defecto es {leccion, paso, motivo}: ese registro se aísla y se sigue."""
    por_id = {lec["id"]: lec for curso in cursos for seccion in curso["secciones"] for lec in seccion["lecciones"]}
    lecciones = progreso.get("lecciones")
    repaso = progreso.get("repaso")
    lecciones = lecciones if isinstance(lecciones, dict) else {}
    repaso = repaso if isinstance(repaso, dict) else {}
    salida, defectos = [], []

    def defecto(leccion_id, paso, motivo):
        if isinstance(paso, str) and len(paso) > 20:
            paso = paso[:20] + "…"                       # una clave dañada enorme no debe inflar el log
        defectos.append({"leccion": leccion_id, "paso": paso, "motivo": motivo})

    for leccion_id, datos in lecciones.items():
        lec = por_id.get(leccion_id)
        if lec is None:
            continue
        if not isinstance(datos, dict):
            defecto(leccion_id, None, "el registro de la lección no es un objeto")
            continue
        pasos = datos.get("pasos")
        if pasos is None:
            pasos = {}
        if not isinstance(pasos, dict):
            defecto(leccion_id, None, "los pasos de la lección no son un objeto")
            continue
        for indice_s, registro in pasos.items():
            indice = _indice_de_paso(indice_s)
            if indice is None:
                defecto(leccion_id, indice_s, "la clave del paso no es un índice")
                continue
            if indice >= len(lec["pasos"]) or lec["pasos"][indice]["tipo"] not in TIPOS:
                continue
            if not isinstance(registro, dict):
                defecto(leccion_id, indice, "el registro del paso no es un objeto")
                continue
            tarjeta = repaso.get(clave(leccion_id, indice), _SIN_TARJETA)
            caja, programado = 0, None
            if tarjeta is not _SIN_TARJETA:
                if not isinstance(tarjeta, dict):
                    defecto(leccion_id, indice, "la tarjeta de repaso no es un objeto")
                    continue
                caja = tarjeta.get("caja", 0)
                if not _caja_valida(caja):
                    defecto(leccion_id, indice, "la caja de la tarjeta no es un entero entre 0 y %d" % MAX_CAJA)
                    continue
                proximo = tarjeta.get("proximo")
                if proximo is not None and proximo != "":         # solo None, vacío o ausente = sin programar
                    programado = _fecha_iso(proximo)
                    if programado is None:
                        defecto(leccion_id, indice, "la fecha `proximo` de la tarjeta no es AAAA-MM-DD")
                        continue
            if programado is not None:
                vence = programado                                # lo programado manda sobre la fecha del paso
            elif registro.get("fecha"):                           # sin fecha (progreso viejo): ya toca
                terminado = _fecha_iso(registro["fecha"])
                if terminado is None or terminado >= date.max:
                    defecto(leccion_id, indice, "la fecha del paso no es AAAA-MM-DD")
                    continue
                vence = terminado + timedelta(days=1)             # un paso nuevo toca un día después de terminarlo
            else:
                vence = date.min
            if vence <= hoy:
                salida.append({"leccion": leccion_id, "paso": indice,
                               "vencido": (hoy - vence).days if vence > date.min else 9999, "caja": caja})
    return salida, defectos



def candidatos(progreso, cursos, hoy):
    """Tarjetas que ya tocan, de las lecciones donde hay pasos terminados:
    [{leccion, paso, vencido, caja}] (vencido = días de atraso). Los registros dañados se ignoran y se avisa en el log."""
    salida, defectos = _analizar(progreso, cursos, hoy)
    if defectos:
        logger.warning("Repaso: %d registro(s) del progreso dañado(s) ignorado(s) (no se modifican): %s",
                       len(defectos), "; ".join(f"{d['leccion']}:{d['paso']} {d['motivo']}" for d in defectos[:5]))
    return salida


def diagnosticar(progreso, cursos, hoy=None):
    """Registros del progreso que el repaso ignora por estar dañados: [{leccion, paso, motivo}]. No modifica nada."""
    return _analizar(progreso, cursos, hoy or date.today())[1]


def pendientes(progreso, cursos, hoy):
    return len(candidatos(progreso, cursos, hoy))


def elegir(progreso, cursos, hoy, cantidad=POR_SESION):
    """La sesión de hoy: lo más atrasado primero e INTERCALANDO lecciones (a lo sumo 2 por lección),
    así no se practica siempre lo mismo seguido. Devuelve [(leccion_id, paso)]."""
    grupos = {}
    for c in candidatos(progreso, cursos, hoy):
        grupos.setdefault(c["leccion"], []).append(c)
    for lista in grupos.values():
        lista.sort(key=lambda c: (-c["vencido"], c["caja"], c["paso"]))
    orden = sorted(grupos, key=lambda l: (-grupos[l][0]["vencido"], l))            # primero la lección más atrasada
    elegidas, ronda = [], 0
    limite = max(MAX_POR_LECCION, -(-cantidad // max(1, len(orden))))        # con pocas lecciones, algo más por lección
    while len(elegidas) < cantidad and ronda < limite:
        for leccion_id in orden:
            if len(grupos[leccion_id]) > ronda and len(elegidas) < cantidad:
                elegidas.append((leccion_id, grupos[leccion_id][ronda]["paso"]))
        ronda += 1
    return elegidas


def registrar(progreso, leccion_id, paso, acierto, hoy):
    """Reprograma la tarjeta. Acierto al primer intento: sube de caja; si no, vuelve a la caja 1 (mañana).

    Si la tarjeta guardada está dañada (no es un objeto, o su caja/contadores no son enteros válidos) no hay
    información que preservar: se parte de cero con lo que sí es válido, y se deja constancia en el log."""
    tarjetas = progreso.get("repaso")
    if not isinstance(tarjetas, dict):
        tarjetas = progreso["repaso"] = {}
    k = clave(leccion_id, paso)
    t = tarjetas.get(k)
    if not isinstance(t, dict):
        if k in tarjetas:
            logger.warning("Repaso: la tarjeta %s estaba dañada (no era un objeto); se reinicia", k)
        t = tarjetas[k] = {}
    for campo, valido in (("caja", _caja_valida), ("aciertos", _contador_valido), ("fallos", _contador_valido)):
        if not valido(t.get(campo, 0)):
            logger.warning("Repaso: %s.%s estaba dañado (%.60r); se reinicia a 0", k, campo, t[campo])
            t[campo] = 0
        t.setdefault(campo, 0)
    if acierto:
        t["caja"] = min(t["caja"] + 1, MAX_CAJA)
        t["aciertos"] += 1
    else:
        t["caja"] = 1
        t["fallos"] += 1
    t["proximo"] = str(hoy + timedelta(days=INTERVALOS[t["caja"] - 1]))
    return t
