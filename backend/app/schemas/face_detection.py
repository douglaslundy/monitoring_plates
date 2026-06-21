from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class FaceDetectionRead(BaseModel):
    id: UUID
    camera_id: UUID
    camera_name: Optional[str] = None
    person_id: Optional[UUID] = None
    person_name: Optional[str] = None
    confidence: Optional[float] = None
    image_url: Optional[str] = None
    bbox_x: Optional[int] = None
    bbox_y: Optional[int] = None
    bbox_w: Optional[int] = None
    bbox_h: Optional[int] = None
    track_id: Optional[str] = None
    detected_at: Optional[datetime] = None
    tracked_seconds: Optional[float] = None
    face_engine_used: Optional[str] = None
