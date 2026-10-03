"""Boundary HTTP mínima para cuentas adultas; separada del runtime educativo local.

La ruta de cuenta usa la infraestructura server-side de tortuscript.auth.
No activa todavía el despliegue remoto: create_app mantiene el límite localhost.
"""
import logging
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, url_for

from tortuscript.acceso import AccesoProducto
from tortuscript.auth import AuthError, AuthRepository
from tortuscript.cuentas import CuentaError, CuentaRepository
from tortuscript.migracion_progreso import MigracionProgresoError, MigracionProgresoLocal
from tortuscript.perfil_educativo import ContextoEducativoError, PerfilEducativoService
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.runtime_educativo import RuntimeEducativo
from tortuscript.rate_limit import RateLimiter

def _rate_limiter():
    # Cada instancia Flask mantiene su propio limitador. Evita compartir estado
    # entre aplicaciones de prueba o instancias WSGI distintas en el mismo proceso.
    return current_app.extensions.setdefault("tortu_rate_limiter", RateLimiter())

logger = logging.getLogger(__name__)

bp = Blueprint("cuenta", __name__, url_prefix="/cuenta")


def _repos():
    path = Path(current_app.config["ACCOUNT_DB"])
    cuentas = CuentaRepository(path)
    cuentas.ensure_schema()
    auth = AuthRepository(path)
    auth.ensure_schema()
    return cuentas, auth


def _educativo():
    cuentas, auth = _repos()
    progreso_dir = Path(current_app.config.get("PROGRESS_DIR", Path(current_app.instance_path) / "progreso_perfiles"))
    store = ProgresoChildProfile(progreso_dir)
    acceso = AccesoProducto(cuentas)
    return PerfilEducativoService(cuentas, auth, store, acceso)


def _limit_or_429(key, limit, window):
    allowed, retry_after = _rate_limiter().allow(key, limit, window)
    if allowed:
        return None
    respuesta = jsonify(ok=False, mensaje="Demasiados intentos. Probá nuevamente más tarde.")
    respuesta.headers["Retry-After"] = str(retry_after)
    return respuesta, 429

def _email_sender_configurado():
    return callable(current_app.config.get("ACCOUNT_EMAIL_SENDER"))


def _emitir_email(tipo, email, token, expires):
    sender = current_app.config.get("ACCOUNT_EMAIL_SENDER")
    if not callable(sender):
        return False
    sender(tipo=tipo, email=email, token=token, expires=expires)
    return True

def _intentar_emitir_email(tipo, email, token, expires):
    """Aísla fallos del proveedor para no convertirlos en errores HTTP inesperados."""
    try:
        return _emitir_email(tipo, email, token, expires)
    except Exception:
        # No registrar token, dirección ni el texto arbitrario de la excepción del proveedor.
        logger.error("Falló el envío de correo transaccional (tipo=%s)", tipo)
        return False

def _safe_next_url(value, default="/"):
    """Acepta solo rutas locales para evitar redirecciones abiertas."""
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return default
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return default
    return value


def _cookie_config():
    return {
        "httponly": True,
        "secure": bool(current_app.config.get("ACCOUNT_COOKIE_SECURE", False)),
        "samesite": current_app.config.get("ACCOUNT_COOKIE_SAMESITE", "Lax"),
        "path": "/",
        "max_age": 12 * 60 * 60,
    }


def _session():
    raw = request.cookies.get("tortu_session")
    if not raw:
        return None, None, None
    cuentas, auth = _repos()
    row = auth.get_session(raw)
    return cuentas, auth, row


def _require_session():
    cuentas, auth, row = _session()
    if not row:
        return None
    return cuentas, auth, row


def _require_csrf(auth, raw_session):
    csrf = request.headers.get("X-Tortu-CSRF") or request.form.get("csrf", "")
    if not auth.csrf_ok(raw_session, csrf):
        return False
    return True


