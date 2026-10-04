"""Boundary HTTP mínima para cuentas adultas; separada del runtime educativo local.

La ruta de cuenta usa la infraestructura server-side de tortuscript.auth.
No activa todavía el despliegue remoto: create_app mantiene el límite localhost.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, jsonify, make_response, redirect, render_template, request, url_for

from tortuscript import federacion, pagos
from tortuscript.acceso import AccesoProducto
from tortuscript.auth import AuthError, AuthRepository
from tortuscript.cuentas import DIAS_DE_GRACIA_ELIMINACION, MAX_CHILD_PROFILES, CuentaError, CuentaRepository
from tortuscript.progreso_childprofile import ProgresoPerfilError
from tortuscript.migracion_progreso import MigracionProgresoError, MigracionProgresoLocal
from tortuscript.perfil_educativo import ContextoEducativoError, PerfilEducativoService
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.runtime_educativo import RuntimeEducativo
from tortuscript.rate_limit import RateLimiter, SQLiteRateLimiter

def _rate_limiter():
    # Por defecto se mantiene el limitador local, apropiado para desarrollo/pruebas.
    # Un despliegue multi-worker puede configurar ACCOUNT_RATE_LIMIT_DB en un
    # volumen compartido para coordinar límites entre procesos de la misma máquina.
    limiter = current_app.extensions.get("tortu_rate_limiter")
    if limiter is None:
        shared_db = current_app.config.get("ACCOUNT_RATE_LIMIT_DB")
        limiter = SQLiteRateLimiter(shared_db) if shared_db else RateLimiter()
        current_app.extensions["tortu_rate_limiter"] = limiter
    return limiter

logger = logging.getLogger(__name__)

bp = Blueprint("cuenta", __name__, url_prefix="/cuenta")


def _json_dict():
    """Devuelve un objeto JSON o un diccionario vacío para cuerpos inválidos/no objeto."""
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else {}


def _form_or_json_dict():
    """Normaliza los cuerpos de formularios y JSON sin asumir que JSON sea un objeto."""
    return request.form if request.form else _json_dict()

def _repos():
    path = Path(current_app.config["ACCOUNT_DB"])
    cuentas = CuentaRepository(path)
    auth = AuthRepository(path)
    # El esquema se asegura una vez por archivo y por proceso: hacerlo en cada pedido
    # costaba una docena de transacciones DDL por página. La marca incluye el inodo
    # para volver a asegurarlo si el archivo se reemplaza (restauración de backup).
    listos = current_app.extensions.setdefault("tortu_esquemas_listos", set())
    try:
        marca = (str(path), path.stat().st_ino)
    except OSError:
        marca = None
    if marca is None or marca not in listos:
        cuentas.ensure_schema()
        auth.ensure_schema()
        listos.add((str(path), path.stat().st_ino))
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


def _next_pedido(default="/"):
    """Destino local pedido por formulario o query string, ya validado."""
    return _safe_next_url(request.form.get("next") or request.args.get("next"), default)


def _pagina_perfiles(cuentas, row, estado=200, error=None):
    return render_template(
        "cuenta/perfiles.html",
        perfiles=cuentas.listar_child_profiles(row["account_id"], solo_activos=True),
        csrf=request.cookies.get("tortu_csrf", ""),
        perfil_activo=row["active_profile_id"],
        next_url=_next_pedido(),
        max_perfiles=MAX_CHILD_PROFILES,
        error=error,
    ), estado


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


@bp.after_request
def _sin_cache(respuesta):
    """Las páginas de cuenta llevan tokens, correos y perfiles: no deben quedar en caché compartida ni en el historial."""
    respuesta.headers.setdefault("Cache-Control", "no-store")
    return respuesta


@bp.get("/registrar")
def registrar():
    return render_template("cuenta/registrar.html")


@bp.get("/ingresar")
def ingresar():
    destino = _next_pedido()
    if _require_session():
        return redirect(url_for("cuenta.seleccionar_perfil_pagina", next=destino))
    return render_template("cuenta/ingresar.html", next_url=destino)


AVISOS_CONFIGURACION = {
    "renombrado": "El nombre del perfil se cambió.",
    "archivado": "El perfil se archivó. Su progreso queda guardado y se puede restaurar.",
    "restaurado": "El perfil volvió a estar disponible.",
    "password": "La contraseña se cambió. Cerramos las demás sesiones abiertas.",
    "consentimiento": "Guardamos tu decisión.",
    "eliminado": "El perfil y su progreso se eliminaron de forma definitiva.",
    "reactivada": "Cancelamos el pedido de eliminación: la cuenta sigue activa y no se borró nada.",
}
AVISOS_SUSCRIPCION = {
    "informada": "Recibimos tu aviso. Cuando confirmemos la transferencia, el acceso se activa solo.",
    "cancelada": "Cancelaste la orden de pago.",
}
NOMBRES_PRODUCTO = {"tortuscript-premium": "TortuScript Premium", "croco-script": "Croco-Script"}
# Finalidades que el adulto puede aceptar o revocar desde la configuración, con la versión de su aviso.
AVISOS_DE_CONSENTIMIENTO = {"tutor_ia": "2026-10-04"}
# Versión del texto que acepta el adulto al registrarse (web/templates/cuenta/registrar.html).
VERSION_AVISO_RESPONSABLE = "2026-10-04"


def _suscripciones(account_id):
    return _servicio_pagos().listar_suscripciones(account_id)


def _pagina_configuracion(cuentas, auth, row, estado=200, error=None):
    perfiles = cuentas.listar_child_profiles(row["account_id"])
    return render_template(
        "cuenta/configuracion.html",
        cuenta=cuentas.obtener_account(row["account_id"]),
        perfiles=[p for p in perfiles if p.active],
        archivados=[p for p in perfiles if not p.active],
        max_perfiles=MAX_CHILD_PROFILES,
        dias_de_gracia=DIAS_DE_GRACIA_ELIMINACION,
        csrf=request.cookies.get("tortu_csrf", ""),
        consentimientos=cuentas.listar_consentimientos(row["account_id"]),
        suscripciones=_suscripciones(row["account_id"]),
        tutor_configurado=current_app.config.get("TUTOR_PROVEEDOR") is not None,
        tutor_aceptado=cuentas.tiene_consentimiento(row["account_id"], "tutor_ia"),
        aviso=AVISOS_CONFIGURACION.get(request.args.get("ok", "")),
        error=error,
    ), estado


def _servicio_pagos():
    from web.pagos_routes import servicio_de_pagos
    return servicio_de_pagos()


def _pagina_suscripcion(cuentas, row, estado=200, error=None):
    oferta = current_app.config.get("PAGOS") or pagos.ConfiguracionPagos()
    servicio = _servicio_pagos()
    ordenes = servicio.listar_ordenes(row["account_id"])
    return render_template(
        "cuenta/suscripcion.html",
        oferta=oferta,
        producto=NOMBRES_PRODUCTO.get(oferta.producto, oferta.producto),
        con_acceso=cuentas.tiene_entitlement(row["account_id"], oferta.producto),
        es_admin=cuentas.es_admin(row["account_id"]),
        suscripciones=servicio.listar_suscripciones(row["account_id"]),
        orden_abierta=next((o for o in ordenes if o["estado"] in pagos.ORDENES_ABIERTAS), None),
        ordenes_cerradas=[o for o in ordenes if o["estado"] not in pagos.ORDENES_ABIERTAS][:5],
        medios=pagos.MEDIOS_DE_PAGO,
        nombres_producto=NOMBRES_PRODUCTO,
        max_nota=pagos.MAX_NOTA,
        csrf=request.cookies.get("tortu_csrf", ""),
        aviso=AVISOS_SUSCRIPCION.get(request.args.get("ok", "")),
        error=error,
    ), estado


@bp.get("/suscripcion")
def suscripcion():
    """Ventana de pagos del adulto: estado del acceso, medios de pago y orden en curso."""
    resultado = _require_session()
    if not resultado:
        return redirect(url_for("cuenta.ingresar", next=url_for("cuenta.suscripcion")))
    cuentas, _, row = resultado
    return _pagina_suscripcion(cuentas, row)


def _operar_orden(operacion, aviso=None):
    """Aplica una operación del adulto sobre una orden de SU cuenta y responde según formulario o JSON."""
    sesion, rechazo = _adulto_con_csrf()
    if rechazo:
        return rechazo
    cuentas, _, row, _ = sesion
    limite = _limit_or_429(f"orden-pago:{row['account_id']}", 20, 3600)
    if limite:
        return limite
    try:
        orden = operacion(_servicio_pagos(), row["account_id"], _form_or_json_dict())
    except pagos.PagoError as exc:
        if request.form:
            return _pagina_suscripcion(cuentas, row, 400, str(exc))
        return jsonify(ok=False, mensaje=str(exc)), 400
    if request.form:
        return redirect(url_for("cuenta.suscripcion", ok=aviso) if aviso else url_for("cuenta.suscripcion"))
    publica = {k: orden[k] for k in ("id", "producto", "medio", "importe_centavos", "moneda", "dias", "referencia", "estado")}
    return jsonify(ok=True, orden=publica)


@bp.post("/suscripcion/orden")
def crear_orden_de_pago():
    """Arma la orden: el importe y la duración salen de la configuración del servidor, nunca del pedido."""
    def crear(servicio, cuenta_id, datos):
        oferta = current_app.config.get("PAGOS") or pagos.ConfiguracionPagos()
        if not oferta.habilitado:
            raise pagos.PagoError("La suscripción todavía no está disponible en esta instalación.")
        return servicio.crear_orden(cuenta_id, oferta.producto, datos.get("medio"), oferta.importe_centavos,
                                    oferta.moneda, oferta.dias)
    return _operar_orden(crear)


@bp.post("/suscripcion/orden/<orden_id>/informar")
def informar_orden_de_pago(orden_id):
    return _operar_orden(
        lambda servicio, cuenta_id, datos: servicio.informar_orden(cuenta_id, orden_id, datos.get("nota") or ""),
        "informada")


@bp.post("/suscripcion/orden/<orden_id>/cancelar")
def cancelar_orden_de_pago(orden_id):
    return _operar_orden(lambda servicio, cuenta_id, datos: servicio.cancelar_orden(cuenta_id, orden_id), "cancelada")


@bp.get("/configuracion")
def configuracion():
    resultado = _require_session()
    if not resultado:
        return redirect(url_for("cuenta.ingresar", next=url_for("cuenta.configuracion")))
    cuentas, auth, row = resultado
    return _pagina_configuracion(cuentas, auth, row)


def _adulto_con_csrf():
    """(cuentas, auth, row, raw) de una sesión válida con CSRF correcto, o la respuesta de rechazo."""
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return None, (jsonify(ok=False, mensaje="Sesión requerida."), 401)
    cuentas, auth, row = resultado
    if not _require_csrf(auth, raw):
        return None, (jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403)
    return (cuentas, auth, row, raw), None


def _gestionar_perfil(accion, aviso):
    """Aplica una operación del adulto sobre un perfil de SU cuenta y responde según formulario o JSON."""
    sesion, rechazo = _adulto_con_csrf()
    if rechazo:
        return rechazo
    cuentas, auth, row, _ = sesion
    try:
        accion(cuentas, row["account_id"])
    except CuentaError as exc:
        if request.form:
            return _pagina_configuracion(cuentas, auth, row, 400, str(exc))
        return jsonify(ok=False, mensaje=str(exc)), 400
    if request.form:
        return redirect(url_for("cuenta.configuracion", ok=aviso))
    return jsonify(ok=True)


@bp.post("/perfiles/<profile_id>/renombrar")
def renombrar_perfil(profile_id):
    nombre = _form_or_json_dict().get("nombre")
    return _gestionar_perfil(
        lambda cuentas, cuenta_id: cuentas.actualizar_nombre_child_profile(cuenta_id, profile_id, nombre), "renombrado")


@bp.post("/perfiles/<profile_id>/archivar")
def archivar_perfil(profile_id):
    return _gestionar_perfil(lambda cuentas, cuenta_id: cuentas.archivar_child_profile(cuenta_id, profile_id), "archivado")


@bp.post("/perfiles/<profile_id>/restaurar")
def restaurar_perfil(profile_id):
    return _gestionar_perfil(lambda cuentas, cuenta_id: cuentas.restaurar_child_profile(cuenta_id, profile_id), "restaurado")


@bp.post("/perfiles/<profile_id>/eliminar")
def eliminar_perfil(profile_id):
    """Supresión definitiva de un perfil archivado (ADR-046): la fila y todos sus archivos de progreso."""
    confirmacion = _form_or_json_dict().get("nombre")

    def eliminar(cuentas, cuenta_id):
        cuentas.eliminar_child_profile(cuenta_id, profile_id, confirmacion)   # rechaza un perfil ajeno o inexistente
        try:
            _educativo().progreso.eliminar(profile_id)
        except ProgresoPerfilError:
            # La fila ya no existe: el archivo quedó huérfano y lo informa el log del almacén. No se le miente al adulto.
            raise CuentaError("El perfil se eliminó, pero no pudimos borrar todos sus archivos. Avisá a quien "
                              "administra esta instalación.")
    return _gestionar_perfil(eliminar, "eliminado")


def purgar_cuentas_vencidas(ahora=None):
    """Borra de forma definitiva las cuentas cuyo plazo de gracia venció (ADR-046). Se llama al arrancar la
    aplicación y al intentar ingresar a una de ellas; necesita contexto de aplicación. Devuelve cuántas borró."""
    cuentas, _ = _repos()
    store = _educativo().progreso
    borradas = 0
    for cuenta_id in cuentas.cuentas_con_plazo_vencido(ahora):
        try:
            perfiles = cuentas.purgar_account(cuenta_id, ahora)
        except CuentaError:
            continue                                                   # otro proceso la borró o la reactivaron
        for perfil_id in perfiles:
            try:
                store.eliminar(perfil_id)
            except ProgresoPerfilError:
                logger.error("Cuenta eliminada: quedaron archivos del perfil %s sin borrar", perfil_id)
        borradas += 1
        logger.info("Cuenta eliminada de forma definitiva tras el plazo de gracia (%d perfiles)", len(perfiles))
    return borradas


@bp.post("/eliminar")
def eliminar_cuenta():
    """Pedido de eliminación de la cuenta (ADR-046): exige la contraseña, cierra las sesiones y deja la cuenta
    pendiente durante el plazo de gracia. Volver a ingresar dentro del plazo lo cancela."""
    sesion, rechazo = _adulto_con_csrf()
    if rechazo:
        return rechazo
    cuentas, auth, row, _ = sesion
    limite = _limit_or_429(f"eliminar-cuenta:{row['account_id']}", 10, 900)
    if limite:
        return limite
    datos = _form_or_json_dict()
    error = None
    if not auth.password_correcta(row["account_id"], datos.get("password")):
        error = "La contraseña no es correcta."
    elif _servicio_pagos().tiene_suscripcion_que_se_renueva(row["account_id"]):
        error = "Esta cuenta tiene una suscripción que se renueva sola. Cancelala antes de eliminar la cuenta."
    if error:
        if request.form:
            return _pagina_configuracion(cuentas, auth, row, 400, error)
        return jsonify(ok=False, mensaje=error), 400
    fecha = cuentas.solicitar_eliminacion(row["account_id"])
    if request.form:
        respuesta = make_response(render_template("cuenta/eliminacion.html", fecha=fecha.date().isoformat()))
    else:
        respuesta = make_response(jsonify(ok=True, estado="pendiente_de_eliminacion", se_elimina=fecha.isoformat()))
    respuesta.delete_cookie("tortu_session", path="/")
    respuesta.delete_cookie("tortu_csrf", path="/")
    return respuesta


@bp.post("/consentimiento")
def registrar_consentimiento():
    """El adulto acepta o revoca una finalidad opcional. Cada decisión se agrega a la bitácora."""
    sesion, rechazo = _adulto_con_csrf()
    if rechazo:
        return rechazo
    cuentas, auth, row, _ = sesion
    datos = _form_or_json_dict()
    finalidad, decision = datos.get("finalidad"), datos.get("decision")
    if finalidad not in AVISOS_DE_CONSENTIMIENTO or decision not in ("aceptar", "revocar"):
        if request.form:
            return _pagina_configuracion(cuentas, auth, row, 400, "Esa decisión no es válida.")
        return jsonify(ok=False, mensaje="Esa decisión no es válida."), 400
    cuentas.registrar_consentimiento(
        row["account_id"], finalidad, AVISOS_DE_CONSENTIMIENTO[finalidad], decision == "aceptar")
    if request.form:
        return redirect(url_for("cuenta.configuracion", ok="consentimiento"))
    return jsonify(ok=True, otorgado=decision == "aceptar")


@bp.post("/password")
def cambiar_password():
    sesion, rechazo = _adulto_con_csrf()
    if rechazo:
        return rechazo
    cuentas, auth, row, raw = sesion
    limite = _limit_or_429(f"change-password:{row['account_id']}", 10, 900)
    if limite:
        return limite
    datos = _form_or_json_dict()
    actual, nueva = datos.get("actual"), datos.get("nueva")
    try:
        if not isinstance(actual, str) or not isinstance(nueva, str):
            raise AuthError("Completá la contraseña actual y la nueva.")
        if request.form and nueva != datos.get("nueva2", nueva):
            raise AuthError("Las dos contraseñas nuevas no coinciden.")
        auth.actualizar_password(row["account_id"], actual, nueva, conservar_sesion=raw)
    except AuthError as exc:
        if request.form:
            return _pagina_configuracion(cuentas, auth, row, 400, str(exc))
        return jsonify(ok=False, mensaje=str(exc)), 400
    if request.form:
        return redirect(url_for("cuenta.configuracion", ok="password"))
    return jsonify(ok=True)


@bp.get("/ir/<producto>")
def ir_a_producto(producto):
    """Transición autenticada hacia otro producto del ecosistema (ADR-037). El acceso se decide acá, en servidor:
    el navegador solo transporta un token firmado de un solo uso que vence en un minuto."""
    destino = (current_app.config.get("FEDERACION") or {}).get(producto)
    if not destino:
        abort(404)
    raw = request.cookies.get("tortu_session")
    try:
        service = _educativo()
        contexto = service.contexto(raw)
        permitido = service.resumen_acceso(raw, [producto]).get(producto, False)
    except ContextoEducativoError:
        return redirect(url_for("cuenta.ingresar", next=url_for("cuenta.ir_a_producto", producto=producto)))
    if not permitido:
        return render_template("cuenta/sin_acceso.html", producto=producto), 403
    try:
        token = federacion.emitir_autorizacion(
            destino["clave"], destino["kid"], producto, contexto.cuenta.id, contexto.perfil.id)
    except (federacion.FederacionError, KeyError):
        logger.error("Federación mal configurada para %s", producto)
        abort(503)
    separador = "&" if "?" in destino["url"] else "?"
    respuesta = redirect(f"{destino['url']}{separador}autorizacion={token}")
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    return respuesta


@bp.get("/datos/exportar")
def exportar_datos():
    """Derecho de acceso: todo lo que TortuScript guarda de la cuenta y sus perfiles, en un archivo legible.
    No incluye secretos (hash de contraseña, tokens, identificadores de sesión)."""
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    cuentas, auth, row = resultado
    cuenta = cuentas.obtener_account(row["account_id"])
    store = _educativo().progreso
    perfiles = []
    for perfil in cuentas.listar_child_profiles(cuenta.id):
        try:
            snapshot = store.cargar(perfil.id)
            progreso = None if snapshot is None else {"actualizado": snapshot.updated_at, "datos": snapshot.data}
        except ProgresoPerfilError:
            progreso = {"error": "El archivo de progreso de este perfil está dañado."}
        perfiles.append({"id": perfil.id, "nombre": perfil.display_name, "creado": perfil.created_at,
                         "en_uso": perfil.active, "progreso": progreso})
    documento = {
        "formato": "tortuscript-datos-de-cuenta", "version": 1,
        "cuenta": {"id": cuenta.id, "correo": cuenta.email, "creada": cuenta.created_at, "rol": cuenta.role},
        "perfiles": perfiles,
        "consentimientos": [
            {"finalidad": c.finalidad, "version": c.version, "otorgado": c.otorgado, "fecha": c.created_at}
            for c in cuentas.listar_consentimientos(cuenta.id)
        ],
        "sesiones_abiertas": auth.listar_sesiones(cuenta.id),
        "suscripciones": [{k: v for k, v in sub.items() if k != "proveedor"} for sub in _suscripciones(cuenta.id)],
        "ordenes_de_pago": [
            {k: o[k] for k in ("producto", "medio", "importe_centavos", "moneda", "dias", "referencia", "estado",
                               "creada", "informada", "resuelta", "nota")}
            for o in _servicio_pagos().listar_ordenes(cuenta.id, limite=200)
        ],
        "accesos": [{"producto": p, "activo": a} for p, a in cuentas.listar_entitlements(cuenta.id)],
    }
    respuesta = jsonify(documento)
    respuesta.headers["Content-Disposition"] = 'attachment; filename="tortuscript-mis-datos.json"'
    return respuesta


@bp.get("/seleccionar-perfil")
def seleccionar_perfil_pagina():
    resultado = _require_session()
    if not resultado:
        return redirect(url_for("cuenta.ingresar"))
    cuentas, _, row = resultado
    return _pagina_perfiles(cuentas, row)


@bp.post("/registrar")
def registrar_post():
    limit = _limit_or_429(f"register:{request.remote_addr or 'unknown'}", 5, 3600)
    if limit:
        return limit
    datos = _form_or_json_dict()
    email = datos.get("email")
    password = datos.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return render_template("cuenta/registrar.html", error="Correo y contraseña son obligatorios."), 400
    if datos.get("responsable") != "si":
        return render_template(
            "cuenta/registrar.html", email=email,
            error="Para crear la cuenta tenés que confirmar que sos la persona adulta responsable.",
        ), 400
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
    cuentas.registrar_consentimiento(cuenta.id, "responsable_adulto", VERSION_AVISO_RESPONSABLE, True)
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
    datos = _json_dict()
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
    if datos.get("responsable") is True:
        cuentas.registrar_consentimiento(cuenta.id, "responsable_adulto", VERSION_AVISO_RESPONSABLE, True)
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
    datos = _form_or_json_dict()
    token = datos.get("token", "")
    try:
        if not isinstance(token, str):
            raise AuthError("El enlace no es válido.")
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
    datos = _form_or_json_dict()
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


@bp.get("/recuperar")
def recuperar():
    return render_template("cuenta/recuperar.html")


@bp.post("/recuperar")
def solicitar_recuperacion():
    # La respuesta no depende de que la cuenta exista; solo indica si el canal
    # global de correo está disponible en esta instalación.
    por_formulario = bool(request.form)
    if not _email_sender_configurado():
        mensaje = "La recuperación no está disponible porque el envío de correo no está configurado."
        if por_formulario:
            return render_template("cuenta/recuperar.html", error=mensaje), 503
        return jsonify(ok=False, codigo="envio_email_no_configurado", mensaje=mensaje), 503
    limit = _limit_or_429(f"recovery:{request.remote_addr or 'unknown'}", 5, 3600)
    if limit:
        if por_formulario:
            respuesta = make_response(render_template(
                "cuenta/recuperar.html", error="Demasiados intentos. Probá nuevamente más tarde."), 429)
            respuesta.headers["Retry-After"] = limit[0].headers["Retry-After"]
            return respuesta
        return limit
    datos = _form_or_json_dict()
    email = datos.get("email")
    if isinstance(email, str):
        cuentas, auth = _repos()
        token_info = auth.create_recovery_token(email)
        if token_info:
            token, expires = token_info
            try:
                cuenta = cuentas.obtener_account_por_email(email)
            except CuentaError:
                cuenta = None
            if cuenta:
                _intentar_emitir_email("recovery", cuenta.email, token, expires)
    if por_formulario:
        # Misma página para cuenta existente, inexistente o proveedor fallido.
        return render_template("cuenta/recuperar.html", enviado=True), 202
    return jsonify(ok=True, estado="solicitud_recibida"), 202


@bp.get("/restablecer-password")
def restablecer_password_pagina():
    # GET no consume el token: solo muestra el formulario para elegir la clave nueva.
    token = request.args.get("token", "")
    if not token:
        return render_template("cuenta/restablecer.html", invalido=True), 400
    return render_template("cuenta/restablecer.html", token=token)


@bp.post("/restablecer-password")
def restablecer_password():
    por_formulario = bool(request.form)
    datos = _form_or_json_dict()
    token = datos.get("token")
    password = datos.get("password")
    if not isinstance(token, str) or not isinstance(password, str):
        if por_formulario:
            return render_template("cuenta/restablecer.html", invalido=True), 400
        return jsonify(ok=False, mensaje="Token y contraseña son obligatorios."), 400
    limit = _limit_or_429(f"reset-password:{request.remote_addr or 'unknown'}", 10, 900)
    if limit:
        if por_formulario:
            respuesta = make_response(render_template(
                "cuenta/restablecer.html", token=token,
                error="Demasiados intentos. Probá nuevamente más tarde."), 429)
            respuesta.headers["Retry-After"] = limit[0].headers["Retry-After"]
            return respuesta
        return limit
    if por_formulario and password != datos.get("password2", password):
        return render_template("cuenta/restablecer.html", token=token,
                               error="Las dos contraseñas no coinciden."), 400
    try:
        AuthRepository.validar_password(password)
    except AuthError as exc:
        # La política se comprueba antes de tocar el token: el enlace sigue sirviendo.
        if por_formulario:
            return render_template("cuenta/restablecer.html", token=token, error=str(exc)), 400
        return jsonify(ok=False, mensaje=str(exc)), 400
    try:
        _, auth = _repos()
        auth.reset_password(token, password)
    except AuthError as exc:
        if por_formulario:
            return render_template("cuenta/restablecer.html", invalido=True), 400
        return jsonify(ok=False, mensaje=str(exc)), 400
    if por_formulario:
        return render_template("cuenta/restablecer.html", listo=True)
    return jsonify(ok=True, estado="password_restablecida")


@bp.post("/login")
def login():
    datos = _form_or_json_dict()
    email = datos.get("email")
    password = datos.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        if request.form:
            return render_template(
                "cuenta/ingresar.html", error="Correo y contraseña son obligatorios.", next_url=_next_pedido()
            ), 401
        return jsonify(ok=False, mensaje="Correo o contraseña incorrectos."), 401
    email_normalizado = email.strip().lower()
    ip = request.remote_addr or "unknown"
    limite = _limit_or_429(f"login-ip:{ip}", 30, 900) or \
        _limit_or_429(f"login-account:{ip}:{email_normalizado}", 10, 900)
    if limite:
        if request.form:
            # El adulto que usa el formulario necesita una página, no un JSON crudo.
            respuesta = make_response(render_template(
                "cuenta/ingresar.html", next_url=_next_pedido(),
                error="Demasiados intentos. Esperá unos minutos y probá de nuevo.",
            ), 429)
            respuesta.headers["Retry-After"] = limite[0].headers["Retry-After"]
            return respuesta
        return limite
    cuentas, auth = _repos()
    reactivada = False
    try:
        cuenta = auth.verify_password(email, password)
        se_elimina = cuentas.eliminacion_pendiente(cuenta["id"])
        if se_elimina is not None:
            if se_elimina <= datetime.now(timezone.utc):
                # El plazo venció: la cuenta ya no existe para nadie, aunque la purga del arranque no haya corrido.
                purgar_cuentas_vencidas()
                raise AuthError("La cuenta fue eliminada.")
            cuentas.cancelar_eliminacion(cuenta["id"])                # ingresar dentro del plazo la reactiva
            reactivada = True
        raw_session, csrf, expires = auth.create_session(cuenta["id"])
    except AuthError:
        # No distinguir cuenta inexistente, contraseña incorrecta o correo pendiente.
        mensaje = "Correo o contraseña incorrectos, o cuenta sin verificar."
        if request.form:
            return render_template("cuenta/ingresar.html", error=mensaje, next_url=_next_pedido()), 401
        return jsonify(ok=False, mensaje=mensaje), 401
    if request.form:
        destino = url_for("cuenta.configuracion", ok="reactivada") if reactivada \
            else url_for("cuenta.seleccionar_perfil_pagina", next=_next_pedido())
        respuesta = make_response(redirect(destino))
    else:
        respuesta = make_response(jsonify(ok=True, cuenta={"id": cuenta["id"], "email": cuenta["email"], "role": cuenta["role"]},
                                          csrf=csrf, expira=expires.isoformat(), reactivada=reactivada))
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
    perfiles = cuentas.listar_child_profiles(row["account_id"], solo_activos=True)
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
    nombre = _form_or_json_dict().get("nombre")
    try:
        perfil = cuentas.crear_child_profile(row["account_id"], nombre)
    except CuentaError as exc:
        if request.form:
            return _pagina_perfiles(cuentas, row, 400, str(exc))
        return jsonify(ok=False, mensaje=str(exc)), 400
    if request.form:
        # La acción del formulario promete crear y entrar al perfil; no dejar al
        # usuario en el selector como si la creación no hubiese terminado.
        try:
            auth.select_profile(raw, perfil.id)
        except AuthError:
            return _pagina_perfiles(cuentas, row, 403, "No se pudo entrar al perfil nuevo. Elegilo de la lista.")
        return redirect(_next_pedido(url_for("inicio")))
    return jsonify(ok=True, perfil={"id": perfil.id, "nombre": perfil.display_name}), 201


@bp.post("/perfil")
def seleccionar_perfil():
    raw = request.cookies.get("tortu_session")
    resultado = _require_session()
    if not resultado:
        return jsonify(ok=False, mensaje="Sesión requerida."), 401
    cuentas, auth, row = resultado
    if not _require_csrf(auth, raw):
        return jsonify(ok=False, mensaje="Falta una protección CSRF válida."), 403
    datos = _form_or_json_dict()
    profile_id = datos.get("perfil_id")
    if not isinstance(profile_id, str) or not profile_id:
        if request.form:
            return _pagina_perfiles(cuentas, row, 400, "Elegí un perfil de la lista.")
        return jsonify(ok=False, mensaje="Falta perfil_id."), 400
    try:
        auth.select_profile(raw, profile_id)
    except AuthError as exc:
        if request.form:
            # Un 403 con cabecera Location no se sigue: el adulto veía una página en blanco.
            return _pagina_perfiles(cuentas, row, 403, "Ese perfil no está disponible en esta cuenta.")
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
    datos = _json_dict()
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
    datos = _json_dict()
    try:
        proyecto_id = RuntimeEducativo(_educativo()).guardar_proyecto(
            raw, datos.get("nombre"), datos.get("tipo"), datos.get("codigo"), datos.get("proyecto_id"))
    except (ContextoEducativoError, ValueError, KeyError) as exc:
        return jsonify(ok=False, mensaje=str(exc)), 400
    return jsonify(ok=True, proyecto_id=proyecto_id)
