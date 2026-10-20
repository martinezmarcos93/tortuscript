"""
Motor de lecciones (sin interfaz): qué ve el chico de cada paso, cómo se comprueba
y cuánto vale. La UI (web) solo dibuja; toda la lógica está acá y tiene tests.

Tipos de paso (ver contenido.py): explicacion, elegir, completar, ordenar, predecir, escribir.

Reglas amables (nada de vidas ni castigos):
- Ante un error hay una pista específica; se puede reintentar todas las veces que haga falta.
- Después de 2 errores aparece "Ver respuesta": se ve y se sigue, sin XP en ese paso.
- XP por paso: 5 al primer intento, 2 si hubo reintentos, 0 si se vio la respuesta.
  Los pasos "escribir" siguen valiendo lo de siempre (30/20/10/5 según las pistas usadas).
- Una lección es "perfecta" si todos sus pasos salieron al primer intento y sin ver respuestas.
"""
import random
import zlib

from . import tortuga, tortugame
from .contenido import HUECO
from .translator import detectar_tipo, palabras_usadas
from .evaluacion import normalizar_salida

XP_PRIMER_INTENTO = 5
XP_REINTENTO = 2
ERRORES_PARA_VER_RESPUESTA = 2

PISTAS_GENERICAS = {
    "elegir": "Leé la pregunta otra vez y descartá las opciones que no pueden ser.",
    "predecir": "Seguí el código línea por línea, como si fueras la computadora.",
    "completar": "Mirá qué necesita cada hueco: una palabra, un texto o un número.",
    "ordenar": "Pensá qué tiene que pasar primero para que lo siguiente tenga sentido.",
}


# ─────────────────────────────────────────
# NAVEGACIÓN
# ─────────────────────────────────────────
def buscar_leccion(curso, leccion_id):
    """(seccion, leccion, posicion) o None. `posicion` es el orden dentro del curso (base 0)."""
    posicion = 0
    for seccion in curso["secciones"]:
        for leccion in seccion["lecciones"]:
            if leccion["id"] == leccion_id:
                return seccion, leccion, posicion
            posicion += 1
    return None


def lista_lecciones(curso):
    return [leccion for seccion in curso["secciones"] for leccion in seccion["lecciones"]]


def buscar_en_cursos(cursos, leccion_id):
    """(curso, seccion, leccion) de la primera lección con ese id, o None."""
    for curso in cursos:
        hallada = buscar_leccion(curso, leccion_id)
        if hallada is not None:
            return curso, hallada[0], hallada[1]
    return None


def siguiente_global(cursos, leccion_id):
    """Lección que sigue: la próxima del mismo curso o, si era la última, la primera del curso siguiente."""
    for i, curso in enumerate(cursos):
        if buscar_leccion(curso, leccion_id) is not None:
            proxima = leccion_siguiente(curso, leccion_id)
            if proxima is not None:
                return proxima
            return lista_lecciones(cursos[i + 1])[0] if i + 1 < len(cursos) else None
    return None


def leccion_siguiente(curso, leccion_id):
    todas = lista_lecciones(curso)
    for i, leccion in enumerate(todas):
        if leccion["id"] == leccion_id:
            return todas[i + 1] if i + 1 < len(todas) else None
    return None


def esta_completada(progreso, leccion_id, indices_escribir):
    """Una lección cuenta como completada si se terminó en el motor de lecciones, o si es
    de las del formato viejo cuyos ejercicios 'escribir' ya estaban resueltos (así el progreso
    guardado antes del motor no se pierde)."""
    if progreso.get("lecciones", {}).get(leccion_id, {}).get("completada"):
        return True
    ejercicios = progreso.get("ejercicios", {})
    return bool(indices_escribir) and all(
        ejercicios.get(str(i), {}).get("completado") for i in indices_escribir)


def es_perfecta(progreso, leccion_id, indices_escribir, total_pasos):
    """Perfecta en el motor de lecciones, o (formato viejo: solo 'escribir') con 3 estrellas."""
    if progreso.get("lecciones", {}).get(leccion_id, {}).get("perfecta"):
        return True
    ejercicios = progreso.get("ejercicios", {})
    return bool(indices_escribir) and len(indices_escribir) == total_pasos and all(
        ejercicios.get(str(i), {}).get("estrellas", 0) == 3 for i in indices_escribir)


