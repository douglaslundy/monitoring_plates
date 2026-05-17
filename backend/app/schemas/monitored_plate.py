from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID


class MonitoredPlateBase(BaseModel):
    client_id: UUID
    plate: str
    description: Optional[str] = None
    alert_email: Optional[str] = None
    is_active: bool = True


class MonitoredPlateCreate(MonitoredPlateBase):
    pass


class MonitoredPlateUpdate(BaseModel):
    plate: Optional[str] = None
    description: Optional[str] = None
    alert_email: Optional[str] = None
    is_active: Optional[bool] = None


class MonitoredPlateRead(MonitoredPlateBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
