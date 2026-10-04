"""Motor educativo de progreso: XP, lecciones, práctica y gamificación.

La persistencia local de archivos y la identidad de perfiles están aisladas en
`persistencia_local.py`.
"""
import copy
import re
from datetime import date, timedelta

from . import practica

VERSION_ESQUEMA = 11


PROGRESO_INICIAL = {
    "version": VERSION_ESQUEMA,
    "xp_total": 0,
    "ejercicios": {},
    "racha": 0,
    "racha_max": 0,
    "ultimo_dia": None,       # "YYYY-MM-DD"
    "dias_activo": [],        # lista de "YYYY-MM-DD" únicos, últimos 90
    "sesion_hoy": [],         # índices completados en `ultimo_dia`
    # Lecciones (v3): {leccion_id: {"pasos": {"0": {"xp": 5, "perfecto": true}}, "completada": bool, "perfecta": bool}}
    "lecciones": {},
    # Configuración del chico (v4): se completa en el onboarding y se cambia desde el resumen.
    "config": {"onboarding": False, "nombre": None, "experiencia": None, "meta_min": 10,
               # Accesibilidad (v8): la elige cada chico y la aplica el servidor al dibujar cada página
               "ajustes": {"tam": "normal", "contraste": "normal", "movimiento": "normal",
                           "letra": "normal", "voz": "no", "velocidad": "normal"}},
    # XP ganado por día (últimos 30), para la meta diaria.
    "xp_por_dia": {},
    # Gamificación amable (v5): sin vidas ni compras; todo se gana jugando.
    "congeladores": 0,        # protegen la racha si se falta UN día (se ganan cada 7 días de racha)
    "dias_congelados": [],    # días que un congelador salvó (últimos 30)
    "dias_meta": [],          # días en que se cumplió la meta diaria (últimos 60)
    "logros": {},             # {id_logro: "YYYY-MM-DD"}
    "liga": {"nivel": 0, "semana": None},
    "stats": {"congeladores_ganados": 0},
    "avisos": [],             # cosas para contarle al chico (logro nuevo, congelador...) hasta que se muestren
    # Práctica del día (v6): tarjetas de repaso espaciado {"leccion:paso": {caja, proximo, aciertos, fallos}}
    "repaso": {},
    "xp_practica": {},        # XP ganado practicando por día (tope diario), últimos 7 días
    "proyectos": {},          # Mis proyectos (v7): {id: {nombre, tipo, codigo, creado, actualizado}}\n    "proyectos_integradores": {},  # Proyectos integradores V1: estado, archivos, etapas y ayudas
    # Diagnóstico (v9, ADR-004): lecciones salteadas al elegir dónde empezar {leccion_id: "YYYY-MM-DD"}.
    # No cuentan como hechas (sin XP, logros, liga ni certificado); solo dejan pasar el camino.
    "salteadas": {},
    # Intereses (v10, ADR-005): {encuesta_id: {"respuestas": [...], "fecha", "omitida"?}}. Solo local, sin texto libre.
    "intereses": {},
    # Recorrido inicial elegido después de Nivel 0: "web" o "python".
    "recorrido_inicial": None,
}


def _migrar(data):
    # Los archivos históricos pueden ser JSON válido pero contener tipos incorrectos
    # en campos anidados. Normalizarlos evita que un ajuste roto inutilice el perfil.
    for campo, valor in PROGRESO_INICIAL.items():
        actual = data.get(campo)
        if campo not in data or (
            isinstance(valor, (dict, list)) and not isinstance(actual, type(valor))
        ):
            data[campo] = copy.deepcopy(valor)

    # Configuración y ajustes se migran por separado porque pueden venir de esquemas
    # antiguos parcialmente completos. No reemplazar los valores válidos del alumno.
    if not isinstance(data.get("config"), dict):
        data["config"] = copy.deepcopy(PROGRESO_INICIAL["config"])
    for clave, valor in PROGRESO_INICIAL["config"].items():
        actual = data["config"].get(clave)
        if clave not in data["config"] or (
            isinstance(valor, (dict, list)) and not isinstance(actual, type(valor))
        ):
            data["config"][clave] = copy.deepcopy(valor)
    if not isinstance(data["config"].get("ajustes"), dict):
        data["config"]["ajustes"] = copy.deepcopy(PROGRESO_INICIAL["config"]["ajustes"])
    for clave, valor in PROGRESO_INICIAL["config"]["ajustes"].items():
        data["config"]["ajustes"].setdefault(clave, copy.deepcopy(valor))

    data["version"] = VERSION_ESQUEMA
    return data