@bp.before_request
def _proteger_login_csrf():
    """Rechaza intentos de login desde otro origen en navegadores modernos."""
    if request.endpoint != "cuenta.login" or request.method != "POST":
        return None

    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        return jsonify(ok=False, mensaje="Solicitud de origen no permitido."), 403

    origen = request.headers.get("Origin") or request.headers.get("Referer")
    if origen:
        parsed = urlsplit(origen)
        if (
            parsed.scheme.lower() != request.scheme.lower()
            or parsed.netloc.lower() != request.host.lower()
        ):
            return jsonify(ok=False, mensaje="Solicitud de origen no permitido."), 403
    return None


@bp.get("/registrar")
def registrar():
    return render_template("cuenta/registrar.html")


@bp.get("/ingresar")
def ingresar():
    if _require_session():
        return redirect(url_for("cuenta.seleccionar_perfil_pagina"))
    return render_template("cuenta/ingresar.html")


@bp.get("/configuracion")
def configuracion():
    resultado = _require_session()
    if not resultado:
        return redirect(url_for("cuenta.ingresar"))
    cuentas, _, row = resultado
    cuenta = cuentas.obtener_account(row["account_id"])
    perfiles = cuentas.listar_child_profiles(row["account_id"])
    return render_template(
        "cuenta/configuracion.html",
        cuenta=cuenta,
        perfiles=perfiles,
        max_perfiles=3,
    )


@bp.get("/seleccionar-perfil")
def seleccionar_perfil_pagina():
    resultado = _require_session()
    if not resultado:
        return redirect(url_for("cuenta.ingresar"))
    cuentas, _, row = resultado
    perfiles = cuentas.listar_child_profiles(row["account_id"])
    return render_template(
        "cuenta/perfiles.html",
        perfiles=perfiles,
        csrf=request.cookies.get("tortu_csrf", ""),
        perfil_activo=row["active_profile_id"],
        next_url=_safe_next_url(request.args.get("next", "/")),
    )


@bp.post("/registrar")
def registrar_post():
    limit = _limit_or_429(f"register:{request.remote_addr or 'unknown'}", 5, 3600)
    if limit:
        return limit
    datos = request.form if request.form else (request.get_json(silent=True) or {})
    email = datos.get("email")
    password = datos.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return render_template("cuenta/registrar.html", error="Correo y contraseña son obligatorios."), 400
    if not _email_sender_configurado():
        return render_template(
            "cuenta/registrar.html",
            error="El registro no está disponible porque el envío de correo no está configurado.",
        ), 503
    cuentas, auth = _repos()
    try:
        auth.validar_password(password)
        cuenta = cuentas.crear_account(email)
        auth.set_password(cuenta.id, password)
    except CuentaError as exc:
        return render_template("cuenta/registrar.html", error=str(exc)), 400
    except AuthError as exc:
        return render_template("cuenta/registrar.html", error=str(exc)), 400
    token, expires = auth.create_verification_token(cuenta.id)
    if not _intentar_emitir_email("verification", cuenta.email, token, expires):
        return render_template(
            "cuenta/pendiente.html",
            email=cuenta.email,
            mensaje="No pudimos confirmar el envío. Podés solicitar otro enlace desde esta página.",
        ), 503
    return render_template("cuenta/pendiente.html", email=cuenta.email), 202


@bp.post("/registro")
def registro():
    limit = _limit_or_429(f"register:{request.remote_addr or 'unknown'}", 5, 3600)
    if limit:
        return limit
    datos = request.get_json(silent=True) or {}
    email = datos.get("email")
    password = datos.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify(ok=False, mensaje="Correo y contraseña son obligatorios."), 400
    if not _email_sender_configurado():
        return jsonify(
            ok=False,
            codigo="envio_email_no_configurado",
            mensaje="El registro no está disponible porque el envío de correo no está configurado.",
        ), 503
    cuentas, auth = _repos()
    try:
        auth.validar_password(password)
        cuenta = cuentas.crear_account(email)
        auth.set_password(cuenta.id, password)
    except CuentaError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 400
    except AuthError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 400
    token, expires = auth.create_verification_token(cuenta.id)
    if not _intentar_emitir_email("verification", cuenta.email, token, expires):
        return jsonify(
            ok=False,
            codigo="envio_email_fallido",
            mensaje="No pudimos confirmar el envío. Solicitá otro enlace de verificación.",
        ), 503
    return jsonify(ok=True, estado="pendiente_verificacion", email=cuenta.email), 202


