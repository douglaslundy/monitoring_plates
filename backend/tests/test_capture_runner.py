"""Testes do capture-runner: motion gating e sincronização de threads."""
from unittest.mock import MagicMock

from app.core.config import settings
from app.workers.capture_runner import CameraCapture, CaptureManager


def _fake_cv2(non_zero: int, size: int = 320 * 180) -> MagicMock:
    cv2 = MagicMock()
    cv2.COLOR_BGR2GRAY = 6
    cv2.THRESH_BINARY = 0
    cv2.resize.return_value = MagicMock()
    cv2.cvtColor.return_value = MagicMock()
    cv2.GaussianBlur.side_effect = lambda *a, **k: MagicMock()
    cv2.absdiff.return_value = MagicMock()
    thresh = MagicMock()
    thresh.size = size
    cv2.threshold.return_value = (0, thresh)
    cv2.countNonZero.return_value = non_zero
    return cv2


def test_motion_gate_detecta_movimento():
    cap = CameraCapture("cam-1", "rtsp://x", dual_lens=False, lens_side=None)
    # acima do limiar (0.0035 * 57600 ≈ 201 pixels)
    cv2 = _fake_cv2(non_zero=4000)
    frame = MagicMock()

    assert cap._has_motion(cv2, frame) is False  # 1o frame: bootstrap do fundo
    assert cap._has_motion(cv2, frame) is True  # movimento detectado


def test_motion_gate_ignora_cena_parada():
    cap = CameraCapture("cam-1", "rtsp://x", dual_lens=False, lens_side=None)
    cv2 = _fake_cv2(non_zero=10)  # bem abaixo do limiar
    frame = MagicMock()

    cap._has_motion(cv2, frame)  # bootstrap
    assert cap._has_motion(cv2, frame) is False


def test_camera_capture_nao_sombreia_thread_bootstrap():
    """Atributo de flag não pode sombrear o método interno Thread._bootstrap."""
    cap = CameraCapture("cam-1", "rtsp://x", dual_lens=False, lens_side=None)
    assert callable(cap._bootstrap)  # método do threading.Thread intacto
    assert cap._force_send is True


def test_manager_inicia_e_encerra_workers(monkeypatch):
    started: list[str] = []
    stopped: list[str] = []

    class FakeWorker:
        def __init__(self, camera_id, rtsp_url, dual_lens, lens_side):
            self.camera_id = camera_id
            self.rtsp_url = rtsp_url

        def start(self):
            started.append(self.camera_id)

        def stop(self):
            stopped.append(self.camera_id)

    monkeypatch.setattr("app.workers.capture_runner.CameraCapture", FakeWorker)

    manager = CaptureManager()
    cameras = {"cam-1": {"rtsp_url": "rtsp://a", "dual_lens": False, "lens_side": None}}
    monkeypatch.setattr(manager, "_active_cameras", lambda: cameras)

    manager._sync()
    assert started == ["cam-1"]
    assert "cam-1" in manager._workers

    # câmera some da lista → thread encerrada
    cameras.clear()
    manager._sync()
    assert stopped == ["cam-1"]
    assert "cam-1" not in manager._workers
