"""Integração da política híbrida no frame_processor.

Prova o comportamento central pedido: um veículo que permanece na cena (parado)
é submetido ao OCR UMA vez — não a cada frame — graças ao estado do track
persistido (read/dormant).

A telemetria/alertas são mockados (como em test_vehicles) p/ o process_frame não
tocar o Redis real: sem isso, o lru_cache dos serviços de telemetria (populado
por testes anteriores com um cliente Redis real inalcançável) faz cada chamada
travar ~dezenas de segundos em timeout — e o track expira entre os frames.
"""
import base64
import copy
import importlib
from unittest.mock import MagicMock, patch


class FakeRedis:
    """Redis em memória (decode_responses=True): get/set/incr/expire."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value, ex: int | None = None, nx: bool = False):
        self.store[key] = value
        return True

    def incr(self, key: str):
        cur = int(self.store.get(key, 0)) + 1
        self.store[key] = str(cur)
        return cur

    def expire(self, key: str, ttl: int):
        return True

    def llen(self, key: str):
        return 0


class _Telemetry:
    preview_frames_last_minute = 0
    preview_status = "streaming"
    preview_fps = 2.0
    preview_last_frame_at = 1.0
    preview_latency_seconds = 1.0


def _vehicle_detection(x=100, y=100, crop=b"vehicle-crop"):
    d = MagicMock()
    d.category = "vehicle"
    d.crop_bytes = crop
    d.vehicle_type = "car"
    d.confidence = 0.9
    d.bbox_x = x
    d.bbox_y = y
    d.bbox_w = 120
    d.bbox_h = 90
    d.frame_w = 640
    d.frame_h = 480
    return d


def test_veiculo_parado_vai_ao_ocr_uma_vez(db):
    """3 frames com o mesmo veículo na mesma posição -> OCR uma vez, 1 ocorrência.

    Antes, o OCR rodava a cada frame (poluição + carga). Agora o track entra em
    'read' na 1ª leitura e os frames seguintes (qualidade não bem melhor) pulam.
    """
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.occurrence import Occurrence
    from app.core.database import engine
    from sqlalchemy.orm import sessionmaker

    plan = Plan(name="PH", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)
    tenant = Client(name="TH", email="th@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)
    cam = Camera(client_id=tenant.id, name="CH", location="LH",
                 connection_type=ConnectionType.rtsp, rtsp_url="rtsp://x/sh", is_active=True)
    db.add(cam); db.commit(); db.refresh(cam)

    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value = {"plate": "HBR2A18", "confidence": 0.93}
    mock_detector = MagicMock()
    mock_detector.detect.return_value = [_vehicle_detection()]

    worker_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    fake = FakeRedis()

    # Persistência do track em memória (independe de redis e de estado global).
    track_store: dict[str, list] = {"state": []}

    def fake_load(_camera_id):
        return copy.deepcopy(track_store["state"])

    def fake_save(_camera_id, state):
        track_store["state"] = copy.deepcopy(state)

    with patch("app.core.database.SessionLocal", worker_session), \
         patch("app.services.ocr_service.recognizer", mock_recognizer), \
         patch("app.services.vehicle_detection_service.vehicle_detector", mock_detector), \
         patch("app.services.frame_quality_service.crop_quality", return_value=0.9), \
         patch("app.services.storage_service.save_bytes", return_value="cameras/test/h.jpg"), \
         patch("app.services.detection_overlay_service.draw_detections", return_value=b"drawn"), \
         patch("app.services.alert_service.process_alerts"), \
         patch("app.services.object_tracker_service.load_tracks", fake_load), \
         patch("app.services.object_tracker_service.save_tracks", fake_save), \
         patch("app.services.preview_telemetry_service.record_preview_frame"), \
         patch("app.services.preview_telemetry_service.get_preview_telemetry", return_value=_Telemetry()), \
         patch("app.services.image_quality_service.record_image_quality"), \
         patch("app.services.ocr_pipeline_metrics_service.record_ocr_pipeline_metrics"), \
         patch("app.services.ocr_pipeline_alert_service.maybe_publish_ocr_pipeline_alert"), \
         patch("app.services.camera_health_alert_service.maybe_publish_camera_health_alert"), \
         patch("app.services.worker_delay_alert_service.maybe_publish_worker_delay_alert"), \
         patch("redis.from_url", return_value=fake):
        from app.workers import frame_processor
        importlib.reload(frame_processor)
        # Frames com bytes DIFERENTES (senão o digest-skip pularia), mesmo veículo.
        for i in range(3):
            frame = base64.b64encode(f"frame-{i}".encode()).decode()
            frame_processor.process_frame(str(cam.id), frame)

    assert mock_recognizer.recognize.call_count == 1
    assert db.query(Occurrence).filter(Occurrence.plate == "HBR2A18").count() == 1


def test_tres_veiculos_compartilham_uma_imagem(db):
    """3 veículos NOVOS no mesmo frame -> 3 ocorrências (contagem mantida) mas
    UMA imagem só (save_bytes chamado 1x) compartilhada por todos."""
    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.occurrence import Occurrence
    from app.core.database import engine
    from sqlalchemy.orm import sessionmaker

    plan = Plan(name="P3V", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)
    tenant = Client(name="T3V", email="t3v@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)
    cam = Camera(client_id=tenant.id, name="C3V", location="L3V",
                 connection_type=ConnectionType.rtsp, rtsp_url="rtsp://x/3v", is_active=True)
    db.add(cam); db.commit(); db.refresh(cam)

    mock_recognizer = MagicMock()
    mock_recognizer.recognize.side_effect = [
        {"plate": "AAA1A11", "confidence": 0.9},
        {"plate": "BBB2B22", "confidence": 0.9},
        {"plate": "CCC3C33", "confidence": 0.9},
    ]
    mock_detector = MagicMock()
    mock_detector.detect.return_value = [
        _vehicle_detection(x=40, y=60),
        _vehicle_detection(x=260, y=60),
        _vehicle_detection(x=460, y=320),  # dentro do frame (não na borda)
    ]
    worker_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    fake = FakeRedis()
    track_store = {"state": []}

    def fake_load(_cid):
        return copy.deepcopy(track_store["state"])

    def fake_save(_cid, state):
        track_store["state"] = copy.deepcopy(state)

    mock_save = MagicMock(return_value="cameras/test/shared.jpg")

    with patch("app.core.database.SessionLocal", worker_session), \
         patch("app.services.ocr_service.recognizer", mock_recognizer), \
         patch("app.services.vehicle_detection_service.vehicle_detector", mock_detector), \
         patch("app.services.frame_quality_service.crop_quality", return_value=0.9), \
         patch("app.services.storage_service.save_bytes", mock_save), \
         patch("app.services.detection_overlay_service.draw_detections", return_value=b"drawn"), \
         patch("app.services.alert_service.process_alerts"), \
         patch("app.services.object_tracker_service.load_tracks", fake_load), \
         patch("app.services.object_tracker_service.save_tracks", fake_save), \
         patch("app.services.preview_telemetry_service.record_preview_frame"), \
         patch("app.services.preview_telemetry_service.get_preview_telemetry", return_value=_Telemetry()), \
         patch("app.services.image_quality_service.record_image_quality"), \
         patch("app.services.ocr_pipeline_metrics_service.record_ocr_pipeline_metrics"), \
         patch("app.services.ocr_pipeline_alert_service.maybe_publish_ocr_pipeline_alert"), \
         patch("app.services.camera_health_alert_service.maybe_publish_camera_health_alert"), \
         patch("app.services.worker_delay_alert_service.maybe_publish_worker_delay_alert"), \
         patch("redis.from_url", return_value=fake):
        from app.workers import frame_processor
        importlib.reload(frame_processor)
        frame_processor.process_frame(str(cam.id), base64.b64encode(b"frame3v").decode())

    plates = {o.plate for o in db.query(Occurrence).all()}
    assert plates == {"AAA1A11", "BBB2B22", "CCC3C33"}  # 3 ocorrências (contagem mantida)
    assert mock_save.call_count == 1  # UMA imagem só para os 3 veículos


def test_parado_dormant_nao_reocr_quando_outro_passa(db):
    """R1: um veículo PARADO já lido (dormant) NÃO é reenviado ao OCR quando outro
    objeto passa; só o objeto NOVO vai ao OCR."""
    import time

    from app.models.plan import Plan
    from app.models.client import Client
    from app.models.camera import Camera, ConnectionType
    from app.models.occurrence import Occurrence
    from app.core.database import engine
    from sqlalchemy.orm import sessionmaker

    plan = Plan(name="PR1", max_cameras=1, retention_days=30, email_alerts=False,
                realtime_alerts=False, price_monthly=0, is_active=True)
    db.add(plan); db.commit(); db.refresh(plan)
    tenant = Client(name="TR1", email="tr1@t.com", plan_id=plan.id, is_active=True)
    db.add(tenant); db.commit(); db.refresh(tenant)
    cam = Camera(client_id=tenant.id, name="CR1", location="LR1",
                 connection_type=ConnectionType.rtsp, rtsp_url="rtsp://x/r1", is_active=True)
    db.add(cam); db.commit(); db.refresh(cam)

    now = time.time()
    # Track do veículo PARADO já lido -> dormant, na posição A (100,100).
    parked = {
        "track_id": "parkeddormant01", "category": "vehicle", "label": "car",
        "votes": {"vehicle|car": 9}, "bbox": {"bbox_x": 100, "bbox_y": 100, "bbox_w": 120, "bbox_h": 90},
        "first_seen_at": now - 600, "last_seen_at": now - 1, "hits": 9,
        "counted": True, "saved_class": "vehicle|car", "avg_disp": 0.0, "stationary": True,
        "vx": 0.0, "vy": 0.0, "ocr_state": "dormant", "best_quality": 0.95,
        "occurrence_id": None, "plate": "AAA1111", "plate_confidence": 0.95,
        "stationary_since": now - 500, "ocr_attempts": 6,
    }
    track_store = {"state": [parked]}

    def fake_load(_cid):
        return copy.deepcopy(track_store["state"])

    def fake_save(_cid, state):
        track_store["state"] = copy.deepcopy(state)

    mock_recognizer = MagicMock()
    mock_recognizer.recognize.return_value = {"plate": "NEW2B22", "confidence": 0.93}
    mock_detector = MagicMock()
    # Frame com o PARADO (posição A) + um veículo NOVO passando (posição B).
    mock_detector.detect.return_value = [
        _vehicle_detection(x=100, y=100),
        _vehicle_detection(x=420, y=300, crop=b"new-vehicle-crop"),
    ]
    worker_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    fake = FakeRedis()

    with patch("app.core.database.SessionLocal", worker_session), \
         patch("app.services.ocr_service.recognizer", mock_recognizer), \
         patch("app.services.vehicle_detection_service.vehicle_detector", mock_detector), \
         patch("app.services.frame_quality_service.crop_quality", return_value=0.9), \
         patch("app.services.storage_service.save_bytes", return_value="cameras/test/r1.jpg"), \
         patch("app.services.detection_overlay_service.draw_detections", return_value=b"drawn"), \
         patch("app.services.alert_service.process_alerts"), \
         patch("app.services.object_tracker_service.load_tracks", fake_load), \
         patch("app.services.object_tracker_service.save_tracks", fake_save), \
         patch("app.services.preview_telemetry_service.record_preview_frame"), \
         patch("app.services.preview_telemetry_service.get_preview_telemetry", return_value=_Telemetry()), \
         patch("app.services.image_quality_service.record_image_quality"), \
         patch("app.services.ocr_pipeline_metrics_service.record_ocr_pipeline_metrics"), \
         patch("app.services.ocr_pipeline_alert_service.maybe_publish_ocr_pipeline_alert"), \
         patch("app.services.camera_health_alert_service.maybe_publish_camera_health_alert"), \
         patch("app.services.worker_delay_alert_service.maybe_publish_worker_delay_alert"), \
         patch("redis.from_url", return_value=fake):
        from app.workers import frame_processor
        importlib.reload(frame_processor)
        frame_processor.process_frame(str(cam.id), base64.b64encode(b"frameR1").decode())

    # OCR rodou UMA vez (só p/ o veículo novo); o parado dormant foi ignorado.
    assert mock_recognizer.recognize.call_count == 1
    assert db.query(Occurrence).filter(Occurrence.plate == "NEW2B22").count() == 1
    assert db.query(Occurrence).filter(Occurrence.plate == "AAA1111").count() == 0
