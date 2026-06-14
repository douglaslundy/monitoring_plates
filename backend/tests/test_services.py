"""
Tests for services and workers (email, camera, storage, retention, frame processor).
These tests mock external dependencies to maximize coverage.
"""

import io
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

import pytest


# ── email_service ─────────────────────────────────────────────────────────────

def test_email_sem_api_key_retorna_false():
    from app.services.email_service import send_plate_alert
    with patch("app.core.config.settings.RESEND_API_KEY", ""):
        result = send_plate_alert("to@test.com", "ABC1234", "Cam1")
    assert result is False


def test_email_enviado_com_sucesso():
    mock_resend = MagicMock()
    mock_resend.Emails.send.return_value = {"id": "abc"}

    with patch("app.core.config.settings.RESEND_API_KEY", "key-test"), \
         patch("app.core.config.settings.RESEND_FROM_EMAIL", "from@test.com"), \
         patch.dict(sys.modules, {"resend": mock_resend}):
        from app.services import email_service
        import importlib
        importlib.reload(email_service)
        result = email_service.send_plate_alert(
            "to@test.com", "ABC1234", "Cam Principal",
            location="Entrada", detected_at="2026-01-01 10:00", image_url="http://img"
        )

    assert result is True


def test_email_com_excecao_retorna_false():
    mock_resend = MagicMock()
    mock_resend.Emails.send.side_effect = Exception("resend error")

    with patch("app.core.config.settings.RESEND_API_KEY", "key-test"), \
         patch("app.core.config.settings.RESEND_FROM_EMAIL", "from@test.com"), \
         patch.dict(sys.modules, {"resend": mock_resend}):
        from app.services import email_service
        import importlib
        importlib.reload(email_service)
        result = email_service.send_plate_alert("to@test.com", "ABC1234", "Cam")

    assert result is False


# ── camera_service ────────────────────────────────────────────────────────────

def test_generate_agent_token_is_32_chars():
    from app.services.camera_service import generate_agent_token
    token = generate_agent_token()
    assert len(token) == 32
    assert token.isalnum()


def test_check_rtsp_online_true():
    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cv2.VideoCapture.return_value = mock_cap
    mock_cv2.CAP_PROP_OPEN_TIMEOUT_MSEC = 0

    with patch.dict(sys.modules, {"cv2": mock_cv2}):
        from app.services import camera_service
        import importlib
        importlib.reload(camera_service)
        result = camera_service.check_rtsp_online("rtsp://test/stream", timeout=5)

    assert result is True
    mock_cap.release.assert_called_once()


def test_check_rtsp_online_false():
    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_cv2.VideoCapture.return_value = mock_cap
    mock_cv2.CAP_PROP_OPEN_TIMEOUT_MSEC = 0

    with patch.dict(sys.modules, {"cv2": mock_cv2}):
        from app.services import camera_service
        import importlib
        importlib.reload(camera_service)
        result = camera_service.check_rtsp_online("rtsp://bad/stream")

    assert result is False


def test_capture_rtsp_frame_success():
    fake_frame = MagicMock()
    fake_buf = MagicMock()
    fake_buf.tobytes.return_value = b"jpeg_data"

    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, fake_frame)
    mock_cv2.VideoCapture.return_value = mock_cap
    mock_cv2.imencode.return_value = (True, fake_buf)
    mock_cv2.IMWRITE_JPEG_QUALITY = 1

    with patch.dict(sys.modules, {"cv2": mock_cv2}):
        from app.services import camera_service
        import importlib
        importlib.reload(camera_service)
        result = camera_service.capture_rtsp_frame("rtsp://test/stream")

    assert result == b"jpeg_data"


def test_capture_rtsp_frame_not_opened():
    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_cv2.VideoCapture.return_value = mock_cap

    with patch.dict(sys.modules, {"cv2": mock_cv2}):
        from app.services import camera_service
        import importlib
        importlib.reload(camera_service)
        result = camera_service.capture_rtsp_frame("rtsp://bad/stream")

    assert result is None


def test_capture_rtsp_frame_read_fails():
    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)
    mock_cv2.VideoCapture.return_value = mock_cap

    with patch.dict(sys.modules, {"cv2": mock_cv2}):
        from app.services import camera_service
        import importlib
        importlib.reload(camera_service)
        result = camera_service.capture_rtsp_frame("rtsp://bad/stream")

    assert result is None


# ── storage_service ───────────────────────────────────────────────────────────

