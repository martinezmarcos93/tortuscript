"""Suscripciones y acceso pago (ADR-032): eventos del proveedor → Subscription → Entitlement.

Este módulo NO cobra ni conoce tarjetas. Recibe eventos ya autenticados de un proveedor
externo (ver `verificar_firma`) y mantiene el estado interno:

    Account → Subscription (lo que dice el proveedor) → Entitlement (lo que TortuScript concede)

Reglas (docs/architecture/CONTRATOS-DOMINIO-PRIVACIDAD-Y-ROADMAP.md):
- Cada evento se aplica una sola vez: el identificador del proveedor es único (idempotencia).
- El evento y su efecto sobre el acceso se guardan en la misma transacción.
- Un evento inconsistente queda «en revisión» y nunca concede acceso.
- Un evento más viejo que el último aplicado a la suscripción se registra pero no cambia nada.
- El acceso nunca se concede por un retorno de checkout: solo por un pago confirmado.
- Cancelar no borra nada: el acceso sigue hasta el fin del período pagado.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

PRODUCTOS = ("tortuscript-premium", "croco-script")
TIPOS = ("checkout_completed", "payment_succeeded", "payment_failed",
         "subscription_updated", "subscription_canceled", "refund")
ESTADOS = ("incomplete", "active", "past_due", "canceled", "refunded")
# Tras un cobro fallido el acceso sigue unos días mientras el proveedor reintenta.
DIAS_DE_GRACIA = 7
# Ventana para aceptar un webhook firmado: evita reenviar uno capturado tiempo atrás.
TOLERANCIA_FIRMA_SEGUNDOS = 300
MAX_CUERPO_WEBHOOK = 64 * 1024

APLICADO, DUPLICADO, OBSOLETO, REVISION = "aplicado", "duplicado", "obsoleto", "revision"


class PagoError(ValueError):
    """El evento o la firma no son válidos."""


@dataclass(frozen=True)
class EventoPago:
    proveedor: str
    id: str
    tipo: str
    cuenta_id: str
    producto: str
    suscripcion: str
    ocurrido: datetime
    periodo_hasta: datetime | None = None


@dataclass(frozen=True)
class Resultado:
    estado: str                # aplicado | duplicado | obsoleto | revision
    detalle: str = ""


def _iso(valor: datetime) -> str:
    return valor.astimezone(timezone.utc).isoformat(timespec="seconds")


def _fecha(valor, campo, obligatoria=True):
    if valor is None and not obligatoria:
        return None
    if not isinstance(valor, str):
        raise PagoError(f"El evento no trae una fecha válida en «{campo}».")
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PagoError(f"El evento no trae una fecha válida en «{campo}».") from exc
    if fecha.tzinfo is None:
        raise PagoError(f"La fecha de «{campo}» no indica zona horaria.")
    return fecha.astimezone(timezone.utc)


def _texto(valor, campo, maximo=200):
    if not isinstance(valor, str) or not valor.strip() or len(valor) > maximo:
        raise PagoError(f"El evento no trae un «{campo}» válido.")
    return valor.strip()


def evento_desde_json(proveedor: str, cuerpo: bytes) -> EventoPago:
    """Formato interno de un evento. El adaptador de cada proveedor real traduce su webhook a este formato;
    el proveedor «prueba» lo usa tal cual para ensayar el circuito sin cobrar."""
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PagoError("El cuerpo del evento no es JSON válido.") from exc
    if not isinstance(datos, dict):
        raise PagoError("El cuerpo del evento no es un objeto JSON.")
    tipo = _texto(datos.get("tipo"), "tipo")
    if tipo not in TIPOS:
        raise PagoError("Tipo de evento desconocido.")
    return EventoPago(
        proveedor=proveedor, id=_texto(datos.get("id"), "id"), tipo=tipo,
        cuenta_id=_texto(datos.get("cuenta"), "cuenta"), producto=_texto(datos.get("producto"), "producto"),
        suscripcion=_texto(datos.get("suscripcion"), "suscripcion"),
        ocurrido=_fecha(datos.get("ocurrido"), "ocurrido"),
        periodo_hasta=_fecha(datos.get("periodo_hasta"), "periodo_hasta", obligatoria=False),
    )


# Un adaptador por proveedor: (nombre) → función que convierte el cuerpo del webhook en EventoPago.
ADAPTADORES = {"prueba": lambda cuerpo: evento_desde_json("prueba", cuerpo)}


def firmar(secreto: str, cuerpo: bytes, momento: int) -> str:
    """Cabecera de firma «t=<unix>,v1=<hmac-sha256 hex de "t.cuerpo">» (la usan las pruebas y el proveedor de prueba)."""
    mac = hmac.new(secreto.encode("utf-8"), f"{momento}.".encode("ascii") + cuerpo, hashlib.sha256).hexdigest()
    return f"t={momento},v1={mac}"


def verificar_firma(secreto: str, cuerpo: bytes, cabecera: str, ahora: datetime | None = None,
                    tolerancia: int = TOLERANCIA_FIRMA_SEGUNDOS) -> None:
    """Lanza PagoError salvo que la cabecera firme exactamente este cuerpo, con este secreto y hace poco."""
    if not secreto or not isinstance(cabecera, str):
        raise PagoError("Firma ausente.")
    partes = dict(p.split("=", 1) for p in cabecera.split(",") if "=" in p)
    try:
        momento = int(partes.get("t", ""))
    except ValueError as exc:
        raise PagoError("Firma malformada.") from exc
    esperada = firmar(secreto, cuerpo, momento).split("v1=", 1)[1]
    if not hmac.compare_digest(esperada, partes.get("v1", "")):
        raise PagoError("La firma no coincide.")
    ahora = ahora or datetime.now(timezone.utc)
    if abs(ahora.timestamp() - momento) > tolerancia:
        raise PagoError("La firma está fuera de la ventana de tiempo aceptada.")


class ServicioPagos:
    """Aplica eventos del proveedor sobre la misma base SQLite de cuentas."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _conexion(self):
        con = sqlite3.connect(self.path, isolation_level=None)       # transacciones explícitas
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def ensure_schema(self) -> None:
        """Agrega lo que necesitan los pagos al esquema de cuentas (que debe existir). Solo suma: no cambia nada previo."""
        with closing(self._conexion()) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                columnas = {r["name"] for r in con.execute("PRAGMA table_info(subscriptions)")}
                if not columnas:
                    raise PagoError("El esquema de cuentas todavía no existe.")
                for nombre in ("product", "period_end", "last_event_at"):
                    if nombre not in columnas:
                        con.execute(f"ALTER TABLE subscriptions ADD COLUMN {nombre} TEXT")
                con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_provider_ref
                               ON subscriptions(provider, provider_reference)""")
                con.execute("""
                    CREATE TABLE IF NOT EXISTS payment_events (
                        provider TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        type TEXT NOT NULL,
                        account_id TEXT,
                        subscription_reference TEXT,
                        occurred_at TEXT,
                        received_at TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('aplicado', 'obsoleto', 'revision')),
                        detail TEXT NOT NULL DEFAULT '',
                        PRIMARY KEY (provider, event_id)
                    )""")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise

    # ── aplicar un evento ──
    def aplicar(self, evento: EventoPago, ahora: datetime | None = None) -> Resultado:
        ahora = ahora or datetime.now(timezone.utc)
        with closing(self._conexion()) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                if con.execute("SELECT 1 FROM payment_events WHERE provider=? AND event_id=?",
                               (evento.proveedor, evento.id)).fetchone():
                    con.execute("ROLLBACK")
                    return Resultado(DUPLICADO)
                estado, detalle = self._aplicar_en_transaccion(con, evento, ahora)
                con.execute(
                    """INSERT INTO payment_events(provider,event_id,type,account_id,subscription_reference,
                                                  occurred_at,received_at,status,detail) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (evento.proveedor, evento.id, evento.tipo, evento.cuenta_id, evento.suscripcion,
                     _iso(evento.ocurrido), _iso(ahora), estado, detalle),
                )
                con.execute("COMMIT")
            except sqlite3.IntegrityError:
                # Otro proceso registró el mismo evento entre la consulta y la inserción.
                con.execute("ROLLBACK")
                return Resultado(DUPLICADO)
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return Resultado(estado, detalle)

    def _aplicar_en_transaccion(self, con, e: EventoPago, ahora: datetime):
        if e.tipo not in TIPOS:
            return REVISION, "tipo de evento desconocido"
        if e.producto not in PRODUCTOS:
            return REVISION, "producto desconocido"
        if not con.execute("SELECT 1 FROM accounts WHERE id=?", (e.cuenta_id,)).fetchone():
            return REVISION, "la cuenta no existe"
        sub = con.execute("SELECT * FROM subscriptions WHERE provider=? AND provider_reference=?",
                          (e.proveedor, e.suscripcion)).fetchone()
        if sub is not None:
            if sub["account_id"] != e.cuenta_id:
                return REVISION, "la suscripción pertenece a otra cuenta"
            if sub["product"] != e.producto:
                return REVISION, "la suscripción es de otro producto"
            if sub["last_event_at"] and _iso(e.ocurrido) < sub["last_event_at"]:
                return OBSOLETO, "hay un evento posterior ya aplicado"
        elif e.tipo not in ("checkout_completed", "payment_succeeded"):
            return REVISION, "evento sobre una suscripción que no se conoce"

        periodo = e.periodo_hasta or (datetime.fromisoformat(sub["period_end"]) if sub is not None and sub["period_end"] else None)
        if e.tipo == "checkout_completed":
            # Terminar el checkout no es haber pagado: todavía no hay acceso.
            estado, acceso = (sub["status"] if sub is not None else "incomplete"), None
        elif e.tipo == "payment_succeeded":
            if e.periodo_hasta is None:
                return REVISION, "pago sin fin de período"
            estado, acceso = "active", (True, e.periodo_hasta + timedelta(days=DIAS_DE_GRACIA))
        elif e.tipo == "payment_failed":
            estado, acceso = "past_due", None                         # sigue lo ya concedido (período + gracia)
        elif e.tipo == "subscription_updated":
            estado = sub["status"]
            acceso = (True, periodo + timedelta(days=DIAS_DE_GRACIA)) if estado == "active" and e.periodo_hasta else None
        elif e.tipo == "subscription_canceled":
            estado = "canceled"
            # Lo pagado se respeta hasta el final del período, sin días de gracia.
            acceso = (True, periodo) if periodo and periodo > ahora else (False, None)
        else:                                                         # refund
            estado, acceso = "refunded", (False, None)

        momento = _iso(e.ocurrido)
        if sub is None:
            con.execute(
                """INSERT INTO subscriptions(id,account_id,provider,provider_reference,status,created_at,updated_at,
                                             product,period_end,last_event_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("sub_" + hashlib.sha256(f"{e.proveedor}:{e.suscripcion}".encode()).hexdigest()[:24], e.cuenta_id,
                 e.proveedor, e.suscripcion, estado, _iso(ahora), _iso(ahora), e.producto,
                 _iso(periodo) if periodo else None, momento),
            )
        else:
            con.execute("UPDATE subscriptions SET status=?, updated_at=?, period_end=?, last_event_at=? WHERE id=?",
                        (estado, _iso(ahora), _iso(periodo) if periodo else None, momento, sub["id"]))
        if acceso is not None:
            # Un acceso concedido a mano (soporte, admin) no lo recorta un evento de pago: el WHERE lo preserva.
            activo, vence = acceso
            con.execute(
                """INSERT INTO entitlements(account_id,product,active,source,updated_at,expires_at) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(account_id,product) DO UPDATE SET active=excluded.active, source=excluded.source,
                       updated_at=excluded.updated_at, expires_at=excluded.expires_at
                   WHERE entitlements.source LIKE 'payment:%' OR entitlements.active=0""",
                (e.cuenta_id, e.producto, int(activo), f"payment:{e.proveedor}", _iso(ahora), _iso(vence) if vence else None),
            )
        return APLICADO, estado

    # ── consultas ──
    def listar_suscripciones(self, account_id: str) -> list[dict]:
        with closing(self._conexion()) as con:
            filas = con.execute(
                "SELECT product,status,period_end,provider FROM subscriptions WHERE account_id=? ORDER BY created_at,id",
                (account_id,),
            ).fetchall()
        return [{"producto": f["product"], "estado": f["status"], "periodo_hasta": f["period_end"],
                 "proveedor": f["provider"]} for f in filas]

    def listar_en_revision(self) -> list[dict]:
        """Eventos que no se pudieron aplicar: los mira una persona (reconciliación)."""
        with closing(self._conexion()) as con:
            filas = con.execute(
                "SELECT provider,event_id,type,account_id,received_at,detail FROM payment_events WHERE status='revision' ORDER BY received_at"
            ).fetchall()
        return [dict(f) for f in filas]
