from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    max_cameras: Optional[int] = None
    retention_days: Optional[int] = None
    email_alerts: bool
    realtime_alerts: bool
    price_monthly: Decimal


class ClientBase(BaseModel):
    name: str
    email: str
    plan_id: UUID
    plan_expires_at: Optional[datetime] = None
    is_active: bool = True


class ClientCreate(ClientBase):
    pass


class ClientCreateWithAdmin(ClientBase):
    admin_name: str
    admin_email: str
    admin_password: str


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    plan_id: Optional[UUID] = None
    plan_expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    plan: Optional[PlanSummary] = None
    camera_count: int = 0