def test_save_bytes_local():
    storage_root = Path(__file__).resolve().parent.parent / ".test-storage" / "services" / uuid.uuid4().hex
    storage_root.mkdir(parents=True, exist_ok=True)
    with patch("app.core.config.settings.STORAGE_TYPE", "local"), \
         patch("app.core.config.settings.STORAGE_PATH", str(storage_root)):
        from app.services import storage_service
        import importlib
        importlib.reload(storage_service)
        camera_id = uuid.uuid4().hex
        path = storage_service.save_bytes(b"fake_image", camera_id)

    assert path.endswith(".jpg")
    assert camera_id in path


def test_save_bytes_s3():
    mock_boto3 = MagicMock()
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    with patch("app.core.config.settings.STORAGE_TYPE", "s3"), \
         patch("app.core.config.settings.S3_ENDPOINT", "http://minio"), \
         patch("app.core.config.settings.S3_ACCESS_KEY", "key"), \
         patch("app.core.config.settings.S3_SECRET_KEY", "secret"), \
         patch("app.core.config.settings.S3_BUCKET", "frames"), \
         patch.dict(sys.modules, {"boto3": mock_boto3}):
        from app.services import storage_service
        import importlib
        importlib.reload(storage_service)
        path = storage_service.save_bytes(b"img", "cam123")

    assert mock_s3.put_object.called
    assert path.endswith(".jpg")


def test_get_url_local():
    with patch("app.core.config.settings.STORAGE_TYPE", "local"):
        from app.services import storage_service
        url = storage_service.get_url("cameras/abc/img.jpg")
    assert url.startswith("/api/images/")


def test_get_url_s3():
    with patch("app.core.config.settings.STORAGE_TYPE", "s3"), \
         patch("app.core.config.settings.S3_ENDPOINT", "https://r2.test"), \
         patch("app.core.config.settings.S3_BUCKET", "mybucket"):
        from app.services import storage_service
        url = storage_service.get_url("cameras/abc/img.jpg")
    assert "mybucket" in url


def test_delete_file_local_existing():
    target_dir = Path(__file__).resolve().parent.parent / ".test-storage" / "services" / uuid.uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "img.jpg"
    target.write_bytes(b"data")

    with patch("app.core.config.settings.STORAGE_TYPE", "local"), \
         patch("app.core.config.settings.STORAGE_PATH", str(target_dir)):
        from app.services import storage_service
        storage_service.delete_file("img.jpg")

    assert not target.exists()


def test_delete_file_local_missing():
    storage_root = Path(__file__).resolve().parent.parent / ".test-storage" / "services" / uuid.uuid4().hex
    storage_root.mkdir(parents=True, exist_ok=True)
    with patch("app.core.config.settings.STORAGE_TYPE", "local"), \
         patch("app.core.config.settings.STORAGE_PATH", str(storage_root)):
        from app.services import storage_service
        storage_service.delete_file("nope.jpg")  # should not raise


# ── retention_cleaner ─────────────────────────────────────────────────────────

