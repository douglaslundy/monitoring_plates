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


class OpsMetricsResetRead(BaseModel):
    cameras_reset: int


class SystemMetricsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    available: bool
    cpu_percent: float
    cpu_count: int
    load_avg_1m: float
    mem_total_mb: int
    mem_used_mb: int
    mem_available_mb: int
    mem_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float
    root_disk_total_gb: float
    root_disk_used_gb: float
    root_disk_free_gb: float
    root_disk_percent: float
