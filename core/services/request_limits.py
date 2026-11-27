"""Limitadores para rutas públicas costosas.

Usa Django cache cuando está configurado; con un backend compartido (Redis,
Memcached) el límite aplica entre workers/instancias. Con el
backend por defecto (locmem) el estado es por proceso.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int = 1):
        super().__init__("Demasiadas peticiones.")
        self.retry_after = max(1, int(retry_after))


def _client_key(prefix: str, request) -> str:
    # REMOTE_ADDR lo fija el servidor; X-Forwarded-For es controlable por el cliente.
    return prefix + (request.META.get("REMOTE_ADDR") or "unknown")


def _window_key(key: str) -> str:
    return f"rl:w:{key}"


def _block_key(key: str) -> str:
    return f"rl:b:{key}"


def _check(key: str, limit: int, window: float, max_keys: int) -> None:
    del max_keys  # la poda la gestiona el backend de cache
    now = time.time()
    blocked_until = cache.get(_block_key(key))
    if blocked_until:
        remaining = float(blocked_until) - now
        if remaining > 0:
            raise RateLimitExceeded(int(remaining) + 1)

    timeout = max(1, int(window) + 1)
    wk = _window_key(key)
    if cache.add(wk, 1, timeout=timeout):
        return
    try:
        count = cache.incr(wk)
    except ValueError:
        # Si expiró entre add e incr, no sobrescribir el contador de otro worker.
        if cache.add(wk, 1, timeout=timeout):
            return
        raise RateLimitExceeded(timeout)
    if int(count) > int(limit):
        raise RateLimitExceeded(timeout)


def _block(key: str, seconds: int | None, maximum: int, max_keys: int) -> None:
    del max_keys
    delay = min(max(1, int(seconds or 1)), int(maximum))
    cache.set(_block_key(key), time.time() + delay, timeout=delay + 1)


def check_tracker(request) -> None:
    _check(
        _client_key("tracker:", request),
        settings.TRACKER_RATE_LIMIT,
        settings.TRACKER_RATE_WINDOW,
        settings.TRACKER_RATE_MAX_KEYS,
    )


def block_tracker(request, retry_after: int | None) -> None:
    _block(
        _client_key("tracker:", request),
        retry_after,
        settings.TRACKER_BACKOFF_MAX,
        settings.TRACKER_RATE_MAX_KEYS,
    )


def check_notes_login(request) -> None:
    _check(
        _client_key("notes:", request),
        settings.NOTES_LOGIN_RATE_LIMIT,
        settings.NOTES_LOGIN_RATE_WINDOW,
        settings.TRACKER_RATE_MAX_KEYS,
    )


def reset_limits() -> None:
    cache.clear()
