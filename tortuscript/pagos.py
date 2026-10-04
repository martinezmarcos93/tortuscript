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

Medios de pago (ADR-047): el primero es la transferencia. El adulto arma una orden, transfiere por
fuera de TortuScript y avisa; quien opera la instalación confirma que el dinero llegó
(`herramientas/gestionar_pagos.py`) y esa confirmación entra como un pago más del proveedor
«transferencia», por el mismo camino que cualquier otro evento. Los medios automáticos (tarjeta)
figuran en `MEDIOS_DE_PAGO` como no disponibles: sumarlos es escribir su adaptador y encenderlos.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
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

# Medios con los que una familia puede pagar. `disponible=False`: se muestra como «próximamente» y no
# admite órdenes; su circuito (adaptador + webhook) todavía no existe.
MEDIOS_DE_PAGO = (
    {"id": "transferencia", "nombre": "Transferencia", "disponible": True,
     "descripcion": "Desde tu banco o billetera virtual, al alias que te mostramos."},
    {"id": "tarjeta", "nombre": "Tarjeta de crédito o débito", "disponible": False,
     "descripcion": "Pago automático con tarjeta."},
)
PROVEEDOR_TRANSFERENCIA = "transferencia"
ORDEN_PENDIENTE, ORDEN_INFORMADA, ORDEN_CONFIRMADA, ORDEN_RECHAZADA, ORDEN_CANCELADA = (
    "pendiente", "informada", "confirmada", "rechazada", "cancelada")
ORDENES_ABIERTAS = (ORDEN_PENDIENTE, ORDEN_INFORMADA)
MAX_NOTA = 120
# Solo letras y números que no se confunden al copiarlos a mano en el concepto de la transferencia.
_ALFABETO_REFERENCIA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


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


def importe_legible(centavos: int) -> str:
    """950000 → «$ 9.500»; 950050 → «$ 9.500,50»."""
    entero, resto = divmod(centavos, 100)
    return "$ " + f"{entero:,}".replace(",", ".") + (f",{resto:02d}" if resto else "")


@dataclass(frozen=True)
class ConfiguracionPagos:
    """Lo que hace falta para ofrecer la suscripción. Sin alias o sin importe, no se ofrece nada."""
    alias: str = ""
    titular: str = ""
    importe_centavos: int = 0
    moneda: str = "ARS"
    dias: int = 30
    producto: str = "tortuscript-premium"

    @property
    def habilitado(self) -> bool:
        return bool(self.alias) and self.importe_centavos > 0

    @property
    def importe_legible(self) -> str:
        return importe_legible(self.importe_centavos)


def configuracion_desde_entorno(entorno=None) -> ConfiguracionPagos:
    """Lee TORTU_PAGO_* (ver `.env.example`). El alias vive solo en el `.env` de la instalación, nunca en el repo.
    Un valor mal escrito deja los pagos apagados y lanza PagoError: es preferible no cobrar a cobrar mal."""
    import os
    entorno = os.environ if entorno is None else entorno
    alias = (entorno.get("TORTU_PAGO_ALIAS") or "").strip()
    importe = (entorno.get("TORTU_PAGO_IMPORTE") or "").strip()
    dias = (entorno.get("TORTU_PAGO_DIAS") or "30").strip()
    if not alias and not importe:
        return ConfiguracionPagos()
    try:
        pesos, _, centavos = importe.replace(",", ".").partition(".")
        importe_centavos = int(pesos) * 100 + int((centavos + "00")[:2] if centavos else 0)
        dias = int(dias)
    except ValueError as exc:
        raise PagoError("TORTU_PAGO_IMPORTE y TORTU_PAGO_DIAS deben ser números (por ejemplo 9500 y 30).") from exc
    if not alias or importe_centavos <= 0 or not 1 <= dias <= 366:
        raise PagoError("Para ofrecer la suscripción hacen falta TORTU_PAGO_ALIAS, un TORTU_PAGO_IMPORTE mayor a cero "
                        "y TORTU_PAGO_DIAS entre 1 y 366.")
    return ConfiguracionPagos(
        alias=alias, titular=(entorno.get("TORTU_PAGO_TITULAR") or "").strip(), importe_centavos=importe_centavos,
        moneda=(entorno.get("TORTU_PAGO_MONEDA") or "ARS").strip().upper(), dias=dias)


