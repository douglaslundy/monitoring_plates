from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.core.security import create_access_token
from app.models.user import User
from app.services.whatsapp_service import send_whatsapp_alert
from app.services.whatsapp_settings_service import WhatsAppDeliveryConfig


def _auth(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def test_whatsapp_settings_get_and_update(client, db, super_admin_user):
    res = client.get("/api/whatsapp-settings", headers=_auth(super_admin_user))
    assert res.status_code == 200
    data = res.json()
    assert data["is_active"] is True
    assert data["api_key_configured"] is False

    payload = {
        "is_active": True,
        "evolution_base_url": "http://192.168.0.115:8081/",
        "evolution_instance_name": "whatsapp",
        "evolution_api_key": "secret-key",
        "request_timeout_seconds": 25,
    }
    res = client.put("/api/whatsapp-settings", json=payload, headers=_auth(super_admin_user))
    assert res.status_code == 200
    data = res.json()
    assert data["evolution_base_url"] == "http://192.168.0.115:8081"
    assert data["evolution_instance_name"] == "whatsapp"
    assert data["request_timeout_seconds"] == 25
    assert data["api_key_configured"] is True

    stored = client.get("/api/whatsapp-settings", headers=_auth(super_admin_user)).json()
    assert stored["evolution_base_url"] == "http://192.168.0.115:8081"
    assert stored["api_key_configured"] is True


def test_whatsapp_send_uses_text_endpoint(monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> FakeResponse:
            calls.append({"url": url, "json": json, "headers": headers, "timeout": self.timeout})
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)

    ok = send_whatsapp_alert(
        to="+5511999998888",
        plate="ABC1234",
        camera_name="Entrada",
        location="Portão principal",
        detected_at="20/06/2026 10:00",
        image_url="",
        confidence=0.9,
        config=WhatsAppDeliveryConfig(
            is_active=True,
            evolution_base_url="http://192.168.0.115:8081",
            evolution_instance_name="whatsapp",
            evolution_api_key="secret-key",
            request_timeout_seconds=9,
        ),
    )

    assert ok is True
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "http://192.168.0.115:8081/message/sendText/whatsapp"
    assert call["headers"]["apikey"] == "secret-key"
    assert call["json"]["number"] == "5511999998888"
    assert "text" in call["json"]


def test_whatsapp_send_uses_media_endpoint(monkeypatch):
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> FakeResponse:
            calls.append({"url": url, "json": json, "headers": headers, "timeout": self.timeout})
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)

    image = Image.new("RGB", (16, 16), color=(255, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    ok = send_whatsapp_alert(
        to="+5511999998888",
        plate="ABC1234",
        camera_name="Entrada",
        location="Portão principal",
        detected_at="20/06/2026 10:00",
        image_url="",
        confidence=0.9,
        image_bytes=buffer.getvalue(),
        config=WhatsAppDeliveryConfig(
            is_active=True,
            evolution_base_url="http://192.168.0.115:8081",
            evolution_instance_name="whatsapp",
            evolution_api_key="secret-key",
            request_timeout_seconds=9,
        ),
    )

    assert ok is True
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "http://192.168.0.115:8081/message/sendMedia/whatsapp"
    assert call["json"]["number"] == "5511999998888"
    assert call["json"]["mediatype"] == "image"
    assert "media" in call["json"]
    assert "caption" in call["json"]
