"""Rate limiting mínimo para endpoints sensibles durante la transición web.
El limitador en memoria es process-local. Para varios workers en una misma máquina puede
optarse por SQLite compartido mediante ACCOUNT_RATE_LIMIT_DB; entre hosts se requiere un
almacén distribuido.
"""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from collections import defaultdict, deque
from math import ceil
from pathlib import Path
from threading import Lock
from time import monotonic, time


class RateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._windows = {}
        self._calls = 0
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            self._calls += 1
            # Los keys de login incluyen email e IP; sin limpieza, intentos con
            # identificadores únicos dejan colas vacías/expiradas para siempre.
            if self._calls % 128 == 0:
                for stored_key, stored_events in list(self._events.items()):
                    stored_cutoff = now - self._windows.get(stored_key, window_seconds)
                    while stored_events and stored_events[0] <= stored_cutoff:
                        stored_events.popleft()
                    if not stored_events:
                        self._events.pop(stored_key, None)
                        self._windows.pop(stored_key, None)
            events = self._events[key]
            self._windows[key] = window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now))
                return False, retry_after
            events.append(now)
            return True, 0



class SQLiteRateLimiter:
    """Limitador compartido entre workers que usan el mismo archivo SQLite.

    Se usa solo cuando la app configura ACCOUNT_RATE_LIMIT_DB explícitamente.
    Los identificadores se guardan como SHA-256, no como IP/correo en claro.
    BEGIN IMMEDIATE serializa la comprobación y el alta para evitar que dos
    workers concedan simultáneamente el último intento disponible.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._calls = 0
        self._ensure_schema()

    def _conexion(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.execute("PRAGMA busy_timeout = 5000")
        return con

    def _ensure_schema(self):
        with closing(self._conexion()) as con:
            with con:
                con.execute(
                    """CREATE TABLE IF NOT EXISTS rate_limit_events (
                        bucket TEXT NOT NULL,
                        occurred_at REAL NOT NULL
                    )"""
                )
                con.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket_time "
                    "ON rate_limit_events(bucket, occurred_at)"
                )

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit y window_seconds deben ser positivos")
        now = time()
        cutoff = now - window_seconds
        bucket = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with closing(self._conexion()) as con:
            with con:
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    "DELETE FROM rate_limit_events WHERE bucket=? AND occurred_at<=?",
                    (bucket, cutoff),
                )
                self._calls += 1
                if self._calls % 256 == 0:
                    con.execute(
                        "DELETE FROM rate_limit_events WHERE occurred_at<=?",
                        (now - 86400,),
                    )
                rows = con.execute(
                    "SELECT occurred_at FROM rate_limit_events "
                    "WHERE bucket=? AND occurred_at>? ORDER BY occurred_at",
                    (bucket, cutoff),
                ).fetchall()
                if len(rows) >= limit:
                    return False, max(1, ceil(rows[0][0] + window_seconds - now))
                con.execute(
                    "INSERT INTO rate_limit_events(bucket, occurred_at) VALUES (?, ?)",
                    (bucket, now),
                )
                return True, 0
