"""
TortuScript web: servidor Flask local (127.0.0.1) + páginas HTML/CSS/JS.

Seguridad de una app local:
- Solo atiende pedidos con Host 127.0.0.1/localhost (frena "DNS rebinding").
- Toda la API exige el token secreto de esta sesión en el encabezado X-Tortu-Token:
  una página web ajena abierta en el navegador no puede mandarlo (no hay CORS).
- El código del chico nunca corre en este proceso: va a tortuscript.proceso.
"""
import base64
import copy
import logging
import secrets
import sys
import threading
from datetime import date
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tortuscript import contenido, evaluacion, leccion as motor, liga, logros, progreso  # noqa: E402
from tortuscript import web_evaluacion, sql_evaluacion  # noqa: E402
from tortuscript import practica as espaciado  # noqa: E402
from tortuscript import proyectos as mis_proyectos  # noqa: E402
from tortuscript import proyectos_integradores, catalogo_producto  # noqa: E402
from tortuscript import diagnostico, intereses, respaldo  # noqa: E402
from tortuscript.juego_ast import arbol_del_juego  # noqa: E402
from tortuscript.executor import CodigoNoPermitido  # noqa: E402
from tortuscript.error_handler import armar_mensaje_error  # noqa: E402
from tortuscript.ejercicios import EJERCICIOS  # noqa: E402
from tortuscript.proceso import correr  # noqa: E402
from tortuscript.referencia import cargar_referencia  # noqa: E402
from tortuscript.runtime_educativo import RuntimeEducativo, ContextoEducativoError  # noqa: E402
from tortuscript.repaso import MODOS, cola_repaso, contar  # noqa: E402
from tortuscript.translator import TraductorTortuScript, detectar_tipo  # noqa: E402
from web.cuenta_routes import bp as cuenta_bp, _educativo  # noqa: E402
from web.pagos_routes import bp as pagos_bp  # noqa: E402

logger = logging.getLogger("tortuscript.web")
HOSTS_PERMITIDOS = {"127.0.0.1", "localhost"}
# Rutas que no operan sobre un perfil educativo: cuenta del adulto y eventos del proveedor de pagos.
SIN_PERFIL = ("/cuenta", "/pagos")


def _json_objeto():
    """Devuelve solo objetos JSON; listas, escalares y JSON inválido se normalizan a {}."""
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


# Cabeceras de seguridad (docs/experimental/SEGURIDAD_SITIO_PROFESIONAL.md §5). La app es local, pero se
# endurece igual: nada se carga de afuera, ningún script inline se ejecuta y ninguna página se puede enmarcar.
# style-src admite 'unsafe-inline' a propósito: las plantillas usan atributos style= y CodeMirror pone estilos;
# inyectar estilos no ejecuta código y las plantillas ya escapan todo (autoescape). Sin HSTS: es http://127.0.0.1.
CSP = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))
# El intérprete de juegos corre en un Web Worker: su CSP (la de la respuesta del script) no le deja nada salvo su propio
# código. Sin red, sin otros scripts (ADR-007, modelo de amenazas A1/A3).
RUTA_WORKER_JUEGOS = "/static/js/tortugame/interprete.js"
CSP_WORKER_JUEGOS = "default-src 'none'; script-src 'self'"
CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


# Lo que ve el chico ante un error: nunca trazas, rutas ni "500 Internal Server Error".
ERRORES = {
    400: ("🤔", "Eso no se entendió", "El pedido llegó incompleto. Volvé a intentarlo desde la página."),
    403: ("🔒", "Esto no se puede abrir desde acá", "Volvé al inicio y seguí desde ahí."),
    404: ("🧭", "Esta página no existe", "Puede que el enlace esté mal escrito. Volvé al inicio y seguí desde ahí."),
    500: ("🔧", "Algo se rompió de nuestro lado",
          "No fue culpa tuya. Tu progreso sigue guardado. Probá de nuevo en un ratito."),
}


def codigo_de_referencia():
    """Código corto para cruzar lo que vio el chico con el log (p. ej. 8F72A1)."""
    return secrets.token_hex(3).upper()


