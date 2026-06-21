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


def _fake_yolo_output(class_id: int, score: float = 0.9):
    """Saída YOLOv8 [1,84,8400] com uma única detecção centralizada (640x640)."""
    import numpy as np

    out = np.zeros((1, 84, 8400), dtype=np.float32)
    # anchor 0: cx,cy,w,h no espaço 640 (carro central de uma imagem 1280x720)
    out[0, 0, 0] = 320.0
    out[0, 1, 0] = 320.0
    out[0, 2, 0] = 240.0
    out[0, 3, 0] = 135.0
    out[0, 4 + class_id, 0] = score
    return out


def _mock_onnxruntime(output):
    """sys.modules patch p/ onnxruntime devolvendo `output` em session.run."""
    import types
    from unittest.mock import MagicMock

    mod = types.ModuleType("onnxruntime")
    session = MagicMock()
    session.run.return_value = [output]
    inp = MagicMock()
    inp.name = "images"
    session.get_inputs.return_value = [inp]
    mod.InferenceSession = MagicMock(return_value=session)
    mod.SessionOptions = MagicMock(return_value=MagicMock())
    return mod


def test_vehicle_detector_detecta_carro_via_onnx():
    """Mock do YOLOv8 ONNX → detecção classificada como 'car'."""
    import sys
    from unittest.mock import patch

    from app.services.vehicle_detection_service import VehicleDetector

    detector = VehicleDetector()
    mock_ort = _mock_onnxruntime(_fake_yolo_output(class_id=2))  # COCO 2 = car
    with patch.dict(sys.modules, {"onnxruntime": mock_ort}), \
         patch("os.path.exists", return_value=True):
        detections = detector.detect(_make_vehicle_image())

    assert detections
    best = detections[0]
    assert best.vehicle_type == "car"
    assert best.confidence >= 0.5
    assert best.crop_bytes
    assert best.bbox_w > 0 and best.bbox_h > 0


def test_vehicle_detector_mapeia_truck_e_motorcycle():
    """Classes COCO 7/3 mapeiam para truck/motorcycle."""
    import sys
    from unittest.mock import patch

    from app.services.vehicle_detection_service import VehicleDetector

    for class_id, expected in ((7, "truck"), (3, "motorcycle")):
        detector = VehicleDetector()
        mock_ort = _mock_onnxruntime(_fake_yolo_output(class_id=class_id))
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}), \
             patch("os.path.exists", return_value=True):
            best = detector.best_detection(_make_vehicle_image())
        assert best is not None
        assert best.vehicle_type == expected


def test_vehicle_detector_modo_degradado_sem_modelo():
    """Sem modelo disponível → devolve o frame inteiro p/ o OCR tentar."""
    from app.services.vehicle_detection_service import VehicleDetector

    detector = VehicleDetector()
    detector._unavailable = True  # noqa: SLF001 — simula ausência do modelo
    best = detector.best_detection(_make_vehicle_image())

    assert best is not None
    assert best.vehicle_type == "unknown"
    assert best.crop_bytes


def test_detector_reconhece_pessoa_e_animal():
    """Classes COCO 0/16 mapeiam para category person/animal com o label correto."""
    import sys
    from unittest.mock import patch

    from app.services.vehicle_detection_service import VehicleDetector

    for class_id, exp_cat, exp_label in ((0, "person", "person"), (16, "animal", "dog")):
        detector = VehicleDetector()
        mock_ort = _mock_onnxruntime(_fake_yolo_output(class_id=class_id))
        with patch.dict(sys.modules, {"onnxruntime": mock_ort}), \
             patch("os.path.exists", return_value=True):
            best = detector.best_detection(_make_vehicle_image())
        assert best is not None, f"class {class_id} não detectada"
        assert best.category == exp_cat
        assert best.vehicle_type == exp_label


