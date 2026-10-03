"""Modelo persistente mínimo de cuenta familiar para la transición web comercial.

Este módulo NO implementa autenticación ni pagos. Define únicamente la frontera
de identidad/comercial sobre la que después podrán apoyarse esos servicios.

Reglas:
- Account es la raíz de identidad adulta.
- ChildProfile pertenece a un Account.
- Subscription pertenece al Account, nunca al perfil.
- Entitlement se materializa para el Account y puede consultarse por perfil.
- No se almacenan contraseñas, tokens ni datos de tarjeta aquí.
- SQLite se usa como almacenamiento inicial; la API queda desacoplada del Flask
  actual para no romper el modo local mientras se construye V1 comercial.
"""
from __future__ import annotations

import re
import secrets
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 3
MAX_CHILD_PROFILES = 3
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CuentaError(ValueError):
    """Error de dominio de cuentas."""


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    created_at: str
    role: str = "adult"


@dataclass(frozen=True)
class ChildProfile:
    id: str
    account_id: str
    display_name: str
    created_at: str
    active: bool = True


@dataclass(frozen=True)
class Entitlement:
    account_id: str
    product: str
    active: bool
    source: str


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefijo: str, valor: str) -> str:
    import hashlib
    return f"{prefijo}_{hashlib.sha256(valor.encode('utf-8')).hexdigest()[:24]}"


def _normalizar_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise CuentaError("El correo electrónico no es válido.")
    return email


def _normalizar_nombre(nombre: str) -> str:
    nombre = " ".join((nombre or "").split())
    if not 1 <= len(nombre) <= 30:
        raise CuentaError("El nombre del perfil debe tener entre 1 y 30 caracteres.")
    return nombre


def _clave_nombre(nombre: str) -> str:
    """Clave estable para unicidad: compatibilidad Unicode + comparación sin caso."""
    return unicodedata.normalize("NFKC", _normalizar_nombre(nombre)).casefold()


