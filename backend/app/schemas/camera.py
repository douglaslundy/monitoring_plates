from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from uuid import UUID


class CameraBase(BaseModel):
    client_id: UUID
    name: str
    location: Optional[str] = None
    connection_type: str = "rtsp"
    rtsp_url: Optional[str] = None
    dual_lens: bool = False
    lens_side: Optional[str] = None
    roi_x: Optional[float] = None
    roi_y: Optional[float] = None
    roi_width: Optional[float] = None
    roi_height: Optional[float] = None
    preview_refresh_seconds: float = 2.5
    is_active: bool = True
    enable_ocr: bool = True
    enable_face: bool = False


class CameraCreate(CameraBase):
    client_id: Optional[UUID] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    connection_type: Optional[str] = None
    rtsp_url: Optional[str] = None
    dual_lens: Optional[bool] = None
    lens_side: Optional[str] = None
    roi_x: Optional[float] = None
    roi_y: Optional[float] = None
    roi_width: Optional[float] = None
    roi_height: Optional[float] = None
    preview_refresh_seconds: Optional[float] = None
    is_active: Optional[bool] = None
    enable_ocr: Optional[bool] = None
    enable_face: Optional[bool] = None


class CameraRead(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_token: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    is_online: bool = False
    preview_fps: float = 0.0
    preview_frames_last_minute: int = 0
    preview_last_frame_at: Optional[datetime] = None
    preview_latency_seconds: Optional[float] = None
    preview_status: str = "offline"
    detector_status: str = "offline"
    detector_health_score: float = 0.0
    detector_status_detail: str = ""
    ocr_pipeline_status: str = "idle"
    ocr_pipeline_health_score: float = 0.0
    ocr_pipeline_status_detail: str = ""
    ocr_attempts: int = 0
    ocr_success_rate: Optional[float] = None
    ocr_false_positive_rate: Optional[float] = None
    avg_ocr_seconds: Optional[float] = None
    last_attempt_at: Optional[datetime] = None
    quality_score: float = 0.0
    quality_label: str = "unknown"
    blur_score: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0


class OccurrenceSmall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plate: str
    confidence: float
    detected_at: Optional[datetime] = None


class CameraDetail(CameraRead):
    last_occurrences: List[OccurrenceSmall] = []