# ─────────────────────────────────────────
# CONFIGURACIÓN, XP Y META DIARIA
# ─────────────────────────────────────────
EXPERIENCIAS = ("nunca", "poquito", "bastante")
# Dónde puede empezar quien ya programó (ADR-004, primera versión: solo un punto de entrada, al comienzo de una
# sección del curso 1). "nunca" empieza siempre por el principio.
PUNTOS_DE_ENTRADA = {"poquito": "tu-primera-variable", "bastante": "si-es-grande"}
METAS_MIN = (5, 10, 15)
XP_POR_MINUTO = 4                 # meta de 5 min = 20 XP, 10 min = 40 XP, 15 min = 60 XP


def sanitizar_perfil(nombre):
    """Normaliza un nombre de perfil para los usos legacy que aún requieren un identificador seguro."""
    nombre = (nombre or "").strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9ñáéíóúü_-]", "", nombre)[:30]


def avisar(progreso, tipo, **datos):
    """Deja anotado algo para contarle al chico (la web lo muestra y lo saca con tomar_avisos)."""
    progreso.setdefault("avisos", []).append({"tipo": tipo, **datos})


def tomar_avisos(progreso):
    """Devuelve los avisos pendientes y los borra."""
    avisos = progreso.get("avisos") or []
    if avisos:
        progreso["avisos"] = []
    return avisos


def sumar_xp(progreso, cantidad, hoy=None):
    """Suma XP al total y al del día (para la meta diaria). Ignora cantidades <= 0.
    Avisa la primera vez que en el día se llega a la meta."""
    if cantidad <= 0:
        return
    hoy_s = str(hoy or date.today())
    meta = meta_diaria_xp(progreso)
    progreso["xp_total"] = progreso.get("xp_total", 0) + cantidad
    por_dia = progreso.setdefault("xp_por_dia", {})
    antes = por_dia.get(hoy_s, 0)
    por_dia[hoy_s] = antes + cantidad
    for viejo in sorted(por_dia)[:-30]:
        del por_dia[viejo]
    if antes < meta <= por_dia[hoy_s]:
        dias = progreso.setdefault("dias_meta", [])
        if hoy_s not in dias:
            dias.append(hoy_s)
            progreso["dias_meta"] = dias[-60:]
        avisar(progreso, "meta_cumplida", xp=meta)


def meta_diaria_xp(progreso):
    minutos = progreso.get("config", {}).get("meta_min", 10)
    return XP_POR_MINUTO * (minutos if minutos in METAS_MIN else 10)


def xp_de_hoy(progreso, hoy=None):
    return progreso.get("xp_por_dia", {}).get(str(hoy or date.today()), 0)


def necesita_onboarding(progreso):
    """Un perfil nuevo pasa por la bienvenida; uno con progreso previo (de antes de que existiera)
    no tiene que volver a empezar."""
    if progreso.get("config", {}).get("onboarding"):
        return False
    hay_avance = progreso.get("xp_total", 0) > 0 or progreso.get("ejercicios") or progreso.get("lecciones")
    return not hay_avance


