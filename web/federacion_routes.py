"""Lo que TortuScript responde a otros productos del ecosistema (ADR-037), de servidor a servidor.

- `GET /federacion/v1/acceso?cuenta=…&producto=croco-script`  → Entitlement.v1 (¿la cuenta conserva el acceso?)
- `GET /federacion/v1/progreso?perfil=…&producto=croco-script` → Progress.v1 del perfil (ProgressQuery.v1)

No son páginas para un navegador: no usan cookies ni sesión. Las autentica una firma HMAC con el secreto de federación
(`Authorization: Croco-HMAC kid=…, ts=…, firma=…`) y vencen en 60 segundos. Ante cualquier fallo de autenticación se
responde lo mismo (401, sin detalles): el motivo va al log, sin identificadores.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from tortuscript import catalogo_producto, federacion
from tortuscript.acceso import AccesoProducto
from tortuscript.progreso_childprofile import ProgresoPerfilError
from web.cuenta_routes import _educativo, _repos

logger = logging.getLogger(__name__)
bp = Blueprint("federacion", __name__, url_prefix="/federacion/v1")

_ID = re.compile(r"[A-Za-z0-9_\-]{1,80}")


def _responder(cuerpo, estado=200):
    respuesta = jsonify(cuerpo)
    respuesta.status_code = estado
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def _no_autorizado():
    return _responder({"error": "autorizacion_invalida"}, 401)


def _autenticar(producto, identificador):
    """El destino configurado para `producto` y None si la firma es válida; si no, la respuesta de error."""
    destino = (current_app.config.get("FEDERACION") or {}).get(producto)
    if not destino:
        return None, _responder({"error": "no_disponible"}, 404)
    if not identificador or not _ID.fullmatch(identificador):
        return None, _no_autorizado()
    try:
        federacion.validar_consulta(request.headers.get("Authorization"), {destino["kid"]: destino["clave"]},
                                    producto, identificador)
    except federacion.FederacionError as exc:
        logger.warning("Consulta de federación rechazada (%s)", exc)
        return None, _no_autorizado()
    return destino, None


@bp.get("/acceso")
def acceso():
    """Entitlement.v1: ¿la cuenta conserva el acceso al producto? Una cuenta desconocida o borrada responde `false`."""
    producto, cuenta_id = request.args.get("producto", ""), request.args.get("cuenta", "")
    destino, error = _autenticar(producto, cuenta_id)
    if error is not None:
        return error
    cuentas, _ = _repos()
    activo = cuentas.obtener_account(cuenta_id) is not None and (
        cuentas.es_admin(cuenta_id) or cuentas.tiene_entitlement(cuenta_id, producto))
    return _responder(federacion.acceso_v1(producto, activo, datetime.now(timezone.utc).isoformat(timespec="seconds")))


@bp.get("/progreso")
def progreso():
    """ProgressQuery.v1: el Progress.v1 de un perfil. Solo se responde por un perfil activo cuya cuenta tiene acceso
    al producto que pregunta: a un perfil sin acceso se le contesta como a uno inexistente."""
    producto, perfil_id = request.args.get("producto", ""), request.args.get("perfil", "")
    destino, error = _autenticar(producto, perfil_id)
    if error is not None:
        return error
    cuentas, _ = _repos()
    if not AccesoProducto(cuentas).puede_acceder(perfil_id, producto):
        return _responder({"error": "perfil_inexistente"}, 404)
    try:
        instantanea = _educativo().progreso.cargar_o_recuperar(perfil_id)
    except ProgresoPerfilError:
        logger.error("Progress.v1: el progreso de un perfil no se pudo leer", exc_info=True)
        return _responder({"error": "no_disponible"}, 503)
    datos = instantanea.data if instantanea else {}
    actualizado = instantanea.updated_at if instantanea else datetime.now(timezone.utc).isoformat(timespec="seconds")
    return _responder(catalogo_producto.progreso_publicable(perfil_id, datos, actualizado))
