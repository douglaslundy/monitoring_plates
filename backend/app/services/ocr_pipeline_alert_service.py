from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from time import time
from typing import Any

from app.core.config import settings
from app.models.camera import Camera
from app.services.ocr_pipeline_health_service import build_ocr_pipeline_health
from app.services.ocr_pipeline_metrics_service import get_ocr_pipeline_metrics

logger = logging.getLogger(__name__)


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
    return f"camera-telemetry:{camera_id}:ocr-alert"


def maybe_publish_ocr_pipeline_alert(camera: Camera) -> bool:
    metrics = get_ocr_pipeline_metrics(str(camera.id))
    health = build_ocr_pipeline_health(metrics)

    if health.ocr_pipeline_status not in {"warning", "degraded"}:
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
        previous_status = str(previous.get("ocr_pipeline_status", ""))
        previous_updated_at = float(previous.get("updated_at", 0.0) or 0.0)
        if previous_status == health.ocr_pipeline_status and now - previous_updated_at < settings.OCR_PIPELINE_ALERT_COOLDOWN_SECONDS:
            return False

    payload = {
        "type": "ocr_pipeline_alert",
        "client_id": str(camera.client_id),
        "camera_id": str(camera.id),
        "camera_name": camera.name,
        "location": camera.location or "",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": now,
        "ocr_pipeline_status": health.ocr_pipeline_status,
        "ocr_pipeline_health_score": health.ocr_pipeline_health_score,
        "ocr_attempts": health.ocr_attempts,
        "ocr_success_rate": health.ocr_success_rate,
        "ocr_false_positive_rate": health.ocr_false_positive_rate,
        "avg_ocr_seconds": health.avg_ocr_seconds,
        "detail": health.ocr_pipeline_status_detail,
    }

    try:
        client.set(key, json.dumps(payload), ex=settings.OCR_PIPELINE_ALERT_COOLDOWN_SECONDS + 60)
        client.publish(f"ws:alerts:{camera.client_id}", json.dumps(payload))
    except Exception:
        logger.warning("Could not publish OCR pipeline alert", exc_info=True)
        return False

    return True