# Cada ajuste y sus valores válidos (el primero es el de fábrica).
AJUSTES = {
    "tam": ("normal", "grande", "enorme"),          # tamaño de letra
    "contraste": ("normal", "alto"),
    "movimiento": ("normal", "reducido"),           # animaciones
    "letra": ("normal", "legible"),                 # tipografía sencilla y más espaciada
    "voz": ("no", "si"),                            # leer las consignas en voz alta automáticamente
    "velocidad": ("lenta", "normal", "rapida"),     # de la voz
}


def guardar_ajustes(progreso, **cambios):
    """Cambia ajustes de accesibilidad. Devuelve False (sin cambiar nada) si algún valor no es válido."""
    for nombre, valor in cambios.items():
        if valor is not None and valor not in AJUSTES.get(nombre, ()):
            return False
    ajustes = progreso.setdefault("config", copy.deepcopy(PROGRESO_INICIAL["config"])).setdefault(
        "ajustes", copy.deepcopy(PROGRESO_INICIAL["config"]["ajustes"]))
    for nombre, valor in cambios.items():
        if valor is not None:
            ajustes[nombre] = valor
    return True


def ajustes_de(progreso):
    """Los ajustes vigentes (con los de fábrica donde falte alguno)."""
    base = copy.deepcopy(PROGRESO_INICIAL["config"]["ajustes"])
    base.update({k: v for k, v in (progreso.get("config", {}).get("ajustes") or {}).items() if v in AJUSTES.get(k, ())})
    return base


def saltear_hasta(progreso, lecciones_en_orden, entrada, hoy=None):
    """Marca como salteadas por diagnóstico las lecciones anteriores a `entrada` que no estaban hechas.
    No toca XP, logros ni lecciones hechas: el progreso solo crece (ADR-002)."""
    if entrada not in lecciones_en_orden:
        raise ValueError(f"lección de entrada desconocida: {entrada!r}")
    salteadas = progreso.setdefault("salteadas", {})
    hechas = progreso.get("lecciones", {})
    for leccion_id in lecciones_en_orden[:lecciones_en_orden.index(entrada)]:
        if not hechas.get(leccion_id, {}).get("completada"):
            salteadas.setdefault(leccion_id, str(hoy or date.today()))
    return True


def guardar_config(progreso, experiencia=None, meta_min=None, nombre=None, onboarding=None):
    """Valida y guarda la configuración. Devuelve False si algún valor no es válido."""
    cfg = progreso.setdefault("config", copy.deepcopy(PROGRESO_INICIAL["config"]))
    if experiencia is not None:
        if experiencia not in EXPERIENCIAS:
            return False
        cfg["experiencia"] = experiencia
    if meta_min is not None:
        if meta_min not in METAS_MIN:
            return False
        cfg["meta_min"] = meta_min
    if nombre is not None:
        cfg["nombre"] = nombre[:30]
    if onboarding is not None:
        cfg["onboarding"] = bool(onboarding)
    return True


# ─────────────────────────────────────────
# RACHA DIARIA
# ─────────────────────────────────────────
MAX_CONGELADORES = 2
DIAS_RETO = 7                     # el reto de racha: cada 7 días seguidos se gana un congelador


def actualizar_racha(progreso, hoy=None):
    """
    Llamar cuando el usuario completa un ejercicio.
    Retorna (racha_actual, es_dia_nuevo).

    Si se faltó UN solo día y hay un congelador, se usa solo y la racha sigue. Cada 7 días
    seguidos se gana un congelador (hasta 2 guardados).
    """
    hoy = hoy or date.today()
    hoy_s = str(hoy)
    ultimo = progreso.get("ultimo_dia")

    if ultimo == hoy_s:
        return progreso.get("racha", 1), False

    ayer = hoy - timedelta(days=1)
    if ultimo == str(ayer):
        progreso["racha"] = progreso.get("racha", 0) + 1
    elif ultimo == str(hoy - timedelta(days=2)) and progreso.get("congeladores", 0) > 0:
        progreso["congeladores"] -= 1
        congelados = progreso.setdefault("dias_congelados", [])
        congelados.append(str(ayer))
        progreso["dias_congelados"] = congelados[-30:]
        progreso["racha"] = progreso.get("racha", 0) + 1
        avisar(progreso, "congelador_usado", racha=progreso["racha"])
    else:
        progreso["racha"] = 1
    if progreso["racha"] % DIAS_RETO == 0:
        _ganar_congelador(progreso)

    progreso["racha_max"] = max(progreso.get("racha_max", 0), progreso["racha"])
    progreso["ultimo_dia"] = hoy_s

    dias = progreso.get("dias_activo", [])
    if hoy_s not in dias:
        dias.append(hoy_s)
    progreso["dias_activo"] = dias[-90:]

    # Día nuevo → la sesión de hoy arranca vacía
    progreso["sesion_hoy"] = []
    return progreso["racha"], True