def create_app(token=None):
    app = Flask(__name__)
    app.config["TOKEN"] = token or secrets.token_urlsafe(24)
    app.config["JSON_AS_ASCII"] = False
    app.config["ACCOUNT_DB"] = Path(app.instance_path) / "cuentas.sqlite3"
    app.config["ACCOUNT_COOKIE_SECURE"] = False
    app.config["ACCOUNT_COOKIE_SAMESITE"] = "Lax"
    # La migración desde perfiles locales legados puede exponer datos entre
    # cuentas en una instalación compartida. Solo habilitar en modo local,
    # de un único usuario, mediante configuración explícita.
    app.config["ENABLE_LOCAL_PROGRESS_MIGRATION"] = False
    # Secretos de webhook por proveedor de pagos. Vacío: no se acepta ningún evento (ADR-032).
    app.config["PAYMENT_WEBHOOK_SECRETS"] = {}
    # Otros productos del ecosistema (ADR-037): {"croco-script": {"url": …, "clave": …, "kid": …}}. Vacío: sin transición.
    app.config["FEDERACION"] = {}
    app.register_blueprint(cuenta_bp)
    app.register_blueprint(pagos_bp)
    # Pistas vistas por (perfil, lección, paso): se reinician al abrir el ejercicio o la lección.
    pistas_vistas = {}
    INDICES_POR_LECCION = {}
    for i, e in enumerate(EJERCICIOS):
        INDICES_POR_LECCION.setdefault(e["leccion_id"], []).append(i)
    intentos = {}    # errores y respuesta vista por (perfil, lección, paso); se reinicia al abrir la lección
    practicas = {}   # sesión de práctica del día por perfil: {"dia", "pasos": [(lección, paso)]}
    colas = {}       # colas de repaso fijadas al empezar: (perfil, modo, semilla) -> [índices]
    turno = threading.RLock()     # los pedidos van de a uno: cargar → modificar → guardar el progreso no se pisa

    # ─────────────── errores ───────────────
    def _respuesta_de_error(estado, codigo=None):
        icono, titulo, mensaje = ERRORES.get(estado, ERRORES[500] if estado >= 500 else ERRORES[400])
        if request.path.startswith("/api/"):
            datos = {"error": titulo, "mensaje": mensaje + (f" (código {codigo})" if codigo else "")}
            if codigo:
                datos["codigo"] = codigo
            return jsonify(datos), estado
        # Sin render_template: sus context processors cargan el progreso, y el error puede venir de ahí.
        html = app.jinja_env.get_template("error.html").render(icono=icono, titulo=titulo, mensaje=mensaje, codigo=codigo)
        return html, estado

    @app.errorhandler(HTTPException)
    def _error_http(e):
        if e.code is None or e.code < 400:
            return e
        if e.code >= 500:
            codigo = codigo_de_referencia()
            logger.error("Error %s [%s] en %s %s", e.code, codigo, request.method, request.path)
            return _respuesta_de_error(e.code, codigo)
        return _respuesta_de_error(e.code)

    @app.errorhandler(Exception)
    def _error_inesperado(e):
        codigo = codigo_de_referencia()
        logger.error("Error interno [%s] en %s %s: %s", codigo, request.method, request.path, e, exc_info=True)
        return _respuesta_de_error(500, codigo)

    # ─────────────── almacenamiento educativo ───────────────
    def _runtime_educativo():
        """Runtime comercial obligatorio: toda experiencia educativa vive en un ChildProfile.
        La sesión se valida una vez por pedido: no puede cambiar a mitad de una respuesta."""
        if "tortu_runtime" in g:
            return g.tortu_runtime
        raw_session = request.cookies.get("tortu_session")
        if not raw_session:
            abort(401)
        runtime = RuntimeEducativo(_educativo())
        try:
            g.tortu_contexto = runtime.contexto(raw_session)
        except ContextoEducativoError:
            abort(401)
        g.tortu_runtime = (runtime, raw_session)
        return g.tortu_runtime

    def _contexto():
        _runtime_educativo()
        return g.tortu_contexto

    def _perfil_contexto():
        return _contexto().perfil.id

    def _nombre_perfil_contexto(p=None):
        # La identidad visible pertenece al ChildProfile, no al nombre legacy del progreso.
        return _contexto().perfil.display_name

    def _cargar_progreso():
        """Una copia propia del progreso del perfil activo. El archivo se lee una vez por pedido;
        toda escritura pasa por los helpers de abajo, que descartan lo leído."""
        if "tortu_progreso" not in g:
            runtime, raw_session = _runtime_educativo()
            g.tortu_progreso = runtime.cargar_datos(raw_session)
        return copy.deepcopy(g.tortu_progreso)

    def _progreso_cambio():
        g.pop("tortu_progreso", None)

    def _guardar_progreso(p):
        runtime, raw_session = _runtime_educativo()
        runtime.guardar_datos(raw_session, p)
        # Lo guardado es lo que devolvería una relectura (sin las claves internas "_…").
        g.tortu_progreso = copy.deepcopy({k: v for k, v in p.items() if not k.startswith("_")})
        return True

    def _tomar_avisos(p):
        avisos = progreso.tomar_avisos(p)
        if avisos:
            _guardar_progreso(p)
        return avisos

    def _registrar_ejercicio(p, indice, estrellas, xp_ganado):
        runtime, raw_session = _runtime_educativo()
        resultado = runtime.registrar_ejercicio(raw_session, indice, estrellas, xp_ganado)
        _progreso_cambio()
        p.clear()
        p.update(_cargar_progreso())
        return resultado

    def _registrar_paso_leccion(p, leccion_id, indice, xp, perfecto, total_pasos, estrellas=None):
        runtime, raw_session = _runtime_educativo()
        resultado = runtime.registrar_paso_leccion(
            raw_session, leccion_id, indice, xp, perfecto, total_pasos, estrellas
        )
        _progreso_cambio()
        p.clear()
        p.update(_cargar_progreso())
        return resultado

    def _registrar_practica(p, leccion_id, paso, acierto):
        runtime, raw_session = _runtime_educativo()
        resultado = runtime.registrar_practica(raw_session, leccion_id, paso, acierto)
        _progreso_cambio()
        p.clear()
        p.update(_cargar_progreso())
        return resultado

    # ─────────────── seguridad ───────────────
    @app.after_request
    def _cabeceras_de_seguridad(respuesta):
        for nombre, valor in CABECERAS_SEGURIDAD.items():
            respuesta.headers.setdefault(nombre, valor)
        if request.path == RUTA_WORKER_JUEGOS:
            respuesta.headers["Content-Security-Policy"] = CSP_WORKER_JUEGOS
        return respuesta

    @app.before_request
    def _proteger():
        if request.host.split(":")[0] not in HOSTS_PERMITIDOS:
            abort(403)
        if request.path.startswith("/api/") and \
                request.headers.get("X-Tortu-Token") != app.config["TOKEN"]:
            abort(403)

    @app.before_request
    def _requiere_contexto_educativo():
        if request.endpoint in (None, "static") or request.path.startswith(SIN_PERFIL):
            return None
        raw_session = request.cookies.get("tortu_session")
        if not raw_session:
            if request.path.startswith("/api/"):
                return jsonify(ok=False, mensaje="Iniciá sesión y seleccioná un perfil educativo."), 401
            return redirect(url_for("cuenta.ingresar", next=request.full_path))
        runtime = RuntimeEducativo(_educativo())
        try:
            g.tortu_contexto = runtime.contexto(raw_session)
            g.tortu_runtime = (runtime, raw_session)
        except ContextoEducativoError:
            if request.path.startswith("/api/"):
                return jsonify(ok=False, mensaje="La sesión educativa ya no es válida."), 401
            cuentas, auth = _educativo().cuentas, _educativo().auth
            sesion = auth.get_session(raw_session)
            if sesion and not sesion["active_profile_id"]:
                return redirect(url_for("cuenta.seleccionar_perfil_pagina", next=request.full_path))
            return redirect(url_for("cuenta.ingresar", next=request.full_path))
        return None

    @app.before_request
    def _de_a_uno():
        """Dos pestañas (o dos toques seguidos) no pueden leer el mismo progreso y pisarse al guardar.
        Todo pedido de página o de API espera su turno; los archivos estáticos no."""
        if request.endpoint in (None, "static"):
            return None
        turno.acquire()
        g.con_turno = True
        return None

    @app.teardown_request
    def _soltar_turno(_error):
        if g.pop("con_turno", False):
            turno.release()

    @app.before_request
    def _bienvenida():
        """Un perfil nuevo empieza por la bienvenida (nombre, experiencia y meta diaria)."""
        if request.method != "GET" or request.endpoint in (None, "static", "bienvenida") \
                or request.path.startswith("/api/") or request.path.startswith(SIN_PERFIL):
            return None
        if progreso.necesita_onboarding(_cargar_progreso()):
            return redirect(url_for("bienvenida"))
        return None

    @app.before_request
    def _semana_de_la_liga():
        """Al cambiar de semana se resuelve la liga anterior (¿subió?) una sola vez."""
        if request.method != "GET" or request.endpoint in (None, "static") \
                or request.path.startswith("/api/") or request.path.startswith(SIN_PERFIL):
            return None
        p = _cargar_progreso()
        viejo = dict(p.get("liga") or {})

        def otros_de_la_semana(domingo):
            return _otros_en_liga(domingo)
        liga.cerrar_semana(p, otros_de_la_semana, date.today())
        if p.get("liga") != viejo or p.get("avisos"):
            _guardar_progreso(p)
        return None

    @app.context_processor
    def _globales():
        # Las páginas de cuenta no tienen contexto educativo.
        if request.path.startswith(SIN_PERFIL):
            return {"token": app.config["TOKEN"]}
        contexto = _contexto()
        avisos = _tomar_avisos(_cargar_progreso())
        return {
            "token": app.config["TOKEN"],
            "estado": _estado(),
            "perfil": contexto.perfil.display_name,
            "cuenta_email": contexto.cuenta.email,
            "cuenta_role": contexto.cuenta.role,
            "cuenta_csrf": request.cookies.get("tortu_csrf", ""),
            "avisos_pendientes": avisos,
            "ajustes": progreso.ajustes_de(_cargar_progreso()),
        }

    # ─────────────── helpers ───────────────
    def _estado():
        p = _cargar_progreso()
        xp = p.get("xp_total", 0)
        nivel, xp_actual, xp_max = progreso.calcular_nivel(xp)
        completados = [int(k) for k, v in p["ejercicios"].items() if v.get("completado")]
        planas = motor.lecciones_planas(_camino(p))
        meta = progreso.meta_diaria_xp(p)
        hoy_xp = progreso.xp_de_hoy(p)
        reto = progreso.reto_de_racha(p)
        tabla_liga = liga.resumen(p, _otros_en_liga(date.today()), date.today())
        return {
            "congeladores": p.get("congeladores", 0), "racha_protegida": progreso.racha_protegida(p),
            "reto_dias": reto[0], "reto_total": reto[1],
            "logros_ganados": len(p.get("logros", {})), "logros_total": len(logros.LOGROS),
            "practica_pendientes": espaciado.pendientes(p, _cursos(), date.today()),
            "liga": {k: tabla_liga[k] for k in ("liga", "icono", "puesto", "tamano", "xp", "dias_restantes", "asciende")},
            "lecciones_hechas": sum(1 for lec in planas if lec["estado"] in ("hecha", "perfecta")),
            "lecciones_total": len(planas),
            "xp_hoy": hoy_xp, "meta_xp": meta, "meta_min": p["config"]["meta_min"],
            "meta_pct": min(100, round(100 * hoy_xp / meta)) if meta else 0,
            "nombre": _nombre_perfil_contexto(),
            "xp": xp, "nivel": nivel, "titulo": progreso.titulo_nivel(nivel),
            "color_tortuga": progreso.color_tortuga(nivel),
            "xp_actual": xp_actual, "xp_max": xp_max,
            "racha": progreso.racha_vigente(p),
            "completados": len(completados), "total": len(EJERCICIOS),
            "estrellas": {k: v.get("estrellas", 0) for k, v in p["ejercicios"].items()},
        }

    def _es_admin():
        if not request.cookies.get("tortu_session"):
            return False
        try:
            return _contexto().cuenta.role == "admin"
        except HTTPException:
            return False

    def _desbloqueado(indice, p=None):
        if _es_admin():
            return True
        p = p or _cargar_progreso()
        ej = p["ejercicios"]
        return indice == 0 or ej.get(str(indice), {}).get("completado") or \
            ej.get(str(indice - 1), {}).get("completado")

    def _siguiente_pendiente():
        p = _cargar_progreso()
        return next((i for i in range(len(EJERCICIOS))
                     if not p["ejercicios"].get(str(i), {}).get("completado")), len(EJERCICIOS) - 1)

    def _ejercicio_o_404(n):
        if not 0 <= n < len(EJERCICIOS):
            abort(404)
        return EJERCICIOS[n]

    def _otros_en_liga(dia):
        """Rivales remotos de la cuenta. Aún no existe ranking remoto V1: nunca usa datos locales ajenos."""
        return {}

    def _avisos_tras(p):
        """Revisa los logros con el progreso ya actualizado y devuelve (y guarda) los avisos pendientes."""
        logros.revisar(p, logros.resumen_de(p, _camino(p)))
        return _tomar_avisos(p)

    def _niveles():
        return {s["nivel"]: s["titulo"] for s in contenido.cargar_curso()["secciones"]}

    def _pagina_ejercicio(indice, repaso=None):
        ej = _ejercicio_o_404(indice)
        pistas_vistas[(_perfil_contexto(), ej["leccion_id"], ej["paso"])] = 0
        hallada = motor.buscar_leccion(_curso(), ej.get("leccion_id"))
        leccion_larga = hallada[1]["id"] if hallada and len(hallada[1]["pasos"]) > 1 else None
        return render_template("ejercicio.html", ej=ej, n=indice + 1, total=len(EJERCICIOS), repaso=repaso,
                               leccion_larga=leccion_larga)

    def _curso():
        """El curso de los ejercicios clásicos: el índice de cada 'escribir' es la clave de su progreso."""
        return contenido.cargar_curso()

    def _cursos():
        return contenido.todos_los_cursos()

    def _camino(p=None):
        camino = motor.estado_cursos(_cursos(), p or _cargar_progreso(), INDICES_POR_LECCION)
        if _es_admin():
            # El admin puede recorrer todo el árbol sin falsear el progreso.
            for curso in camino:
                curso["abierto"] = True
                for seccion in curso.get("secciones", []):
                    for leccion in seccion.get("lecciones", []):
                        if leccion.get("estado") == "bloqueada":
                            leccion["estado"] = "actual"
        return camino

    def _leccion_o_404(leccion_id):
        hallada = motor.buscar_en_cursos(_cursos(), leccion_id)
        if hallada is None:
            abort(404)
        return hallada                                          # (curso, sección, lección)

    def _nivel0_completo(p=None):
        p = p or _cargar_progreso()
        curso = next((c for c in _camino(p) if c["id"] == "alfabetizacion-digital"), None)
        return bool(curso and curso["completo"])

    def _curso_inicial(recorrido):
        return {"web": "web-esencial", "python": "python-real"}.get(recorrido)

    def _completada(leccion, p=None):
        p = p or _cargar_progreso()
        return motor.esta_completada(p, leccion["id"], INDICES_POR_LECCION.get(leccion["id"], []))

    def _leccion_desbloqueada(leccion_id, p=None):
        if _es_admin():
            return True
        return any(l["id"] == leccion_id and l["estado"] != "bloqueada"
                   for l in motor.lecciones_planas(_camino(p)))

    palabras_por_leccion = {}     # qué enseña y qué practica cada lección (el contenido no cambia: se calcula una vez)

    def _resumen_leccion(leccion_id, info):
        """Lo que la página necesita saber al terminar (o no) una lección: qué aprendió, qué ganó y qué sigue."""
        if not palabras_por_leccion:
            palabras_por_leccion.update(motor.resumen_de_palabras(_cursos()))
        siguiente = motor.siguiente_global(_cursos(), leccion_id)
        resultado = {**info, **palabras_por_leccion.get(leccion_id, {"aprendiste": [], "practicaste": []}),
                     "siguiente": siguiente["id"] if siguiente else None,
                     "titulo_siguiente": siguiente["titulo"] if siguiente else None}
        p = _cargar_progreso()
        if leccion_id.startswith("nivel0-") and _nivel0_completo(p):
            recorrido = p.get("recorrido_inicial")
            if recorrido:
                curso_id = _curso_inicial(recorrido)
                curso = next((c for c in _cursos() if c["id"] == curso_id), None)
                primera = contenido.lecciones(curso)[0][1] if curso and contenido.lecciones(curso) else None
                resultado["siguiente"] = primera["id"] if primera else None
                resultado["titulo_siguiente"] = primera["titulo"] if primera else None
            else:
                resultado["siguiente"] = None
                resultado["titulo_siguiente"] = "Elegí qué aprender primero"
                resultado["elegir_recorrido"] = True
        return resultado

    def _ejecutar_para_motor(paso):
        """Cómo el motor corre un programa para comparar (completar/ordenar): devuelve
        {"salida", "ordenes"}, o None si falla o pregunta algo."""
        op = "juego" if paso.get("juego") else "tortuga" if paso.get("tortuga") else "ejecutar"

        def ejecutar(fuente, entradas):
            r = correr({"op": op, "fuente": fuente, "entradas": entradas, "semilla": evaluacion.SEMILLA_EVALUACION})
            if r.get("error") or r.get("pregunta") is not None:
                return None
            return {"salida": r.get("salida_programa", ""), "ordenes": r.get("ordenes", []), "eventos": r.get("eventos", [])}
        return ejecutar

    objetivos = {}   # dibujo de la solución de cada paso de tortuga: (fuente, entradas) -> órdenes

    def _objetivo(paso):
        clave = (paso["solucion"] if paso["tipo"] == "escribir" else "\n".join(paso.get("lineas") or [])
                 or _completado_oficial(paso), tuple(paso.get("entradas_prueba") or ()))
        if clave not in objetivos:
            r = correr({"op": "tortuga", "fuente": clave[0], "entradas": list(clave[1]),
                        "semilla": evaluacion.SEMILLA_EVALUACION})
            objetivos[clave] = [] if r.get("error") else r.get("ordenes", [])
        return objetivos[clave]

    def _completado_oficial(paso):
        codigo = paso.get("codigo", "")
        for r in paso.get("respuesta", []):
            codigo = codigo.replace("___", r, 1)
        return codigo

    def _publico(paso, leccion_id, i):
        """El paso listo para el navegador (+ el dibujo objetivo de los pasos de tortuga)."""
        ejercicio = contenido.indices_ejercicio(leccion_id).get(i)
        publico = motor.paso_publico(paso, leccion_id, i, None if ejercicio is None else ejercicio + 1)
        if paso.get("tortuga") and paso["tipo"] in ("escribir", "completar", "ordenar") and not paso.get("laberinto"):
            publico["objetivo"] = _objetivo(paso)          # en un laberinto no hay dibujo objetivo: vale cualquier camino
        return publico

    # ─────────────── páginas ───────────────
    @app.get("/")
    def inicio():
        camino = _camino()
        p = _cargar_progreso()
        # ADR-005: se pregunta después de usar el producto: como mucho una encuesta por curso terminado
        terminados = sum(1 for c in camino if c["completo"])
        encuesta = intereses.pendiente(p, "curso-terminado", cupo=terminados) if terminados else None
        return render_template("inicio.html", camino=camino, actual=motor.leccion_actual(camino),
                               regreso=progreso.regreso(p), encuesta=encuesta)

    @app.get("/aprender")
    def aprender():
        """Va directo a la lección que toca (o a la última si ya terminó todo)."""
        planas = motor.lecciones_planas(_camino())
        destino = motor.leccion_actual(_camino()) or planas[-1]
        return redirect(url_for("leccion", leccion_id=destino["id"]))

    @app.get("/bienvenida")
    def bienvenida():
        lecciones = {lec["id"]: (seccion["titulo"], lec["titulo"].partition(". ")[0])
                     for seccion, lec in contenido.lecciones(contenido.cargar_curso())}
        entradas = {exp: {"id": lid, "seccion": lecciones[lid][0], "numero": lecciones[lid][1]}
                    for exp, lid in progreso.PUNTOS_DE_ENTRADA.items()}
        return render_template("bienvenida.html", metas=progreso.METAS_MIN, xp_por_minuto=progreso.XP_POR_MINUTO,
                               entradas=entradas, prueba=diagnostico.preguntas_publicas())

    @app.get("/ejercicios")
    def ejercicios_siguiente():
        return redirect(url_for("ejercicio", n=_siguiente_pendiente() + 1))

    @app.get("/ejercicios/<int:n>")
    def ejercicio(n):
        indice = n - 1
        _ejercicio_o_404(indice)
        if not _desbloqueado(indice):
            return redirect(url_for("ejercicio", n=_siguiente_pendiente() + 1))
        return _pagina_ejercicio(indice)

    @app.get("/leccion/<leccion_id>")
    def leccion(leccion_id):
        curso, seccion, lec = _leccion_o_404(leccion_id)
        p = _cargar_progreso()
        if not _leccion_desbloqueada(leccion_id, p):
            return redirect(url_for("aprender"))
        for i in range(len(lec["pasos"])):
            intentos.pop((_perfil_contexto(), leccion_id, i), None)
            pistas_vistas.pop((_perfil_contexto(), leccion_id, i), None)
        datos = {"id": leccion_id, "titulo": lec["titulo"], "seccion": seccion["titulo"], "curso": curso["titulo"],
                 "nivel": seccion["nivel"], "pasos": [_publico(paso, leccion_id, i) for i, paso in enumerate(lec["pasos"])],
                 "ya_completada": _completada(lec, p)}
        return render_template("leccion.html", datos=datos, titulo=lec["titulo"])

    @app.route("/elegir-recorrido", methods=["GET", "POST"])
    def elegir_recorrido():
        p = _cargar_progreso()
        if not _nivel0_completo(p):
            return redirect(url_for("mapa"))
        if request.method == "POST":
            recorrido = (request.form.get("recorrido") or "").strip()
            curso_id = _curso_inicial(recorrido)
            if not curso_id:
                abort(400)
            p["recorrido_inicial"] = recorrido
            _guardar_progreso(p)
            curso = next(c for c in _cursos() if c["id"] == curso_id)
            primera = contenido.lecciones(curso)[0][1]
            return redirect(url_for("leccion", leccion_id=primera["id"]))
        return render_template(
            "elegir_recorrido.html",
            recorrido_actual=p.get("recorrido_inicial"),
            cursos={c["id"]: c for c in _cursos()},
            sql_desbloqueado=next(
                (c["abierto"] for c in _camino(p) if c["id"] == "sql-fundamentos"), False
            ),
        )

    @app.get("/mapa")
    def mapa():
        p = _cargar_progreso()
        datos = p["ejercicios"]
        niveles = {}
        for i, ej in enumerate(EJERCICIOS):
            d = datos.get(str(i), {})
            numero, _, nombre = ej["titulo"].partition(". ")
            niveles.setdefault(ej["nivel"], []).append({
                "n": i + 1, "leccion": ej["leccion_id"], "numero": numero, "nombre": nombre or ej["titulo"],
                "completado": bool(d.get("completado")), "estrellas": d.get("estrellas", 0),
                "xp": d.get("xp", 0), "abierto": bool(_desbloqueado(i, p)),
            })
        camino = _camino(p)
        nivel0_curso = next((c for c in camino if c["id"] == "alfabetizacion-digital"), None)
        nivel0 = []
        if nivel0_curso:
            for seccion in nivel0_curso["secciones"]:
                for lec in seccion["lecciones"]:
                    lp = p.get("lecciones", {}).get(lec["id"], {})
                    nivel0.append({
                        "leccion": lec["id"],
                        "numero": lec["numero"],
                        "nombre": lec["nombre"],
                        "completado": lec["estado"] in ("hecha", "perfecta"),
                        "perfecto": lec["estado"] == "perfecta",
                        "abierto": lec["estado"] != "bloqueada",
                        "xp": sum(v.get("xp", 0) for v in lp.get("pasos", {}).values()),
                    })
        tres = sum(1 for d in datos.values() if d.get("estrellas", 0) == 3)
        return render_template("mapa.html", niveles=niveles, nombres=_niveles(),
                               nivel0=nivel0, camino=camino, recorrido_inicial=p.get("recorrido_inicial"), tres_estrellas=tres)

    @app.get("/resumen")
    def resumen():
        p = _cargar_progreso()
        hoy = progreso.resumen_sesion_hoy(p, EJERCICIOS)
        return render_template(
            "resumen.html", hoy=hoy, racha=progreso.racha_vigente(p), racha_max=p.get("racha_max", 0),
            jugo_hoy=p.get("ultimo_dia") == str(date.today()), calendario=progreso.calendario_semana(p),
            estrellas_texto=progreso.estrellas_texto, metas=progreso.METAS_MIN,
            recientes=sorted((c for c in logros.catalogo(p) if c["ganado"]), key=lambda c: c["fecha"], reverse=True)[:4])

    @app.get("/practica")
    def practica():
        """Práctica del día: hasta 6 tarjetas que ya tocan, de lecciones distintas (repaso espaciado)."""
        p = _cargar_progreso()
        elegidas = espaciado.elegir(p, _cursos(), date.today())
        if not elegidas:
            return render_template("practica_vacia.html")
        practicas[_perfil_contexto()] = {"dia": str(date.today()), "pasos": elegidas}
        pasos = []
        for leccion_id, i in elegidas:
            _, _, lec = _leccion_o_404(leccion_id)
            intentos.pop((_perfil_contexto(), "practica", leccion_id, i), None)
            publico = _publico(lec["pasos"][i], leccion_id, i)
            publico["leccion"] = leccion_id
            pasos.append(publico)
        datos = {"id": "practica", "modo": "practica", "titulo": "Práctica del día", "seccion": "Repaso espaciado",
                 "nivel": None, "pasos": pasos, "ya_completada": False}
        return render_template("leccion.html", datos=datos, titulo="Práctica del día")

    @app.get("/certificado/<curso_id>")
    def certificado(curso_id):
        """Diploma imprimible (o para guardar como PDF) al terminar un curso. Gratis y sin cuentas."""
        p = _cargar_progreso()
        curso = next((c for c in _camino(p) if c["id"] == curso_id), None)
        if curso is None:
            abort(404)
        if not curso["completo"]:
            return redirect(url_for("inicio"))
        return render_template("certificado.html", curso=curso, hoy=date.today(), xp=p.get("xp_total", 0),
                               nombre=_nombre_perfil_contexto(p))

    @app.get("/logros")
    def pagina_logros():
        p = _cargar_progreso()
        return render_template("logros.html", catalogo=logros.catalogo(p),
                               diplomas=[c for c in _camino(p) if c["completo"]])

    @app.get("/liga")
    def pagina_liga():
        p = _cargar_progreso()
        return render_template("liga.html", liga=liga.resumen(p, _otros_en_liga(date.today()), date.today()),
                               ligas=liga.LIGAS)

    @app.get("/referencia")
    def referencia():
        return render_template("referencia.html", ref=cargar_referencia())

    @app.get("/ayuda")
    def ayuda():
        return render_template("ayuda.html", ayuda=contenido.cargar_ayuda())

    @app.get("/repaso")
    def repaso():
        completados, imperfectos = contar(_cargar_progreso(), len(EJERCICIOS))
        return render_template("repaso.html", modos=MODOS, completados=completados, imperfectos=imperfectos)

    def _cola_o_404(modo, semilla, nueva=False):
        """La cola se fija al empezar el repaso: si un ejercicio pasa a 3 estrellas a mitad
        de camino, no desaparece de la lista ni se corren los lugares."""
        if modo not in MODOS:
            abort(404)
        clave = (_perfil_contexto(), modo, semilla)
        if nueva or clave not in colas:
            colas[clave] = cola_repaso(_cargar_progreso(), modo, len(EJERCICIOS), semilla)
        return colas[clave]

    @app.get("/repaso/<modo>")
    def repaso_modo(modo):
        semilla = request.args.get("s", type=int)
        if semilla is None:
            semilla = secrets.randbelow(10**6)
        _cola_o_404(modo, semilla, nueva=True)
        return redirect(url_for("repaso_paso", modo=modo, pos=1, s=semilla))

    @app.get("/repaso/<modo>/<int:pos>")
    def repaso_paso(modo, pos):
        semilla = request.args.get("s", 0, type=int)
        cola = _cola_o_404(modo, semilla)
        if not cola:
            return render_template("repaso_fin.html", modo=modo, modos=MODOS, total=0)
        if pos > len(cola):
            return render_template("repaso_fin.html", modo=modo, modos=MODOS, total=len(cola))
        if pos < 1:
            abort(404)
        anterior = url_for("repaso_paso", modo=modo, pos=pos - 1, s=semilla) if pos > 1 else None
        siguiente = url_for("repaso_paso", modo=modo, pos=pos + 1, s=semilla)
        return _pagina_ejercicio(cola[pos - 1], repaso={
            "modo": MODOS[modo][1], "pos": pos, "total": len(cola),
            "anterior": anterior, "siguiente": siguiente, "ultimo": pos == len(cola)})

    def _proyecto_pedido(tipo):
        """El proyecto de ?proyecto=<id>: (proyecto|None, redirección|None). Si es de otro tipo, va a su página."""
        pedido = request.args.get("proyecto")
        if not pedido:
            return None, None
        p = mis_proyectos.obtener(_cargar_progreso(), pedido)
        if p is None:
            return None, redirect(url_for(tipo))
        if p["tipo"] != tipo:
            return None, redirect(url_for(p["tipo"], proyecto=pedido))
        return p, None

    @app.get("/experimentar")
    def experimentar():
        proyecto, otra = _proyecto_pedido("experimentar")
        return otra or render_template("experimentar.html", proyecto=proyecto)

    @app.get("/juego")
    def juego():
        proyecto, otra = _proyecto_pedido("juego")
        return otra or render_template("juego.html", proyecto=proyecto)

    @app.post("/api/juego/correr")
    def api_juego_correr():
        """Corre un juego con la implementación de referencia (ejemplos de las lecciones): devuelve el registro."""
        datos = _json_objeto()
        return jsonify(correr({"op": "juego", "fuente": str(datos.get("codigo", ""))[:mis_proyectos.MAX_CODIGO],
                               "entradas": datos.get("entradas", []), "semilla": datos.get("semilla")}))

    @app.post("/api/juego/arbol")
    def api_juego_arbol():
        """El árbol del juego (TortuGame): el servidor analiza y valida, el navegador ejecuta (ADR-006/007)."""
        codigo = str((_json_objeto()).get("codigo", ""))
        if len(codigo) > mis_proyectos.MAX_CODIGO:
            return jsonify(ok=False, mensaje="Tu juego es demasiado largo."), 400
        try:
            return jsonify(ok=True, arbol=arbol_del_juego(codigo))
        except CodigoNoPermitido as e:
            linea = f"\n\n📍 Mirá la línea {e.linea}" if e.linea else ""
            return jsonify(ok=False, mensaje=f"🚫 Eso no se puede usar en un juego\n\n{e}{linea}", linea=e.linea)
        except SyntaxError as e:
            return jsonify(ok=False, mensaje=armar_mensaje_error(e), linea=e.lineno)
        except ValueError:
            # Python 3.9 rechaza con ValueError (no SyntaxError) el código con caracteres nulos.
            return jsonify(ok=False, mensaje="Tu juego tiene un carácter que no se puede usar. Borralo y probá de nuevo.",
                           linea=None)

    @app.get("/tortuga")
    def tortuga():
        proyecto, otra = _proyecto_pedido("tortuga")
        return otra or render_template("tortuga.html", proyecto=proyecto)

    @app.get("/proyectos")
    def proyectos():
        return render_template("proyectos.html", proyectos=mis_proyectos.listar(_cargar_progreso()),
                               maximo=mis_proyectos.MAX_PROYECTOS)
    @app.get("/proyectos-integradores/vscode")
    def guia_vscode():
        return render_template("guia_vscode.html")

    @app.get("/proyectos-integradores")
    def proyectos_integradores_pagina():
        return render_template("proyectos_integradores.html",
                               proyectos=proyectos_integradores.resumen_catalogo(_cargar_progreso()))

    @app.get("/proyectos-integradores/<proyecto_id>")
    def proyecto_integrador(proyecto_id):
        p = _cargar_progreso()
        estado = proyectos_integradores.estado(p, proyecto_id)
        if estado is None:
            return redirect(url_for("proyectos_integradores_pagina"))
        return render_template("proyecto_integrador.html", proyecto=estado,
                               ayudas=proyectos_integradores.ayudas(p, proyecto_id))


    # ─────────────── API ───────────────
    @app.post("/api/traducir")
    def api_traducir():
        fuente = (_json_objeto()).get("codigo", "")
        if not isinstance(fuente, str):
            abort(400)
        tipo = detectar_tipo(fuente)
        python = fuente if tipo == "python" else TraductorTortuScript().traducir_codigo(fuente)
        return jsonify(tipo=tipo, python=python)

    @app.post("/api/ejecutar")
    def api_ejecutar():
        datos = _json_objeto()
        return jsonify(correr({"op": "ejecutar", "fuente": datos.get("codigo", ""),
                               "entradas": datos.get("entradas", []), "semilla": datos.get("semilla")}))

    @app.post("/api/tortuga")
    def api_tortuga():
        datos = _json_objeto()
        return jsonify(correr({"op": "tortuga", "fuente": datos.get("codigo", ""),
                               "entradas": datos.get("entradas", []), "semilla": datos.get("semilla")}))

    def _paso_o_404(leccion_id, i):
        _, _, lec = _leccion_o_404(leccion_id)
        if not 0 <= i < len(lec["pasos"]):
            abort(404)
        if not _leccion_desbloqueada(leccion_id):
            abort(403)
        return lec, lec["pasos"][i]

    @app.post("/api/lecciones/<leccion_id>/pasos/<int:i>/comprobar")
    def api_comprobar_paso(leccion_id, i):
        lec, paso = _paso_o_404(leccion_id, i)
        if paso["tipo"] == "escribir":
            abort(400)                           # se evalúa ejecutando: .../evaluar
        clave = (_perfil_contexto(), leccion_id, i)
        estado_paso = intentos.setdefault(clave, {"errores": 0, "revelado": False})
        r = motor.comprobar(paso, (_json_objeto()).get("respuesta"), _ejecutar_para_motor(paso))
        if not r["ok"]:
            estado_paso["errores"] += 1
            return jsonify(ok=False, pista=r["pista"], malos=r["malos"],
                           puede_ver_respuesta=motor.puede_ver_respuesta(estado_paso["errores"]))
        p = _cargar_progreso()
        nivel_antes = progreso.calcular_nivel(p.get("xp_total", 0))[0]
        xp = 0 if paso["tipo"] == "explicacion" else motor.xp_por_intentos(estado_paso["errores"] + 1, False)
        perfecto = estado_paso["errores"] == 0
        info = _registrar_paso_leccion(p, leccion_id, i, xp, perfecto, len(lec["pasos"]))
        avisos = _avisos_tras(p)
        return jsonify(ok=True, xp=info["xp_ganado"], perfecto=perfecto,
                       sube_nivel=progreso.calcular_nivel(p["xp_total"])[0] > nivel_antes,
                       leccion=_resumen_leccion(leccion_id, info), estado_juego=_estado(), avisos=avisos)

    @app.post("/api/lecciones/<leccion_id>/pasos/<int:i>/respuesta")
    def api_ver_respuesta(leccion_id, i):
        lec, paso = _paso_o_404(leccion_id, i)
        if paso["tipo"] in ("escribir", "explicacion"):
            abort(400)
        clave = (_perfil_contexto(), leccion_id, i)
        estado_paso = intentos.setdefault(clave, {"errores": 0, "revelado": False})
        if not motor.puede_ver_respuesta(estado_paso["errores"]):
            abort(403)                           # primero hay que intentarlo (2 errores)
        estado_paso["revelado"] = True
        p = _cargar_progreso()
        info = _registrar_paso_leccion(p, leccion_id, i, 0, False, len(lec["pasos"]))
        return jsonify(respuesta=motor.respuesta_correcta(paso), leccion=_resumen_leccion(leccion_id, info),
                       estado_juego=_estado(), avisos=_avisos_tras(p))

    def _evaluar_escribir(leccion_id, i, paso, datos):
        """Ejecuta y evalúa un paso escribir. Web se evalúa declarativamente: el servidor
        nunca ejecuta HTML/CSS/JavaScript del alumno."""
        if paso.get("lenguaje") == "sql":
            r = {"evaluacion": sql_evaluacion.evaluar(
                datos.get("codigo", ""), paso["solucion"], paso.get("sql_dataset"), paso.get("sql") or {}
            )}
            if r["evaluacion"]["estado"] == evaluacion.CORRECTO:
                _, _, lec = _leccion_o_404(leccion_id)
                vistas = pistas_vistas.get((_perfil_contexto(), leccion_id, i), 0)
                estrellas, xp = evaluacion.estrellas_por_pistas(vistas)
                p = _cargar_progreso()
                nivel_antes = progreso.calcular_nivel(p.get("xp_total", 0))[0]
                indice = contenido.indices_ejercicio(leccion_id).get(i)
                if indice is not None:
                    mejora = _registrar_ejercicio(p, indice, estrellas, xp)
                    info = _registrar_paso_leccion(p, leccion_id, i, 0, estrellas == 3, len(lec["pasos"]))
                else:
                    info = _registrar_paso_leccion(p, leccion_id, i, xp, estrellas == 3, len(lec["pasos"]),
                                                   estrellas=estrellas)
                    mejora = info["xp_ganado"] > 0
                r["premio"] = {"estrellas": estrellas, "xp": xp, "mejora": mejora,
                               "sube_nivel": progreso.calcular_nivel(p["xp_total"])[0] > nivel_antes}
                r["leccion"] = _resumen_leccion(leccion_id, info)
                r["avisos"] = _avisos_tras(p)
            r["estado_juego"] = _estado()
            return r

        if paso.get("web"):
            reglas = paso.get("web") or {}
            lenguaje = paso.get("lenguaje") or reglas.get("lenguaje")
            r = {"evaluacion": web_evaluacion.evaluar(
                datos.get("codigo", ""), paso["solucion"], lenguaje, reglas
            )}
            if r["evaluacion"]["estado"] == evaluacion.CORRECTO:
                _, _, lec = _leccion_o_404(leccion_id)
                vistas = pistas_vistas.get((_perfil_contexto(), leccion_id, i), 0)
                estrellas, xp = evaluacion.estrellas_por_pistas(vistas)
                p = _cargar_progreso()
                nivel_antes = progreso.calcular_nivel(p.get("xp_total", 0))[0]
                indice = contenido.indices_ejercicio(leccion_id).get(i)
                if indice is not None:
                    mejora = _registrar_ejercicio(p, indice, estrellas, xp)
                    info = _registrar_paso_leccion(p, leccion_id, i, 0, estrellas == 3, len(lec["pasos"]))
                else:
                    info = _registrar_paso_leccion(p, leccion_id, i, xp, estrellas == 3, len(lec["pasos"]),
                                                   estrellas=estrellas)
                    mejora = info["xp_ganado"] > 0
                r["premio"] = {"estrellas": estrellas, "xp": xp, "mejora": mejora,
                               "sube_nivel": progreso.calcular_nivel(p["xp_total"])[0] > nivel_antes}
                r["leccion"] = _resumen_leccion(leccion_id, info)
                r["avisos"] = _avisos_tras(p)
            r["estado_juego"] = _estado()
            return r
        op = "evaluar_juego" if paso.get("juego") else "evaluar_tortuga" if paso.get("tortuga") else "evaluar"
        pedido = {"op": op, "fuente": datos.get("codigo", ""),
                  "entradas": datos.get("entradas", []), "solucion": paso["solucion"]}
        if paso.get("laberinto"):
            pedido.update(laberinto=paso["laberinto"], usar=paso.get("usar") or [])
        r = correr(pedido)
        ev = r.get("evaluacion")
        if ev and ev.get("objetivo") is not None:
            ev.pop("objetivo")                   # el dibujo objetivo ya está en la página
        if ev and ev["estado"] == evaluacion.CORRECTO:
            _, _, lec = _leccion_o_404(leccion_id)
            vistas = pistas_vistas.get((_perfil_contexto(), leccion_id, i), 0)
            estrellas, xp = evaluacion.estrellas_por_pistas(vistas)
            p = _cargar_progreso()
            nivel_antes = progreso.calcular_nivel(p.get("xp_total", 0))[0]
            indice = contenido.indices_ejercicio(leccion_id).get(i)
            if indice is not None:
                mejora = _registrar_ejercicio(p, indice, estrellas, xp)
                info = _registrar_paso_leccion(p, leccion_id, i, 0, estrellas == 3, len(lec["pasos"]))
            else:
                info = _registrar_paso_leccion(p, leccion_id, i, xp, estrellas == 3, len(lec["pasos"]),
                                                       estrellas=estrellas)
                mejora = info["xp_ganado"] > 0
            r["premio"] = {"estrellas": estrellas, "xp": xp, "mejora": mejora,
                           "sube_nivel": progreso.calcular_nivel(p["xp_total"])[0] > nivel_antes}
            r["leccion"] = _resumen_leccion(leccion_id, info)
            r["avisos"] = _avisos_tras(p)
        r["estado_juego"] = _estado()
        return r

    def _dar_pista(leccion_id, i, paso):
        clave = (_perfil_contexto(), leccion_id, i)
        nivel = min(pistas_vistas.get(clave, 0) + 1, 3)
        pistas_vistas[clave] = nivel
        sol = paso["solucion"].strip()
        lineas = sol.split("\n")
        if nivel == 1:
            palabras = paso.get("palabras_pista") or evaluacion.palabras_clave(sol)
            contenido_pista = {"titulo": "Palabras clave a usar", "texto": ", ".join(palabras)}
        elif nivel == 2:
            contenido_pista = {"titulo": "La primera línea es", "codigo": lineas[0],
                               "texto": f"En total son {len(lineas)} línea{'s' if len(lineas) != 1 else ''}."}
        else:
            contenido_pista = {"titulo": "Solución completa", "codigo": sol}
            if paso.get("web"):
                contenido_pista["lenguaje"] = paso.get("lenguaje", "html")
            elif paso.get("lenguaje") != "python":
                contenido_pista["python"] = TraductorTortuScript().traducir_codigo(sol)
        return jsonify(nivel=nivel, **contenido_pista)

    @app.post("/api/lecciones/<leccion_id>/pasos/<int:i>/evaluar")
    def api_evaluar_paso(leccion_id, i):
        lec, paso = _paso_o_404(leccion_id, i)
        if paso["tipo"] != "escribir":
            abort(400)
        return jsonify(_evaluar_escribir(leccion_id, i, paso, _json_objeto()))

    @app.post("/api/lecciones/<leccion_id>/pasos/<int:i>/pista")
    def api_pista_paso(leccion_id, i):
        lec, paso = _paso_o_404(leccion_id, i)
        if paso["tipo"] != "escribir":
            abort(400)
        return _dar_pista(leccion_id, i, paso)

    # Ejercicios clásicos (/ejercicios/N): mismas reglas, identificados por el índice de su 'escribir'.
    def _ejercicio_como_paso(n):
        ej = _ejercicio_o_404(n - 1)
        _, _, lec = _leccion_o_404(ej["leccion_id"])
        return ej["leccion_id"], ej["paso"], lec["pasos"][ej["paso"]]

    @app.post("/api/ejercicios/<int:n>/evaluar")
    def api_evaluar(n):
        indice = n - 1
        _ejercicio_o_404(indice)
        if not _desbloqueado(indice):
            abort(403)
        leccion_id, i, paso = _ejercicio_como_paso(n)
        return jsonify(_evaluar_escribir(leccion_id, i, paso, _json_objeto()))

    @app.post("/api/ejercicios/<int:n>/pista")
    def api_pista(n):
        leccion_id, i, paso = _ejercicio_como_paso(n)
        return _dar_pista(leccion_id, i, paso)

    def _tarjeta_de_la_sesion(datos):
        """(leccion_id, indice, paso) si la tarjeta es de la sesión de hoy; si no, 403."""
        try:
            leccion_id, i = str(datos.get("leccion", "")), int(datos.get("paso"))
        except (TypeError, ValueError):
            abort(400)
        sesion = practicas.get(_perfil_contexto())
        if not sesion or (leccion_id, i) not in sesion["pasos"]:
            abort(403)
        _, _, lec = _leccion_o_404(leccion_id)
        return leccion_id, i, lec["pasos"][i]

    @app.post("/api/practica/comprobar")
    def api_practica_comprobar():
        datos = _json_objeto()
        leccion_id, i, paso = _tarjeta_de_la_sesion(datos)
        clave = (_perfil_contexto(), "practica", leccion_id, i)
        estado_paso = intentos.setdefault(clave, {"errores": 0, "revelado": False})
        r = motor.comprobar(paso, datos.get("respuesta"), _ejecutar_para_motor(paso))
        if not r["ok"]:
            estado_paso["errores"] += 1
            return jsonify(ok=False, pista=r["pista"], malos=r["malos"],
                           puede_ver_respuesta=motor.puede_ver_respuesta(estado_paso["errores"]))
        p = _cargar_progreso()
        nivel_antes = progreso.calcular_nivel(p.get("xp_total", 0))[0]
        acierto = estado_paso["errores"] == 0
        ganado = _registrar_practica(p, leccion_id, i, acierto)
        intentos.pop(clave, None)
        avisos = _avisos_tras(p)
        return jsonify(ok=True, xp=ganado, perfecto=acierto,
                       sube_nivel=progreso.calcular_nivel(p["xp_total"])[0] > nivel_antes,
                       leccion={"siguiente": None}, estado_juego=_estado(), avisos=avisos)

    @app.post("/api/practica/respuesta")
    def api_practica_respuesta():
        datos = _json_objeto()
        leccion_id, i, paso = _tarjeta_de_la_sesion(datos)
        clave = (_perfil_contexto(), "practica", leccion_id, i)
        estado_paso = intentos.setdefault(clave, {"errores": 0, "revelado": False})
        if not motor.puede_ver_respuesta(estado_paso["errores"]):
            abort(403)
        estado_paso["revelado"] = True
        p = _cargar_progreso()
        _registrar_practica(p, leccion_id, i, False)
        intentos.pop(clave, None)
        return jsonify(respuesta=motor.respuesta_correcta(paso), leccion={"siguiente": None},
                       estado_juego=_estado(), avisos=_avisos_tras(p))

    def _con_proyectos(accion):
        """Aplica `accion(p)` al progreso; los errores que el chico puede corregir vuelven como 400."""
        p = _cargar_progreso()
        try:
            resultado = accion(p)
        except mis_proyectos.ErrorProyecto as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        _guardar_progreso(p)
        return jsonify(ok=True, id=resultado, total=len(p.get("proyectos", {})), avisos=_avisos_tras(p),
                       estado_juego=_estado())

    @app.post("/api/proyectos")
    def api_proyecto_guardar():
        d = _json_objeto()
        return _con_proyectos(lambda p: mis_proyectos.guardar(p, d.get("nombre"), d.get("tipo"), d.get("codigo"),
                                                              proyecto_id=d.get("id")))

    @app.post("/api/proyectos/<proyecto_id>/duplicar")
    def api_proyecto_duplicar(proyecto_id):
        return _con_proyectos(lambda p: mis_proyectos.duplicar(p, proyecto_id))

    @app.post("/api/proyectos/<proyecto_id>/borrar")
    def api_proyecto_borrar(proyecto_id):
        return _con_proyectos(lambda p: mis_proyectos.borrar(p, proyecto_id))
    @app.post("/api/proyectos-integradores/<proyecto_id>")
    def api_proyecto_integrador_iniciar(proyecto_id):
        p = _cargar_progreso()
        try:
            proyectos_integradores.iniciar(p, proyecto_id)
            _guardar_progreso(p)
        except proyectos_integradores.ErrorProyectoIntegrador as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        return jsonify(ok=True, url=url_for("proyecto_integrador", proyecto_id=proyecto_id),
                       estado=proyectos_integradores.estado(p, proyecto_id))

    @app.post("/api/proyectos-integradores/<proyecto_id>/archivo")
    def api_proyecto_integrador_archivo(proyecto_id):
        d = _json_objeto()
        p = _cargar_progreso()
        try:
            proyectos_integradores.guardar_archivo(p, proyecto_id, d.get("nombre"), d.get("codigo"))
            _guardar_progreso(p)
        except proyectos_integradores.ErrorProyectoIntegrador as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        return jsonify(ok=True)

    @app.post("/api/proyectos-integradores/<proyecto_id>/etapas/<etapa_id>")
    def api_proyecto_integrador_etapa(proyecto_id, etapa_id):
        p = _cargar_progreso()
        try:
            resultado = proyectos_integradores.validar_etapa(p, proyecto_id, etapa_id)
            if not resultado["ok"]:
                return jsonify(ok=False, mensaje=resultado["mensaje"]), 400
            _guardar_progreso(p)
        except proyectos_integradores.ErrorProyectoIntegrador as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        return jsonify(ok=True, completado=resultado["completado"])

    @app.post("/api/proyectos-integradores/<proyecto_id>/ayudas/<ayuda_id>")
    def api_proyecto_integrador_ayuda(proyecto_id, ayuda_id):
        p = _cargar_progreso()
        try:
            texto = proyectos_integradores.ver_ayuda(p, proyecto_id, ayuda_id)
            _guardar_progreso(p)
        except proyectos_integradores.ErrorProyectoIntegrador as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        return jsonify(ok=True, texto=texto)

    @app.post("/api/proyectos-integradores/<proyecto_id>/exportar")
    def api_proyecto_integrador_exportar(proyecto_id):
        p = _cargar_progreso()
        try:
            datos, nombre = proyectos_integradores.exportar(p, proyecto_id)
        except proyectos_integradores.ErrorProyectoIntegrador as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        return jsonify(ok=True, nombre=nombre, archivo=base64.b64encode(datos).decode("ascii"))


    @app.post("/api/onboarding")
    def api_onboarding():
        datos = _json_objeto()
        crudo = str(datos.get("nombre") or "").strip()
        if crudo and not progreso.sanitizar_perfil(crudo):
            return jsonify(ok=False, mensaje="Usá letras o números para el nombre."), 400
        entrada = datos.get("entrada")                   # diagnóstico (ADR-004): solo el punto que le toca
        if entrada and not isinstance(entrada, str):
            return jsonify(ok=False, mensaje="Alguna respuesta no es válida."), 400
        if entrada and entrada not in diagnostico.entradas_permitidas(datos.get("experiencia")):
            return jsonify(ok=False, mensaje="Alguna respuesta no es válida."), 400
        p = _cargar_progreso()
        ok = progreso.guardar_config(
            p, experiencia=datos.get("experiencia"), meta_min=datos.get("meta_min"),
            nombre=crudo or None, onboarding=True
        )
        if not ok:
            return jsonify(ok=False, mensaje="Alguna respuesta no es válida."), 400
        if entrada:
            progreso.saltear_hasta(
                p, [lec["id"] for _, lec in contenido.lecciones(contenido.cargar_curso())],
                entrada
            )
        _guardar_progreso(p)
        return jsonify(ok=True, actual=_nombre_perfil_contexto(p), estado=_estado())

    @app.post("/api/config")
    def api_config():
        datos = _json_objeto()
        p = _cargar_progreso()
        if not progreso.guardar_config(p, meta_min=datos.get("meta_min")):
            return jsonify(ok=False, mensaje="Esa meta no existe."), 400
        _guardar_progreso(p)
        return jsonify(ok=True, estado=_estado())

    @app.post("/api/ajustes")
    def api_ajustes():
        datos = _json_objeto()
        p = _cargar_progreso()
        cambios = {k: datos.get(k) for k in progreso.AJUSTES if k in datos}
        if not progreso.guardar_ajustes(p, **cambios):
            return jsonify(ok=False, mensaje="Ese ajuste no existe."), 400
        _guardar_progreso(p)
        return jsonify(ok=True, ajustes=progreso.ajustes_de(p))

    @app.get("/api/perfiles")
    def api_perfiles():
        contexto = _contexto()
        cuentas = _educativo().cuentas
        perfiles = [
            {"id": p.id, "nombre": p.display_name}
            for p in cuentas.listar_child_profiles(contexto.cuenta.id, solo_activos=True)
        ]
        return jsonify(modo="cuenta", actual=contexto.perfil.id, perfiles=perfiles)

    @app.get("/api/perfil/exportar")
    def api_exportar_perfil():
        """El progreso del perfil actual, listo para descargar como archivo."""
        nombre = _nombre_perfil_contexto()
        return jsonify(archivo=respaldo.nombre_de_archivo(nombre),
                       datos=respaldo.exportar(_cargar_progreso(), nombre))

    @app.post("/api/diagnostico")
    def api_diagnostico():
        """Corrige la prueba de nivel (ADR-004) y recomienda dónde empezar. No guarda nada: lo elige el chico."""
        try:
            entrada = diagnostico.recomendar((_json_objeto()).get("respuestas"))
        except ValueError as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        seccion, lec = next((s, l) for s, l in contenido.lecciones(contenido.cargar_curso()) if l["id"] == entrada)
        return jsonify(ok=True, entrada=entrada, seccion=seccion["titulo"], numero=lec["titulo"].partition(". ")[0])

    @app.post("/api/intereses/<encuesta_id>")
    def api_intereses(encuesta_id):
        """Guarda lo que el chico eligió (o "Ahora no"), solo en su progreso local."""
        datos = _json_objeto()
        p = _cargar_progreso()
        try:
            if datos.get("omitir") is True:
                intereses.omitir(p, encuesta_id)
            else:
                intereses.responder(p, encuesta_id, datos.get("respuestas"))
        except ValueError as e:
            return jsonify(ok=False, mensaje=str(e)), 400
        _guardar_progreso(p)
        return jsonify(ok=True)

    @app.get("/api/catalogo-producto")
    def api_catalogo_producto():
        """Catálogo curricular, competencias y acceso para la UI de producto V1."""
        return jsonify(catalogo_producto.progreso_para_mostrar(_cargar_progreso()))

    @app.get("/api/estado")
    def api_estado():
        return jsonify(_estado())

    return app
