"""Integração com o go2rtc para live em tempo real (WebRTC).

O go2rtc mantém UMA conexão RTSP por câmera e a multiplexa para o ANPR e para
os operadores via WebRTC (vídeo de baixa latência, usando o H.264 da câmera —
o FastAPI sai do caminho do vídeo). Aqui registramos/removemos câmeras no go2rtc
pela REST API dele.

Cada câmera vira um stream nomeado pelo seu UUID. O navegador acessa
`GO2RTC_PUBLIC_URL/stream.html?src=<camera_id>`.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 5


def _api_base() -> str:
    return settings.GO2RTC_URL.rstrip("/")


def stream_name(camera_id: str) -> str:
    return str(camera_id)


def public_stream_url(camera_id: str) -> str:
    """URL do player WebRTC do go2rtc para o navegador do operador."""
    base = settings.GO2RTC_PUBLIC_URL.rstrip("/")
    return f"{base}/stream.html?src={stream_name(camera_id)}"


def register_stream(camera_id: str, rtsp_url: str) -> bool:
    """Cadastra/atualiza um stream RTSP no go2rtc (idempotente)."""
    if not settings.GO2RTC_ENABLED or not rtsp_url:
        return False
    try:
        import requests

        resp = requests.put(
            f"{_api_base()}/api/streams",
            params={"name": stream_name(camera_id), "src": rtsp_url},
            timeout=_TIMEOUT,
        )
        ok = resp.status_code < 400
        if not ok:
            logger.warning("go2rtc register %s -> HTTP %s", camera_id, resp.status_code)
        return ok
    except Exception as exc:
        logger.warning("go2rtc indisponível ao registrar %s: %s", camera_id, exc)
        return False


def remove_stream(camera_id: str) -> bool:
    if not settings.GO2RTC_ENABLED:
        return False
    try:
        import requests

        resp = requests.delete(
            f"{_api_base()}/api/streams",
            params={"src": stream_name(camera_id)},
            timeout=_TIMEOUT,
        )
        return resp.status_code < 400
    except Exception as exc:
        logger.debug("go2rtc indisponível ao remover %s: %s", camera_id, exc)
        return False


def sync_streams(db) -> int:
    """Registra no go2rtc todas as câmeras RTSP ativas. Retorna quantas."""
    if not settings.GO2RTC_ENABLED:
        return 0
    from app.models.camera import Camera, ConnectionType

    cameras = (
        db.query(Camera)
        .filter(
            Camera.connection_type == ConnectionType.rtsp,
            Camera.is_active == True,  # noqa: E712
            Camera.rtsp_url.isnot(None),
        )
        .all()
    )
    count = 0
    for camera in cameras:
        if register_stream(str(camera.id), camera.rtsp_url):
            count += 1
    logger.info("go2rtc: %s/%s streams sincronizados", count, len(cameras))
    return count