class CuentaRepository:
    """Repositorio SQLite pequeño y explícito; no conoce Flask ni la sesión HTTP."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _conexion(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def ensure_schema(self) -> None:
        with self._conexion() as con:
            # Nunca modificar una base creada por una versión futura del programa.
            existe_version = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            if existe_version:
                try:
                    version_actual = con.execute(
                        "SELECT MAX(version) AS version FROM schema_version"
                    ).fetchone()
                except sqlite3.DatabaseError as exc:
                    raise CuentaError("La versión del esquema de cuentas no es compatible.") from exc
                if version_actual and version_actual["version"] not in (1, 2, SCHEMA_VERSION):
                    raise CuentaError("Versión de esquema de cuentas no compatible.")
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'adult' CHECK (role IN ('adult', 'admin'))
                );

                CREATE TABLE IF NOT EXISTS child_profiles (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    UNIQUE(account_id, display_name)
                );

                CREATE INDEX IF NOT EXISTS idx_child_profiles_account
                    ON child_profiles(account_id);

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    provider_reference TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_subscriptions_account
                    ON subscriptions(account_id);

                CREATE TABLE IF NOT EXISTS entitlements (
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    product TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(account_id, product)
                );
                """
            )
            cols = {r["name"] for r in con.execute("PRAGMA table_info(accounts)")}
            profile_cols = {r["name"] for r in con.execute("PRAGMA table_info(child_profiles)")}
            # Validar todos los alias históricos antes de tocar el esquema: ALTER TABLE
            # puede persistir aunque después abortemos la migración por duplicados.
            filas = con.execute(
                "SELECT id,account_id,display_name FROM child_profiles ORDER BY created_at,id"
            ).fetchall()
            claves = {}
            claves_por_id = {}
            for perfil in filas:
                clave = (perfil["account_id"], _clave_nombre(perfil["display_name"]))
                anterior = claves.get(clave)
                if anterior is not None and anterior != perfil["id"]:
                    raise CuentaError(
                        "Hay perfiles existentes con nombres equivalentes por mayúsculas o Unicode; "
                        "resolvé esos duplicados antes de actualizar el esquema."
                    )
                claves[clave] = perfil["id"]
                claves_por_id[perfil["id"]] = clave[1]
            # No alterar ninguna tabla existente hasta validar todo el historial.
            if "role" not in cols:
                con.execute("ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'adult'")
            if "display_name_key" not in profile_cols:
                con.execute("ALTER TABLE child_profiles ADD COLUMN display_name_key TEXT")
            for perfil_id, clave in claves_por_id.items():
                con.execute(
                    "UPDATE child_profiles SET display_name_key=? WHERE id=?",
                    (clave, perfil_id),
                )
            con.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_child_profiles_account_name_key
                   ON child_profiles(account_id, display_name_key)"""
            )

            row = con.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            if row is None:
                con.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
            elif row["version"] in (1, 2):
                con.execute("UPDATE schema_version SET version=?", (SCHEMA_VERSION,))
            elif row["version"] != SCHEMA_VERSION:
                raise CuentaError("Versión de esquema de cuentas no compatible.")


    def obtener_account_por_email(self, email: str) -> Optional[Account]:
        email = _normalizar_email(email)
        with self._conexion() as con:
            row = con.execute(
                "SELECT id,email,created_at,role FROM accounts WHERE email=?", (email,)
            ).fetchone()
        return Account(row["id"], row["email"], row["created_at"], row["role"]) if row else None

    def crear_account(self, email: str) -> Account:
        email = _normalizar_email(email)
        account_id = _id("acc", email)
        now = _ahora()
        with self._conexion() as con:
            try:
                con.execute(
                    "INSERT INTO accounts(id,email,created_at) VALUES (?,?,?)",
                    (account_id, email, now),
                )
            except sqlite3.IntegrityError as exc:
                raise CuentaError("La cuenta ya existe.") from exc
        return Account(account_id, email, now)

    def obtener_account(self, account_id: str) -> Optional[Account]:
        with self._conexion() as con:
            row = con.execute(
                "SELECT id,email,created_at,role FROM accounts WHERE id=?", (account_id,)
            ).fetchone()
        return Account(row["id"], row["email"], row["created_at"], row["role"]) if row else None


    def establecer_role(self, account_id: str, role: str) -> Account:
        if role not in {"adult", "admin"}:
            raise CuentaError("Rol de cuenta inválido.")
        with self._conexion() as con:
            con.execute("UPDATE accounts SET role=? WHERE id=?", (role, account_id))
            row = con.execute(
                "SELECT id,email,created_at,role FROM accounts WHERE id=?", (account_id,)
            ).fetchone()
            if not row:
                raise CuentaError("La cuenta no existe.")
        return Account(row["id"], row["email"], row["created_at"], row["role"])

    def es_admin(self, account_id: str) -> bool:
        with self._conexion() as con:
            row = con.execute("SELECT role FROM accounts WHERE id=?", (account_id,)).fetchone()
        return bool(row and row["role"] == "admin")

    def es_admin_por_perfil(self, profile_id: str) -> bool:
        with self._conexion() as con:
            row = con.execute(
                """SELECT a.role FROM child_profiles p
                   JOIN accounts a ON a.id=p.account_id
                   WHERE p.id=? AND p.active=1""",
                (profile_id,),
            ).fetchone()
        return bool(row and row["role"] == "admin")

    def crear_child_profile(self, account_id: str, display_name: str) -> ChildProfile:
        display_name = _normalizar_nombre(display_name)
        now = _ahora()
        # El ID interno es opaco y no deriva del alias visible: renombrar/recrear
        # un perfil no debe volver a asociar accidentalmente progreso huérfano.
        profile_id = f"child_{secrets.token_hex(12)}"
        display_name_key = _clave_nombre(display_name)
        with self._conexion() as con:
            account = con.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not account:
                raise CuentaError("La cuenta no existe.")
            duplicado = con.execute(
                "SELECT 1 FROM child_profiles WHERE account_id=? AND display_name_key=?",
                (account_id, display_name_key),
            ).fetchone()
            if duplicado:
                raise CuentaError("Ya existe un perfil con ese nombre.")
            cantidad = con.execute(
                "SELECT COUNT(*) AS n FROM child_profiles WHERE account_id=? AND active=1",
                (account_id,),
            ).fetchone()["n"]
            if cantidad >= MAX_CHILD_PROFILES:
                raise CuentaError(f"Una cuenta admite como máximo {MAX_CHILD_PROFILES} perfiles.")
            try:
                con.execute(
                    """INSERT INTO child_profiles(id,account_id,display_name,created_at,display_name_key)
                       VALUES (?,?,?,?,?)""",
                    (profile_id, account_id, display_name, now, display_name_key),
                )
            except sqlite3.IntegrityError as exc:
                raise CuentaError("Ya existe un perfil con ese nombre.") from exc
        return ChildProfile(profile_id, account_id, display_name, now)

    def listar_child_profiles(self, account_id: str) -> list[ChildProfile]:
        with self._conexion() as con:
            rows = con.execute(
                """SELECT id,account_id,display_name,created_at,active
                   FROM child_profiles WHERE account_id=? ORDER BY created_at,id""",
                (account_id,),
            ).fetchall()
        return [
            ChildProfile(r["id"], r["account_id"], r["display_name"], r["created_at"], bool(r["active"]))
            for r in rows
        ]

    def establecer_entitlement(self, account_id: str, product: str, active: bool, source: str) -> Entitlement:
        if not product.strip() or not source.strip():
            raise CuentaError("Producto y fuente son obligatorios.")
        now = _ahora()
        with self._conexion() as con:
            if not con.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone():
                raise CuentaError("La cuenta no existe.")
            con.execute(
                """INSERT INTO entitlements(account_id,product,active,source,updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(account_id,product) DO UPDATE SET
                     active=excluded.active, source=excluded.source, updated_at=excluded.updated_at""",
                (account_id, product.strip(), int(active), source.strip(), now),
            )
        return Entitlement(account_id, product.strip(), active, source.strip())

    def tiene_entitlement(self, account_id: str, product: str) -> bool:
        with self._conexion() as con:
            row = con.execute(
                "SELECT active FROM entitlements WHERE account_id=? AND product=?",
                (account_id, product),
            ).fetchone()
        return bool(row and row["active"])

    def tiene_entitlement_por_perfil(self, profile_id: str, product: str) -> bool:
        with self._conexion() as con:
            row = con.execute(
                """SELECT e.active
                   FROM child_profiles p
                   JOIN entitlements e ON e.account_id=p.account_id
                   WHERE p.id=? AND e.product=? AND p.active=1""",
                (profile_id, product),
            ).fetchone()
        return bool(row and row["active"])
