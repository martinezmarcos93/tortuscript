"""Envío de los correos transaccionales de cuenta (verificación y recuperación).

Las rutas de cuenta solo conocen un invocable `sender(tipo=, email=, token=, expires=)`
en `ACCOUNT_EMAIL_SENDER`. Este módulo ofrece dos implementaciones, ambas con la
biblioteca estándar, y las arma desde variables de entorno:

- `smtp`: entrega real por un servidor SMTP (el del proveedor que se contrate).
- `consola`: escribe el enlace en la terminal del servidor. Solo para una instalación
  local de una sola máquina, donde quien registra la cuenta es quien ve la terminal.

Sin configuración no se devuelve ningún enviador y las rutas fallan cerradas (503):
nunca se crean cuentas que no puedan verificarse.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib.parse import quote, urlsplit

logger = logging.getLogger(__name__)

MODOS = ("smtp", "consola")
SEGURIDADES = ("starttls", "ssl", "ninguna")
RUTAS = {
    "verification": "/cuenta/verificar-email",
    "recovery": "/cuenta/restablecer-password",
}
TEXTOS = {
    "verification": (
        "Confirmá tu correo en TortuScript",
        "Alguien creó una cuenta adulta de TortuScript con este correo.\n"
        "Para confirmarla, abrí este enlace y apretá «Confirmar correo»:",
        "Si no fuiste vos, no hagas nada: sin confirmación la cuenta no se puede usar.",
    ),
    "recovery": (
        "Elegí una contraseña nueva para TortuScript",
        "Pidieron cambiar la contraseña de la cuenta adulta de TortuScript de este correo.\n"
        "Para elegir una nueva, abrí este enlace:",
        "Si no fuiste vos, no hagas nada: la contraseña actual sigue funcionando.",
    ),
}


class CorreoError(ValueError):
    """La configuración de correo no es válida o el tipo de mensaje no existe."""


def _base_valida(url_base):
    partes = urlsplit(url_base or "")
    if partes.scheme not in ("http", "https") or not partes.netloc:
        raise CorreoError("TORTU_URL_BASE debe ser una URL http(s) completa, por ejemplo https://tortuscript.example")
    return url_base.rstrip("/")


def enlace(tipo, token, url_base):
    """El enlace que abre la persona. El token va en la consulta; abrirlo no lo consume."""
    if tipo not in RUTAS:
        raise CorreoError(f"Tipo de correo desconocido: {tipo!r}")
    return f"{_base_valida(url_base)}{RUTAS[tipo]}?token={quote(token, safe='')}"


def construir_mensaje(tipo, email, token, expires, url_base, remitente):
    asunto, entrada, salida = TEXTOS.get(tipo) or (None, None, None)
    if asunto is None:
        raise CorreoError(f"Tipo de correo desconocido: {tipo!r}")
    vence = expires.strftime("%d/%m/%Y a las %H:%M UTC") if hasattr(expires, "strftime") else str(expires)
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = email
    mensaje["Date"] = formatdate(localtime=False)
    mensaje["Message-ID"] = make_msgid(domain=(remitente.rsplit("@", 1)[-1].strip("> ") or None))
    # Correo transaccional: que los servidores no respondan con avisos automáticos.
    mensaje["Auto-Submitted"] = "auto-generated"
    mensaje.set_content(
        f"Hola,\n\n{entrada}\n\n{enlace(tipo, token, url_base)}\n\n"
        f"El enlace vence el {vence} y sirve una sola vez.\n\n{salida}\n\n— TortuScript\n"
    )
    return mensaje


class EnviadorSMTP:
    """Entrega por SMTP. Lanza la excepción del servidor: la ruta la convierte en «no pudimos confirmar el envío»."""

    def __init__(self, host, puerto, remitente, url_base, usuario=None, clave=None, seguridad="starttls", espera=15):
        if seguridad not in SEGURIDADES:
            raise CorreoError(f"TORTU_SMTP_SEGURIDAD debe ser una de: {', '.join(SEGURIDADES)}")
        if not host or not remitente:
            raise CorreoError("Faltan TORTU_SMTP_HOST o TORTU_EMAIL_REMITENTE.")
        if seguridad == "ninguna" and usuario:
            # Nunca mandar credenciales en claro por la red.
            raise CorreoError("No se permite autenticación SMTP sin cifrado (TORTU_SMTP_SEGURIDAD=ninguna).")
        self.host, self.puerto, self.remitente = host, int(puerto), remitente
        self.url_base = _base_valida(url_base)
        self.usuario, self.clave, self.seguridad, self.espera = usuario, clave, seguridad, espera

    def __call__(self, tipo, email, token, expires):
        mensaje = construir_mensaje(tipo, email, token, expires, self.url_base, self.remitente)
        contexto = ssl.create_default_context()
        if self.seguridad == "ssl":
            servidor = smtplib.SMTP_SSL(self.host, self.puerto, timeout=self.espera, context=contexto)
        else:
            servidor = smtplib.SMTP(self.host, self.puerto, timeout=self.espera)
        with servidor:
            if self.seguridad == "starttls":
                servidor.starttls(context=contexto)
            if self.usuario:
                servidor.login(self.usuario, self.clave or "")
            servidor.send_message(mensaje)
        # Nunca registrar el token ni la dirección: solo que hubo un envío.
        logger.info("Correo transaccional enviado (tipo=%s)", tipo)


class EnviadorConsola:
    """Muestra el enlace en la terminal del servidor en vez de mandarlo. Solo para uso local."""

    def __init__(self, url_base, salida=print):
        self.url_base = _base_valida(url_base)
        self.salida = salida

    def __call__(self, tipo, email, token, expires):
        titulo = TEXTOS[tipo][0] if tipo in TEXTOS else tipo
        self.salida(f"\n✉️  {titulo} ({email})\n    {enlace(tipo, token, self.url_base)}\n")


def desde_entorno(entorno=None, url_base=None):
    """El enviador que describe el entorno, o None si el correo no está configurado.

    Una configuración a medias es un error explícito: es preferible no arrancar a
    aceptar registros cuyos correos nunca van a salir.
    """
    entorno = os.environ if entorno is None else entorno
    modo = (entorno.get("TORTU_EMAIL_MODO") or "").strip().lower()
    if not modo:
        return None
    if modo not in MODOS:
        raise CorreoError(f"TORTU_EMAIL_MODO debe ser una de: {', '.join(MODOS)}")
    url_base = (entorno.get("TORTU_URL_BASE") or url_base or "").strip()
    if modo == "consola":
        return EnviadorConsola(url_base)
    try:
        puerto = int(entorno.get("TORTU_SMTP_PUERTO") or 587)
    except ValueError as exc:
        raise CorreoError("TORTU_SMTP_PUERTO debe ser un número.") from exc
    return EnviadorSMTP(
        host=(entorno.get("TORTU_SMTP_HOST") or "").strip(),
        puerto=puerto,
        remitente=(entorno.get("TORTU_EMAIL_REMITENTE") or "").strip(),
        url_base=url_base,
        usuario=(entorno.get("TORTU_SMTP_USUARIO") or "").strip() or None,
        clave=entorno.get("TORTU_SMTP_CLAVE") or None,
        seguridad=(entorno.get("TORTU_SMTP_SEGURIDAD") or "starttls").strip().lower(),
    )