def _fake_yolo_two_boxes(
    box_a: tuple[float, float, float, float],
    class_a: int,
    score_a: float,
    box_b: tuple[float, float, float, float],
    class_b: int,
    score_b: float,
):
    """Saída YOLOv8 [1,84,8400] com DUAS detecções (cx,cy,w,h no espaço 640)."""
    import numpy as np

    out = np.zeros((1, 84, 8400), dtype=np.float32)
    for anchor, (cx, cy, w, h), cls, score in (
        (0, box_a, class_a, score_a),
        (1, box_b, class_b, score_b),
    ):
        out[0, 0, anchor] = cx
        out[0, 1, anchor] = cy
        out[0, 2, anchor] = w
        out[0, 3, anchor] = h
        out[0, 4 + cls, anchor] = score
    return out


def test_detector_pessoa_e_cachorro_sobrepostos_ambos_detectados():
    """Pessoa + cachorro sobrepostos (pessoa passeando com o cão) → AMBOS detectados.

    Regressão: o NMS era class-agnostic e suprimia a caixa de classe diferente com
    menor confiança (o cachorro), sobrando só a pessoa no histórico.
    """
    import sys
    from unittest.mock import patch

    from app.services.vehicle_detection_service import VehicleDetector

    # Pessoa (alta conf) e cachorro (conf menor) com caixas sobrepostas (IoU > 0.45).
    person_box = (320.0, 300.0, 120.0, 260.0)
    dog_box = (330.0, 320.0, 130.0, 230.0)
    output = _fake_yolo_two_boxes(person_box, 0, 0.90, dog_box, 16, 0.70)

    detector = VehicleDetector()
    mock_ort = _mock_onnxruntime(output)
    with patch.dict(sys.modules, {"onnxruntime": mock_ort}), \
         patch("os.path.exists", return_value=True):
        detections = detector.detect(_make_vehicle_image())

    categories = {d.category for d in detections}
    assert "person" in categories, "pessoa deveria ser detectada"
    assert "animal" in categories, "cachorro (animal) sobreposto à pessoa não pode ser suprimido pelo NMS"


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


def test_crop_pequeno_e_ampliado_para_legibilidade():
    """Recortes pequenos (veículo distante) são ampliados; grandes ficam nativos."""
    import numpy as np

    from app.core.config import settings
    from app.services.vehicle_detection_service import VehicleDetector

    detector = VehicleDetector()
    img = np.zeros((1000, 1000, 3), dtype=np.uint8)

    small = detector._crop_with_padding(img, 100, 100, 140, 140, 1000, 1000)
    assert max(small.shape[0], small.shape[1]) >= settings.DETECTION_MIN_CROP_SIDE

    big = detector._crop_with_padding(img, 0, 0, 800, 800, 1000, 1000)
    # já é maior que o mínimo -> não amplia além do nativo
    assert max(big.shape[0], big.shape[1]) <= 1000


def test_stats_by_category_e_filtro(client, db, camera_rtsp_a, super_admin_user):
    from app.models.vehicle_event import VehicleEvent

    def _ev(category, label):
        return VehicleEvent(
            camera_id=camera_rtsp_a.id, category=category, vehicle_type=label,
            confidence=0.8, bbox_x=0, bbox_y=0, bbox_w=10, bbox_h=10,
        )

    db.add_all([_ev("vehicle", "car"), _ev("person", "person"), _ev("animal", "dog"), _ev("animal", "cat")])
    db.commit()
    h = _auth_header(super_admin_user)

    stats = client.get("/api/vehicles/stats", headers=h).json()
    by_cat = {c["category"]: c["count"] for c in stats["by_category"]}
    assert by_cat == {"vehicle": 1, "person": 1, "animal": 2}

    # stats?category=animal -> by_type por tipo de animal (Tarefa 4.1)
    animal_stats = client.get("/api/vehicles/stats?category=animal", headers=h).json()
    by_type = {t["vehicle_type"]: t["count"] for t in animal_stats["by_type"]}
    assert by_type == {"dog": 1, "cat": 1}

    # listagem filtrada por categoria (Tarefa 3.1)
    page = client.get("/api/vehicles?category=person", headers=h).json()
    assert page["total"] == 1
    assert len(page["items"]) == 1
    assert page["items"][0]["category"] == "person"


