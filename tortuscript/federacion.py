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
    if type(cuerpo.get("v")) is not int or cuerpo.get("v") != VERSION:
        raise FederacionError("Versión de contrato no admitida.")
    if cuerpo.get("iss") != EMISOR or cuerpo.get("aud") != destino:
        raise FederacionError("El token no fue emitido para este producto.")
    momento = int((ahora or datetime.now(timezone.utc)).timestamp())
    iat, exp = cuerpo.get("iat"), cuerpo.get("exp")
    if type(iat) is not int or type(exp) is not int or exp <= iat or exp - iat > VIDA_SEGUNDOS:
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


# ── consultas firmadas de servidor a servidor (Entitlement.v1 y ProgressQuery.v1: Croco-Script pregunta) ──
VENTANA_CONSULTA = 60            # segundos de diferencia de reloj que se toleran en un pedido
ACCIONES_SOBRE_DATOS = ("suprimir_perfil", "suprimir_cuenta", "exportar_perfil")


def firma_de_consulta(clave: str, momento: int, producto: str, identificador: str) -> str:
    """HMAC-SHA256 de «momento.producto.identificador» (base64 para direcciones, sin «=»). `identificador` es la
    cuenta (Entitlement.v1) o el perfil (ProgressQuery.v1)."""
    mensaje = f"{int(momento)}.{producto}.{identificador}".encode("utf-8")
    return _b64(hmac.new(_validar_clave(clave).encode("utf-8"), mensaje, hashlib.sha256).digest())


def validar_consulta(encabezado, claves: dict, producto: str, identificador: str, ahora: datetime | None = None) -> None:
    """Valida `Authorization: Croco-HMAC kid=…, ts=…, firma=…`. Lanza FederacionError si no corresponde.
    El motivo es para el log; al que pregunta se le responde siempre lo mismo."""
    if not isinstance(encabezado, str) or not encabezado.startswith("Croco-HMAC "):
        raise FederacionError("Falta la firma de la consulta.")
    partes = {}
    for trozo in encabezado[len("Croco-HMAC "):].split(","):
        nombre, separador, valor = trozo.strip().partition("=")
        if not separador or nombre in partes:
            raise FederacionError("Firma de consulta mal formada.")
        partes[nombre] = valor
    if set(partes) != {"kid", "ts", "firma"} or not partes["ts"].isdigit() or len(partes["ts"]) > 12:
        raise FederacionError("Firma de consulta mal formada.")
    clave = claves.get(partes["kid"]) if isinstance(claves, dict) else None
    if not clave:
        raise FederacionError("Clave de firma desconocida.")
    esperada = firma_de_consulta(clave, int(partes["ts"]), producto, identificador)
    if not hmac.compare_digest(esperada, partes["firma"]):
        raise FederacionError("La firma no coincide.")
    momento = int((ahora or datetime.now(timezone.utc)).timestamp())
    if abs(momento - int(partes["ts"])) > VENTANA_CONSULTA:
        raise FederacionError("La consulta está fuera de la ventana de tiempo aceptada.")


def emitir_operacion(clave: str, kid: str, destino: str, accion: str, cuenta_id: str, perfil_id: str | None = None,
                     ahora: datetime | None = None, jti: str | None = None) -> str:
    """Token Supresion.v1: pide a otro producto borrar o exportar datos. Mismo formato y claves que Authorization.v1,
    pero con `act` y sin `ent`: ninguno de los dos tokens sirve en el lugar del otro."""
    _validar_clave(clave)
    if destino not in PRODUCTOS:
        raise FederacionError("Producto de destino desconocido.")
    if accion not in ACCIONES_SOBRE_DATOS:
        raise FederacionError("Acción no admitida.")
    if not cuenta_id or (accion != "suprimir_cuenta" and not perfil_id):
        raise FederacionError("Falta un identificador.")
    momento = int((ahora or datetime.now(timezone.utc)).timestamp())
    cuerpo = {"v": VERSION, "iss": EMISOR, "aud": destino, "act": accion, "acc": cuenta_id,
              "iat": momento, "exp": momento + VIDA_SEGUNDOS, "jti": jti or secrets.token_urlsafe(16)}
    if perfil_id:
        cuerpo["sub"] = perfil_id
    cabecera = {"alg": "HS256", "typ": "JWT", "kid": str(kid)}
    partes = ".".join(_b64(json.dumps(p, separators=(",", ":"), sort_keys=True).encode("utf-8")) for p in (cabecera, cuerpo))
    return f"{partes}.{_firma(clave, partes)}"


