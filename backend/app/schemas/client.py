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
    plan_activated_at: Optional[datetime] = None
    is_active: bool = True


class ClientCreate(ClientBase):
    pass


class ClientCreateWithAdmin(ClientBase):
    # Usuário de acesso criado junto com o cliente (todo cliente precisa de ao
    # menos um usuário para entrar). admin_role define se ele entra como admin
    # do cliente (gerencia usuários/câmeras) ou usuário comum (só visualiza).
    admin_name: str
    admin_email: str
    admin_password: str
    admin_role: str = "client_admin"


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