def test_stats_conta_companion_piloto_moto(client, db, camera_rtsp_a, super_admin_user):
    """T5: uma detecção moto+pessoa conta os dois nas estatísticas."""
    from app.models.vehicle_event import VehicleEvent

    # Um único registro: moto com piloto (pessoa) agrupado.
    db.add(
        VehicleEvent(
            camera_id=camera_rtsp_a.id,
            category="vehicle",
            vehicle_type="motorcycle",
            companion_category="person",
            companion_type="person",
            confidence=0.8,
            bbox_x=0,
            bbox_y=0,
            bbox_w=10,
            bbox_h=10,
        )
    )
    db.commit()
    h = _auth_header(super_admin_user)

    stats = client.get("/api/vehicles/stats", headers=h).json()
    by_cat = {c["category"]: c["count"] for c in stats["by_category"]}
    by_type = {t["vehicle_type"]: t["count"] for t in stats["by_type"]}
    # Um registro, mas conta moto E pessoa.
    assert by_cat.get("vehicle") == 1
    assert by_cat.get("person") == 1
    assert by_type.get("motorcycle") == 1
    assert by_type.get("person") == 1

    # listagem: um único item, exibindo o companion.
    page = client.get("/api/vehicles", headers=h).json()
    assert page["total"] == 1
    assert page["items"][0]["companion_type"] == "person"