def test_clean_old_occurrences_removes_expired(db):
    """clean_old_occurrences deletes expired records and leaves fresh ones."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.occurrence import Occurrence

    plan = Plan(name="P", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)

    tenant = Client(name="T", email="t@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)

    cam = Camera(client_id=tenant.id, name="C", location="L",
                 connection_type=ConnectionType.rtsp,
                 rtsp_url="rtsp://x/s", is_active=True)
    db.add(cam); db.commit(); db.refresh(cam)

    now = datetime.now(timezone.utc)
    expired_occ = Occurrence(camera_id=cam.id, plate="OLD", confidence=0.9,
                              image_path="cameras/old.jpg", expires_at=now - timedelta(days=1))
    fresh_occ = Occurrence(camera_id=cam.id, plate="NEW", confidence=0.9,
                            image_path="cameras/new.jpg", expires_at=now + timedelta(days=10))
    no_expiry_occ = Occurrence(camera_id=cam.id, plate="NONE", confidence=0.9,
                                image_path="cameras/none.jpg", expires_at=None)
    db.add_all([expired_occ, fresh_occ, no_expiry_occ])
    db.commit()

    with patch("app.core.database.SessionLocal", return_value=db), \
         patch("app.services.storage_service.delete_file"):
        from app.workers import retention_cleaner
        import importlib
        importlib.reload(retention_cleaner)
        retention_cleaner.clean_old_occurrences()

    remaining = db.query(Occurrence).all()
    plates = {o.plate for o in remaining}
    assert "OLD" not in plates
    assert "NEW" in plates
    assert "NONE" in plates


# ── frame_processor (process_frame task body) ─────────────────────────────────

def test_process_frame_cria_ocorrencia(db):
    """process_frame creates an Occurrence when OCR finds a plate."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.occurrence import Occurrence
    from app.core.database import engine
    from sqlalchemy.orm import sessionmaker
    import base64

    plan = Plan(name="P2", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)

    tenant = Client(name="T2", email="t2@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)

    cam = Camera(client_id=tenant.id, name="C2", location="L2",
                 connection_type=ConnectionType.rtsp,
                 rtsp_url="rtsp://x/s2", is_active=True)
    db.add(cam); db.commit(); db.refresh(cam)

    frame_b64 = base64.b64encode(b"fake_frame").decode()

    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value = {"plate": "XYZ5678", "confidence": 0.95}
    worker_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with patch("app.core.database.SessionLocal", worker_session), \
         patch("app.services.ocr_service.recognizer", mock_recognizer), \
         patch("app.services.storage_service.save_bytes", return_value="cameras/test/img.jpg"), \
         patch("app.services.alert_service.process_alerts"):
        from app.workers import frame_processor
        import importlib
        importlib.reload(frame_processor)
        frame_processor.process_frame(str(cam.id), frame_b64)

    occ = db.query(Occurrence).filter(Occurrence.plate == "XYZ5678").first()
    assert occ is not None
    assert occ.camera_id == cam.id


def test_process_frame_ocr_none_nao_cria(db):
    """process_frame skips when OCR returns None."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.occurrence import Occurrence
    import base64

    plan = Plan(name="P3", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)
    tenant = Client(name="T3", email="t3@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)
    cam = Camera(client_id=tenant.id, name="C3", location="L3",
                 connection_type=ConnectionType.rtsp, rtsp_url="rtsp://x/s3", is_active=True)
    db.add(cam); db.commit(); db.refresh(cam)

    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value = None

    with patch("app.core.database.SessionLocal", return_value=db), \
         patch("app.services.ocr_service.recognizer", mock_recognizer):
        from app.workers import frame_processor
        import importlib
        importlib.reload(frame_processor)
        frame_processor.process_frame(str(cam.id), base64.b64encode(b"x").decode())

    assert db.query(Occurrence).count() == 0


def test_preview_telemetry_record_and_read(monkeypatch):
    """Preview telemetry should track recent stream frames and status."""
    from app.services import preview_telemetry_service as telemetry_service

    class FakePipeline:
        def __init__(self, store: dict[str, list[tuple[str, float]]], key: str) -> None:
            self.store = store
            self.key = key
            self.ops: list[tuple[str, tuple]] = []

        def zadd(self, key: str, values: dict[str, float]):
            self.ops.append(("zadd", (key, values)))
            return self

        def zremrangebyscore(self, key: str, min_score: float, max_score: float):
            self.ops.append(("zremrangebyscore", (key, min_score, max_score)))
            return self

        def expire(self, key: str, ttl: int):
            self.ops.append(("expire", (key, ttl)))
            return self

        def zcard(self, key: str):
            self.ops.append(("zcard", (key,)))
            return self

        def zrevrange(self, key: str, start: int, stop: int, withscores: bool = False):
            self.ops.append(("zrevrange", (key, start, stop, withscores)))
            return self

        def execute(self):
            result = []
            for op, args in self.ops:
                if op == "zadd":
                    key, values = args
                    bucket = self.store.setdefault(key, [])
                    for member, score in values.items():
                        bucket.append((member, float(score)))
                    bucket.sort(key=lambda item: item[1])
                    result.append(None)
                elif op == "zremrangebyscore":
                    key, min_score, max_score = args
                    bucket = self.store.setdefault(key, [])
                    self.store[key] = [
                        item for item in bucket if not (float(min_score) <= item[1] <= float(max_score))
                    ]
                    result.append(None)
                elif op == "expire":
                    result.append(True)
                elif op == "zcard":
                    key = args[0]
                    result.append(len(self.store.get(key, [])))
                elif op == "zrevrange":
                    key, start, stop, withscores = args
                    bucket = sorted(self.store.get(key, []), key=lambda item: item[1], reverse=True)
                    selected = bucket[start : stop + 1 if stop >= 0 else None]
                    if withscores:
                        result.append(selected)
                    else:
                        result.append([member for member, _ in selected])
            self.ops.clear()
            return result

    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, list[tuple[str, float]]] = {}

        def pipeline(self):
            return FakePipeline(self.store, "")

    fake_redis = FakeRedis()
    monkeypatch.setattr(telemetry_service, "_redis_client", lambda: fake_redis)
    monkeypatch.setattr(telemetry_service, "time", lambda: 1000.0)

    telemetry_service.record_preview_frame("cam-1")
    telemetry_service.record_preview_frame("cam-1")

    metrics = telemetry_service.get_preview_telemetry("cam-1", is_online=True)
    assert metrics.preview_frames_last_minute == 2
    assert metrics.preview_fps == 0.03
    assert metrics.preview_status == "streaming"
    assert metrics.preview_latency_seconds == 0.0