def esta_superada(progreso, leccion_id, indices_escribir):
    """Hecha, o salteada por el diagnóstico (ADR-004): deja pasar el camino y los `requiere`, pero no da nada."""
    return leccion_id in (progreso.get("salteadas") or {}) or esta_completada(progreso, leccion_id, indices_escribir)


def estado_camino(curso, progreso, indices_por_leccion, curso_abierto=True, titulos=None):
    """Estado de cada lección para dibujar el camino:
    'perfecta' | 'hecha' | 'salteada' (por el diagnóstico: se puede hacer cuando se quiera) |
    'actual' (la primera pendiente) | 'bloqueada'.
    `indices_por_leccion`: {leccion_id: [índices de ejercicio 'escribir']}.
    Con `curso_abierto=False` (el curso pide algo que falta) todas salen bloqueadas.
    Una lección puede pedir otra con {"requiere": "<id>"}: hasta completarla queda bloqueada (y las
    que siguen también: el camino nunca se saltea una lección). `titulos` = {id: título} para el aviso."""
    salida, primera_pendiente_vista = [], False
    titulos = titulos or {}
    for seccion in curso["secciones"]:
        lecciones = []
        for lec in seccion["lecciones"]:
            indices = indices_por_leccion.get(lec["id"], [])
            pide = None
            if esta_completada(progreso, lec["id"], indices):
                estado = "perfecta" if es_perfecta(progreso, lec["id"], indices, len(lec["pasos"])) else "hecha"
            elif lec["id"] in (progreso.get("salteadas") or {}) and curso_abierto:
                estado = "salteada"
            else:
                requisito = lec.get("requiere")
                cumplido = not requisito or esta_superada(progreso, requisito, indices_por_leccion.get(requisito, []))
                if not primera_pendiente_vista and curso_abierto and cumplido:
                    estado = "actual"
                else:
                    estado = "bloqueada"
                    if requisito and not cumplido and curso_abierto and not primera_pendiente_vista:
                        pide = titulos.get(requisito, requisito)
                primera_pendiente_vista = True
            numero, _, nombre = lec["titulo"].partition(". ")
            fila = {"id": lec["id"], "numero": numero, "nombre": nombre or lec["titulo"],
                    "estado": estado, "pasos": len(lec["pasos"])}
            if pide:
                fila["pide"] = pide
            lecciones.append(fila)
        salida.append({"nivel": seccion["nivel"], "titulo": seccion["titulo"], "lecciones": lecciones})
    return salida


def estado_cursos(cursos, progreso, indices_por_leccion):
    """El camino completo, con requisitos de curso o de lección.
    Los cursos se muestran siempre; abierto solo controla si sus lecciones pueden abrirse."""
    salida = []
    titulos = {lec["id"]: lec["titulo"].partition(". ")[2] or lec["titulo"]
               for curso in cursos for seccion in curso["secciones"] for lec in seccion["lecciones"]}
    por_id = {curso["id"]: curso for curso in cursos}

    def curso_completo(curso_id):
        curso = por_id.get(curso_id)
        if not curso:
            return False
        lecciones_curso = [l for s in curso["secciones"] for l in s["lecciones"]]
        return bool(lecciones_curso) and all(
            esta_superada(progreso, l["id"], indices_por_leccion.get(l["id"], []))
            for l in lecciones_curso
        )

    for curso in cursos:
        requisito = curso.get("requiere") or {}
        abierto = True
        requisito_texto = None

        if requisito.get("leccion"):
            leccion_id = requisito["leccion"]
            hallada = buscar_en_cursos(cursos, leccion_id)
            requisito_texto = (
                hallada[2]["titulo"].partition(". ")[2] or hallada[2]["titulo"]
                if hallada else leccion_id
            )
            abierto = esta_superada(progreso, leccion_id, indices_por_leccion.get(leccion_id, []))
        elif requisito.get("curso"):
            curso_id = requisito["curso"]
            curso_requerido = por_id.get(curso_id)
            requisito_texto = curso_requerido["titulo"] if curso_requerido else curso_id
            abierto = curso_completo(curso_id)
        elif requisito.get("uno_de_cursos"):
            ids = requisito["uno_de_cursos"]
            nombres = [por_id[c]["titulo"] for c in ids if c in por_id]
            requisito_texto = " o ".join(nombres)
            abierto = any(curso_completo(c) for c in ids)

        secciones = estado_camino(curso, progreso, indices_por_leccion, abierto, titulos)
        lecciones = [l for s in secciones for l in s["lecciones"]]
        hechas = sum(1 for l in lecciones if l["estado"] in ("hecha", "perfecta"))
        salida.append({
            "id": curso["id"], "titulo": curso["titulo"], "icono": curso.get("icono", "📘"),
            "descripcion": curso.get("descripcion", ""), "abierto": abierto,
            "requiere": None if abierto else requisito_texto,
            "hechas": hechas, "total": len(lecciones),
            "completo": bool(lecciones) and hechas == len(lecciones),
            "perfectas": sum(1 for l in lecciones if l["estado"] == "perfecta"),
            "proximamente": bool(curso.get("proximamente")),
            "secciones": secciones,
        })
    return salida


