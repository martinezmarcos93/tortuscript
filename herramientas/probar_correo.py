"""Comprueba la entrega real de correo con la configuración de esta instalación (barrido 6).

Uso:
    python herramientas/probar_correo.py destinatario@ejemplo.com
    python herramientas/probar_correo.py destinatario@ejemplo.com --tipo recovery

Lee `TORTU_EMAIL_MODO`, `TORTU_SMTP_*`, `TORTU_EMAIL_REMITENTE` y `TORTU_URL_BASE` del entorno o del `.env`
(el de la carpeta de datos y el que está junto a `iniciar_web.py`) y manda UN correo de prueba, igual al que
recibe una familia, con un enlace que no sirve (el token es inventado y no existe en ninguna base).

Sale con 0 si el servidor SMTP aceptó el mensaje. Que lo acepte no prueba que llegue a la bandeja de
entrada: hay que mirarla (y la carpeta de correo no deseado), y revisar SPF/DKIM del dominio remitente.
"""
from __future__ import annotations

import argparse
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from iniciar_web import cargar_env  # noqa: E402
from tortuscript import correo, rutas  # noqa: E402


def main(argv=None, entorno=None):
    ap = argparse.ArgumentParser(description="Manda un correo de prueba con la configuración de la instalación.")
    ap.add_argument("destinatario")
    ap.add_argument("--tipo", choices=("verification", "recovery"), default="verification")
    ap.add_argument("--url-base", default=None, help="si TORTU_URL_BASE no está definida (uso local)")
    args = ap.parse_args(argv)
    if entorno is None:
        for archivo in (rutas.carpeta_de_datos() / ".env", RAIZ / ".env"):
            cargar_env(archivo)
    if "@" not in args.destinatario:
        print("❌ El destinatario no parece una dirección de correo.", file=sys.stderr)
        return 2
    try:
        enviador = correo.desde_entorno(entorno, url_base=args.url_base)
    except correo.CorreoError as e:
        print(f"❌ Configuración de correo inválida: {e}", file=sys.stderr)
        return 2
    if enviador is None:
        print("❌ TORTU_EMAIL_MODO está vacío: el correo está deshabilitado en esta instalación.", file=sys.stderr)
        return 2
    try:
        enviador(tipo=args.tipo, email=args.destinatario, token="token-de-prueba-sin-validez",
                 expires=datetime.now(timezone.utc) + timedelta(hours=1))
    except (smtplib.SMTPException, OSError) as e:
        # El mensaje del servidor puede traer la dirección; se muestra a quien corre la prueba, no se registra.
        print(f"❌ El servidor de correo rechazó el envío: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if isinstance(enviador, correo.EnviadorSMTP):
        print(f"✅ El servidor SMTP aceptó el mensaje para {args.destinatario}. Revisá la bandeja de entrada y el correo no deseado.")
    else:
        print("ℹ️  Modo consola: el enlace se mostró arriba; no se envió ningún correo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
