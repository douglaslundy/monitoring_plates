from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


class LoginRequest(BaseModel):
    email: str
    password: str


class UserInToken(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
    client_id: Optional[UUID] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInToken


class PlanInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    max_cameras: Optional[int] = None
    retention_days: Optional[int] = None
    email_alerts: bool
    realtime_alerts: bool
    price_monthly: Decimal


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ClientInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    plan_expires_at: Optional[datetime] = None
    plan: Optional[PlanInfo] = None


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
    client_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    client: Optional[ClientInfo] = None
