"""Envio direto de alertas WhatsApp pela Evolution API."""
from __future__ import annotations

import base64
import io
import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from PIL import Image

from app.core.config import settings
from app.services.whatsapp_settings_service import WhatsAppDeliveryConfig

logger = logging.getLogger(__name__)

_DEFAULT_MIME_TYPE = "image/jpeg"
_SAO_PAULO = ZoneInfo("America/Sao_Paulo")
_RECIPIENT_RE = re.compile(r"^\d{10,15}$")


def _normalize_digits(number: str) -> str:
    return "".join(char for char in number if char.isdigit())


def _format_confidence(confidence: float | None) -> str:
    if confidence is None:
        return "desconhecida"
    return f"{confidence * 100:.1f}%"


def _format_detected_at(value: datetime | str | None) -> str:
    if value is None:
        return "não informado"
    if isinstance(value, str):
        return value.strip() or "não informado"
    # Datetimes do banco são naive UTC — assumir UTC antes de converter.
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SAO_PAULO).strftime("%d/%m/%Y %H:%M:%S")


def build_whatsapp_message(
    *,
    plate: str,
    camera_name: str,
    location: str,
    detected_at: datetime | str | None,
    confidence: float | None,
    image_url: str | None = None,
) -> str:
    # A imagem é enviada como mídia (caption), então NÃO incluímos o caminho/URL
    # da imagem no texto — antes saía "Imagem: <path>" poluindo a mensagem.
    lines = [
        f"Placa {plate} detectada",
        f"Câmera: {camera_name}",
        f"Local: {location or 'não informado'}",
        f"Horário: {_format_detected_at(detected_at)}",
        f"Confiança: {_format_confidence(confidence)}",
    ]
    return "\n".join(lines)


def _resize_frame(image_bytes: bytes) -> tuple[bytes, str]:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image = image.convert("RGB")
            image.thumbnail((settings.WHATSAPP_FRAME_MAX_SIDE, settings.WHATSAPP_FRAME_MAX_SIDE))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=settings.WHATSAPP_FRAME_JPEG_QUALITY, optimize=True)
            return buffer.getvalue(), _DEFAULT_MIME_TYPE
    except Exception:
        logger.debug("Falha ao redimensionar frame do WhatsApp; enviando bytes originais", exc_info=True)
        return image_bytes, _DEFAULT_MIME_TYPE


def _build_send_text_url(base_url: str, instance_name: str) -> str:
    return f"{base_url.rstrip('/')}/message/sendText/{instance_name.strip()}"


def _build_send_media_url(base_url: str, instance_name: str) -> str:
    return f"{base_url.rstrip('/')}/message/sendMedia/{instance_name.strip()}"


def _send_to_evolution(
    *,
    config: WhatsAppDeliveryConfig,
    recipient: str,
    message: str,
    image_bytes: bytes | None,
) -> bool:
    if not config.is_active:
        logger.info("Canal WhatsApp desativado; envio ignorado")
        return False

    api_key = config.evolution_api_key.strip()
    if not api_key:
        logger.warning("Evolution API key não configurada para WhatsApp")
        return False

    normalized_recipient = _normalize_digits(recipient)
    if not _RECIPIENT_RE.match(normalized_recipient):
        logger.warning("Número de WhatsApp inválido: %s", recipient)
        return False

    headers = {"apikey": api_key, "Content-Type": "application/json"}
    timeout = max(int(config.request_timeout_seconds), 1)
    endpoint = _build_send_text_url(config.evolution_base_url, config.evolution_instance_name)
    body: dict[str, object]

    if image_bytes:
        resized_bytes, mime_type = _resize_frame(image_bytes)
        endpoint = _build_send_media_url(config.evolution_base_url, config.evolution_instance_name)
        body = {
            "number": normalized_recipient,
            "mediatype": "image",
            "mimetype": mime_type,
            "media": base64.b64encode(resized_bytes).decode("ascii"),
            "caption": message,
            "delay": 0,
            "linkPreview": False,
        }
    else:
        body = {
            "number": normalized_recipient,
            "text": message,
            "delay": 0,
            "linkPreview": False,
        }

    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()
        return True
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        response_text = getattr(getattr(exc, "response", None), "text", None)
        if status_code is not None:
            logger.warning(
                "Falha ao enviar mensagem via Evolution API (status=%s, response=%s)",
                status_code,
                response_text,
                exc_info=True,
            )
        else:
            logger.warning("Falha ao enviar mensagem via Evolution API", exc_info=True)
        return False


def send_whatsapp_alert(
    *,
    to: str,
    plate: str,
    camera_name: str,
    location: str,
    detected_at: datetime | str | None,
    image_url: str,
    confidence: float | None = None,
    image_bytes: bytes | None = None,
    message: str | None = None,
    config: WhatsAppDeliveryConfig | None = None,
) -> bool:
    delivery_config = config or WhatsAppDeliveryConfig(
        is_active=True,
        evolution_base_url=settings.WHATSAPP_EVOLUTION_BASE_URL,
        evolution_instance_name=settings.WHATSAPP_EVOLUTION_INSTANCE_NAME,
        evolution_api_key=settings.WHATSAPP_EVOLUTION_API_KEY,
        request_timeout_seconds=settings.WHATSAPP_WEBHOOK_TIMEOUT_SECONDS,
    )

    text = message or build_whatsapp_message(
        plate=plate,
        camera_name=camera_name,
        location=location,
        detected_at=detected_at,
        confidence=confidence,
        image_url=image_url or None,
    )
    return _send_to_evolution(
        config=delivery_config,
        recipient=to,
        message=text,
        image_bytes=image_bytes,
    )
