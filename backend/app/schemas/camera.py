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
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    connection_type: Optional[str] = None
    rtsp_url: Optional[str] = None
    is_active: Optional[bool] = None


class CameraRead(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_token: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    is_online: bool = False


class OccurrenceSmall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plate: str
    confidence: float
    detected_at: Optional[datetime] = None


class CameraDetail(CameraRead):
    last_occurrences: List[OccurrenceSmall] = []