def configuracion_desde_entorno(entorno=None) -> dict:
    """La configuración `FEDERACION` a partir de TORTU_CROCO_* (ver `.env.example`). Vacía si no hay nada definido.

    Una configuración a medias o insegura lanza FederacionError: es preferible no levantar el puente a levantarlo
    con una clave débil o hacia una dirección mal escrita."""
    import os
    from urllib.parse import urlsplit
    entorno = os.environ if entorno is None else entorno
    url = (entorno.get("TORTU_CROCO_URL") or "").strip()
    clave = (entorno.get("TORTU_CROCO_CLAVE") or "").strip()
    kid = (entorno.get("TORTU_CROCO_KID") or "k1").strip()
    if not url and not clave:
        return {}
    if not url or not clave:
        raise FederacionError("Para conectar con Croco-Script hacen falta TORTU_CROCO_URL y TORTU_CROCO_CLAVE.")
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise FederacionError("TORTU_CROCO_URL debe ser la dirección de entrada de Croco-Script, por ejemplo "
                              "http://127.0.0.1:5067/entrar")
    local = partes.hostname in ("127.0.0.1", "localhost")
    if partes.scheme != "https" and not local:
        raise FederacionError("TORTU_CROCO_URL debe ser https:// salvo que Croco-Script corra en esta misma máquina.")
    _validar_clave(clave)
    if not kid or len(kid) > 40:
        raise FederacionError("TORTU_CROCO_KID no es válido.")
    return {"croco-script": {"url": url, "clave": clave, "kid": kid}}


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


def curriculo_v1(producto: str, version_curricular: str, itinerarios: list) -> dict:
    """Curriculum.v1: los identificadores estables que otro producto puede nombrar como prerrequisito.

    Solo identificadores y orden: ni títulos, ni contenido, ni reglas comerciales. Un itinerario se nombra por su
    `id`; una unidad, por el suyo. El orden de las unidades dentro del itinerario es el del recorrido.
    """
    limpios, vistos = [], set()
    for itinerario in itinerarios:
        itinerario_id = str(itinerario["id"])
        unidades = [str(u) for u in itinerario["unidades"]]
        for identificador in [itinerario_id, *unidades]:
            if identificador in vistos:
                raise FederacionError(f"Identificador curricular repetido: {identificador}")
            vistos.add(identificador)
        limpios.append({"id": itinerario_id, "unidades": unidades})
    return {"contrato": "Curriculum.v1", "producto": producto, "version_curricular": str(version_curricular),
            "itinerarios": limpios}


def prerrequisitos_desconocidos_v1(curriculo: dict, prerrequisitos: list) -> list:
    """Los prerrequisitos que no nombran ni un itinerario ni una unidad publicados (vacío: todos existen).
    Lo usa quien consume el contrato para validar su propio catálogo contra el de quien lo publica."""
    if not isinstance(curriculo, dict) or curriculo.get("contrato") != "Curriculum.v1":
        raise FederacionError("El documento no es un Curriculum.v1.")
    conocidos = set()
    for itinerario in curriculo.get("itinerarios", []):
        conocidos.add(itinerario["id"])
        conocidos.update(itinerario["unidades"])
    return [p for p in prerrequisitos if p not in conocidos]
