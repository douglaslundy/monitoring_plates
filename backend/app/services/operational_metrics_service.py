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
from app.services.ocr_pipeline_health_service import build_ocr_pipeline_health
from app.services.ocr_pipeline_metrics_service import get_ocr_pipeline_metrics
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
    avg_capture_seconds: float | None
    avg_ocr_seconds: float | None
    avg_persistence_seconds: float | None
    avg_ocr_success_rate: float | None
    avg_ocr_false_positive_rate: float | None
    ocr_pipeline_healthy_cameras: int
    ocr_pipeline_warning_cameras: int
    ocr_pipeline_degraded_cameras: int
    ocr_pipeline_idle_cameras: int
    ocr_pipeline_status: str
    ocr_pipeline_status_detail: str
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
            "avg_capture_seconds": self.avg_capture_seconds,
            "avg_ocr_seconds": self.avg_ocr_seconds,
            "avg_persistence_seconds": self.avg_persistence_seconds,
            "avg_ocr_success_rate": self.avg_ocr_success_rate,
            "avg_ocr_false_positive_rate": self.avg_ocr_false_positive_rate,
            "ocr_pipeline_healthy_cameras": self.ocr_pipeline_healthy_cameras,
            "ocr_pipeline_warning_cameras": self.ocr_pipeline_warning_cameras,
            "ocr_pipeline_degraded_cameras": self.ocr_pipeline_degraded_cameras,
            "ocr_pipeline_idle_cameras": self.ocr_pipeline_idle_cameras,
            "ocr_pipeline_status": self.ocr_pipeline_status,
            "ocr_pipeline_status_detail": self.ocr_pipeline_status_detail,
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


def _format_ratio(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value * 100:.0f}%"


