from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from time import time
from typing import Any

from app.core.config import settings

WINDOW_SECONDS = 7 * 24 * 60 * 60


@dataclass(slots=True)
class OcrPipelineMetrics:
    capture_attempts: int
    capture_successes: int
    capture_failures: int
    ocr_attempts: int
    ocr_successes: int
    ocr_failures: int
    ocr_false_positives: int
    persistence_attempts: int
    avg_capture_seconds: float | None
    avg_ocr_seconds: float | None
    avg_persistence_seconds: float | None
    capture_success_rate: float | None
    ocr_success_rate: float | None
    ocr_false_positive_rate: float | None
    last_attempt_at: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "capture_attempts": self.capture_attempts,
            "capture_successes": self.capture_successes,
            "capture_failures": self.capture_failures,
            "ocr_attempts": self.ocr_attempts,
            "ocr_successes": self.ocr_successes,
            "ocr_failures": self.ocr_failures,
            "ocr_false_positives": self.ocr_false_positives,
            "persistence_attempts": self.persistence_attempts,
            "avg_capture_seconds": self.avg_capture_seconds,
            "avg_ocr_seconds": self.avg_ocr_seconds,
            "avg_persistence_seconds": self.avg_persistence_seconds,
            "capture_success_rate": self.capture_success_rate,
            "ocr_success_rate": self.ocr_success_rate,
            "ocr_false_positive_rate": self.ocr_false_positive_rate,
            "last_attempt_at": self.last_attempt_at,
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


def _metrics_key(camera_id: str) -> str:
    return f"camera-telemetry:{camera_id}:ocr-pipeline"


def record_ocr_pipeline_metrics(
    camera_id: str,
    *,
    capture_seconds: float | None = None,
    capture_success: bool | None = None,
    ocr_seconds: float | None = None,
    ocr_success: bool | None = None,
    false_positive: bool = False,
    persistence_seconds: float | None = None,
) -> None:
    client = _redis_client()
    if client is None:
        return

    now = time()
    key = _metrics_key(camera_id)

    try:
        pipeline = client.pipeline()
        if capture_seconds is not None:
            pipeline.hincrby(key, "capture_attempts", 1)
            pipeline.hincrbyfloat(key, "total_capture_seconds", float(capture_seconds))
            if capture_success:
                pipeline.hincrby(key, "capture_successes", 1)
            else:
                pipeline.hincrby(key, "capture_failures", 1)

        if ocr_seconds is not None:
            pipeline.hincrby(key, "ocr_attempts", 1)
            pipeline.hincrbyfloat(key, "total_ocr_seconds", float(ocr_seconds))
            if ocr_success:
                pipeline.hincrby(key, "ocr_successes", 1)
            else:
                pipeline.hincrby(key, "ocr_failures", 1)
            if false_positive:
                pipeline.hincrby(key, "ocr_false_positives", 1)

        if persistence_seconds is not None:
            pipeline.hincrby(key, "persistence_attempts", 1)
            pipeline.hincrbyfloat(key, "total_persistence_seconds", float(persistence_seconds))

        pipeline.hset(key, mapping={"last_attempt_at": now})
        pipeline.expire(key, WINDOW_SECONDS)
        pipeline.execute()
    except Exception:
        return


def get_ocr_pipeline_metrics(camera_id: str) -> OcrPipelineMetrics:
    client = _redis_client()
    if client is None:
        return OcrPipelineMetrics(
            capture_attempts=0,
            capture_successes=0,
            capture_failures=0,
            ocr_attempts=0,
            ocr_successes=0,
            ocr_failures=0,
            ocr_false_positives=0,
            persistence_attempts=0,
            avg_capture_seconds=None,
            avg_ocr_seconds=None,
            avg_persistence_seconds=None,
            capture_success_rate=None,
            ocr_success_rate=None,
            ocr_false_positive_rate=None,
            last_attempt_at=None,
        )

    key = _metrics_key(camera_id)
    try:
        raw = client.hgetall(key)
    except Exception:
        raw = {}

    def _int(name: str) -> int:
        try:
            return int(raw.get(name, 0) or 0)
        except Exception:
            return 0

    def _float(name: str) -> float:
        try:
            return float(raw.get(name, 0.0) or 0.0)
        except Exception:
            return 0.0

    capture_attempts = _int("capture_attempts")
    capture_successes = _int("capture_successes")
    capture_failures = _int("capture_failures")
    ocr_attempts = _int("ocr_attempts")
    ocr_successes = _int("ocr_successes")
    ocr_failures = _int("ocr_failures")
    ocr_false_positives = _int("ocr_false_positives")
    persistence_attempts = _int("persistence_attempts")

    total_capture_seconds = _float("total_capture_seconds")
    total_ocr_seconds = _float("total_ocr_seconds")
    total_persistence_seconds = _float("total_persistence_seconds")

    avg_capture_seconds = round(total_capture_seconds / capture_attempts, 3) if capture_attempts else None
    avg_ocr_seconds = round(total_ocr_seconds / ocr_attempts, 3) if ocr_attempts else None
    avg_persistence_seconds = round(total_persistence_seconds / persistence_attempts, 3) if persistence_attempts else None
    capture_success_rate = round(capture_successes / capture_attempts, 3) if capture_attempts else None
    ocr_success_rate = round(ocr_successes / ocr_attempts, 3) if ocr_attempts else None
    ocr_false_positive_rate = round(ocr_false_positives / ocr_attempts, 3) if ocr_attempts else None

    try:
        last_attempt_at = float(raw.get("last_attempt_at")) if raw.get("last_attempt_at") else None
    except Exception:
        last_attempt_at = None

    return OcrPipelineMetrics(
        capture_attempts=capture_attempts,
        capture_successes=capture_successes,
        capture_failures=capture_failures,
        ocr_attempts=ocr_attempts,
        ocr_successes=ocr_successes,
        ocr_failures=ocr_failures,
        ocr_false_positives=ocr_false_positives,
        persistence_attempts=persistence_attempts,
        avg_capture_seconds=avg_capture_seconds,
        avg_ocr_seconds=avg_ocr_seconds,
        avg_persistence_seconds=avg_persistence_seconds,
        capture_success_rate=capture_success_rate,
        ocr_success_rate=ocr_success_rate,
        ocr_false_positive_rate=ocr_false_positive_rate,
        last_attempt_at=last_attempt_at,
    )
