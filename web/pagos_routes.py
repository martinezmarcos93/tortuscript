"""Entrada de los eventos del proveedor de pagos (ADR-032).

El webhook no usa sesión ni CSRF: se autentica con la firma HMAC del cuerpo original.
Sin un secreto configurado para el proveedor, la ruta no existe (404): por defecto no
se aceptan eventos de nadie.
"""
import logging
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request

from tortuscript import pagos

logger = logging.getLogger(__name__)

bp = Blueprint("pagos", __name__, url_prefix="/pagos")


def servicio_de_pagos():
    servicio = pagos.ServicioPagos(Path(current_app.config["ACCOUNT_DB"]))
    listos = current_app.extensions.setdefault("tortu_pagos_listos", set())
    if str(servicio.path) not in listos or not servicio.path.exists():
        from web.cuenta_routes import _repos
        _repos()                                                   # el esquema de cuentas va primero
        servicio.ensure_schema()
        listos.add(str(servicio.path))
    return servicio


@bp.post("/webhook/<proveedor>")
def webhook(proveedor):
    secreto = (current_app.config.get("PAYMENT_WEBHOOK_SECRETS") or {}).get(proveedor)
    adaptador = pagos.ADAPTADORES.get(proveedor)
    if not secreto or adaptador is None:
        abort(404)
    if (request.content_length or 0) > pagos.MAX_CUERPO_WEBHOOK:
        abort(413)
    cuerpo = request.get_data(cache=False)
    if len(cuerpo) > pagos.MAX_CUERPO_WEBHOOK:
        abort(413)
    try:
        # La firma se verifica sobre los bytes recibidos, antes de interpretar nada.
        pagos.verificar_firma(secreto, cuerpo, request.headers.get("X-Tortu-Firma"))
        evento = adaptador(cuerpo)
    except pagos.PagoError as exc:
        logger.warning("Webhook de pagos rechazado (proveedor=%s): %s", proveedor, exc)
        return jsonify(ok=False), 400
    resultado = servicio_de_pagos().aplicar(evento)
    if resultado.estado == pagos.REVISION:
        # Sin datos personales: identificadores opacos y la razón.
        logger.error("Evento de pago en revisión (proveedor=%s evento=%s): %s", proveedor, evento.id, resultado.detalle)
    # 200 también para duplicados, obsoletos y en revisión: reintentar no los arreglaría.
    return jsonify(ok=True, estado=resultado.estado)
