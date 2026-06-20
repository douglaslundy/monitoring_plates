from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class WhatsAppChannelSettingsBase(BaseModel):
    is_active: bool = True
    evolution_base_url: str = Field(default_factory=lambda: settings.WHATSAPP_EVOLUTION_BASE_URL)
    evolution_instance_name: str = Field(default_factory=lambda: settings.WHATSAPP_EVOLUTION_INSTANCE_NAME)
    request_timeout_seconds: int = Field(default_factory=lambda: settings.WHATSAPP_WEBHOOK_TIMEOUT_SECONDS)
    test_recipient: Optional[str] = None

    @field_validator("evolution_base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("evolution_instance_name")
    @classmethod
    def normalize_instance_name(cls, value: str) -> str:
        return value.strip()


class WhatsAppChannelSettingsCreate(WhatsAppChannelSettingsBase):
    evolution_api_key: Optional[str] = None


class WhatsAppChannelSettingsUpdate(BaseModel):
    is_active: Optional[bool] = None
    evolution_base_url: Optional[str] = None
    evolution_instance_name: Optional[str] = None
    evolution_api_key: Optional[str] = None
    request_timeout_seconds: Optional[int] = None
    test_recipient: Optional[str] = None

    @field_validator("evolution_base_url")
    @classmethod
    def normalize_base_url(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().rstrip("/") if value else value

    @field_validator("evolution_instance_name")
    @classmethod
    def normalize_instance_name(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class WhatsAppChannelSettingsRead(WhatsAppChannelSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[UUID] = None
    api_key_configured: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WhatsAppTestSendRequest(BaseModel):
    recipient: str
    message: Optional[str] = None


class WhatsAppTestSendResponse(BaseModel):
    success: bool
    message: str
    recipient: str


class WhatsAppInstanceStatus(BaseModel):
    state: str  # "open" | "close" | "connecting" | "unknown"
    qr_code: Optional[str] = None  # base64 data URL when state == "connecting"