@bp.get("/verificar-email")
def verificar_email():
    # GET no consume tokens: los escáneres de enlaces de correo pueden abrirlos
    # automáticamente. La confirmación efectiva requiere un POST explícito.
    token = request.args.get("token", "")
    if not token:
        if request.accept_mimetypes.best == "application/json":
            return jsonify(ok=False, mensaje="El enlace no es válido o ya expiró."), 400
        return render_template("cuenta/verificacion.html", ok=False), 400
    if request.accept_mimetypes.best == "application/json":
        return jsonify(ok=True, estado="confirmacion_requerida")
    return render_template("cuenta/verificacion.html", confirmar=True, token=token)


@bp.post("/verificar-email")
def confirmar_verificacion_email():
    limit = _limit_or_429(f"verify-email:{request.remote_addr or 'unknown'}", 10, 900)
    if limit:
        return limit
    datos = request.get_json(silent=True) or request.form
    token = datos.get("token", "")
    try:
        _, auth = _repos()
        auth.verify_email_token(token)
    except AuthError:
        if request.accept_mimetypes.best == "application/json":
            return jsonify(ok=False, mensaje="El enlace no es válido o ya expiró."), 400
        return render_template("cuenta/verificacion.html", ok=False), 400
    if request.accept_mimetypes.best == "application/json":
        return jsonify(ok=True, estado="correo_verificado")
    return render_template("cuenta/verificacion.html", ok=True)


@bp.post("/reenviar-verificacion")
def reenviar_verificacion():
    """Reintenta el correo sin revelar si una cuenta existe o ya está verificada."""
    limit = _limit_or_429(f"resend-verification:{request.remote_addr or 'unknown'}", 5, 3600)
    if limit:
        return limit
    if not _email_sender_configurado():
        if request.form:
            return render_template(
                "cuenta/pendiente.html",
                email=request.form.get("email", ""),
                mensaje="El envío de correo no está configurado en esta instalación.",
            ), 503
        return jsonify(
            ok=False,
            codigo="envio_email_no_configurado",
            mensaje="El reenvío no está disponible porque el envío de correo no está configurado.",
        ), 503
    datos = request.form if request.form else (request.get_json(silent=True) or {})
    email = datos.get("email")
    if isinstance(email, str) and _email_sender_configurado():
        _, auth = _repos()
        token_info = auth.create_verification_token_for_email(email)
        if token_info:
            token, expires = token_info
            _intentar_emitir_email("verification", email.strip().lower(), token, expires)
    # Misma respuesta para correo inexistente, verificado o proveedor fallido.
    if request.form:
        return render_template(
            "cuenta/pendiente.html",
            email=email.strip() if isinstance(email, str) else "",
            mensaje="Si la cuenta existe y todavía no está verificada, enviaremos un nuevo enlace.",
        ), 202
    return jsonify(
        ok=True,
        estado="solicitud_recibida",
        mensaje="Si la cuenta existe y todavía no está verificada, enviaremos un nuevo enlace.",
    ), 202