def lecciones_planas(estado):
    """Lista plana de lecciones (con su curso) del resultado de estado_cursos."""
    return [dict(lec, curso=c["id"]) for c in estado for s in c["secciones"] for lec in s["lecciones"]]


def leccion_actual(estado):
    """La lección que toca ahora: la primera pendiente del primer curso que tenga alguna abierta."""
    return next((l for l in lecciones_planas(estado) if l["estado"] == "actual"), None)


# ─────────────────────────────────────────
# LO QUE VE EL CHICO (sin las respuestas)
# ─────────────────────────────────────────
def _semilla(leccion_id, indice):
    return zlib.crc32(f"{leccion_id}:{indice}".encode("utf-8"))


def _mezclar(elementos, semilla, distinto_del_original=False):
    """Mezcla reproducible (la página se ve igual al recargar). Si se pide, evita devolver
    el mismo orden que el original (para 'ordenar')."""
    mezclado = list(elementos)
    azar = random.Random(semilla)
    for _ in range(10):
        azar.shuffle(mezclado)
        if not distinto_del_original or mezclado != list(elementos) or len(set(elementos)) < 2:
            break
    return mezclado


def paso_publico(paso, leccion_id, indice, numero_ejercicio=None):
    """El paso tal como lo recibe el navegador. Nunca incluye la respuesta correcta."""
    tipo = paso["tipo"]
    semilla = _semilla(leccion_id, indice)
    publico = {"tipo": tipo, "indice": indice}
    for bandera in ("lienzo", "tortuga", "juego"):            # cómo se dibuja / se compara el paso
        if paso.get(bandera):
            publico[bandera] = True
    if paso.get("lenguaje"):
        publico["lenguaje"] = paso["lenguaje"]
    if paso.get("web"):
        publico["web"] = {"lenguaje": paso["web"].get("lenguaje", paso.get("lenguaje", "html"))}
    if paso.get("laberinto"):                                  # el mundo del paso: paredes y salida (no es la respuesta)
        publico["laberinto"] = {"paredes": paso["laberinto"]["paredes"], "salida": paso["laberinto"]["salida"]}
    if tipo == "explicacion":
        publico.update(texto=paso["texto"], codigo=paso.get("codigo"), forma=paso.get("forma"), tortu=paso.get("tortu"))
    elif tipo == "elegir":
        publico.update(pregunta=paso["pregunta"], codigo=paso.get("codigo"),
                       opciones=_mezclar([str(o) for o in paso["opciones"]], semilla))
    elif tipo == "predecir":
        publico.update(pregunta=paso.get("pregunta", "¿Qué va a mostrar este programa?"),
                       codigo=paso["codigo"],
                       opciones=_mezclar([str(o) for o in paso["opciones"]], semilla))
    elif tipo == "completar":
        publico.update(consigna=paso["consigna"], codigo=paso["codigo"],
                       fichas=_mezclar(paso["fichas"], semilla), huecos=paso["codigo"].count(HUECO))
    elif tipo == "ordenar":
        publico.update(consigna=paso["consigna"],
                       lineas=_mezclar(paso["lineas"], semilla, distinto_del_original=True))
    elif tipo == "escribir":
        publico.update(consigna=paso["consigna"], forma=paso.get("forma"), nota=paso.get("nota"),
                       ejercicio=numero_ejercicio, inicial=paso.get("inicial"))
    return publico


def respuesta_correcta(paso):
    """La respuesta para mostrar cuando el chico elige 'Ver respuesta'."""
    tipo = paso["tipo"]
    if tipo in ("elegir", "predecir"):
        return str(paso["opciones"][paso["correcta"]])
    if tipo == "completar":
        return list(paso["respuesta"])
    if tipo == "ordenar":
        return list(paso["lineas"])
    if tipo == "escribir":
        return paso["solucion"]
    return None