def test_vehicle_list_endpoint_retorna_historico_paginado(client, db):
    from app.models.vehicle_event import VehicleEvent
    from app.models.occurrence import Occurrence

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
    occurrence = Occurrence(
        camera_id=camera.id,
        plate="ABC1234",
        image_path=f"cameras/{camera.id}/occ.jpg",
        confidence=0.95,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(occurrence)
    db.flush()
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
            VehicleEvent(
                camera_id=camera.id,
                vehicle_type="car",
                confidence=0.81,
                bbox_x=22,
                bbox_y=34,
                bbox_w=132,
                bbox_h=96,
                occurrence_id=occurrence.id,
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


def test_vehicle_list_endpoint_usa_imagem_da_ocorrencia_como_fallback(client, db):
    from app.models.vehicle_event import VehicleEvent
    from app.models.occurrence import Occurrence

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

    occurrence = Occurrence(
        camera_id=camera.id,
        plate="ABC1234",
        image_path=f"cameras/{camera.id}/occurrence.jpg",
        confidence=0.97,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(occurrence)
    db.flush()

    vehicle_event = VehicleEvent(
        camera_id=camera.id,
        occurrence_id=occurrence.id,
        vehicle_type="truck",
        confidence=0.88,
        bbox_x=20,
        bbox_y=30,
        bbox_w=140,
        bbox_h=100,
        image_path=None,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(vehicle_event)
    db.commit()

    super_admin = User(
        email=f"sa-fallback-{suffix}@sistema.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(super_admin)
    db.commit()

    r = client.get("/api/vehicles", headers=_auth_header(super_admin))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["image_url"].endswith(f"cameras/{camera.id}/occurrence.jpg")
    assert data["items"][0]["plate"] == "ABC1234"


def test_process_frame_usa_recorte_do_veiculo(db, camera_agent_a):
    from app.core.database import SessionLocal
    from app.workers import frame_processor
    from app.models.occurrence import Occurrence
    from app.models.vehicle_event import VehicleEvent

    frame_bytes = _make_vehicle_image()
    fake_detection = MagicMock()
    fake_detection.category = "vehicle"
    fake_detection.crop_bytes = b"vehicle-crop"
    fake_detection.vehicle_type = "car"
    fake_detection.confidence = 0.91
    fake_detection.bbox_x = 10
    fake_detection.bbox_y = 20
    fake_detection.bbox_w = 100
    fake_detection.bbox_h = 80

    mock_query = patch("app.services.vehicle_detection_service.vehicle_detector.detect", return_value=[fake_detection])
    mock_recognizer = patch("app.services.ocr_service.recognizer.recognize", return_value={"plate": "ABC1234", "confidence": 0.95, "engine": "easyocr"})
    mock_save = patch("app.services.storage_service.save_bytes", return_value="cameras/test/crop.jpg")
    mock_alerts = patch("app.services.alert_service.process_alerts")
    mock_redis = patch("redis.from_url")
    # Crop mockado (b"vehicle-crop") não decodifica -> a qualidade real ficaria
    # abaixo do gate de OCR. Este teste foca no uso do recorte, não na qualidade.
    mock_quality = patch("app.services.frame_quality_service.crop_quality", return_value=0.9)

    fake_redis = MagicMock()
    fake_redis.set.return_value = True
    worker_db = SessionLocal()
    try:
        with patch("app.core.database.SessionLocal", return_value=worker_db), mock_query, mock_recognizer as recognizer_mock, mock_save, mock_alerts, mock_quality, mock_redis as redis_from_url:
            redis_from_url.return_value = fake_redis
            frame_processor.process_frame.run(str(camera_agent_a.id), __import__("base64").b64encode(frame_bytes).decode())

            recognizer_mock.assert_called_once()
            assert recognizer_mock.call_args.args[0] == b"vehicle-crop"
            vehicle_event = db.query(VehicleEvent).first()
            assert vehicle_event is not None
            assert db.query(VehicleEvent).count() == 1
            assert vehicle_event.image_path == "cameras/test/crop.jpg"
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
    fake_detection.category = "vehicle"
    fake_detection.crop_bytes = b"vehicle-crop"
    fake_detection.vehicle_type = "car"
    fake_detection.confidence = 0.91
    fake_detection.bbox_x = 10
    fake_detection.bbox_y = 20
    fake_detection.bbox_w = 100
    fake_detection.bbox_h = 80
    mock_vehicle_detector.detect.return_value = [fake_detection]
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
            patch("app.services.frame_quality_service.crop_quality", return_value=0.9),
            patch("redis.from_url", return_value=FakeRedis()),
        ):
            frame_processor.process_frame.run(str(camera_agent_a.id), frame_b64)
            frame_processor.process_frame.run(str(camera_agent_a.id), frame_b64)

        assert mock_vehicle_detector.detect.call_count == 1
        assert mock_recognizer.recognize.call_count == 1
    finally:
        worker_db.close()


def test_process_frame_sem_veiculo_nao_chama_ocr(db, camera_agent_a):
    from app.core.database import SessionLocal
    from app.workers import frame_processor

    frame_bytes = _make_vehicle_image()
    frame_b64 = __import__("base64").b64encode(frame_bytes).decode()

    mock_vehicle_detector = MagicMock()
    mock_vehicle_detector.detect.return_value = []
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

        mock_vehicle_detector.detect.assert_called_once()
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
    fake_detection.category = "vehicle"
    fake_detection.crop_bytes = b"vehicle-crop"
    fake_detection.vehicle_type = "truck"
    fake_detection.confidence = 0.91
    fake_detection.bbox_x = 10
    fake_detection.bbox_y = 20
    fake_detection.bbox_w = 100
    fake_detection.bbox_h = 80

    mock_query = patch("app.services.vehicle_detection_service.vehicle_detector.detect", return_value=[fake_detection])
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


def test_vehicles_list_filtra_por_data(client, db, camera_rtsp_a, super_admin_user):
    """Filtro de data/hora em /api/vehicles (a pagina /detections envia ISO UTC)."""
    from datetime import timedelta
    from app.models.vehicle_event import VehicleEvent

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=2)

    def _ev(dt, label):
        return VehicleEvent(
            camera_id=camera_rtsp_a.id, category="vehicle", vehicle_type=label,
            confidence=0.8, bbox_x=0, bbox_y=0, bbox_w=10, bbox_h=10, detected_at=dt,
        )

    db.add_all([_ev(old, "car"), _ev(now, "truck")])
    db.commit()
    h = _auth_header(super_admin_user)

    # date_from = ontem -> só o evento recente (truck) entra.
    cutoff = (now - timedelta(days=1)).isoformat()
    r = client.get("/api/vehicles", params={"date_from": cutoff}, headers=h)
    assert r.status_code == 200
    types = [it["vehicle_type"] for it in r.json()["items"]]
    assert "truck" in types and "car" not in types

    # date_to = 3 dias atrás -> só o antigo (car) entra.
    upper = (now - timedelta(days=1)).isoformat()
    r2 = client.get("/api/vehicles", params={"date_to": upper}, headers=h)
    assert r2.status_code == 200
    types2 = [it["vehicle_type"] for it in r2.json()["items"]]
    assert "car" in types2 and "truck" not in types2
