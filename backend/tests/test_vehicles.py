import csv
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

from app.core.security import create_access_token
from app.core.security import hash_password
from app.models.camera import Camera, ConnectionType
from app.models.client import Client
from app.models.plan import Plan
from app.models.user import User, UserRole


def _auth_header(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role})}"}


def _make_vehicle_image() -> bytes:
    img = Image.new("RGB", (1280, 720), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((420, 340, 900, 610), outline=(0, 0, 0), width=10, fill=(35, 35, 35))
    draw.rectangle((450, 370, 870, 585), fill=(245, 245, 245))
    draw.rectangle((500, 520, 610, 620), fill=(30, 30, 30))
    draw.rectangle((710, 520, 820, 620), fill=(30, 30, 30))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def test_vehicle_detector_identifica_veiculo_sintetico():
    from app.services.vehicle_detection_service import VehicleDetector

    detector = VehicleDetector()
    detections = detector.detect(_make_vehicle_image())

    assert detections
    best = detections[0]
    assert best.vehicle_type in {"car", "motorcycle", "truck"}
    assert best.confidence >= 0.5
    assert best.crop_bytes


def test_vehicle_stats_endpoint_conta_por_tipo(client, db):
    from app.models.vehicle_event import VehicleEvent

    suffix = uuid.uuid4().hex[:8]
    plan = Plan(
        name=f"Plano-{suffix}",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=99.90,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    tenant = Client(
        name=f"Cliente-{suffix}",
        email=f"cliente-{suffix}@test.com",
        plan_id=plan.id,
        is_active=True,
    )
    db.add(tenant)
    db.flush()

    camera = Camera(
        client_id=tenant.id,
        name=f"Cam-{suffix}",
        location="Entrada",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://test/stream",
        is_active=True,
    )
    db.add(camera)
    db.flush()

    super_admin = User(
        email=f"sa-{suffix}@sistema.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(super_admin)
    db.add_all(
        [
            VehicleEvent(
                camera_id=camera.id,
                vehicle_type="car",
                confidence=0.9,
                bbox_x=10,
                bbox_y=20,
                bbox_w=100,
                bbox_h=80,
                detected_at=datetime.now(timezone.utc),
            ),
            VehicleEvent(
                camera_id=camera.id,
                vehicle_type="motorcycle",
                confidence=0.85,
                bbox_x=20,
                bbox_y=30,
                bbox_w=60,
                bbox_h=45,
                detected_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()

    r = client.get("/api/vehicles/stats", headers=_auth_header(super_admin))
    assert r.status_code == 200
    data = r.json()
    assert data["total_today"] >= 2
    assert any(item["vehicle_type"] == "car" for item in data["by_type"])
    assert any(item["vehicle_type"] == "motorcycle" for item in data["by_type"])
    assert data["latest_event"] is not None
    assert data["latest_event"]["camera_name"] == camera.name
    assert data["latest_event"]["vehicle_type"] in {"car", "motorcycle"}


def test_vehicle_export_endpoint_retorna_csv(client, db):
    from app.models.vehicle_event import VehicleEvent

    suffix = uuid.uuid4().hex[:8]
    plan = Plan(
        name=f"Plano-{suffix}",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=99.90,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    tenant = Client(
        name=f"Cliente-{suffix}",
        email=f"cliente-{suffix}@test.com",
        plan_id=plan.id,
        is_active=True,
    )
    db.add(tenant)
    db.flush()

    camera = Camera(
        client_id=tenant.id,
        name=f"Cam-{suffix}",
        location="Entrada",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://test/stream",
        is_active=True,
    )
    db.add(camera)
    db.flush()

    super_admin = User(
        email=f"sa-export-{suffix}@sistema.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(super_admin)
    db.add(
        VehicleEvent(
            camera_id=camera.id,
            vehicle_type="truck",
            confidence=0.88,
            bbox_x=15,
            bbox_y=25,
            bbox_w=120,
            bbox_h=90,
            detected_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    r = client.get("/api/vehicles/export", headers=_auth_header(super_admin))
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "vehicle_events_" in r.headers["content-disposition"]

    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["Camera"] == camera.name
    assert rows[0]["Tipo"] == "truck"
    assert rows[0]["Confiança (%)"] == "88.0"


def test_vehicle_list_endpoint_retorna_historico_paginado(client, db):
    from app.models.vehicle_event import VehicleEvent

    suffix = uuid.uuid4().hex[:8]
    plan = Plan(
        name=f"Plano-{suffix}",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=99.90,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    tenant = Client(
        name=f"Cliente-{suffix}",
        email=f"cliente-{suffix}@test.com",
        plan_id=plan.id,
        is_active=True,
    )
    db.add(tenant)
    db.flush()

    camera = Camera(
        client_id=tenant.id,
        name=f"Cam-{suffix}",
        location="Entrada",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://test/stream",
        is_active=True,
    )
    db.add(camera)
    db.flush()

    super_admin = User(
        email=f"sa-list-{suffix}@sistema.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(super_admin)
    db.add_all(
        [
            VehicleEvent(
                camera_id=camera.id,
                vehicle_type="car",
                confidence=0.93,
                bbox_x=12,
                bbox_y=24,
                bbox_w=110,
                bbox_h=90,
                image_path=f"cameras/{camera.id}/car.jpg",
                detected_at=datetime.now(timezone.utc),
            ),
            VehicleEvent(
                camera_id=camera.id,
                vehicle_type="truck",
                confidence=0.88,
                bbox_x=20,
                bbox_y=30,
                bbox_w=140,
                bbox_h=100,
                image_path=f"cameras/{camera.id}/truck.jpg",
                detected_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()

    r = client.get(
        "/api/vehicles?vehicle_type=truck&limit=1&page=1",
        headers=_auth_header(super_admin),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["pages"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["vehicle_type"] == "truck"
    assert item["camera"]["name"] == camera.name
    assert item["image_url"].endswith(f"cameras/{camera.id}/truck.jpg")


def test_process_frame_usa_recorte_do_veiculo(db, camera_agent_a):
    from app.core.database import SessionLocal
    from app.workers import frame_processor
    from app.models.occurrence import Occurrence
    from app.models.vehicle_event import VehicleEvent

    frame_bytes = _make_vehicle_image()
    fake_detection = MagicMock()
    fake_detection.crop_bytes = b"vehicle-crop"
    fake_detection.vehicle_type = "car"
    fake_detection.confidence = 0.91
    fake_detection.bbox_x = 10
    fake_detection.bbox_y = 20
    fake_detection.bbox_w = 100
    fake_detection.bbox_h = 80

    mock_query = patch("app.services.vehicle_detection_service.vehicle_detector.best_detection", return_value=fake_detection)
    mock_recognizer = patch("app.services.ocr_service.recognizer.recognize", return_value={"plate": "ABC1234", "confidence": 0.95, "engine": "easyocr"})
    mock_save = patch("app.services.storage_service.save_bytes", return_value="cameras/test/crop.jpg")
    mock_alerts = patch("app.services.alert_service.process_alerts")
    mock_redis = patch("redis.from_url")

    fake_redis = MagicMock()
    fake_redis.set.return_value = True
    worker_db = SessionLocal()
    try:
        with patch("app.core.database.SessionLocal", return_value=worker_db), mock_query, mock_recognizer as recognizer_mock, mock_save, mock_alerts, mock_redis as redis_from_url:
            redis_from_url.return_value = fake_redis
            frame_processor.process_frame.run(str(camera_agent_a.id), __import__("base64").b64encode(frame_bytes).decode())

        recognizer_mock.assert_called_once()
        assert recognizer_mock.call_args.args[0] == b"vehicle-crop"
        assert db.query(VehicleEvent).count() == 1
        occ = db.query(Occurrence).first()
        assert occ is not None
        assert occ.vehicle_type == "car"
    finally:
        worker_db.close()


def test_process_frame_ignora_frame_repetido(db, camera_agent_a):
    from app.core.database import SessionLocal
    from app.workers import frame_processor

    frame_bytes = _make_vehicle_image()
    frame_b64 = __import__("base64").b64encode(frame_bytes).decode()

    mock_vehicle_detector = MagicMock()
    fake_detection = MagicMock()
    fake_detection.crop_bytes = b"vehicle-crop"
    fake_detection.vehicle_type = "car"
    fake_detection.confidence = 0.91
    fake_detection.bbox_x = 10
    fake_detection.bbox_y = 20
    fake_detection.bbox_w = 100
    fake_detection.bbox_h = 80
    mock_vehicle_detector.best_detection.return_value = fake_detection
    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value = {"plate": "ABC1234", "confidence": 0.95, "engine": "easyocr"}

    fake_cache_state: dict[str, str] = {}

    class FakeRedis:
        def get(self, key: str):
            return fake_cache_state.get(key)

        def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
            fake_cache_state[key] = value
            return True

    worker_db = SessionLocal()
    try:
        with (
            patch("app.core.database.SessionLocal", return_value=worker_db),
            patch("app.services.vehicle_detection_service.vehicle_detector", mock_vehicle_detector),
            patch("app.services.ocr_service.recognizer", mock_recognizer),
            patch("app.services.storage_service.save_bytes", return_value="cameras/test/repeat.jpg"),
            patch("app.services.alert_service.process_alerts"),
            patch("app.services.preview_telemetry_service.record_preview_frame"),
            patch("app.services.image_quality_service.record_image_quality"),
            patch("app.services.ocr_pipeline_metrics_service.record_ocr_pipeline_metrics"),
            patch("app.services.ocr_pipeline_alert_service.maybe_publish_ocr_pipeline_alert"),
            patch("app.services.camera_health_alert_service.maybe_publish_camera_health_alert"),
            patch("app.services.worker_delay_alert_service.maybe_publish_worker_delay_alert"),
            patch("redis.from_url", return_value=FakeRedis()),
        ):
            frame_processor.process_frame.run(str(camera_agent_a.id), frame_b64)
            frame_processor.process_frame.run(str(camera_agent_a.id), frame_b64)

        assert mock_vehicle_detector.best_detection.call_count == 1
        assert mock_recognizer.recognize.call_count == 1
    finally:
        worker_db.close()


def test_process_frame_sem_veiculo_nao_chama_ocr(db, camera_agent_a):
    from app.core.database import SessionLocal
    from app.workers import frame_processor

    frame_bytes = _make_vehicle_image()
    frame_b64 = __import__("base64").b64encode(frame_bytes).decode()

    mock_vehicle_detector = MagicMock()
    mock_vehicle_detector.best_detection.return_value = None
    mock_recognizer = MagicMock()

    worker_db = SessionLocal()
    try:
        with (
            patch("app.core.database.SessionLocal", return_value=worker_db),
            patch("app.services.vehicle_detection_service.vehicle_detector", mock_vehicle_detector),
            patch("app.services.ocr_service.recognizer", mock_recognizer),
            patch("app.services.preview_telemetry_service.record_preview_frame"),
            patch("app.services.image_quality_service.record_image_quality"),
            patch("app.services.ocr_pipeline_metrics_service.record_ocr_pipeline_metrics"),
            patch("app.services.ocr_pipeline_alert_service.maybe_publish_ocr_pipeline_alert"),
            patch("app.services.camera_health_alert_service.maybe_publish_camera_health_alert"),
            patch("app.services.worker_delay_alert_service.maybe_publish_worker_delay_alert"),
        ):
            frame_processor.process_frame.run(str(camera_agent_a.id), frame_b64)

        mock_vehicle_detector.best_detection.assert_called_once()
        mock_recognizer.recognize.assert_not_called()
    finally:
        worker_db.close()


def test_process_frame_nao_duplica_veiculo_parado(db, camera_agent_a):
    from app.core.database import SessionLocal
    from app.workers import frame_processor
    from app.models.vehicle_event import VehicleEvent

    frame_one = _make_vehicle_image()
    frame_two = _make_vehicle_image()

    fake_detection = MagicMock()
    fake_detection.crop_bytes = b"vehicle-crop"
    fake_detection.vehicle_type = "truck"
    fake_detection.confidence = 0.91
    fake_detection.bbox_x = 10
    fake_detection.bbox_y = 20
    fake_detection.bbox_w = 100
    fake_detection.bbox_h = 80

    mock_query = patch("app.services.vehicle_detection_service.vehicle_detector.best_detection", return_value=fake_detection)
    mock_recognizer = patch("app.services.ocr_service.recognizer.recognize", return_value=None)
    fake_cache_state: dict[str, str] = {}

    class FakeRedis:
        def get(self, key: str):
            return fake_cache_state.get(key)

        def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
            fake_cache_state[key] = value
            return True

    worker_db = SessionLocal()
    try:
        with (
            patch("app.core.database.SessionLocal", return_value=worker_db),
            mock_query,
            mock_recognizer,
            patch("redis.from_url", return_value=FakeRedis()),
            patch("app.services.preview_telemetry_service.record_preview_frame"),
            patch("app.services.image_quality_service.record_image_quality"),
            patch("app.services.ocr_pipeline_metrics_service.record_ocr_pipeline_metrics"),
            patch("app.services.ocr_pipeline_alert_service.maybe_publish_ocr_pipeline_alert"),
            patch("app.services.camera_health_alert_service.maybe_publish_camera_health_alert"),
            patch("app.services.worker_delay_alert_service.maybe_publish_worker_delay_alert"),
        ):
            frame_processor.process_frame.run(str(camera_agent_a.id), __import__("base64").b64encode(frame_one).decode())
            frame_processor.process_frame.run(str(camera_agent_a.id), __import__("base64").b64encode(frame_two).decode())

        assert db.query(VehicleEvent).count() == 1
    finally:
        worker_db.close()
