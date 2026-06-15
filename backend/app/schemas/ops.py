from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OpsMetricsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
