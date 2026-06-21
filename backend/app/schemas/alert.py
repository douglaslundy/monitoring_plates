from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class AlertSentRead(BaseModel):
    id: UUID
    occurrence_id: UUID
    monitored_plate_id: UUID
    channel: str
    sent_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class AlertSentLogRead(BaseModel):
    id: UUID
    occurrence_id: UUID
    monitored_plate_id: UUID
    plate: str
    camera_name: str
    location: Optional[str] = None
    channel: str
    sent_at: datetime
    status: str
    message: Optional[str] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
