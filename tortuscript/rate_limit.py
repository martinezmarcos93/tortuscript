"""Rate limiting mínimo para endpoints sensibles durante la transición web.
La implementación es deliberadamente process-local; en producción debe sustituirse por
un almacén compartido antes de escalar a múltiples workers.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


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
