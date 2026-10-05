"""Configuración para atender a terceros (modo servidor), separada del uso local en la compu de una familia.

`iniciar_web.py` es el modo local: 127.0.0.1, un proceso, sin HTTPS. Este módulo arma la misma aplicación
para ponerla detrás de un proxy con HTTPS. Falla al arrancar, con un mensaje claro, si falta algo que en
un servidor público no puede faltar: es preferible no levantar a levantar inseguro.

Variables (ver `.env.example`):
- TORTU_HOSTS            nombres de host que atiende, separados por comas (obligatorio)
- TORTU_URL_BASE         URL pública https:// para los enlaces de los correos (obligatorio)
- TORTUSCRIPT_DATOS      carpeta de datos fuera del código (obligatorio)
- TORTU_SANDBOX=docker   el código de los chicos solo corre aislado (obligatorio, ADR-014 y ADR-033)
- TORTU_EMAIL_MODO=smtp  correo real (obligatorio: sin correo nadie puede registrarse)
- TORTU_PROXIES          cuántos proxies propios hay delante (por defecto 1)
- TORTU_TOKEN            token de la API compartido entre reinicios (opcional; si no, uno nuevo por arranque)
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from werkzeug.middleware.proxy_fix import ProxyFix

HSTS = "max-age=31536000; includeSubDomains"


class ConfiguracionInvalida(RuntimeError):
    """Falta o es insegura una configuración obligatoria del modo servidor."""


def _hosts(valor):
    hosts = {h.strip().lower() for h in (valor or "").split(",") if h.strip()}
    if not hosts:
        raise ConfiguracionInvalida("TORTU_HOSTS es obligatorio: los nombres de host que atiende el servidor.")
    for host in hosts:
        if "/" in host or ":" in host or " " in host or host == "*":
            raise ConfiguracionInvalida(f"TORTU_HOSTS tiene un nombre de host inválido: {host!r} (sin esquema, puerto ni comodines).")
    return hosts


def crear_aplicacion_servidor(entorno=None):
    """La aplicación lista para un servidor WSGI. Lanza ConfiguracionInvalida si algo obligatorio falta."""
    from tortuscript import correo, federacion, pagos, rutas, sandbox_docker, tutor
    from web.app import create_app

    entorno = os.environ if entorno is None else entorno
    hosts = _hosts(entorno.get("TORTU_HOSTS"))
    url_base = (entorno.get("TORTU_URL_BASE") or "").strip()
    partes = urlsplit(url_base)
    if partes.scheme != "https" or (partes.hostname or "").lower() not in hosts:
        raise ConfiguracionInvalida("TORTU_URL_BASE debe ser https:// y su host debe estar en TORTU_HOSTS.")
    if not entorno.get("TORTUSCRIPT_DATOS"):
        raise ConfiguracionInvalida("TORTUSCRIPT_DATOS es obligatorio: los datos no pueden vivir junto al código.")
    if not sandbox_docker.activo(entorno):
        raise ConfiguracionInvalida(
            "TORTU_SANDBOX=docker es obligatorio: un servidor público no ejecuta código de los chicos sin aislamiento.")
    try:
        enviador = correo.desde_entorno(entorno, url_base=url_base)
    except correo.CorreoError as e:
        raise ConfiguracionInvalida(f"Correo mal configurado: {e}") from e
    if not isinstance(enviador, correo.EnviadorSMTP):
        raise ConfiguracionInvalida("TORTU_EMAIL_MODO=smtp es obligatorio (el modo consola es solo para uso local).")
    try:
        oferta = pagos.configuracion_desde_entorno(entorno)
    except pagos.PagoError as e:
        raise ConfiguracionInvalida(f"Pagos mal configurados: {e}") from e
    try:
        puente = federacion.configuracion_desde_entorno(entorno)
    except federacion.FederacionError as e:
        raise ConfiguracionInvalida(f"Conexión con Croco-Script mal configurada: {e}") from e
    if any(not destino["url"].startswith("https://") for destino in puente.values()):
        raise ConfiguracionInvalida("En modo servidor TORTU_CROCO_URL debe ser https://.")
    token = entorno.get("TORTU_TOKEN") or None
    if token is not None and len(token) < 32:
        raise ConfiguracionInvalida("TORTU_TOKEN debe tener al menos 32 caracteres.")
    try:
        proxies = int(entorno.get("TORTU_PROXIES") or 1)
    except ValueError as e:
        raise ConfiguracionInvalida("TORTU_PROXIES debe ser un número.") from e
    if not 0 <= proxies <= 5:
        raise ConfiguracionInvalida("TORTU_PROXIES debe estar entre 0 y 5.")

    datos = Path(entorno["TORTUSCRIPT_DATOS"])
    cuentas = rutas.carpeta_de_cuentas(datos)
    cuentas.mkdir(parents=True, exist_ok=True)
    app = create_app(token=token)
    app.config.update(
        HOSTS_PERMITIDOS=hosts,
        ACCOUNT_DB=cuentas / "cuentas.sqlite3",
        PROGRESS_DIR=cuentas / "progreso_perfiles",
        # El límite de intentos se comparte entre los hilos y procesos de esta máquina.
        ACCOUNT_RATE_LIMIT_DB=cuentas / "limites.sqlite3",
        ACCOUNT_COOKIE_SECURE=True,
        ACCOUNT_COOKIE_SAMESITE="Lax",
        ACCOUNT_EMAIL_SENDER=enviador,
        TUTOR_PROVEEDOR=tutor.proveedor_desde_entorno(entorno),
        PAGOS=oferta,
        FEDERACION=puente,
        HSTS=HSTS,
        PREFERRED_URL_SCHEME="https",
    )
    from iniciar_web import purgar_cuentas_vencidas
    purgar_cuentas_vencidas(app)                                   # ADR-046: plazo de eliminación vencido
    if proxies:
        # Detrás del proxy, la IP del cliente (límites de intentos), el esquema y el host vienen en X-Forwarded-*.
        # Solo se confía en la cantidad de proxies propios declarada: más sería dejar que el cliente mienta su IP.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)
    return app
