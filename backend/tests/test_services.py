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
from PIL import Image


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


def test_crop_roi_frame_reduz_imagem():
    from app.services.camera_service import crop_roi_frame

    image = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format="JPEG")

    cropped = crop_roi_frame(buf.getvalue(), 0.25, 0.25, 0.5, 0.5)
    result = Image.open(io.BytesIO(cropped))

    assert result.size == (50, 50)


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


def test_process_frame_usa_roi_da_camera(db):
    """process_frame should crop the configured ROI before OCR and vehicle detection."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.core.database import engine
    from sqlalchemy.orm import sessionmaker
    import base64

    plan = Plan(name="P4", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)

    tenant = Client(name="T4", email="t4@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)

    cam = Camera(
        client_id=tenant.id,
        name="C4",
        location="L4",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://x/s4",
        is_active=True,
        roi_x=0.1,
        roi_y=0.2,
        roi_width=0.4,
        roi_height=0.5,
    )
    db.add(cam); db.commit(); db.refresh(cam)

    frame_b64 = base64.b64encode(b"fake_frame").decode()
    worker_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value = {"plate": "ROI1234", "confidence": 0.9}
    mock_vehicle_detector = MagicMock()
    mock_vehicle_detector.best_detection.return_value = None

    with patch("app.core.database.SessionLocal", worker_session), \
         patch("app.services.camera_service.crop_roi_frame", return_value=b"roi_frame") as mock_crop, \
         patch("app.services.ocr_service.recognizer", mock_recognizer), \
         patch("app.services.vehicle_detection_service.vehicle_detector", mock_vehicle_detector), \
         patch("app.services.storage_service.save_bytes", return_value="cameras/test/roi.jpg") as mock_save, \
         patch("app.services.alert_service.process_alerts"):
        from app.workers import frame_processor
        import importlib
        importlib.reload(frame_processor)
        frame_processor.process_frame(str(cam.id), frame_b64)

    mock_crop.assert_called_once()
    mock_vehicle_detector.best_detection.assert_called_once_with(b"roi_frame")
    mock_recognizer.recognize.assert_called_once_with(b"roi_frame", camera_id=str(cam.id))
    assert mock_save.call_args is not None
    assert mock_save.call_args.args[0] == b"roi_frame"


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


def test_image_quality_record_and_read(monkeypatch):
    """Image quality telemetry should be persisted and read back from Redis."""
    from app.services import image_quality_service as quality_service

    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}

        def set(self, key: str, value: str, ex: int | None = None):
            self.store[key] = value
            return True

        def get(self, key: str):
            return self.store.get(key)

    fake_redis = FakeRedis()
    monkeypatch.setattr(quality_service, "_redis_client", lambda: fake_redis)
    monkeypatch.setattr(
        quality_service,
        "analyze_image_quality",
        lambda _image_bytes: quality_service.ImageQuality(
            quality_score=72.5,
            quality_label="good",
            blur_score=28.0,
            brightness=58.0,
            contrast=18.0,
        ),
    )

    quality_service.record_image_quality("cam-1", b"frame-bytes")
    metrics = quality_service.get_image_quality("cam-1")

    assert metrics.quality_score == 72.5
    assert metrics.quality_label == "good"
    assert metrics.blur_score == 28.0
    assert metrics.brightness == 58.0
    assert metrics.contrast == 18.0


def test_detector_health_reflete_status_e_qualidade():
    """Detector health should combine preview and image quality into one status."""
    from app.services.detector_health_service import build_detector_health
    from app.services.image_quality_service import ImageQuality
    from app.services.preview_telemetry_service import PreviewTelemetry

    healthy = build_detector_health(
        True,
        PreviewTelemetry(2.5, 150, 1234.0, 1.2, "streaming"),
        ImageQuality(82.0, "good", 25.0, 55.0, 18.0),
    )
    warning = build_detector_health(
        True,
        PreviewTelemetry(2.5, 150, 1234.0, 1.2, "streaming"),
        ImageQuality(32.0, "poor", 10.0, 40.0, 12.0),
    )
    offline = build_detector_health(
        False,
        PreviewTelemetry(0.0, 0, None, None, "offline"),
        ImageQuality(0.0, "unknown", 0.0, 0.0, 0.0),
    )

    assert healthy.detector_status == "healthy"
    assert healthy.detector_health_score == 100.0
    assert warning.detector_status == "warning"
    assert warning.detector_health_score == 45.0
    assert offline.detector_status == "offline"
    assert offline.detector_health_score == 0.0


def test_camera_health_alert_publica_e_aplica_cooldown(monkeypatch):
    """Camera health alerts should publish once and then respect cooldown for same status."""
    from app.services import camera_health_alert_service as alert_service
    from app.services.image_quality_service import ImageQuality
    from app.services.preview_telemetry_service import PreviewTelemetry

    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}
            self.published: list[tuple[str, str]] = []

        def get(self, key: str):
            return self.store.get(key)

        def set(self, key: str, value: str, ex: int | None = None):
            self.store[key] = value
            return True

        def publish(self, channel: str, message: str):
            self.published.append((channel, message))
            return 1

    class CameraStub:
        id = "cam-1"
        client_id = "client-1"
        name = "Cam Principal"
        location = "Entrada"
        is_online = True

    fake_redis = FakeRedis()
    monkeypatch.setattr(alert_service, "_redis_client", lambda: fake_redis)
    monkeypatch.setattr(
        alert_service,
        "get_preview_telemetry",
        lambda *_args, **_kwargs: PreviewTelemetry(1.5, 90, 1234.0, 0.8, "streaming"),
    )
    monkeypatch.setattr(
        alert_service,
        "get_image_quality",
        lambda *_args, **_kwargs: ImageQuality(31.0, "poor", 8.0, 42.0, 10.0),
    )

    first = alert_service.maybe_publish_camera_health_alert(CameraStub())
    second = alert_service.maybe_publish_camera_health_alert(CameraStub())

    assert first is True
    assert second is False
    assert len(fake_redis.published) == 1
    assert fake_redis.published[0][0] == "ws:alerts:client-1"


def test_worker_delay_alert_publica_e_aplica_cooldown(db, monkeypatch):
    """Worker delay alerts should publish once and then respect cooldown for same queue depth."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.services import worker_delay_alert_service as alert_service

    plan = Plan(
        name="P-worker",
        max_cameras=5,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=0,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    tenant = Client(name="Worker", email="worker@test.com", plan_id=plan.id, is_active=True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    camera = Camera(
        client_id=tenant.id,
        name="Cam Worker",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://example/stream",
        is_active=True,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)

    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}
            self.published: list[tuple[str, str]] = []

        def llen(self, key: str) -> int:
            return 25 if key == "frames" else 0

        def get(self, key: str):
            return self.store.get(key)

        def set(self, key: str, value: str, ex: int | None = None):
            self.store[key] = value
            return True

        def publish(self, channel: str, message: str):
            self.published.append((channel, message))
            return 1

    fake_redis = FakeRedis()
    monkeypatch.setattr(alert_service, "_redis_client", lambda: fake_redis)
    monkeypatch.setattr(alert_service, "time", lambda: 1000.0)

    first = alert_service.maybe_publish_worker_delay_alert(db)
    second = alert_service.maybe_publish_worker_delay_alert(db)

    assert first is True
    assert second is False
    assert len(fake_redis.published) == 1
    channel, payload = fake_redis.published[0]
    assert channel == f"ws:alerts:{tenant.id}"
    assert "worker_delay_alert" in payload


def test_operational_metrics_resume_saude_do_painel(db, monkeypatch):
    """Operational metrics should aggregate preview and queue health for the dashboard."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    from app.services import operational_metrics_service as ops_service
    from app.services.image_quality_service import ImageQuality
    from app.services.preview_telemetry_service import PreviewTelemetry

    plan = Plan(
        name="P-ops",
        max_cameras=5,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=0,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    tenant = Client(name="Ops", email="ops@test.com", plan_id=plan.id, is_active=True)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    camera = Camera(
        client_id=tenant.id,
        name="Cam Ops",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://example/stream",
        is_active=True,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)

    admin = User(
        email="ops@sistema.com",
        name="Ops",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    class FakeRedis:
        def llen(self, key: str):
            return 3 if key == "frames" else 0

    monkeypatch.setattr(ops_service, "_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(
        ops_service,
        "get_preview_telemetry",
        lambda *_args, **_kwargs: PreviewTelemetry(2.4, 144, 1234.0, 1.8, "streaming"),
    )
    monkeypatch.setattr(
        ops_service,
        "get_image_quality",
        lambda *_args, **_kwargs: ImageQuality(84.0, "good", 26.0, 56.0, 20.0),
    )

    metrics = ops_service.build_operational_metrics(db, admin)

    assert metrics.total_cameras == 1
    assert metrics.online_cameras == 1
    assert metrics.streaming_cameras == 1
    assert metrics.degraded_cameras == 0
    assert metrics.low_quality_cameras == 0
    assert metrics.queue_depth == 3
    assert metrics.operational_status == "healthy"
