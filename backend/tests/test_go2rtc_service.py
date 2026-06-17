"""T0: live dual-lens via go2rtc — fonte de recorte sem espaços (aceita pela API)."""
import sys
import types
from unittest.mock import MagicMock

from app.services import go2rtc_service


def test_build_source_camera_normal_usa_rtsp_cru():
    assert go2rtc_service.build_source("rtsp://x/y") == "rtsp://x/y"
    assert go2rtc_service.build_source("rtsp://x/y", dual_lens=False, lens_side="lower") == "rtsp://x/y"


def test_build_source_dual_lens_lower_referencia_template():
    src = go2rtc_service.build_source("rtsp://x/y", dual_lens=True, lens_side="lower")
    assert src == "ffmpeg:rtsp://x/y#video=lens_lower"


def test_build_source_dual_lens_upper_referencia_template():
    src = go2rtc_service.build_source("rtsp://x/y", dual_lens=True, lens_side="upper")
    assert src == "ffmpeg:rtsp://x/y#video=lens_upper"


def test_build_source_dual_lens_sem_espacos():
    """A fonte registrada via API NÃO pode conter espaços (go2rtc recusa)."""
    src = go2rtc_service.build_source("rtsp://user:pass@10.0.0.1:554/cam1", dual_lens=True, lens_side="lower")
    assert " " not in src


def test_build_source_dual_lens_sem_lado_cai_no_rtsp():
    # dual_lens marcado mas sem lente válida -> não recorta (evita stream quebrado)
    assert go2rtc_service.build_source("rtsp://x/y", dual_lens=True, lens_side=None) == "rtsp://x/y"


def _patch_requests(monkeypatch, captured: dict):
    fake = types.ModuleType("requests")

    def _put(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return MagicMock(status_code=200)

    fake.put = _put
    monkeypatch.setitem(sys.modules, "requests", fake)


def test_register_stream_dual_lens_registra_via_api(monkeypatch):
    captured: dict = {}
    _patch_requests(monkeypatch, captured)
    ok = go2rtc_service.register_stream("cam-uuid", "rtsp://x/y", dual_lens=True, lens_side="lower")
    assert ok is True
    assert captured["params"]["name"] == "cam-uuid"
    assert captured["params"]["src"] == "ffmpeg:rtsp://x/y#video=lens_lower"


def test_register_stream_normal_registra_rtsp(monkeypatch):
    captured: dict = {}
    _patch_requests(monkeypatch, captured)
    ok = go2rtc_service.register_stream("cam-uuid", "rtsp://x/y")
    assert ok is True
    assert captured["params"]["src"] == "rtsp://x/y"


def test_register_stream_sem_rtsp_nao_registra(monkeypatch):
    captured: dict = {}
    _patch_requests(monkeypatch, captured)
    assert go2rtc_service.register_stream("cam-uuid", "") is False
    assert captured == {}
