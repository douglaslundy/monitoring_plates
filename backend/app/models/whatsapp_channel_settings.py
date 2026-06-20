import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy import Uuid
from sqlalchemy.sql import func

from app.core.config import settings
from app.core.database import Base


class WhatsAppChannelSettings(Base):
    __tablename__ = "whatsapp_channel_settings"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    is_active = Column(Boolean, nullable=False, default=True)
    evolution_base_url = Column(String(255), nullable=False, default=settings.WHATSAPP_EVOLUTION_BASE_URL)
    evolution_instance_name = Column(String(100), nullable=False, default=settings.WHATSAPP_EVOLUTION_INSTANCE_NAME)
    evolution_api_key = Column(String(255), nullable=True, default=settings.WHATSAPP_EVOLUTION_API_KEY)
    request_timeout_seconds = Column(Integer, nullable=False, default=settings.WHATSAPP_WEBHOOK_TIMEOUT_SECONDS)
    test_recipient = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