def _ganar_congelador(progreso):
    if progreso.get("congeladores", 0) < MAX_CONGELADORES:
        progreso["congeladores"] = progreso.get("congeladores", 0) + 1
        avisar(progreso, "congelador_ganado", racha=progreso["racha"])
    stats = progreso.setdefault("stats", {})
    stats["congeladores_ganados"] = stats.get("congeladores_ganados", 0) + 1


def regreso(progreso, hoy=None):
    """Qué contarle al chico cuando vuelve un día nuevo: {"dias": desde la última vez, "xp": lo que ganó ese día}.
    None si nunca practicó o si ya vino hoy. Solo cuenta lo bueno: no reta por los días que faltó."""
    hoy = hoy or date.today()
    try:
        ultimo = date.fromisoformat(progreso.get("ultimo_dia") or "")
    except ValueError:
        return None
    dias = (hoy - ultimo).days
    if dias < 1:
        return None
    return {"dias": dias, "xp": int((progreso.get("xp_por_dia") or {}).get(ultimo.isoformat(), 0) or 0)}


def racha_vigente(progreso, hoy=None):
    """La racha que corresponde mostrar: si el último día jugado fue antes de ayer,
    la racha ya se cortó (aunque el archivo todavía guarde el número viejo).
    Si se faltó un solo día y hay un congelador, sigue viva: al volver a jugar lo usa."""
    hoy = hoy or date.today()
    ultimo = progreso.get("ultimo_dia")
    if ultimo in (str(hoy), str(hoy - timedelta(days=1))):
        return progreso.get("racha", 0)
    if ultimo == str(hoy - timedelta(days=2)) and progreso.get("congeladores", 0) > 0:
        return progreso.get("racha", 0)
    return 0


def racha_protegida(progreso, hoy=None):
    """True si hoy todavía no se jugó y la racha se salvaría con un congelador."""
    hoy = hoy or date.today()
    return progreso.get("ultimo_dia") == str(hoy - timedelta(days=2)) and progreso.get("congeladores", 0) > 0


def reto_de_racha(progreso, hoy=None):
    """Progreso del reto de 7 días: (días_seguidos_del_reto_actual, total).
    Al llegar a 7 se gana el congelador y el reto arranca de nuevo."""
    racha = racha_vigente(progreso, hoy)
    if racha == 0:
        return 0, DIAS_RETO
    resto = racha % DIAS_RETO
    return (resto if resto else DIAS_RETO), DIAS_RETO


def registrar_sesion_hoy(progreso, indice):
    sesion = progreso.get("sesion_hoy", [])
    if indice not in sesion:
        sesion.append(indice)
    progreso["sesion_hoy"] = sesion


# ─────────────────────────────────────────
# REGISTRO DE EJERCICIO
# ─────────────────────────────────────────
def registrar_ejercicio(progreso, indice, estrellas, xp_ganado):
    """Registra un ejercicio RESUELTO. Solo suma XP si mejora el puntaje anterior."""
    key = str(indice)
    anterior = progreso["ejercicios"].get(key, {})
    hubo_mejora = estrellas > anterior.get("estrellas", 0)

    if hubo_mejora:
        sumar_xp(progreso, xp_ganado - anterior.get("xp", 0))
        progreso["ejercicios"][key] = {"estrellas": estrellas, "xp": xp_ganado, "completado": True}

    if estrellas >= 1:
        actualizar_racha(progreso)
        registrar_sesion_hoy(progreso, indice)

    return hubo_mejora


