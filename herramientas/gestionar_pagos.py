"""Órdenes de pago por transferencia (ADR-047): ver las que esperan y confirmar o rechazar cada una.

Uso:
    python herramientas/gestionar_pagos.py                       # órdenes abiertas (primero las ya informadas)
    python herramientas/gestionar_pagos.py confirmar TS-ABC234   # el dinero llegó: activa o extiende el acceso
    python herramientas/gestionar_pagos.py rechazar TS-ABC234 --nota "no encontramos la transferencia"

La orden se nombra por su referencia (la que la familia pone en el concepto de la transferencia) o por su
identificador. Confirmar es la única forma de que una transferencia dé acceso: hacelo recién cuando veas
el dinero acreditado en tu cuenta. Confirmar dos veces la misma orden no suma días.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tortuscript import rutas  # noqa: E402
from tortuscript.cuentas import CuentaRepository  # noqa: E402
from tortuscript.pagos import PagoError, ServicioPagos, importe_legible  # noqa: E402


def _linea(orden, correo):
    aviso = f"avisó el {orden['informada'][:10]}" if orden["informada"] else "todavía no avisó"
    nota = f" · «{orden['nota']}»" if orden["nota"] else ""
    return (f"  {orden['referencia']}  {orden['estado']:<10} {importe_legible(orden['importe_centavos'])} {orden['moneda']}"
            f"  {orden['dias']} días  {orden['producto']}  {correo}  creada {orden['creada'][:10]}, {aviso}{nota}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Órdenes de pago por transferencia.")
    ap.add_argument("--db", type=Path, default=rutas.carpeta_de_cuentas() / "cuentas.sqlite3")
    sub = ap.add_subparsers(dest="accion")
    for accion in ("confirmar", "rechazar"):
        p = sub.add_parser(accion)
        p.add_argument("orden", help="referencia (TS-…) o identificador de la orden")
        if accion == "rechazar":
            p.add_argument("--nota", default="", help="motivo que verá la familia")
    args = ap.parse_args(argv)
    if not args.db.is_file():
        print(f"❌ No existe la base de cuentas: {args.db}", file=sys.stderr)
        return 1
    cuentas = CuentaRepository(args.db)
    cuentas.ensure_schema()
    servicio = ServicioPagos(args.db)
    servicio.ensure_schema()

    def correo(orden):
        cuenta = cuentas.obtener_account(orden["cuenta"])
        return cuenta.email if cuenta else "(cuenta eliminada)"

    if args.accion is None:
        abiertas = servicio.listar_ordenes_abiertas()
        print(f"Órdenes abiertas: {len(abiertas)}")
        for orden in abiertas:
            print(_linea(orden, correo(orden)))
        # Distinto de cero si hay algo que la familia ya pagó y espera: sirve para una alerta programada.
        return 2 if any(o["estado"] == "informada" for o in abiertas) else 0

    orden = servicio.buscar_orden(args.orden)
    if orden is None:
        print(f"❌ No hay ninguna orden con esa referencia: {args.orden}", file=sys.stderr)
        return 1
    try:
        if args.accion == "confirmar":
            orden = servicio.confirmar_orden(orden["id"])
            periodo = next((s["periodo_hasta"] for s in servicio.listar_suscripciones(orden["cuenta"])
                            if s["producto"] == orden["producto"] and s["proveedor"] == "transferencia"), None)
            print(f"✅ Orden {orden['referencia']} confirmada: {correo(orden)} tiene {orden['producto']} "
                  f"hasta el {(periodo or '')[:10]}.")
        else:
            orden = servicio.rechazar_orden(orden["id"], args.nota)
            print(f"Orden {orden['referencia']} rechazada. La familia puede armar otra.")
    except PagoError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
