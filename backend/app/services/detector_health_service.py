from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.image_quality_service import ImageQuality
from app.services.preview_telemetry_service import PreviewTelemetry


@dataclass(slots=True)
class DetectorHealth:
    detector_status: str
    detector_health_score: float
    detector_status_detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "detector_status": self.detector_status,
            "detector_health_score": self.detector_health_score,
            "detector_status_detail": self.detector_status_detail,
        }


def build_detector_health(
    is_online: bool,
    preview: PreviewTelemetry,
    quality: ImageQuality,
) -> DetectorHealth:
    if not is_online or preview.preview_status == "offline":
        return DetectorHealth(
            detector_status="offline",
            detector_health_score=0.0,
            detector_status_detail="Sem frames recentes da câmera.",
        )

    if preview.preview_status == "idle":
        return DetectorHealth(
            detector_status="idle",
            detector_health_score=25.0,
            detector_status_detail="Câmera conectada, aguardando frames novos.",
        )

    if preview.preview_status in {"degraded", "stale"}:
        detail = "Preview com atraso ou intermitência."
        if preview.preview_latency_seconds is not None:
            detail = f"Preview com atraso de {preview.preview_latency_seconds:.1f}s."
        return DetectorHealth(
            detector_status="degraded",
            detector_health_score=55.0 if preview.preview_status == "degraded" else 40.0,
            detector_status_detail=detail,
        )

    if quality.quality_label in {"poor", "fair"}:
        return DetectorHealth(
            detector_status="warning",
            detector_health_score=70.0 if quality.quality_label == "fair" else 45.0,
            detector_status_detail="Imagem com qualidade baixa para OCR confiável.",
        )

    return DetectorHealth(
        detector_status="healthy",
        detector_health_score=100.0,
        detector_status_detail="Detector operando normalmente.",
    )
