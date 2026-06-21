from app.models.face_detection import FaceDetection
from app.models.camera import Camera, ConnectionType


def test_create_face_detection(db, client_a):
    cam = Camera(client_id=client_a.id, name="C", connection_type=ConnectionType.rtsp)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    fd = FaceDetection(
        camera_id=cam.id,
        confidence=0.9,
        track_id="abc123",
        bbox_x=1,
        bbox_y=2,
        bbox_w=3,
        bbox_h=4,
        face_engine_used="opencv",
    )
    db.add(fd)
    db.commit()
    db.refresh(fd)
    assert fd.person_id is None
    assert fd.detected_at is not None
    assert fd.tracked_seconds is None
