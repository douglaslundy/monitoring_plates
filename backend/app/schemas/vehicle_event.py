from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VehicleEventBase(BaseModel):
    camera_id: UUID
    occurrence_id: Optional[UUID] = None
    category: str = "vehicle"
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


class VehicleCameraMin(BaseModel):
    id: UUID
    name: str
    location: Optional[str] = None


class VehicleEventWithCamera(VehicleEventRead):
    image_url: str
    plate: Optional[str] = None
    camera: VehicleCameraMin


class VehicleEventPage(BaseModel):
    items: List[VehicleEventWithCamera]
    total: int
    page: int
    pages: int


class VehicleEventTypeCount(BaseModel):
    vehicle_type: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class TopVehicleCamera(BaseModel):
    camera_id: str
    camera_name: str
    count: int


class HourBucket(BaseModel):
    hour: int
    count: int


class LatestVehicleEvent(BaseModel):
    id: UUID
    camera_id: UUID
    camera_name: str
    camera_location: Optional[str] = None
    category: str = "vehicle"
    vehicle_type: str
    confidence: float
    detected_at: datetime


class VehicleEventStats(BaseModel):
    total_today: int
    total_week: int
    by_type: List[VehicleEventTypeCount]
    by_category: List[CategoryCount]
    top_cameras: List[TopVehicleCamera]
    by_hour: List[HourBucket]
    latest_event: Optional[LatestVehicleEvent] = None
