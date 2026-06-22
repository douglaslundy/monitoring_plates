"""Backend de rastreamento selecionável pelo admin (legacy | bytetrack).

Guardado numa chave do Redis para todos os processos (worker/capture) lerem; o
admin troca via API sem rebuild. Sem Redis ou valor inválido, cai no padrão
(`TRACKER_BACKEND_DEFAULT`). Mesmo padrão do `detector_model_service`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import settings

_REDIS_KEY = "tracker:backend"
VALID_BACKENDS = ("legacy", "bytetrack")


@lru_cache(maxsize=1)
def _client() -> Any | None:
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


def default_backend() -> str:
    backend = settings.TRACKER_BACKEND_DEFAULT
    return backend if backend in VALID_BACKENDS else "legacy"


def get_backend() -> str:
    """Backend escolhido (Redis) ou o padrão."""
    client = _client()
    if client is not None:
        try:
            value = client.get(_REDIS_KEY)
            if value in VALID_BACKENDS:
                return value
        except Exception:
            pass
    return default_backend()


def set_backend(name: str) -> bool:
    """Persiste o backend escolhido. Retorna False se inválido/indisponível."""
    if name not in VALID_BACKENDS:
        return False
    client = _client()
    if client is None:
        return False
    try:
        client.set(_REDIS_KEY, name)
        return True
    except Exception:
        return False
