"""Server-side session primitives for adult accounts."""
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

SESSION_HOURS = 12
VERIFICATION_HOURS = 24
RECOVERY_HOURS = 1


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat(timespec="seconds")


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthError(ValueError):
    pass


class AuthRepository:
    def __init__(self, path):
        self.path = Path(path)

    def _db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def ensure_schema(self):
        with self._db() as db:
            cols = {row["name"] for row in db.execute("PRAGMA table_info(accounts)")}
            if "password_hash" not in cols:
                db.execute("ALTER TABLE accounts ADD COLUMN password_hash TEXT")
            if "verified_at" not in cols:
                db.execute("ALTER TABLE accounts ADD COLUMN verified_at TEXT")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id_hash TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    active_profile_id TEXT REFERENCES child_profiles(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);

                CREATE TABLE IF NOT EXISTS account_tokens (
                    token_hash TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK (kind IN ('verification', 'recovery')),
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_account_tokens_account_kind
                    ON account_tokens(account_id, kind);
            """)
            session_cols = {row["name"] for row in db.execute("PRAGMA table_info(sessions)")}
            if "active_profile_id" not in session_cols:
                db.execute("ALTER TABLE sessions ADD COLUMN active_profile_id TEXT REFERENCES child_profiles(id) ON DELETE SET NULL")


    def create_verification_token(self, account_id):
        return self._create_account_token(account_id, "verification", VERIFICATION_HOURS)

    def verify_email_token(self, raw_token):
        account_id = self._consume_account_token(raw_token, "verification")
        self.marcar_verificada(account_id)
        return account_id

    def create_verification_token_for_email(self, email):
        """Crea token solo para cuentas existentes aún no verificadas.

        Devuelve None tanto para correos desconocidos como verificados para que
        la ruta HTTP pueda responder de forma indistinguible.
        """
        email = (email or "").strip().lower()
        if not email:
            return None
        with self._db() as db:
            row = db.execute(
                "SELECT id,verified_at FROM accounts WHERE email=?", (email,)
            ).fetchone()
        if not row or row["verified_at"]:
            return None
        return self.create_verification_token(row["id"])

    def create_recovery_token(self, email):
        email = (email or "").strip().lower()
        with self._db() as db:
            row = db.execute("SELECT id FROM accounts WHERE email=?", (email,)).fetchone()
        if not row:
            return None
        return self._create_account_token(row["id"], "recovery", RECOVERY_HOURS)

    def reset_password(self, raw_token, new_password):
        # Validar antes de consumir el token: un error de política no debe
        # inutilizar un enlace de recuperación todavía válido.
        self.validar_password(new_password)
        account_id = self._consume_account_token(raw_token, "recovery")
        self.set_password(account_id, new_password)
        with self._db() as db:
            db.execute("UPDATE sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                       (_iso(_now()), account_id))
        return account_id

    def _create_account_token(self, account_id, kind, hours):
        raw = secrets.token_urlsafe(32)
        now = _now()
        expires = now + timedelta(hours=hours)
        with self._db() as db:
            if not db.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone():
                raise AuthError("La cuenta no existe.")
            db.execute("UPDATE account_tokens SET consumed_at=? WHERE account_id=? AND kind=? AND consumed_at IS NULL",
                       (_iso(now), account_id, kind))
            db.execute(
                "INSERT INTO account_tokens(token_hash,account_id,kind,created_at,expires_at) VALUES (?,?,?,?,?)",
                (_digest(raw), account_id, kind, _iso(now), _iso(expires)),
            )
        return raw, expires

    def _consume_account_token(self, raw_token, kind):
        if not raw_token:
            raise AuthError("El enlace no es válido.")
        now = _now()
        with self._db() as db:
            row = db.execute(
                "SELECT account_id,expires_at,consumed_at FROM account_tokens WHERE token_hash=? AND kind=?",
                (_digest(raw_token), kind),
            ).fetchone()
            if not row or row["consumed_at"] or datetime.fromisoformat(row["expires_at"]) <= now:
                raise AuthError("El enlace no es válido o ya expiró.")
            db.execute(
                "UPDATE account_tokens SET consumed_at=? WHERE token_hash=? AND consumed_at IS NULL",
                (_iso(now), _digest(raw_token)),
            )
            if db.total_changes != 1:
                raise AuthError("El enlace no es válido o ya fue utilizado.")
            return row["account_id"]

    def marcar_verificada(self, account_id):
        with self._db() as db:
            row = db.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not row:
                raise AuthError("La cuenta no existe.")
            db.execute(
                "UPDATE accounts SET verified_at=? WHERE id=?",
                (_iso(_now()), account_id),
            )

    @staticmethod
    def validar_password(password):
        if not isinstance(password, str) or len(password) < 12:
            raise AuthError("La contraseña debe tener al menos 12 caracteres.")

    def set_password(self, account_id, password):
        self.validar_password(password)
        encoded = generate_password_hash(password, method="scrypt")
        with self._db() as db:
            db.execute("UPDATE accounts SET password_hash=? WHERE id=?", (encoded, account_id))

    def verify_password(self, email, password):
        email = (email or "").strip().lower()
        with self._db() as db:
            row = db.execute(
                "SELECT id,email,password_hash,verified_at,role FROM accounts WHERE email=?",
                (email,),
            ).fetchone()
        if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], password or ""):
            raise AuthError("Correo o contraseña incorrectos.")
        if not row["verified_at"]:
            raise AuthError("La cuenta todavía no verificó su correo.")
        return row

    def create_session(self, account_id):
        session = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _now()
        expires = now + timedelta(hours=SESSION_HOURS)
        with self._db() as db:
            db.execute(
                "INSERT INTO sessions(id_hash,account_id,csrf_hash,created_at,expires_at,revoked_at,active_profile_id) VALUES (?,?,?,?,?,NULL,NULL)",
                (_digest(session), account_id, _digest(csrf), _iso(now), _iso(expires)),
            )
        return session, csrf, expires

    def get_session(self, session):
        if not session:
            return None
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM sessions WHERE id_hash=?",
                (_digest(session),),
            ).fetchone()
        if not row or row["revoked_at"]:
            return None
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
        except (TypeError, ValueError):
            return None
        if expires_at <= _now():
            return None
        return row

    def csrf_ok(self, session, csrf):
        row = self.get_session(session)
        return bool(row and csrf and hmac.compare_digest(row["csrf_hash"], _digest(csrf)))

    def select_profile(self, session, profile_id):
        if not session or not profile_id:
            raise AuthError("Sesión y perfil son obligatorios.")
        session_row = self.get_session(session)
        if not session_row:
            raise AuthError("La sesión no es válida o ya expiró.")
        with self._db() as db:
            row = db.execute(
                """SELECT id FROM child_profiles
                   WHERE id=? AND account_id=? AND active=1""",
                (profile_id, session_row["account_id"]),
            ).fetchone()
            if not row:
                raise AuthError("El perfil no pertenece a la cuenta o no está activo.")
            db.execute("UPDATE sessions SET active_profile_id=? WHERE id_hash=?",
                       (profile_id, _digest(session)))

    def clear_profile(self, session):
        if not session:
            return
        with self._db() as db:
            db.execute("UPDATE sessions SET active_profile_id=NULL WHERE id_hash=?",
                       (_digest(session),))
    def revoke(self, session):
        if not session:
            return
        with self._db() as db:
            db.execute(
                "UPDATE sessions SET revoked_at=? WHERE id_hash=?",
                (_iso(_now()), _digest(session)),
            )

    def revoke_all(self, account_id):
        """Revoca todas las sesiones activas de una cuenta."""
        if not account_id:
            return
        with self._db() as db:
            db.execute(
                "UPDATE sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL",
                (_iso(_now()), account_id),
            )