@bp.post("/recuperar")
def solicitar_recuperacion():
    # La respuesta no depende de que la cuenta exista; solo indica si el canal
    # global de correo está disponible en esta instalación.
    if not _email_sender_configurado():
        return jsonify(
            ok=False,
            codigo="envio_email_no_configurado",
            mensaje="La recuperación no está disponible porque el envío de correo no está configurado.",
        ), 503
    limit = _limit_or_429(f"recovery:{request.remote_addr or 'unknown'}", 5, 3600)
    if limit:
        return limit
    datos = request.get_json(silent=True) or {}
    email = datos.get("email")
    if isinstance(email, str):
        _, auth = _repos()
        token_info = auth.create_recovery_token(email)
        if token_info:
            token, expires = token_info
            cuenta = _repos()[0].obtener_account_por_email(email)
            if cuenta:
                _intentar_emitir_email("recovery", cuenta.email, token, expires)
    return jsonify(ok=True, estado="solicitud_recibida"), 202


@bp.post("/restablecer-password")
def restablecer_password():
    datos = request.get_json(silent=True) or {}
    token = datos.get("token")
    password = datos.get("password")
    if not isinstance(token, str) or not isinstance(password, str):
        return jsonify(ok=False, mensaje="Token y contraseña son obligatorios."), 400
    limit = _limit_or_429(f"reset-password:{request.remote_addr or 'unknown'}", 10, 900)
    if limit:
        return limit
    try:
        _, auth = _repos()
        auth.reset_password(token, password)
    except AuthError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 400
    return jsonify(ok=True, estado="password_restablecida")


@bp.post("/login")
def login():
    datos = request.get_json(silent=True) or request.form
    email = datos.get("email")
    password = datos.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify(ok=False, mensaje="Correo o contraseña incorrectos."), 401
    email_normalizado = email.strip().lower()
    ip = request.remote_addr or "unknown"
    limit_ip = _limit_or_429(f"login-ip:{ip}", 30, 900)
    if limit_ip:
        return limit_ip
    limit_cuenta = _limit_or_429(f"login-account:{ip}:{email_normalizado}", 10, 900)
    if limit_cuenta:
        return limit_cuenta
    _, auth = _repos()
    try:
        cuenta = auth.verify_password(email, password)
        raw_session, csrf, expires = auth.create_session(cuenta["id"])
    except AuthError:
        # No distinguir cuenta inexistente, contraseña incorrecta o correo pendiente.
        mensaje = "Correo o contraseña incorrectos, o cuenta sin verificar."
        if request.form:
            return render_template("cuenta/ingresar.html", error=mensaje), 401
        return jsonify(ok=False, mensaje=mensaje), 401
    if request.form:
        respuesta = make_response(redirect(url_for("cuenta.seleccionar_perfil_pagina")))
    else:
        respuesta = make_response(jsonify(ok=True, cuenta={"id": cuenta["id"], "email": cuenta["email"], "role": cuenta["role"]},
                                          csrf=csrf, expira=expires.isoformat()))
    respuesta.set_cookie("tortu_session", raw_session, **_cookie_config())
    respuesta.set_cookie(
        "tortu_csrf", csrf,
        httponly=False,
        secure=bool(current_app.config.get("ACCOUNT_COOKIE_SECURE", False)),
        samesite=current_app.config.get("ACCOUNT_COOKIE_SAMESITE", "Lax"),
        path="/",
        max_age=12 * 60 * 60,
    )
    return respuesta


@bp.get("/me")
def me():
    resultado = _require_session()
    if not resultado:
        return jsonify(autenticado=False), 401
    cuentas, auth, row = resultado
    cuenta = cuentas.obtener_account(row["account_id"])
    perfiles = cuentas.listar_child_profiles(row["account_id"])
    return jsonify(
        autenticado=True,
        cuenta={"id": cuenta.id, "email": cuenta.email, "role": cuenta.role},
        perfiles=[{"id": p.id, "nombre": p.display_name} for p in perfiles],
        perfil_activo=row["active_profile_id"] if "active_profile_id" in row.keys() else None,
    )


@bp.get("/csrf")
def csrf():
    resultado = _require_session()
    if not resultado:
        return jsonify(autenticado=False), 401
    return jsonify(autenticado=True, requiere_csrf=True)


