from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.whatsapp_channel_settings import WhatsAppChannelSettings
from app.schemas.whatsapp_channel_settings import WhatsAppChannelSettingsCreate, WhatsAppChannelSettingsUpdate


@dataclass(frozen=True)
class WhatsAppDeliveryConfig:
    is_active: bool
    evolution_base_url: str
    evolution_instance_name: str
    evolution_api_key: str
    request_timeout_seconds: int
    test_recipient: str | None = None


def _to_delivery_config(model: WhatsAppChannelSettings | None) -> WhatsAppDeliveryConfig:
    if model is None:
        return WhatsAppDeliveryConfig(
            is_active=True,
            evolution_base_url=settings.WHATSAPP_EVOLUTION_BASE_URL,
            evolution_instance_name=settings.WHATSAPP_EVOLUTION_INSTANCE_NAME,
            evolution_api_key=settings.WHATSAPP_EVOLUTION_API_KEY,
            request_timeout_seconds=settings.WHATSAPP_WEBHOOK_TIMEOUT_SECONDS,
            test_recipient=None,
        )
    return WhatsAppDeliveryConfig(
        is_active=bool(model.is_active),
        evolution_base_url=model.evolution_base_url,
        evolution_instance_name=model.evolution_instance_name,
        evolution_api_key=model.evolution_api_key or "",
        request_timeout_seconds=int(model.request_timeout_seconds),
        test_recipient=model.test_recipient,
    )


def get_whatsapp_settings_model(db: Session) -> WhatsAppChannelSettings | None:
    return db.query(WhatsAppChannelSettings).order_by(WhatsAppChannelSettings.created_at.asc()).first()


def get_effective_whatsapp_delivery_config(db: Session) -> tuple[WhatsAppChannelSettings | None, WhatsAppDeliveryConfig]:
    model = get_whatsapp_settings_model(db)
    return model, _to_delivery_config(model)


def upsert_whatsapp_settings(
    db: Session,
    payload: WhatsAppChannelSettingsCreate | WhatsAppChannelSettingsUpdate,
) -> WhatsAppChannelSettings:
    model = get_whatsapp_settings_model(db)
    data = payload.model_dump(exclude_unset=True)

    if model is None:
        create_payload = WhatsAppChannelSettingsCreate.model_validate(
            {
                "is_active": data.get("is_active", True),
                "evolution_base_url": data.get("evolution_base_url", settings.WHATSAPP_EVOLUTION_BASE_URL),
                "evolution_instance_name": data.get("evolution_instance_name", settings.WHATSAPP_EVOLUTION_INSTANCE_NAME),
                "evolution_api_key": data.get("evolution_api_key", settings.WHATSAPP_EVOLUTION_API_KEY or None),
                "request_timeout_seconds": data.get("request_timeout_seconds", settings.WHATSAPP_WEBHOOK_TIMEOUT_SECONDS),
                "test_recipient": data.get("test_recipient"),
            }
        )
        model = WhatsAppChannelSettings(
            is_active=create_payload.is_active,
            evolution_base_url=create_payload.evolution_base_url,
            evolution_instance_name=create_payload.evolution_instance_name,
            evolution_api_key=create_payload.evolution_api_key,
            request_timeout_seconds=create_payload.request_timeout_seconds,
            test_recipient=create_payload.test_recipient,
        )
        db.add(model)
    else:
        if "is_active" in data:
            model.is_active = bool(data["is_active"])
        if "evolution_base_url" in data and data["evolution_base_url"] is not None:
            model.evolution_base_url = str(data["evolution_base_url"]).strip().rstrip("/")
        if "evolution_instance_name" in data and data["evolution_instance_name"] is not None:
            model.evolution_instance_name = str(data["evolution_instance_name"]).strip()
        if "request_timeout_seconds" in data and data["request_timeout_seconds"] is not None:
            model.request_timeout_seconds = int(data["request_timeout_seconds"])
        if "test_recipient" in data:
            recipient = data["test_recipient"]
            model.test_recipient = str(recipient).strip() if recipient else None
        if "evolution_api_key" in data and data["evolution_api_key"] is not None:
            api_key = str(data["evolution_api_key"]).strip()
            if api_key:
                model.evolution_api_key = api_key

    db.commit()
    db.refresh(model)
    return model