# ─────────────────────────────────────────
# PRÁCTICA DEL DÍA
# ─────────────────────────────────────────
def registrar_practica(progreso, leccion_id, paso, acierto, hoy=None):
    """Anota un paso practicado: reprograma su tarjeta, suma un poco de XP (con tope diario) y cuenta
    como actividad del día. `acierto` = respondió bien al primer intento. Guarda. Devuelve el XP ganado."""
    hoy = hoy or date.today()
    hoy_s = str(hoy)
    practica.registrar(progreso, leccion_id, paso, acierto, hoy)
    por_dia = progreso.setdefault("xp_practica", {})
    ganado = 0
    if acierto:
        ganado = max(0, min(practica.XP_ACIERTO, practica.XP_MAXIMO_DIARIO - por_dia.get(hoy_s, 0)))
        por_dia[hoy_s] = por_dia.get(hoy_s, 0) + ganado
        for viejo in sorted(por_dia)[:-7]:
            del por_dia[viejo]
        sumar_xp(progreso, ganado, hoy)
    actualizar_racha(progreso, hoy)
    return ganado


# ─────────────────────────────────────────
# LECCIONES
# ─────────────────────────────────────────
def registrar_paso_leccion(progreso, leccion_id, indice, xp, perfecto, total_pasos, estrellas=None):
    """Anota un paso terminado de una lección y guarda.

    Se recuerda el MEJOR resultado de cada paso: repetir una lección nunca da XP doble, solo
    suma la diferencia si el resultado mejora. Los pasos 'escribir' se pagan por
    registrar_ejercicio (xp=0 acá) y solo se anotan para saber si la lección está completa.
    Devuelve {"xp_ganado", "completa", "perfecta", "recien_completa"}.
    """
    lec = progreso.setdefault("lecciones", {}).setdefault(
        leccion_id, {"pasos": {}, "completada": False, "perfecta": False})
    antes = lec["pasos"].get(str(indice), {"xp": 0, "perfecto": False})
    mejor = {"xp": max(antes["xp"], xp), "perfecto": bool(antes["perfecto"] or perfecto),
             "fecha": antes.get("fecha") or str(date.today())}         # la práctica del día parte de acá
    if estrellas is not None or "estrellas" in antes:                # pasos 'escribir' de cursos sin ejercicio
        mejor["estrellas"] = max(antes.get("estrellas", 0), estrellas or 0)
    ganado = mejor["xp"] - antes["xp"]
    lec["pasos"][str(indice)] = mejor
    sumar_xp(progreso, ganado)

    estaba_completa = lec["completada"]
    lec["completada"] = lec["completada"] or all(str(i) in lec["pasos"] for i in range(total_pasos))
    lec["perfecta"] = lec["completada"] and all(
        lec["pasos"].get(str(i), {}).get("perfecto") for i in range(total_pasos))
    actualizar_racha(progreso)
    return {"xp_ganado": ganado, "completa": lec["completada"], "perfecta": lec["perfecta"],
            "recien_completa": lec["completada"] and not estaba_completa}


# ─────────────────────────────────────────
# RESUMEN DE SESIÓN DE HOY
# ─────────────────────────────────────────
CONCEPTO_NIVEL = {
    1: "Mostrar texto",
    2: "Variables",
    3: "Entrada de datos",
    4: "Operaciones matemáticas",
    5: "Condicionales (si/sino)",
    6: "Bucles (repetir)",
    7: "Funciones",
    8: "Desafíos combinados",
}


