"""T5: trocar a lente (lens_side) deve reiniciar a captura (não ficar fixo)."""
from types import SimpleNamespace

from app.workers.capture_runner import _worker_needs_restart


def _worker(rtsp_url="rtsp://x/y", dual_lens=True, lens_side="lower"):
    return SimpleNamespace(rtsp_url=rtsp_url, dual_lens=dual_lens, lens_side=lens_side)


def test_sem_mudanca_nao_reinicia():
    w = _worker()
    cfg = {"rtsp_url": "rtsp://x/y", "dual_lens": True, "lens_side": "lower"}
    assert _worker_needs_restart(w, cfg) is False


def test_troca_de_lente_reinicia():
    w = _worker(lens_side="lower")
    cfg = {"rtsp_url": "rtsp://x/y", "dual_lens": True, "lens_side": "upper"}
    assert _worker_needs_restart(w, cfg) is True


def test_toggle_dual_lens_reinicia():
    w = _worker(dual_lens=False, lens_side=None)
    cfg = {"rtsp_url": "rtsp://x/y", "dual_lens": True, "lens_side": "upper"}
    assert _worker_needs_restart(w, cfg) is True


def test_troca_de_rtsp_reinicia():
    w = _worker()
    cfg = {"rtsp_url": "rtsp://novo/url", "dual_lens": True, "lens_side": "lower"}
    assert _worker_needs_restart(w, cfg) is True
