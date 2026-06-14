from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from time import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.camera import Camera

logger = logging.getLogger(__name__)


def _redis_client() -> Any | None:
    try:
        import redis
    except Exception:
        return None

    try:
        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        return None


def _alert_key() -> str:
    return "worker-delay:global"


def _queue_depth() -> int:
    client = _redis_client()
    if client is None:
        return 0

    for queue_name in ("frames", "celery"):
        try:
            depth = client.llen(queue_name)
            if depth:
                return int(depth)
        except Exception:
            continue
    return 0


def maybe_publish_worker_delay_alert(db: Session) -> bool:
    queue_depth = _queue_depth()
    if queue_depth < settings.WORKER_DELAY_QUEUE_THRESHOLD:
        return False

    client = _redis_client()
    if client is None:
        return False

    now = time()
    key = _alert_key()
    try:
        raw = client.get(key)
    except Exception:
        raw = None

    if raw:
        try:
            previous = json.loads(raw)
        except Exception:
            previous = {}
        previous_depth = int(previous.get("queue_depth", 0) or 0)
        previous_updated_at = float(previous.get("updated_at", 0.0) or 0.0)
        if previous_depth == queue_depth and now - previous_updated_at < settings.WORKER_DELAY_ALERT_COOLDOWN_SECONDS:
            return False

    camera_client_ids = [str(client_id) for (client_id,) in db.query(Camera.client_id).distinct().all() if client_id]
    if not camera_client_ids:
        return False

    payload = {
        "type": "worker_delay_alert",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": now,
        "queue_depth": queue_depth,
        "threshold": settings.WORKER_DELAY_QUEUE_THRESHOLD,
        "detail": f"Fila OCR com {queue_depth} frames aguardando.",
    }

    try:
        client.set(key, json.dumps(payload), ex=settings.WORKER_DELAY_ALERT_COOLDOWN_SECONDS + 60)
        for client_id in camera_client_ids:
            client.publish(f"ws:alerts:{client_id}", json.dumps(payload))
    except Exception:
        logger.warning("Could not publish worker delay alert", exc_info=True)
        return False

    return True
