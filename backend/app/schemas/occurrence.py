from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from uuid import UUID


class CameraMin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    location: Optional[str] = None


class OccurrenceBase(BaseModel):
    camera_id: UUID
    plate: str
    confidence: float
    image_path: str


class OccurrenceCreate(OccurrenceBase):
    expires_at: Optional[datetime] = None


class OccurrenceRead(OccurrenceBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    detected_at: datetime
    expires_at: Optional[datetime] = None
    created_at: datetime


class OccurrenceWithCamera(BaseModel):
    id: UUID
    plate: str
    confidence: float
    image_path: str
    image_url: str
    detected_at: datetime
    expires_at: Optional[datetime] = None
    camera: CameraMin
    vehicle_type: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_make_model: Optional[str] = None
    region_code: Optional[str] = None
    ocr_engine_used: Optional[str] = None


class OccurrenceSearch(BaseModel):
    plate: str = ""
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    camera_ids: Optional[List[UUID]] = None
    page: int = 1
    limit: int = 20


class OccurrencePage(BaseModel):
    items: List[OccurrenceWithCamera]
    total: int
    page: int
    pages: int


class TopCamera(BaseModel):
    camera_id: str
    camera_name: str
    count: int


class TopPlate(BaseModel):
    plate: str
    count: int


class HourBucket(BaseModel):
    hour: int
    count: int


class OccurrenceStats(BaseModel):
    total_today: int
    total_week: int
    top_cameras: List[TopCamera]
    top_plates: List[TopPlate]
    by_hour: List[HourBucket]