def medio_de_pago(medio_id):
    for medio in MEDIOS_DE_PAGO:
        if medio["id"] == medio_id:
            return medio
    return None


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
                # Órdenes de pago de los medios que confirma una persona (ADR-047). No guardan datos bancarios.
                con.execute("""
                    CREATE TABLE IF NOT EXISTS payment_orders (
                        id TEXT PRIMARY KEY,
                        account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                        product TEXT NOT NULL,
                        method TEXT NOT NULL,
                        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                        currency TEXT NOT NULL,
                        days INTEGER NOT NULL CHECK (days > 0),
                        reference TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL CHECK (status IN ('pendiente','informada','confirmada','rechazada','cancelada')),
                        created_at TEXT NOT NULL,
                        informed_at TEXT,
                        resolved_at TEXT,
                        payer_note TEXT NOT NULL DEFAULT '',
                        operator_note TEXT NOT NULL DEFAULT ''
                    )""")
                con.execute("CREATE INDEX IF NOT EXISTS idx_payment_orders_account ON payment_orders(account_id, created_at)")
                # Como mucho una orden abierta por cuenta y producto: pedirla dos veces devuelve la misma.
                con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_orders_abierta
                               ON payment_orders(account_id, product) WHERE status IN ('pendiente','informada')""")
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

    # ── órdenes de pago (medios que confirma una persona) ──
    @staticmethod
    def _orden(fila) -> dict:
        return {"id": fila["id"], "cuenta": fila["account_id"], "producto": fila["product"], "medio": fila["method"],
                "importe_centavos": fila["amount_cents"], "importe_legible": importe_legible(fila["amount_cents"]),
                "moneda": fila["currency"], "dias": fila["days"],
                "referencia": fila["reference"], "estado": fila["status"], "creada": fila["created_at"],
                "informada": fila["informed_at"], "resuelta": fila["resolved_at"], "nota": fila["payer_note"],
                "nota_operador": fila["operator_note"]}

    def crear_orden(self, account_id: str, producto: str, medio: str, importe_centavos: int, moneda: str,
                    dias: int, ahora: datetime | None = None) -> dict:
        """Orden pendiente para pagar `producto`. Si la cuenta ya tiene una abierta para ese producto, devuelve esa."""
        definicion = medio_de_pago(medio)
        if definicion is None:
            raise PagoError("Ese medio de pago no existe.")
        if not definicion["disponible"]:
            raise PagoError("Ese medio de pago todavía no está disponible.")
        if producto not in PRODUCTOS:
            raise PagoError("Ese producto no existe.")
        if type(importe_centavos) is not int or importe_centavos <= 0 or type(dias) is not int or dias <= 0:
            raise PagoError("El importe y la duración de la orden no son válidos.")
        ahora = ahora or datetime.now(timezone.utc)
        with closing(self._conexion()) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                if not isinstance(account_id, str) or \
                        not con.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone():
                    raise PagoError("La cuenta no existe.")
                abierta = con.execute(
                    "SELECT * FROM payment_orders WHERE account_id=? AND product=? AND status IN ('pendiente','informada')",
                    (account_id, producto)).fetchone()
                if abierta is None:
                    orden_id = "ord_" + secrets.token_hex(12)
                    referencia = "TS-" + "".join(secrets.choice(_ALFABETO_REFERENCIA) for _ in range(6))
                    con.execute(
                        """INSERT INTO payment_orders(id,account_id,product,method,amount_cents,currency,days,reference,
                                                      status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (orden_id, account_id, producto, medio, importe_centavos, moneda, dias, referencia,
                         ORDEN_PENDIENTE, _iso(ahora)))
                    abierta = con.execute("SELECT * FROM payment_orders WHERE id=?", (orden_id,)).fetchone()
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return self._orden(abierta)

    def _cambiar_orden(self, orden_id, desde, hacia, columnas, cuenta=None):
        """Pasa una orden de uno de los estados `desde` a `hacia`. Con `cuenta`, solo si es de esa cuenta."""
        with closing(self._conexion()) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                fila = con.execute("SELECT * FROM payment_orders WHERE id=?", (orden_id,)).fetchone() \
                    if isinstance(orden_id, str) else None
                if fila is None or (cuenta is not None and fila["account_id"] != cuenta):
                    raise PagoError("La orden no existe.")
                if fila["status"] not in desde:
                    raise PagoError(f"La orden está {fila['status']}: ya no se puede modificar.")
                asignaciones = ", ".join(f"{columna}=?" for columna in columnas)
                con.execute(f"UPDATE payment_orders SET status=?, {asignaciones} WHERE id=?",
                            (hacia, *columnas.values(), orden_id))
                fila = con.execute("SELECT * FROM payment_orders WHERE id=?", (orden_id,)).fetchone()
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return self._orden(fila)

    def informar_orden(self, account_id: str, orden_id: str, nota: str = "", ahora: datetime | None = None) -> dict:
        """El adulto avisa que ya transfirió. No concede acceso: falta que alguien confirme que el dinero llegó."""
        if not isinstance(nota, str):
            raise PagoError("La nota no es válida.")
        nota = " ".join(nota.split())[:MAX_NOTA]
        return self._cambiar_orden(orden_id, (ORDEN_PENDIENTE,), ORDEN_INFORMADA,
                                   {"informed_at": _iso(ahora or datetime.now(timezone.utc)), "payer_note": nota},
                                   cuenta=account_id)

    def cancelar_orden(self, account_id: str, orden_id: str, ahora: datetime | None = None) -> dict:
        return self._cambiar_orden(orden_id, ORDENES_ABIERTAS, ORDEN_CANCELADA,
                                   {"resolved_at": _iso(ahora or datetime.now(timezone.utc))}, cuenta=account_id)

    def rechazar_orden(self, orden_id: str, nota: str = "", ahora: datetime | None = None) -> dict:
        """Quien opera no encontró el pago. La familia puede armar otra orden."""
        return self._cambiar_orden(orden_id, ORDENES_ABIERTAS, ORDEN_RECHAZADA,
                                   {"resolved_at": _iso(ahora or datetime.now(timezone.utc)),
                                    "operator_note": " ".join(str(nota).split())[:MAX_NOTA]})

    def confirmar_orden(self, orden_id: str, ahora: datetime | None = None) -> dict:
        """Quien opera vio el dinero en su cuenta: el pago entra como evento del proveedor «transferencia».

        El período nuevo arranca donde termina el que la cuenta ya tiene pago (o ahora, si no tiene). Repetir la
        confirmación no suma días: el identificador del evento es el de la orden.
        """
        ahora = ahora or datetime.now(timezone.utc)
        with closing(self._conexion()) as con:
            fila = con.execute("SELECT * FROM payment_orders WHERE id=?", (orden_id,)).fetchone() \
                if isinstance(orden_id, str) else None
            if fila is None:
                raise PagoError("La orden no existe.")
            if fila["status"] == ORDEN_CONFIRMADA:
                return self._orden(fila)
            if fila["status"] not in ORDENES_ABIERTAS:
                raise PagoError(f"La orden está {fila['status']}: no se puede confirmar.")
            # Una suscripción por cuenta y producto. Es un hash: la referencia queda en el registro de eventos,
            # que sobrevive a la eliminación de la cuenta (ADR-046) y no debe permitir identificarla.
            suscripcion = "tr_" + hashlib.sha256(
                f"transferencia:{fila['account_id']}:{fila['product']}".encode("utf-8")).hexdigest()[:24]
            vigente = con.execute(
                "SELECT period_end FROM subscriptions WHERE provider=? AND provider_reference=? AND status='active'",
                (PROVEEDOR_TRANSFERENCIA, suscripcion)).fetchone()
        desde = ahora
        if vigente is not None and vigente["period_end"]:
            desde = max(ahora, datetime.fromisoformat(vigente["period_end"]))
        resultado = self.aplicar(EventoPago(
            proveedor=PROVEEDOR_TRANSFERENCIA, id=fila["id"], tipo="payment_succeeded", cuenta_id=fila["account_id"],
            producto=fila["product"], suscripcion=suscripcion, ocurrido=ahora,
            periodo_hasta=desde + timedelta(days=fila["days"])), ahora=ahora)
        if resultado.estado not in (APLICADO, DUPLICADO):
            raise PagoError(f"El pago no se pudo aplicar: {resultado.detalle}")
        return self._cambiar_orden(orden_id, ORDENES_ABIERTAS, ORDEN_CONFIRMADA, {"resolved_at": _iso(ahora)})

    def listar_ordenes(self, account_id: str, limite: int = 20) -> list[dict]:
        """Las órdenes de la cuenta, de la más nueva a la más vieja."""
        with closing(self._conexion()) as con:
            filas = con.execute("SELECT * FROM payment_orders WHERE account_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                                (account_id, limite)).fetchall()
        return [self._orden(f) for f in filas]

    def listar_ordenes_abiertas(self) -> list[dict]:
        """Lo que tiene que mirar quien opera: primero las que la familia ya avisó que pagó."""
        with closing(self._conexion()) as con:
            filas = con.execute(
                """SELECT * FROM payment_orders WHERE status IN ('pendiente','informada')
                   ORDER BY status='informada' DESC, COALESCE(informed_at, created_at), id""").fetchall()
        return [self._orden(f) for f in filas]

    def buscar_orden(self, texto: str) -> dict | None:
        """Por identificador o por la referencia que la familia puso en el concepto de la transferencia."""
        if not isinstance(texto, str) or not texto.strip():
            return None
        with closing(self._conexion()) as con:
            fila = con.execute("SELECT * FROM payment_orders WHERE id=? OR reference=?",
                               (texto.strip(), texto.strip().upper())).fetchone()
        return self._orden(fila) if fila else None

    # ── consultas ──
    def tiene_suscripcion_que_se_renueva(self, account_id: str) -> bool:
        """True si algún proveedor va a seguir cobrando (ADR-046: antes de eliminar la cuenta hay que cancelarla).
        Una transferencia no se renueva sola."""
        with closing(self._conexion()) as con:
            return con.execute(
                "SELECT 1 FROM subscriptions WHERE account_id=? AND provider<>? AND status IN ('active','past_due')",
                (account_id, PROVEEDOR_TRANSFERENCIA)).fetchone() is not None

    def listar_suscripciones(self, account_id: str) -> list[dict]:
        with closing(self._conexion()) as con:
            filas = con.execute(
                "SELECT product,status,period_end,provider FROM subscriptions WHERE account_id=? ORDER BY created_at,id",
                (account_id,),
            ).fetchall()
        ahora = _iso(datetime.now(timezone.utc))
        # Un medio que no se renueva solo (transferencia) deja la suscripción «activa» con el período vencido:
        # `vencida` lo dice sin tocar el estado que informó el proveedor.
        return [{"producto": f["product"], "estado": f["status"], "periodo_hasta": f["period_end"],
                 "proveedor": f["provider"],
                 "vencida": bool(f["status"] == "active" and f["period_end"] and f["period_end"] < ahora)}
                for f in filas]

    def listar_en_revision(self) -> list[dict]:
        """Eventos que no se pudieron aplicar: los mira una persona (reconciliación)."""
        with closing(self._conexion()) as con:
            filas = con.execute(
                "SELECT provider,event_id,type,account_id,received_at,detail FROM payment_events WHERE status='revision' ORDER BY received_at"
            ).fetchall()
        return [dict(f) for f in filas]
