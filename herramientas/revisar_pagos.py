"""Reconciliación manual de pagos (ADR-032): eventos que quedaron «en revisión» y estado de las suscripciones.

Uso:
    python herramientas/revisar_pagos.py                 # eventos en revisión
    python herramientas/revisar_pagos.py --suscripciones # además, todas las suscripciones y su acceso

Solo lee. Un evento en revisión nunca concedió acceso: hay que mirar por qué no coincidía (cuenta inexistente,
producto desconocido, suscripción de otra cuenta, pago sin período) y resolverlo con el proveedor.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tortuscript import rutas  # noqa: E402
from tortuscript.pagos import ServicioPagos  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eventos de pago en revisión y estado de suscripciones.")
    ap.add_argument("--db", type=Path, default=rutas.carpeta_de_cuentas() / "cuentas.sqlite3")
    ap.add_argument("--suscripciones", action="store_true")
    args = ap.parse_args(argv)
    if not args.db.is_file():
        print(f"❌ No existe la base de cuentas: {args.db}", file=sys.stderr)
        return 1
    uri = args.db.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        con.row_factory = sqlite3.Row
        tablas = {f["name"] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "payment_events" not in tablas:
            print("Esta instalación todavía no recibió ningún evento de pago.")
            return 0
        revision = con.execute(
            "SELECT provider,event_id,type,account_id,received_at,detail FROM payment_events "
            "WHERE status='revision' ORDER BY received_at").fetchall()
        print(f"Eventos en revisión: {len(revision)}")
        for e in revision:
            print(f"  {e['received_at']}  {e['provider']}/{e['event_id']}  {e['type']}  cuenta={e['account_id']}  → {e['detail']}")
        if args.suscripciones:
            filas = con.execute(
                """SELECT s.account_id, s.product, s.status, s.period_end, e.active, e.expires_at
                   FROM subscriptions s LEFT JOIN entitlements e
                     ON e.account_id = s.account_id AND e.product = s.product
                   ORDER BY s.updated_at""").fetchall()
            print(f"Suscripciones: {len(filas)}")
            for f in filas:
                acceso = "sin acceso" if not f["active"] else f"acceso hasta {f['expires_at'] or 'sin vencimiento'}"
                print(f"  {f['account_id']}  {f['product']}  {f['status']}  período hasta {f['period_end'] or '—'}  ({acceso})")
    # Código de salida distinto de cero si hay algo para mirar: sirve para una alerta programada.
    return 2 if revision else 0


if __name__ == "__main__":
    raise SystemExit(main())