# ─────────────────────────────────────────
# COMPROBAR
# ─────────────────────────────────────────
def _completado(paso, rellenos):
    codigo = paso["codigo"]
    for r in rellenos:
        codigo = codigo.replace(HUECO, r, 1)
    return codigo


def _pista(paso, tipo, errores_previos):
    pista = paso.get("pista") or PISTAS_GENERICAS[tipo]
    pistas = paso.get("pistas")
    if isinstance(pistas, list) and pistas and all(isinstance(p, str) and p.strip() for p in pistas):
        nivel = errores_previos if isinstance(errores_previos, int) and not isinstance(errores_previos, bool) and errores_previos >= 0 else 0
        return pistas[min(nivel, len(pistas) - 1)]
    return pista


def _mismo_resultado(paso, ejecutar, fuente_a, fuente_b, entradas):
    """True si ambos programas dan el mismo resultado sin errores: el mismo texto en pantalla o,
    en los pasos de tortuga, el mismo dibujo. `ejecutar(fuente, entradas)` devuelve
    {"salida": str, "ordenes": [...]} o None si falló o preguntó algo."""
    a, b = ejecutar(fuente_a, entradas), ejecutar(fuente_b, entradas)
    if a is None or b is None:
        return False
    if paso.get("juego"):                                         # TortuGame: el mismo registro de eventos
        return bool(a.get("eventos")) and tortugame.sin_lineas(a["eventos"]) == tortugame.sin_lineas(b["eventos"])
    if paso.get("tortuga"):
        return tortuga.mismo_dibujo(a["ordenes"], b["ordenes"])
    return normalizar_salida(a["salida"]) != "" and normalizar_salida(a["salida"]) == normalizar_salida(b["salida"])


def comprobar(paso, respuesta, ejecutar=None, errores_previos=0):
    """Comprueba la respuesta a un paso que NO es 'escribir' (ese se evalúa ejecutando).

    respuesta: elegir/predecir → el texto de la opción; completar → lista de textos;
    ordenar → lista de líneas; explicacion → ignorada.
    `ejecutar` (opcional) permite aceptar otra forma válida de resolver 'completar' y
    'ordenar' cuando muestra lo mismo que la respuesta oficial.
    Devuelve {"ok": bool, "pista": str|None, "malos": [índices]|None}.
    """
    tipo = paso["tipo"]
    if tipo == "explicacion":
        return {"ok": True, "pista": None, "malos": None}

    if tipo in ("elegir", "predecir"):
        ok = isinstance(respuesta, str) and respuesta == str(paso["opciones"][paso["correcta"]])
        return {"ok": ok, "pista": None if ok else _pista(paso, tipo, errores_previos), "malos": None}

    if tipo == "completar":
        esperado = paso["respuesta"]
        if not isinstance(respuesta, list) or len(respuesta) != len(esperado):
            return {"ok": False, "pista": "Todavía quedan huecos sin completar.", "malos": None}
        malos = [i for i, (r, e) in enumerate(zip(respuesta, esperado)) if r != e]
        if not malos:
            return {"ok": True, "pista": None, "malos": None}
        if ejecutar and all(isinstance(r, str) and r in paso["fichas"] for r in respuesta):
            entradas = paso.get("entradas_prueba") or []
            if paso.get("tortuga") or paso.get("juego"):                # mismo dibujo / mismo juego que la respuesta oficial
                if _mismo_resultado(paso, ejecutar, _completado(paso, respuesta),
                                    _completado(paso, esperado), entradas):
                    return {"ok": True, "pista": None, "malos": None}
            elif paso.get("salida") is not None:
                resultado = ejecutar(_completado(paso, respuesta), entradas)
                if resultado is not None and normalizar_salida(resultado["salida"]) == normalizar_salida(paso["salida"]):
                    return {"ok": True, "pista": None, "malos": None}
        return {"ok": False, "pista": _pista(paso, "completar", errores_previos), "malos": malos}

    if tipo == "ordenar":
        esperado = paso["lineas"]
        if not isinstance(respuesta, list) or len(respuesta) != len(esperado):
            return {"ok": False, "pista": "Todavía faltan líneas por ubicar.", "malos": None}
        if respuesta == esperado:
            return {"ok": True, "pista": None, "malos": None}
        if ejecutar and sorted(respuesta) == sorted(esperado) and \
                _mismo_resultado(paso, ejecutar, "\n".join(respuesta), "\n".join(esperado),
                                 paso.get("entradas_prueba") or []):
            return {"ok": True, "pista": None, "malos": None}
        malos = [i for i, (r, e) in enumerate(zip(respuesta, esperado)) if r != e]
        return {"ok": False, "pista": _pista(paso, "ordenar", errores_previos), "malos": malos}

    raise ValueError(f"tipo de paso sin comprobación directa: {tipo!r}")