def _sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _build_operational_detail(
    *,
    online_cameras: int,
    degraded_cameras: int,
    low_quality_cameras: int,
    queue_depth: int,
    avg_preview_latency_seconds: float | None,
    avg_ocr_success_rate: float | None,
) -> str:
    if online_cameras == 0:
        return "Nenhuma camera online."

    reasons: list[str] = []
    if degraded_cameras > 0:
        reasons.append(f"{degraded_cameras} camera(s) com detector degradado")
    if queue_depth >= settings.WORKER_DELAY_QUEUE_THRESHOLD:
        reasons.append(
            f"fila OCR em {queue_depth} frames (limite {settings.WORKER_DELAY_QUEUE_THRESHOLD})"
        )
    if avg_ocr_success_rate is not None and avg_ocr_success_rate < 0.35:
        ratio = _format_ratio(avg_ocr_success_rate)
        if ratio:
            reasons.append(f"taxa de sucesso do OCR em {ratio}")
    if low_quality_cameras > 0:
        reasons.append(f"{low_quality_cameras} camera(s) com baixa qualidade")
    if avg_preview_latency_seconds is not None and avg_preview_latency_seconds > 4.0:
        reasons.append(f"latencia media do preview em {avg_preview_latency_seconds:.1f}s")

    if reasons:
        return _sentence_case("; ".join(reasons)) + "."

    if avg_ocr_success_rate is not None and avg_ocr_success_rate < 0.6:
        ratio = _format_ratio(avg_ocr_success_rate)
        if ratio:
            return f"Taxa de sucesso do OCR abaixo do ideal ({ratio})."
    if low_quality_cameras > 0 or (
        avg_preview_latency_seconds is not None and avg_preview_latency_seconds > 4.0
    ):
        return "Algumas cameras estao com qualidade ou latencia abaixo do ideal."
    return "Operacao dentro do esperado."


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
            avg_capture_seconds=None,
            avg_ocr_seconds=None,
            avg_persistence_seconds=None,
            avg_ocr_success_rate=None,
            avg_ocr_false_positive_rate=None,
            ocr_pipeline_healthy_cameras=0,
            ocr_pipeline_warning_cameras=0,
            ocr_pipeline_degraded_cameras=0,
            ocr_pipeline_idle_cameras=0,
            ocr_pipeline_status="empty",
            ocr_pipeline_status_detail="Nenhuma camera disponivel para avaliacao do OCR.",
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
    capture_attempts_total = 0
    ocr_attempts_total = 0
    ocr_successes_total = 0
    ocr_false_positives_total = 0
    persistence_attempts_total = 0
    total_capture_seconds = 0.0
    total_ocr_seconds = 0.0
    total_persistence_seconds = 0.0
    ocr_pipeline_healthy_cameras = 0
    ocr_pipeline_warning_cameras = 0
    ocr_pipeline_degraded_cameras = 0
    ocr_pipeline_idle_cameras = 0

    for camera in cameras:
        telemetry = get_preview_telemetry(str(camera.id), camera.is_online)
        quality = get_image_quality(str(camera.id))
        ocr_metrics = get_ocr_pipeline_metrics(str(camera.id))
        ocr_health = build_ocr_pipeline_health(ocr_metrics)
        health = build_detector_health(camera.is_online, telemetry, quality)

        if camera.is_online:
            online_cameras += 1
        if camera.is_online and telemetry.preview_status == "streaming":
            streaming_cameras += 1
        if health.detector_status == "degraded":
            degraded_cameras += 1
        if quality.quality_label in {"fair", "poor"}:
            low_quality_cameras += 1
        if ocr_health.ocr_pipeline_status == "healthy":
            ocr_pipeline_healthy_cameras += 1
        elif ocr_health.ocr_pipeline_status == "warning":
            ocr_pipeline_warning_cameras += 1
        elif ocr_health.ocr_pipeline_status == "degraded":
            ocr_pipeline_degraded_cameras += 1
        else:
            ocr_pipeline_idle_cameras += 1

        fps_values.append(telemetry.preview_fps)
        if telemetry.preview_latency_seconds is not None:
            latency_values.append(telemetry.preview_latency_seconds)
        capture_attempts_total += ocr_metrics.capture_attempts
        ocr_attempts_total += ocr_metrics.ocr_attempts
        ocr_successes_total += ocr_metrics.ocr_successes
        ocr_false_positives_total += ocr_metrics.ocr_false_positives
        persistence_attempts_total += ocr_metrics.persistence_attempts

        total_capture_seconds += ocr_metrics.avg_capture_seconds * ocr_metrics.capture_attempts if ocr_metrics.avg_capture_seconds is not None else 0.0
        total_ocr_seconds += ocr_metrics.avg_ocr_seconds * ocr_metrics.ocr_attempts if ocr_metrics.avg_ocr_seconds is not None else 0.0
        total_persistence_seconds += (
            ocr_metrics.avg_persistence_seconds * ocr_metrics.persistence_attempts
            if ocr_metrics.avg_persistence_seconds is not None
            else 0.0
        )

    queue_depth = _queue_depth()
    avg_preview_fps = round(mean(fps_values), 2) if fps_values else 0.0
    avg_preview_latency_seconds = round(mean(latency_values), 2) if latency_values else None
    avg_capture_seconds = round(total_capture_seconds / capture_attempts_total, 3) if capture_attempts_total else None
    avg_ocr_seconds = round(total_ocr_seconds / ocr_attempts_total, 3) if ocr_attempts_total else None
    avg_persistence_seconds = (
        round(total_persistence_seconds / persistence_attempts_total, 3) if persistence_attempts_total else None
    )
    avg_ocr_success_rate = round(ocr_successes_total / ocr_attempts_total, 3) if ocr_attempts_total else None
    avg_ocr_false_positive_rate = (
        round(ocr_false_positives_total / ocr_attempts_total, 3) if ocr_attempts_total else None
    )

    ocr_pipeline_status = "healthy"
    ocr_pipeline_status_detail = "Pipeline OCR sem alertas."
    if ocr_pipeline_degraded_cameras > 0:
        ocr_pipeline_status = "degraded"
        ocr_pipeline_status_detail = "Ha cameras com OCR degradado."
    elif ocr_pipeline_warning_cameras > 0:
        ocr_pipeline_status = "warning"
        ocr_pipeline_status_detail = "Ha cameras com OCR em atencao."
    elif ocr_pipeline_idle_cameras == len(cameras):
        ocr_pipeline_status = "idle"
        ocr_pipeline_status_detail = "Ainda nao ha leituras suficientes do OCR."

    operational_status = "healthy"
    operational_status_detail = "Operacao dentro do esperado."
    if online_cameras == 0:
        operational_status = "offline"
        operational_status_detail = "Nenhuma camera online."
    elif queue_depth >= settings.WORKER_DELAY_QUEUE_THRESHOLD or degraded_cameras > 0:
        operational_status = "degraded"
        operational_status_detail = _build_operational_detail(
            online_cameras=online_cameras,
            degraded_cameras=degraded_cameras,
            low_quality_cameras=low_quality_cameras,
            queue_depth=queue_depth,
            avg_preview_latency_seconds=avg_preview_latency_seconds,
            avg_ocr_success_rate=avg_ocr_success_rate,
        )
    elif avg_ocr_success_rate is not None and avg_ocr_success_rate < 0.35:
        operational_status = "degraded"
        operational_status_detail = _build_operational_detail(
            online_cameras=online_cameras,
            degraded_cameras=degraded_cameras,
            low_quality_cameras=low_quality_cameras,
            queue_depth=queue_depth,
            avg_preview_latency_seconds=avg_preview_latency_seconds,
            avg_ocr_success_rate=avg_ocr_success_rate,
        )
    elif avg_ocr_success_rate is not None and avg_ocr_success_rate < 0.6:
        operational_status = "warning"
        ratio = _format_ratio(avg_ocr_success_rate)
        operational_status_detail = (
            f"Taxa de sucesso do OCR abaixo do ideal ({ratio})."
            if ratio
            else "A taxa de sucesso do OCR precisa de ajuste."
        )
    elif low_quality_cameras > 0 or (avg_preview_latency_seconds is not None and avg_preview_latency_seconds > 4.0):
        operational_status = "warning"
        details: list[str] = []
        if low_quality_cameras > 0:
            details.append(f"{low_quality_cameras} camera(s) com baixa qualidade")
        if avg_preview_latency_seconds is not None and avg_preview_latency_seconds > 4.0:
            details.append(f"latencia media do preview em {avg_preview_latency_seconds:.1f}s")
        operational_status_detail = (
            _sentence_case("; ".join(details)) + "." if details else "Algumas cameras estao com qualidade ou latencia abaixo do ideal."
        )

    return OperationalMetrics(
        total_cameras=len(cameras),
        online_cameras=online_cameras,
        streaming_cameras=streaming_cameras,
        degraded_cameras=degraded_cameras,
        low_quality_cameras=low_quality_cameras,
        avg_preview_fps=avg_preview_fps,
        avg_preview_latency_seconds=avg_preview_latency_seconds,
        avg_capture_seconds=avg_capture_seconds,
        avg_ocr_seconds=avg_ocr_seconds,
        avg_persistence_seconds=avg_persistence_seconds,
        avg_ocr_success_rate=avg_ocr_success_rate,
        avg_ocr_false_positive_rate=avg_ocr_false_positive_rate,
        ocr_pipeline_healthy_cameras=ocr_pipeline_healthy_cameras,
        ocr_pipeline_warning_cameras=ocr_pipeline_warning_cameras,
        ocr_pipeline_degraded_cameras=ocr_pipeline_degraded_cameras,
        ocr_pipeline_idle_cameras=ocr_pipeline_idle_cameras,
        ocr_pipeline_status=ocr_pipeline_status,
        ocr_pipeline_status_detail=ocr_pipeline_status_detail,
        queue_depth=queue_depth,
        operational_status=operational_status,
        operational_status_detail=operational_status_detail,
        generated_at=now,
    )
