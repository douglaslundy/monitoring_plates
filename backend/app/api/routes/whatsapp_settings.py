from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.schemas.whatsapp_channel_settings import (
    WhatsAppChannelSettingsRead,
    WhatsAppChannelSettingsUpdate,
    WhatsAppTestSendResponse,
    WhatsAppTestSendRequest,
)
from app.services.whatsapp_service import build_whatsapp_message, send_whatsapp_alert
from app.services.whatsapp_settings_service import get_effective_whatsapp_delivery_config, upsert_whatsapp_settings

router = APIRouter(prefix="/whatsapp-settings", tags=["whatsapp-settings"])


def _read_model_view(db: Session) -> WhatsAppChannelSettingsRead:
    model, config = get_effective_whatsapp_delivery_config(db)
    if model is None:
        return WhatsAppChannelSettingsRead(
            is_active=config.is_active,
            evolution_base_url=config.evolution_base_url,
            evolution_instance_name=config.evolution_instance_name,
            request_timeout_seconds=config.request_timeout_seconds,
            api_key_configured=bool(config.evolution_api_key.strip()),
        )
    return WhatsAppChannelSettingsRead.model_validate(
        {
            "id": model.id,
            "is_active": model.is_active,
            "evolution_base_url": model.evolution_base_url,
            "evolution_instance_name": model.evolution_instance_name,
            "request_timeout_seconds": model.request_timeout_seconds,
            "api_key_configured": bool(model.evolution_api_key and model.evolution_api_key.strip()),
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
    )


@router.get("", response_model=WhatsAppChannelSettingsRead)
def read_settings(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    return _read_model_view(db)


@router.put("", response_model=WhatsAppChannelSettingsRead)
def update_settings(
    payload: WhatsAppChannelSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    upsert_whatsapp_settings(db, payload)
    return _read_model_view(db)


@router.post("/test", response_model=WhatsAppTestSendResponse)
def test_send(
    payload: WhatsAppTestSendRequest,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    _model, config = get_effective_whatsapp_delivery_config(db)
    message = payload.message.strip() if payload.message else None
    if not message:
        message = build_whatsapp_message(
            plate="TESTE",
            camera_name="Painel administrativo",
            location="Configuração WhatsApp",
            detected_at=None,
            confidence=None,
        )

    success = send_whatsapp_alert(
        to=payload.recipient,
        plate="TESTE",
        camera_name="Painel administrativo",
        location="Configuração WhatsApp",
        detected_at=None,
        image_url="",
        confidence=None,
        message=message,
        image_bytes=None,
        config=config,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Falha ao enviar mensagem de teste para a Evolution API")

    return WhatsAppTestSendResponse(
        success=True,
        message="Mensagem de teste enviada com sucesso",
        recipient=payload.recipient,
    )