@bp.post("/logout")
def logout():
    raw = request.cookies.get("tortu_session")
    if not raw:
        return jsonify(ok=True)
    resultado = _session()
    if resultado:
        _, auth, _ = resultado
        if not _require_csrf(auth, raw):
            return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
        auth.revoke(raw)
    if request.form:
        respuesta = make_response(redirect(url_for("cuenta.ingresar")))
    else:
        respuesta = make_response(jsonify(ok=True))
    respuesta.delete_cookie("tortu_session", path="/")
    respuesta.delete_cookie("tortu_csrf", path="/")
    return respuesta


@bp.post("/perfiles")
def crear_perfil():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    cuentas, auth, row = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    nombre = (request.get_json(silent=True) or {}).get("nombre")
    try:
        perfil = cuentas.crear_child_profile(row["account_id"], nombre)
    except CuentaError as exc:
        if request.form:
            return render_template("cuenta/perfiles.html", perfiles=cuentas.listar_child_profiles(row["account_id"]), csrf=request.cookies.get("tortu_csrf", ""), perfil_activo=row["active_profile_id"], next_url=_safe_next_url(request.args.get("next", "/")), error=str(exc)), 400
        return jsonify(ok=False, mensaje=str(exc)), 400
    if request.form:
        return redirect(url_for("cuenta.seleccionar_perfil_pagina"))
    return jsonify(ok=True, perfil={"id": perfil.id, "nombre": perfil.display_name}), 201


@bp.post("/perfil")
def seleccionar_perfil():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, row = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    datos = request.get_json(silent=True) or request.form
    profile_id = datos.get("perfil_id")
    if not profile_id:
        return jsonify(ok=False, mensaje="Falta perfil_id."), 400
    try:
        auth.select_profile(raw, profile_id)
    except AuthError as exc:
        if request.form:
            return redirect(url_for("cuenta.seleccionar_perfil_pagina")), 403
        return jsonify(ok=False, mensaje=str(exc)), 403
    if request.form:
        return redirect(_safe_next_url(request.form.get("next"), url_for("inicio")))
    return jsonify(ok=True, perfil_activo=profile_id)


@bp.get("/progreso")
def obtener_progreso():
    raw = request.cookies.get("tortu_session")
    try:
        service = _educativo()
        contexto = service.contexto(raw)
        snapshot = service.cargar_progreso(raw)
    except ContextoEducativoError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 401
    return jsonify(
        ok=True,
        perfil={"id": contexto.perfil.id, "nombre": contexto.perfil.display_name},
        progreso=None if snapshot is None else {
            "contract_version": snapshot.schema_version,
            "profile_id": snapshot.profile_id,
            "updated_at": snapshot.updated_at,
            "data": snapshot.data,
        },
    )


@bp.put("/progreso")
def guardar_progreso():
    # Un snapshot completo enviado por el navegador permite falsificar XP,
    # ejercicios y finalización de lecciones. La persistencia se realiza desde
    # operaciones evaluadas en el servidor; no se aceptan escrituras genéricas.
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, _ = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    return jsonify(
        ok=False,
        codigo="escritura_no_autoritativa",
        mensaje="No se aceptan snapshots de progreso enviados por el cliente.",
    ), 410


@bp.get("/acceso")
def acceso_producto():
    raw = request.cookies.get("tortu_session")
    producto = request.args.get("producto", "")
    try:
        service = _educativo()
        contexto = service.contexto(raw)
        acceso = service.resumen_acceso(raw, [producto])
    except ContextoEducativoError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 401
    return jsonify(
        ok=True,
        perfil_id=contexto.perfil.id,
        producto=producto,
        permitido=acceso.get(producto, False),
    )


