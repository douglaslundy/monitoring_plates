from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


class PlanBase(BaseModel):
    name: str
    max_cameras: Optional[int] = None
    retention_days: Optional[int] = None
    email_alerts: bool = False
    realtime_alerts: bool = True
    price_monthly: Decimal
    is_active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    max_cameras: Optional[int] = None
    retention_days: Optional[int] = None
    email_alerts: Optional[bool] = None
    realtime_alerts: Optional[bool] = None
    price_monthly: Optional[Decimal] = None
    is_active: Optional[bool] = None


class PlanRead(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    client_count: int = 0