# ─────────────────────────────────────────
# XP
# ─────────────────────────────────────────
def xp_por_intentos(intentos, vio_respuesta):
    """XP de un paso que no es 'escribir'."""
    if vio_respuesta:
        return 0
    return XP_PRIMER_INTENTO if intentos <= 1 else XP_REINTENTO


def xp_maximo(curso):
    """XP de una pasada perfecta por todo el curso (los 'escribir' valen 30; leer no da XP)."""
    total = 0
    for seccion in curso["secciones"]:
        for lec in seccion["lecciones"]:
            for paso in lec["pasos"]:
                if paso["tipo"] == "escribir":
                    total += 30
                elif paso["tipo"] != "explicacion":
                    total += XP_PRIMER_INTENTO
    return total


def puede_ver_respuesta(errores):
    return errores >= ERRORES_PARA_VER_RESPUESTA


# ─────────────────────────────────────────
# QUÉ ENSEÑA CADA LECCIÓN (para el cierre: "Aprendiste... Practicaste...")
# ─────────────────────────────────────────
_NO_SE_ENSENAN = {"verdadero", "falso"}         # valores, no palabras que se presentan


def _fuentes_tortu(paso):
    """(código que presenta, código que usa) de un paso, solo si es TortuScript."""
    presenta = [paso.get("forma")] + ([paso.get("tortu") or paso.get("codigo")] if paso["tipo"] == "explicacion" else [])
    usa = [paso.get("codigo") if paso["tipo"] != "completar" else None,
           "\n".join(paso.get("lineas") or []), paso.get("solucion")]
    if paso["tipo"] == "completar" and paso.get("codigo"):
        codigo = paso["codigo"]
        for r in paso.get("respuesta") or []:
            codigo = codigo.replace(HUECO, r, 1)
        usa.append(codigo)
    limpio = lambda lista: [c for c in lista if c and detectar_tipo(c) != "python"]  # noqa: E731
    return limpio(presenta), limpio(usa)


def resumen_de_palabras(cursos):
    """{leccion_id: {"aprendiste": [...], "practicaste": [...]}} recorriendo los cursos en orden.
    Aprendiste = palabras que la lección presenta por primera vez (en una Forma o un ejemplo, la misma regla del
    validador); practicaste = las demás que usa. En Python real se usan las `palabras_pista` del contenido."""
    vistas, salida = set(), {}
    for curso in cursos:
        for seccion in curso["secciones"]:
            for lec in seccion["lecciones"]:
                nuevas, usadas = [], set()
                for paso in lec["pasos"]:
                    if paso.get("lenguaje") == "sql":
                        codigo = str(paso.get("codigo") or paso.get("solucion") or "").upper()
                        for palabra in ("SELECT", "FROM", "WHERE", "ORDER BY", "LIMIT", "COUNT", "GROUP BY", "JOIN", "ON", "INSERT", "UPDATE", "DELETE"):
                            if palabra in codigo:
                                if palabra not in vistas:
                                    vistas.add(palabra)
                                    nuevas.append(palabra)
                                usadas.add(palabra)
                        continue
                    if paso.get("lenguaje") in {"html", "css", "javascript"}:
                        for palabra in paso.get("palabras_pista") or []:
                            if palabra not in vistas:
                                vistas.add(palabra)
                                nuevas.append(palabra)
                            usadas.add(palabra)
                        continue
                    presenta, usa = _fuentes_tortu(paso)
                    for fuente in presenta:
                        for p in sorted(palabras_usadas(fuente) - _NO_SE_ENSENAN):
                            if p not in vistas:
                                vistas.add(p)
                                nuevas.append(p)
                    for fuente in presenta + usa:
                        usadas |= palabras_usadas(fuente)
                    if paso.get("lenguaje") == "python":
                        usadas |= set(paso.get("palabras_pista") or [])
                practicadas = sorted(usadas - set(nuevas) - _NO_SE_ENSENAN - {"="})
                salida[lec["id"]] = {"aprendiste": nuevas, "practicaste": practicadas}
    return salida

