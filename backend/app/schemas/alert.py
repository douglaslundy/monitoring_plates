from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class AlertSentRead(BaseModel):
    id: UUID
    occurrence_id: UUID
    monitored_plate_id: UUID
    channel: str
    sent_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)
