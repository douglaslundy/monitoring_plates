from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VehicleEventBase(BaseModel):
    camera_id: UUID
    occurrence_id: Optional[UUID] = None
    vehicle_type: str
    confidence: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int
    image_path: Optional[str] = None


class VehicleEventRead(VehicleEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    detected_at: datetime
    created_at: datetime


class VehicleEventTypeCount(BaseModel):
    vehicle_type: str
    count: int


class TopVehicleCamera(BaseModel):
    camera_id: str
    camera_name: str
    count: int


class HourBucket(BaseModel):
    hour: int
    count: int


class VehicleEventStats(BaseModel):
    total_today: int
    total_week: int
    by_type: List[VehicleEventTypeCount]
    top_cameras: List[TopVehicleCamera]
    by_hour: List[HourBucket]
