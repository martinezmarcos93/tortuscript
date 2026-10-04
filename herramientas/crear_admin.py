"""Crea o actualiza una cuenta administrativa local sin guardar su contraseña en Git.

Uso:
    python herramientas/crear_admin.py
    python herramientas/crear_admin.py --email admin@tortuscript.local

La contraseña se solicita con getpass, por lo que no aparece en pantalla ni en la
línea de comandos. Se almacena únicamente como hash scrypt dentro de SQLite.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaError, CuentaRepository
from tortuscript import rutas


EMAIL_PREDETERMINADO = "admin@tortuscript.local"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Configura el acceso administrativo local de TortuScript.")
    parser.add_argument("--email", default=EMAIL_PREDETERMINADO)
    parser.add_argument(
        "--db",
        type=Path,
        default=rutas.carpeta_de_cuentas() / "cuentas.sqlite3",
        help="SQLite de cuentas (por defecto, la misma que usa iniciar_web.py).",
    )
    args = parser.parse_args(argv)

    password = getpass.getpass("Contraseña del Admin: ")
    confirmacion = getpass.getpass("Repetir contraseña: ")
    if password != confirmacion:
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 2

    cuentas = CuentaRepository(args.db)
    cuentas.ensure_schema()
    auth = AuthRepository(args.db)
    auth.ensure_schema()

    email = args.email.strip().lower()
    cuenta = cuentas.obtener_account_por_email(email)

    if cuenta is None:
        try:
            cuenta = cuentas.crear_account(email)
        except CuentaError as exc:
            print(f"No se pudo crear la cuenta: {exc}", file=sys.stderr)
            return 1

    cuentas.establecer_role(cuenta.id, "admin")
    auth.set_password(cuenta.id, password)
    auth.marcar_verificada(cuenta.id)

    perfiles = cuentas.listar_child_profiles(cuenta.id)
    if not perfiles:
        cuentas.crear_child_profile(cuenta.id, "Admin")

    print(f"Admin configurado: {cuenta.email}")
    print(f"Base de datos: {args.db}")
    print("El rol admin omite los entitlements comerciales para las pruebas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
