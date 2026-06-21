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


def _vehicle_detection():
    d = MagicMock()
    d.category = "vehicle"
    d.crop_bytes = b"vehicle-crop"
    d.vehicle_type = "car"
    d.confidence = 0.9
    d.bbox_x = 100
    d.bbox_y = 100
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
