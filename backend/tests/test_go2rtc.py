"""Testes da integração com go2rtc (live WebRTC)."""
import sys
import types
from unittest.mock import MagicMock, patch

from app.services import go2rtc_service


def _mock_requests(status_code: int = 200):
    mod = types.ModuleType("requests")
    resp = MagicMock()
    resp.status_code = status_code
    mod.put = MagicMock(return_value=resp)
    mod.delete = MagicMock(return_value=resp)
    return mod


def test_public_stream_url_formato():
    with patch("app.core.config.settings.GO2RTC_PUBLIC_URL", "http://host:1984/"):
        url = go2rtc_service.public_stream_url("cam-1")
    assert url == "http://host:1984/stream.html?src=cam-1"


def test_register_stream_ok():
    mod = _mock_requests(200)
    with patch("app.core.config.settings.GO2RTC_ENABLED", True), \
         patch("app.core.config.settings.GO2RTC_URL", "http://go2rtc:1984"), \
         patch.dict(sys.modules, {"requests": mod}):
        ok = go2rtc_service.register_stream("cam-1", "rtsp://x/stream")
    assert ok is True
    assert mod.put.call_args.kwargs["params"] == {"name": "cam-1", "src": "rtsp://x/stream"}


def test_register_stream_desabilitado_nao_chama():
    mod = _mock_requests(200)
    with patch("app.core.config.settings.GO2RTC_ENABLED", False), \
         patch.dict(sys.modules, {"requests": mod}):
        ok = go2rtc_service.register_stream("cam-1", "rtsp://x/stream")
    assert ok is False
    assert mod.put.called is False


def test_register_stream_erro_http_retorna_false():
    mod = _mock_requests(500)
    with patch("app.core.config.settings.GO2RTC_ENABLED", True), \
         patch.dict(sys.modules, {"requests": mod}):
        ok = go2rtc_service.register_stream("cam-1", "rtsp://x/stream")
    assert ok is False


def test_sync_streams_registra_rtsp_ativas(db):
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType

    plan = Plan(name="P-go2rtc", max_cameras=5, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)
    tenant = Client(name="T-go2rtc", email="g@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)
    db.add(Camera(client_id=tenant.id, name="C", connection_type=ConnectionType.rtsp,
                  rtsp_url="rtsp://x/s", is_active=True))
    db.commit()

    with patch("app.core.config.settings.GO2RTC_ENABLED", True), \
         patch.object(go2rtc_service, "register_stream", return_value=True) as reg:
        count = go2rtc_service.sync_streams(db)

    assert count == 1
    assert reg.called
