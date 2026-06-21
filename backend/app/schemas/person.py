from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PersonBase(BaseModel):
    name: str
    birth_date: Optional[date] = None
    cpf: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    alert_active: bool = False
    alert_email: Optional[str] = None
    alert_whatsapp: Optional[str] = None
    is_active: bool = True


class PersonCreate(PersonBase):
    client_id: Optional[UUID] = None  # super_admin informa; cliente usa o próprio


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    birth_date: Optional[date] = None
    cpf: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    alert_active: Optional[bool] = None
    alert_email: Optional[str] = None
    alert_whatsapp: Optional[str] = None
    is_active: Optional[bool] = None


class PersonRead(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    photo_url: Optional[str] = None
    faces_count: int = 0
    created_at: Optional[datetime] = None