def resumen_sesion_hoy(progreso, ejercicios_lista, hoy=None):
    hoy = hoy or date.today()
    # `sesion_hoy` solo vale si el último día jugado es hoy
    indices_hoy = progreso.get("sesion_hoy", []) if progreso.get("ultimo_dia") == str(hoy) else []
    completados, xp_hoy, niveles_vistos = [], 0, set()

    for idx in indices_hoy:
        if idx < len(ejercicios_lista):
            ej = ejercicios_lista[idx]
            datos = progreso["ejercicios"].get(str(idx), {})
            completados.append({
                "titulo": ej["titulo"],
                "estrellas": datos.get("estrellas", 0),
                "xp": datos.get("xp", 0),
            })
            xp_hoy += datos.get("xp", 0)
            niveles_vistos.add(ej["nivel"])

    conceptos = [CONCEPTO_NIVEL[nv] for nv in sorted(niveles_vistos) if nv in CONCEPTO_NIVEL]
    return {"completados": completados, "xp_ganado_hoy": xp_hoy, "conceptos": conceptos}


def calendario_semana(progreso, hoy=None):
    """Los últimos 7 días (el más viejo primero) para el mini calendario del resumen."""
    hoy = hoy or date.today()
    activos = set(progreso.get("dias_activo", []))
    congelados = set(progreso.get("dias_congelados", []))
    dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
    return [{"dia": d.day, "fecha": str(d), "activo": str(d) in activos, "hoy": d == hoy,
             "congelado": str(d) in congelados}
            for d in dias]


# ─────────────────────────────────────────
# NIVEL Y UTILIDADES
# ─────────────────────────────────────────
# Con el curso completo (30 ejercicios a 30 XP + 143 pasos a 5 XP) el máximo es 1460: el nivel 10
# tiene que ser alcanzable, pero solo hacia el final. tests/test_progreso.py lo verifica.
UMBRALES_NIVEL = [0, 80, 180, 300, 440, 600, 780, 980, 1200, 1350]
_TRAMO_FINAL = 100


def calcular_nivel(xp):
    """Retorna (nivel, xp_en_nivel, xp_para_siguiente)."""
    nivel = 1
    for i, umbral in enumerate(UMBRALES_NIVEL):
        if xp >= umbral:
            nivel = i + 1
    base = UMBRALES_NIVEL[nivel - 1]
    if nivel < len(UMBRALES_NIVEL):
        return nivel, xp - base, UMBRALES_NIVEL[nivel] - base
    return nivel, min(xp - base, _TRAMO_FINAL), _TRAMO_FINAL


def estrellas_texto(n):
    return "⭐" * n + "☆" * (3 - n)


def titulo_nivel(nivel):
    titulos = {
        1: "🐣 Aprendiz",
        2: "🐢 Tortuga",
        3: "🐍 Serpiente",
        4: "🦎 Lagarto",
        5: "🦅 Águila",
        6: "🔥 Dragón",
        7: "💎 Cristal",
        8: "🚀 Cohete",
        9: "⚡ Rayo",
        10: "🏆 Maestro",
    }
    return titulos.get(nivel, "🏆 Maestro")


# Color del CUERPO de la tortuga según el nivel: muestra el progreso del chico. No es el color del lápiz
# (ese arranca siempre en verde y es parte del dibujo que se compara). Todos contrastan ≥ 3:1 con el
# fondo blanco del lienzo (tests/test_progreso.py lo verifica); el nivel 1 es el verde de siempre.
COLORES_TORTUGA = {
    1: "#16a34a",   # verde
    2: "#0d9488",   # turquesa
    3: "#2563eb",   # azul
    4: "#7c3aed",   # violeta
    5: "#c026d3",   # fucsia
    6: "#dc2626",   # rojo
    7: "#c2410c",   # naranja
    8: "#a16207",   # dorado
    9: "#7c2d12",   # marrón
    10: "#111827",  # negro
}


def color_tortuga(nivel):
    return COLORES_TORTUGA[min(max(nivel, 1), max(COLORES_TORTUGA))]
