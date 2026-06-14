from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.camera import Camera
from app.models.user import User, UserRole
from app.services.detector_health_service import build_detector_health
from app.services.image_quality_service import get_image_quality
from app.services.preview_telemetry_service import get_preview_telemetry


@dataclass(slots=True)
class OperationalMetrics:
    total_cameras: int
    online_cameras: int
    streaming_cameras: int
    degraded_cameras: int
    low_quality_cameras: int
    avg_preview_fps: float
    avg_preview_latency_seconds: float | None
    queue_depth: int
    operational_status: str
    operational_status_detail: str
    generated_at: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "total_cameras": self.total_cameras,
            "online_cameras": self.online_cameras,
            "streaming_cameras": self.streaming_cameras,
            "degraded_cameras": self.degraded_cameras,
            "low_quality_cameras": self.low_quality_cameras,
            "avg_preview_fps": self.avg_preview_fps,
            "avg_preview_latency_seconds": self.avg_preview_latency_seconds,
            "queue_depth": self.queue_depth,
            "operational_status": self.operational_status,
            "operational_status_detail": self.operational_status_detail,
            "generated_at": self.generated_at,
        }


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


def _camera_scope_query(db: Session, current_user: User) -> list[Camera]:
    query = db.query(Camera)
    if current_user.role != UserRole.super_admin:
        query = query.filter(Camera.client_id == current_user.client_id)
    return query.all()


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


def build_operational_metrics(db: Session, current_user: User) -> OperationalMetrics:
    cameras = _camera_scope_query(db, current_user)
    now = datetime.now(timezone.utc)

    if not cameras:
        return OperationalMetrics(
            total_cameras=0,
            online_cameras=0,
            streaming_cameras=0,
            degraded_cameras=0,
            low_quality_cameras=0,
            avg_preview_fps=0.0,
            avg_preview_latency_seconds=None,
            queue_depth=_queue_depth(),
            operational_status="empty",
            operational_status_detail="Nenhuma camera disponivel para analise.",
            generated_at=now,
        )

    online_cameras = 0
    streaming_cameras = 0
    degraded_cameras = 0
    low_quality_cameras = 0
    fps_values: list[float] = []
    latency_values: list[float] = []

    for camera in cameras:
        telemetry = get_preview_telemetry(str(camera.id), camera.is_online)
        quality = get_image_quality(str(camera.id))
        health = build_detector_health(camera.is_online, telemetry, quality)

        if camera.is_online:
            online_cameras += 1
        if telemetry.preview_status == "streaming":
            streaming_cameras += 1
        if health.detector_status == "degraded":
            degraded_cameras += 1
        if quality.quality_label in {"fair", "poor"}:
            low_quality_cameras += 1

        fps_values.append(telemetry.preview_fps)
        if telemetry.preview_latency_seconds is not None:
            latency_values.append(telemetry.preview_latency_seconds)

    queue_depth = _queue_depth()
    avg_preview_fps = round(mean(fps_values), 2) if fps_values else 0.0
    avg_preview_latency_seconds = round(mean(latency_values), 2) if latency_values else None

    operational_status = "healthy"
    operational_status_detail = "Operacao dentro do esperado."
    if online_cameras == 0:
        operational_status = "offline"
        operational_status_detail = "Nenhuma camera online."
    elif queue_depth >= settings.WORKER_DELAY_QUEUE_THRESHOLD or degraded_cameras > 0:
        operational_status = "degraded"
        operational_status_detail = "Existem cameras degradadas ou fila OCR acumulando."
    elif low_quality_cameras > 0 or (avg_preview_latency_seconds is not None and avg_preview_latency_seconds > 4.0):
        operational_status = "warning"
        operational_status_detail = "Algumas cameras estao com qualidade ou latencia abaixo do ideal."

    return OperationalMetrics(
        total_cameras=len(cameras),
        online_cameras=online_cameras,
        streaming_cameras=streaming_cameras,
        degraded_cameras=degraded_cameras,
        low_quality_cameras=low_quality_cameras,
        avg_preview_fps=avg_preview_fps,
        avg_preview_latency_seconds=avg_preview_latency_seconds,
        queue_depth=queue_depth,
        operational_status=operational_status,
        operational_status_detail=operational_status_detail,
        generated_at=now,
    )
