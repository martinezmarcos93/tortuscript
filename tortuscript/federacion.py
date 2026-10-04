"""Contratos entre TortuScript y Croco-Script (ADR-037): identidad, acceso y transición autenticada.

Croco-Script es otra aplicación y otro repositorio: no importa este módulo. Lo que comparten es el
CONTRATO, descrito en `docs/contratos/` con vectores de prueba que ambas partes deben pasar.

`Authorization.v1` es un token compacto firmado (HS256, mismo formato que un JWT) que TortuScript emite
cuando un perfil autorizado pasa a Croco-Script:

- vive 60 segundos y lleva un identificador único (`jti`) para que el receptor lo acepte una sola vez;
- nombra emisor (`iss`) y destinatario (`aud`): un token para otro producto no sirve;
- solo lleva identificadores opacos de cuenta y perfil y el estado de acceso: ni correo, ni nombre
  del chico, ni datos de pago;
- la clave es un secreto de servicio con identificador (`kid`) para poder rotarla.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

EMISOR = "tortuscript"
VERSION = 1
VIDA_SEGUNDOS = 60
TOLERANCIA_RELOJ = 5
CLAVE_MINIMA = 32                 # caracteres del secreto de servicio
PRODUCTOS = ("croco-script",)


class FederacionError(ValueError):
    """El token o la configuración de federación no son válidos."""


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _desb64(texto: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))
    except (ValueError, TypeError) as exc:
        raise FederacionError("Token malformado.") from exc


def _firma(clave: str, mensaje: str) -> str:
    return _b64(hmac.new(clave.encode("utf-8"), mensaje.encode("ascii"), hashlib.sha256).digest())


def _validar_clave(clave) -> str:
    if not isinstance(clave, str) or len(clave) < CLAVE_MINIMA:
        raise FederacionError(f"El secreto de federación debe tener al menos {CLAVE_MINIMA} caracteres.")
    return clave


def emitir_autorizacion(clave: str, kid: str, destino: str, cuenta_id: str, perfil_id: str,
                        ahora: datetime | None = None, jti: str | None = None) -> str:
    """Token Authorization.v1 para que `perfil_id` entre a `destino`. Quien llama ya comprobó el acceso en servidor."""
    _validar_clave(clave)
    if destino not in PRODUCTOS:
        raise FederacionError("Producto de destino desconocido.")
    momento = int((ahora or datetime.now(timezone.utc)).timestamp())
    cabecera = {"alg": "HS256", "typ": "JWT", "kid": str(kid)}
    cuerpo = {
        "v": VERSION, "iss": EMISOR, "aud": destino, "sub": perfil_id, "acc": cuenta_id,
        "ent": {"producto": destino, "activo": True},
        "iat": momento, "exp": momento + VIDA_SEGUNDOS, "jti": jti or secrets.token_urlsafe(16),
    }
    partes = ".".join(_b64(json.dumps(p, separators=(",", ":"), sort_keys=True).encode("utf-8")) for p in (cabecera, cuerpo))
    return f"{partes}.{_firma(clave, partes)}"


def validar_autorizacion(token: str, claves: dict, destino: str, ahora: datetime | None = None,
                         ya_usado=None) -> dict:
    """Implementación de referencia de lo que debe hacer el receptor. Devuelve los datos del token o lanza.

    `claves` es {kid: secreto} (varias durante una rotación). `ya_usado(jti)` debe devolver True si ese
    token ya se aceptó: el receptor tiene que recordar cada `jti` hasta que venza.
    """
    if not isinstance(token, str) or token.count(".") != 2:
        raise FederacionError("Token malformado.")
    cabecera_b64, cuerpo_b64, firma = token.split(".")
    try:
        cabecera = json.loads(_desb64(cabecera_b64))
        cuerpo = json.loads(_desb64(cuerpo_b64))
    except ValueError as exc:
        raise FederacionError("Token malformado.") from exc
    if not isinstance(cabecera, dict) or not isinstance(cuerpo, dict):
        raise FederacionError("Token malformado.")
    # El algoritmo es fijo: nunca se toma del token (evita «alg: none» y la confusión de algoritmos).
    if cabecera.get("alg") != "HS256":
        raise FederacionError("Algoritmo de firma no admitido.")
    clave = claves.get(cabecera.get("kid")) if isinstance(claves, dict) else None
    if not clave:
        raise FederacionError("Clave de firma desconocida.")
    if not hmac.compare_digest(_firma(_validar_clave(clave), f"{cabecera_b64}.{cuerpo_b64}"), firma):
        raise FederacionError("La firma no coincide.")
    if cuerpo.get("v") != VERSION:
        raise FederacionError("Versión de contrato no admitida.")
    if cuerpo.get("iss") != EMISOR or cuerpo.get("aud") != destino:
        raise FederacionError("El token no fue emitido para este producto.")
    momento = int((ahora or datetime.now(timezone.utc)).timestamp())
    iat, exp = cuerpo.get("iat"), cuerpo.get("exp")
    if type(iat) is not int or type(exp) is not int or exp - iat > VIDA_SEGUNDOS:
        raise FederacionError("Vigencia del token no válida.")
    if momento > exp or momento < iat - TOLERANCIA_RELOJ:
        raise FederacionError("El token venció o todavía no vale.")
    for campo in ("sub", "acc", "jti"):
        if not isinstance(cuerpo.get(campo), str) or not cuerpo[campo]:
            raise FederacionError("Al token le falta un identificador.")
    acceso = cuerpo.get("ent")
    if not isinstance(acceso, dict) or acceso.get("producto") != destino or acceso.get("activo") is not True:
        raise FederacionError("El token no concede acceso a este producto.")
    if ya_usado is not None and ya_usado(cuerpo["jti"]):
        raise FederacionError("El token ya fue utilizado.")
    return cuerpo


# ── documentos de contrato (lo que TortuScript expone a otro producto del ecosistema) ──
def identidad_v1(cuenta_id: str, perfil_id: str) -> dict:
    """Identity.v1: solo identificadores opacos. Sin correo, sin nombre visible, sin credenciales."""
    return {"contrato": "Identity.v1", "cuenta": cuenta_id, "perfil": perfil_id}


def acceso_v1(producto: str, activo: bool, vigente_desde: str) -> dict:
    """Entitlement.v1: estado de acceso a un producto en un momento dado."""
    return {"contrato": "Entitlement.v1", "producto": producto, "activo": bool(activo), "consultado": vigente_desde}


def progreso_v1(perfil_id: str, producto: str, version_curricular: str, cursos: list, actualizado: str) -> dict:
    """Progress.v1: resumen educativo por curso. Lo llena cada producto con SU progreso; no es la base interna."""
    limpio = []
    for curso in cursos:
        limpio.append({
            "curso": str(curso["curso"]),
            "lecciones_completadas": sorted(str(x) for x in curso.get("lecciones_completadas", [])),
            "ejercicios_completados": int(curso.get("ejercicios_completados", 0)),
            "proyectos": int(curso.get("proyectos", 0)),
            "evaluaciones": [{"id": str(e["id"]), "aprobada": bool(e["aprobada"])} for e in curso.get("evaluaciones", [])],
        })
    return {"contrato": "Progress.v1", "perfil": perfil_id, "producto": producto,
            "version_curricular": version_curricular, "actualizado": actualizado, "cursos": limpio}
