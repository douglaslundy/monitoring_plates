"""Envio de alertas via WhatsApp Business Cloud API (Meta).

Requer WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID no .env.
Número do destinatário no formato E.164 sem '+' (ex: 5511999998888).
Falha silenciosa: loga warning e retorna False sem estourar exceção.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_API_VERSION = "v20.0"
_BASE_URL = "https://graph.facebook.com"


def _to_digits(number: str) -> str:
    return "".join(c for c in number if c.isdigit())


def send_whatsapp_alert(
    *,
    to: str,
    plate: str,
    camera_name: str,
    location: str,
    detected_at: str,
    image_url: str,
) -> bool:
    from app.core.config import settings

    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp nao configurado (WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID ausentes)")
        return False

    try:
        import httpx

        recipient = _to_digits(to)
        body = (
            f"🚗 Placa {plate} detectada\n"
            f"📷 Câmera: {camera_name}\n"
            f"📍 Local: {location or 'nao informado'}\n"
            f"🕐 Horário: {detected_at}"
        )
        if image_url:
            body += f"\n🔗 Imagem: {image_url}"

        url = f"{_BASE_URL}/{_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": body},
        }
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        return True
    except Exception:
        logger.warning("Falha ao enviar alerta WhatsApp", exc_info=True)
        return False