@bp.get("/progreso/locales")
def listar_progresos_locales():
    if not current_app.config.get("ENABLE_LOCAL_PROGRESS_MIGRATION", False):
        abort(404)
    raw = request.cookies.get("tortu_session")
    try:
        locales = MigracionProgresoLocal(_educativo()).listar_locales(raw)
    except (ContextoEducativoError, MigracionProgresoError) as exc:
        return jsonify(ok=False, mensaje=str(exc)), 401
    return jsonify(ok=True, perfiles=locales)


@bp.post("/progreso/importar-local")
def importar_progreso_local():
    if not current_app.config.get("ENABLE_LOCAL_PROGRESS_MIGRATION", False):
        abort(404)
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, _ = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    datos = request.get_json(silent=True) or {}
    nombre = datos.get("perfil_local")
    reemplazar = datos.get("reemplazar") is True
    try:
        snapshot = MigracionProgresoLocal(_educativo()).importar_local(raw, nombre, reemplazar=reemplazar)
    except (ContextoEducativoError, MigracionProgresoError) as exc:
        return jsonify(ok=False, mensaje=str(exc)), 400
    return jsonify(
        ok=True,
        profile_id=snapshot.profile_id,
        updated_at=snapshot.updated_at,
        progreso=snapshot.data,
    )


@bp.get("/runtime/progreso")
def runtime_progreso():
    """Primer punto de entrada del runtime educativo autenticado, aún separado del runtime local."""
    raw = request.cookies.get("tortu_session")
    try:
        runtime = RuntimeEducativo(_educativo())
        return jsonify(ok=True, **runtime.snapshot_publico(raw))
    except ContextoEducativoError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 401


@bp.post("/runtime/ejercicio")
def runtime_registrar_ejercicio():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, _ = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    # No aceptar puntuación/XP declarados por el cliente: se pueden falsificar.
    # La evaluación autoritativa vive en /api/ejercicios/<n>/evaluar.
    return jsonify(
        ok=False,
        codigo="evaluacion_requerida",
        mensaje="La puntuación debe obtenerse mediante la evaluación del ejercicio.",
        evaluador="/api/ejercicios/<n>/evaluar",
    ), 410


@bp.post("/runtime/leccion/paso")
def runtime_registrar_paso():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, _ = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    # El cliente no puede declarar un paso correcto ni decidir cuántos pasos tiene la lección.
    # El endpoint canónico evalúa el contenido y deriva los metadatos del curso.
    return jsonify(
        ok=False,
        codigo="evaluacion_requerida",
        mensaje="El paso debe comprobarse mediante el evaluador de la lección.",
        evaluador="/api/lecciones/<leccion_id>/pasos/<i>/evaluar",
    ), 410


@bp.post("/runtime/practica")
def runtime_registrar_practica():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, _ = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    # "acierto" no es evidencia de una respuesta correcta. La práctica se acredita
    # únicamente a través de /api/practica/comprobar, que valida la respuesta del alumno.
    return jsonify(
        ok=False,
        codigo="comprobacion_requerida",
        mensaje="La práctica debe comprobarse mediante el evaluador de respuestas.",
        evaluador="/api/practica/comprobar",
    ), 410


@bp.get("/runtime/proyectos")
def runtime_listar_proyectos():
    raw = request.cookies.get("tortu_session")
    try:
        proyectos = RuntimeEducativo(_educativo()).listar_proyectos(raw)
    except ContextoEducativoError as exc:
        return jsonify(ok=False, mensaje=str(exc)), 401
    return jsonify(ok=True, proyectos=proyectos)


@bp.post("/runtime/proyectos")
def runtime_guardar_proyecto():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    _, auth, _ = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    datos = request.get_json(silent=True) or {}
    try:
        proyecto_id = RuntimeEducativo(_educativo()).guardar_proyecto(
            raw, datos.get("nombre"), datos.get("tipo"), datos.get("codigo"), datos.get("proyecto_id"))
    except (ContextoEducativoError, ValueError, KeyError) as exc:
        return jsonify(ok=False, mensaje=str(exc)), 400
    return jsonify(ok=True, proyecto_id=proyecto_id)
