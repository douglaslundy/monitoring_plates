from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any

from app.services.ocr_pipeline_metrics_service import OcrPipelineMetrics

IDLE_THRESHOLD_SECONDS = 15 * 60
WARNING_SUCCESS_RATE = 0.60
DEGRADED_SUCCESS_RATE = 0.35
WARNING_AVG_OCR_SECONDS = 1.0
DEGRADED_AVG_OCR_SECONDS = 2.5
WARNING_FALSE_POSITIVE_RATE = 0.20
DEGRADED_FALSE_POSITIVE_RATE = 0.35


@dataclass(slots=True)
class OcrPipelineHealth:
    ocr_pipeline_status: str
    ocr_pipeline_health_score: float
    ocr_pipeline_status_detail: str
    ocr_attempts: int
    ocr_success_rate: float | None
    ocr_false_positive_rate: float | None
    avg_ocr_seconds: float | None
    last_attempt_at: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ocr_pipeline_status": self.ocr_pipeline_status,
            "ocr_pipeline_health_score": self.ocr_pipeline_health_score,
            "ocr_pipeline_status_detail": self.ocr_pipeline_status_detail,
            "ocr_attempts": self.ocr_attempts,
            "ocr_success_rate": self.ocr_success_rate,
            "ocr_false_positive_rate": self.ocr_false_positive_rate,
            "avg_ocr_seconds": self.avg_ocr_seconds,
            "last_attempt_at": self.last_attempt_at,
        }


def build_ocr_pipeline_health(metrics: OcrPipelineMetrics) -> OcrPipelineHealth:
    now = time()

    if metrics.ocr_attempts <= 0:
        return OcrPipelineHealth(
            ocr_pipeline_status="idle",
            ocr_pipeline_health_score=20.0,
            ocr_pipeline_status_detail="Ainda nao ha leituras suficientes para avaliar o OCR.",
            ocr_attempts=metrics.ocr_attempts,
            ocr_success_rate=None,
            ocr_false_positive_rate=None,
            avg_ocr_seconds=None,
            last_attempt_at=metrics.last_attempt_at,
        )

    is_stale = metrics.last_attempt_at is not None and now - metrics.last_attempt_at > IDLE_THRESHOLD_SECONDS
    success_rate = metrics.ocr_success_rate or 0.0
    false_positive_rate = metrics.ocr_false_positive_rate or 0.0
    avg_ocr_seconds = metrics.avg_ocr_seconds

    if is_stale:
        return OcrPipelineHealth(
            ocr_pipeline_status="degraded",
            ocr_pipeline_health_score=35.0,
            ocr_pipeline_status_detail="Nao houve leituras recentes do OCR para esta camera.",
            ocr_attempts=metrics.ocr_attempts,
            ocr_success_rate=metrics.ocr_success_rate,
            ocr_false_positive_rate=metrics.ocr_false_positive_rate,
            avg_ocr_seconds=avg_ocr_seconds,
            last_attempt_at=metrics.last_attempt_at,
        )

    if success_rate < DEGRADED_SUCCESS_RATE or (
        avg_ocr_seconds is not None and avg_ocr_seconds > DEGRADED_AVG_OCR_SECONDS
    ) or false_positive_rate >= DEGRADED_FALSE_POSITIVE_RATE:
        detail = "OCR em estado degradado para esta camera."
        if metrics.ocr_success_rate is not None:
            detail = f"Taxa de sucesso do OCR em {metrics.ocr_success_rate * 100:.0f}%."
        return OcrPipelineHealth(
            ocr_pipeline_status="degraded",
            ocr_pipeline_health_score=35.0,
            ocr_pipeline_status_detail=detail,
            ocr_attempts=metrics.ocr_attempts,
            ocr_success_rate=metrics.ocr_success_rate,
            ocr_false_positive_rate=metrics.ocr_false_positive_rate,
            avg_ocr_seconds=avg_ocr_seconds,
            last_attempt_at=metrics.last_attempt_at,
        )

    if success_rate < WARNING_SUCCESS_RATE or (
        avg_ocr_seconds is not None and avg_ocr_seconds > WARNING_AVG_OCR_SECONDS
    ) or false_positive_rate >= WARNING_FALSE_POSITIVE_RATE:
        detail = "OCR funcionando, mas ainda abaixo do ideal."
        if metrics.ocr_success_rate is not None:
            detail = f"Taxa de sucesso do OCR em {metrics.ocr_success_rate * 100:.0f}%."
        return OcrPipelineHealth(
            ocr_pipeline_status="warning",
            ocr_pipeline_health_score=65.0,
            ocr_pipeline_status_detail=detail,
            ocr_attempts=metrics.ocr_attempts,
            ocr_success_rate=metrics.ocr_success_rate,
            ocr_false_positive_rate=metrics.ocr_false_positive_rate,
            avg_ocr_seconds=avg_ocr_seconds,
            last_attempt_at=metrics.last_attempt_at,
        )

    return OcrPipelineHealth(
        ocr_pipeline_status="healthy",
        ocr_pipeline_health_score=100.0,
        ocr_pipeline_status_detail="Pipeline OCR operando normalmente.",
        ocr_attempts=metrics.ocr_attempts,
        ocr_success_rate=metrics.ocr_success_rate,
        ocr_false_positive_rate=metrics.ocr_false_positive_rate,
        avg_ocr_seconds=avg_ocr_seconds,
        last_attempt_at=metrics.last_attempt_at,
    )
