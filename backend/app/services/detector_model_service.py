"""Seleção do modelo YOLO usado pelo detector (configurável pelo admin) (T A).

Os modelos disponíveis são os `.onnx` presentes em MODELS_DIR (gerados no build:
yolov8n/s/m...). O modelo escolhido fica numa chave do Redis para todos os
processos (worker/capture) lerem; o admin altera via API. Sem Redis ou sem a
chave, cai no modelo padrão (o mais preciso disponível).
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from app.core.config import settings

_REDIS_KEY = "detector:model"
# Ordem de preferência para o padrão (mais preciso primeiro entre os comuns na CPU).
_DEFAULT_PREFERENCE = ("yolov8m", "yolov8s", "yolov8n")


def _models_dir() -> str:
    return os.getenv("MODELS_DIR", "/app/models")


def available_models() -> list[str]:
    """Modelos disponíveis = arquivos .onnx em MODELS_DIR (sem extensão)."""
    try:
        return sorted(f[:-5] for f in os.listdir(_models_dir()) if f.endswith(".onnx"))
    except Exception:
        return []


def model_path(name: str) -> str:
    return os.path.join(_models_dir(), f"{name}.onnx")


def default_model() -> str:
    """Padrão: o mais preciso disponível (preferência), senão o do env, senão o 1º."""
    avail = available_models()
    for name in _DEFAULT_PREFERENCE:
        if name in avail:
            return name
    env = os.getenv("VEHICLE_MODEL_PATH")
    if env:
        return os.path.splitext(os.path.basename(env))[0]
    return avail[0] if avail else "yolov8s"


@lru_cache(maxsize=1)
def _client() -> Any | None:
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


def get_selected_model() -> str:
    """Modelo escolhido (Redis) ou o padrão. Garante que o arquivo exista."""
    avail = available_models()
    client = _client()
    if client is not None:
        try:
            value = client.get(_REDIS_KEY)
            if value and (not avail or value in avail):
                return value
        except Exception:
            pass
    return default_model()


def set_selected_model(name: str) -> bool:
    """Persiste o modelo escolhido no Redis. Retorna False se indisponível/inválido."""
    if name not in available_models():
        return False
    client = _client()
    if client is None:
        return False
    try:
        client.set(_REDIS_KEY, name)
        return True
    except Exception:
        return False
