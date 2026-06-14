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
    queue_depth: int
    operational_status: str
    operational_status_detail: str
    generated_at: datetime
