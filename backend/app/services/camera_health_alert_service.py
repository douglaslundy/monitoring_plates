from __future__ import annotations

import json
import logging
from functools import lru_cache
from datetime import datetime, timezone
from time import time
from typing import Any

from app.core.config import settings
from app.models.camera import Camera
from app.services.detector_health_service import build_detector_health
from app.services.image_quality_service import get_image_quality
from app.services.preview_telemetry_service import get_preview_telemetry

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = 300


@lru_cache(maxsize=1)
def _redis_client() -> Any | None:
    try:
        import redis
    except Exception:
        return None

    try:
        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


def _alert_key(camera_id: str) -> str:
    return f"camera-telemetry:{camera_id}:health-alert"


def maybe_publish_camera_health_alert(camera: Camera) -> bool:
    preview = get_preview_telemetry(str(camera.id), camera.is_online)
    quality = get_image_quality(str(camera.id))
    health = build_detector_health(camera.is_online, preview, quality)

    if health.detector_status not in {"warning", "degraded"}:
        return False

    client = _redis_client()
    if client is None:
        return False

    now = time()
    key = _alert_key(str(camera.id))
    try:
        raw = client.get(key)
    except Exception:
        raw = None

    if raw:
        try:
            previous = json.loads(raw)
        except Exception:
            previous = {}
        previous_status = str(previous.get("detector_status", ""))
        previous_updated_at = float(previous.get("updated_at", 0.0) or 0.0)
        if previous_status == health.detector_status and now - previous_updated_at < ALERT_COOLDOWN_SECONDS:
            return False

    payload = {
        "type": "camera_health_alert",
        "client_id": str(camera.client_id),
        "camera_id": str(camera.id),
        "camera_name": camera.name,
        "location": camera.location or "",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": now,
        "detector_status": health.detector_status,
        "detector_health_score": health.detector_health_score,
        "preview_status": preview.preview_status,
        "quality_label": quality.quality_label,
        "detail": health.detector_status_detail,
    }

    try:
        client.set(key, json.dumps(payload), ex=ALERT_COOLDOWN_SECONDS + 60)
        client.publish(f"ws:alerts:{camera.client_id}", json.dumps(payload))
    except Exception:
        logger.warning("Could not publish camera health alert", exc_info=True)
        return False

    return True
