import pytest

from app.models.plan import Plan
from app.models.client import Client
from app.models.camera import Camera, ConnectionType
from app.models.face_detection import FaceDetection
from app.services.vehicle_detection_service import VehicleDetection


@pytest.fixture
def face_camera(db):
    plan = Plan(
        name="Faces Plano",
        max_cameras=5,
        retention_days=30,
        price_monthly=0,
        face_recognition_enabled=True,
        face_engine="opencv",
    )
    db.add(plan)
    db.flush()
    c = Client(name="Cliente Face", email="facecam@test.com", plan_id=plan.id, is_active=True)
    db.add(c)
    db.flush()
    cam = Camera(client_id=c.id, name="CamFace", connection_type=ConnectionType.rtsp, enable_face=True)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@pytest.fixture
def person_detection_with_track():
    det = VehicleDetection(
        vehicle_type="person",
        category="person",
        confidence=0.9,
        bbox_x=10,
        bbox_y=20,
        bbox_w=30,
        bbox_h=40,
        crop_bytes=b"personcrop",
    )
    track = {"track_id": "trk1", "counted": True, "first_seen_at": 100.0, "last_seen_at": 100.0}
    return [det], {0: track}


def test_process_faces_creates_one_detection_per_track(db, monkeypatch, face_camera, person_detection_with_track):
    from app.services import face_pipeline_service as fps

    monkeypatch.setattr(fps, "_detect_face_crop", lambda crop: b"facecrop")
    monkeypatch.setattr("app.services.face_pipeline_service.face_recognizer.identify", lambda cid, b: None)

    detections, det_to_track = person_detection_with_track
    fps.process_faces(db, face_camera, detections, det_to_track, lambda: "img.jpg", now_ts=100.0)
    assert db.query(FaceDetection).count() == 1
    # 2ª passada no mesmo track NÃO cria outra
    fps.process_faces(db, face_camera, detections, det_to_track, lambda: "img.jpg", now_ts=101.0)
    assert db.query(FaceDetection).count() == 1


def test_process_faces_skips_uncounted_track(db, monkeypatch, face_camera, person_detection_with_track):
    from app.services import face_pipeline_service as fps

    monkeypatch.setattr(fps, "_detect_face_crop", lambda crop: b"facecrop")
    monkeypatch.setattr("app.services.face_pipeline_service.face_recognizer.identify", lambda cid, b: None)

    detections, det_to_track = person_detection_with_track
    det_to_track[0]["counted"] = False
    fps.process_faces(db, face_camera, detections, det_to_track, lambda: "img.jpg", now_ts=100.0)
    assert db.query(FaceDetection).count() == 0


def test_process_faces_no_face_in_crop(db, monkeypatch, face_camera, person_detection_with_track):
    from app.services import face_pipeline_service as fps

    monkeypatch.setattr(fps, "_detect_face_crop", lambda crop: None)  # sem rosto
    detections, det_to_track = person_detection_with_track
    fps.process_faces(db, face_camera, detections, det_to_track, lambda: "img.jpg", now_ts=100.0)
    assert db.query(FaceDetection).count() == 0


def test_finalize_expired_sets_duration(db, face_camera):
    from app.services import face_pipeline_service as fps

    fd = FaceDetection(camera_id=face_camera.id, track_id="t1", face_engine_used="opencv")
    db.add(fd)
    db.commit()
    db.refresh(fd)
    expired = [
        {
            "track_id": "t1",
            "first_seen_at": 100.0,
            "last_seen_at": 142.0,
            "category": "person",
            "face_detection_id": str(fd.id),
        }
    ]
    fps.finalize_expired_faces(db, expired)
    db.refresh(fd)
    assert fd.tracked_seconds == 42.0
