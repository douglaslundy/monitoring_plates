from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_super_admin
from app.schemas.whatsapp_channel_settings import (
    WhatsAppChannelSettingsRead,
    WhatsAppChannelSettingsUpdate,
    WhatsAppInstanceStatus,
    WhatsAppTestSendResponse,
    WhatsAppTestSendRequest,
)
from app.services.whatsapp_service import build_whatsapp_message, send_whatsapp_alert
from app.services.whatsapp_settings_service import get_effective_whatsapp_delivery_config, upsert_whatsapp_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp-settings", tags=["whatsapp-settings"])


def _read_model_view(db: Session) -> WhatsAppChannelSettingsRead:
    model, config = get_effective_whatsapp_delivery_config(db)
    if model is None:
        return WhatsAppChannelSettingsRead(
            is_active=config.is_active,
            evolution_base_url=config.evolution_base_url,
            evolution_instance_name=config.evolution_instance_name,
            request_timeout_seconds=config.request_timeout_seconds,
            test_recipient=config.test_recipient,
            api_key_configured=bool(config.evolution_api_key.strip()),
        )
    return WhatsAppChannelSettingsRead.model_validate(
        {
            "id": model.id,
            "is_active": model.is_active,
            "evolution_base_url": model.evolution_base_url,
            "evolution_instance_name": model.evolution_instance_name,
            "request_timeout_seconds": model.request_timeout_seconds,
            "test_recipient": model.test_recipient,
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
    if payload.recipient.strip():
        from app.schemas.whatsapp_channel_settings import WhatsAppChannelSettingsUpdate

        upsert_whatsapp_settings(db, WhatsAppChannelSettingsUpdate(test_recipient=payload.recipient.strip()))
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


# ── Instance management (proxy to Evolution API) ──────────────────────────────

def _evolution(method: str, path: str, db: Session) -> dict:
    _, config = get_effective_whatsapp_delivery_config(db)
    url = f"{config.evolution_base_url}{path}"
    headers = {"apikey": config.evolution_api_key or ""}
    try:
        with httpx.Client(timeout=15) as client:
            resp = getattr(client, method)(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/instance/status", response_model=WhatsAppInstanceStatus)
def instance_status(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    _, config = get_effective_whatsapp_delivery_config(db)
    data = _evolution("get", f"/instance/connectionState/{config.evolution_instance_name}", db)
    state = data.get("instance", {}).get("state", "unknown")
    return WhatsAppInstanceStatus(state=state)


@router.post("/instance/connect", response_model=WhatsAppInstanceStatus)
def instance_connect(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    _, config = get_effective_whatsapp_delivery_config(db)
    data = _evolution("get", f"/instance/connect/{config.evolution_instance_name}", db)
    if "instance" in data:
        return WhatsAppInstanceStatus(state=data["instance"].get("state", "open"))
    return WhatsAppInstanceStatus(state="connecting", qr_code=data.get("base64"))


@router.post("/instance/disconnect", response_model=WhatsAppInstanceStatus)
def instance_disconnect(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    _, config = get_effective_whatsapp_delivery_config(db)
    _evolution("delete", f"/instance/logout/{config.evolution_instance_name}", db)
    return WhatsAppInstanceStatus(state="close")


@router.post("/instance/restart", response_model=WhatsAppInstanceStatus)
def instance_restart(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    _, config = get_effective_whatsapp_delivery_config(db)
    _evolution("put", f"/instance/restart/{config.evolution_instance_name}", db)
    return WhatsAppInstanceStatus(state="unknown")
