from app.core.security import create_access_token
from app.models.camera import Camera, ConnectionType
from app.models.person import Person
from app.models.face_detection import FaceDetection
from app.models.user import User


def _auth(user: User) -> dict:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _cam(db, client_id, name="Cam"):
    cam = Camera(client_id=client_id, name=name, connection_type=ConnectionType.rtsp)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def test_list_face_detections_inclui_person_name(client, db, admin_a, client_a):
    cam = _cam(db, client_a.id)
    p = Person(client_id=client_a.id, name="Beltrano", is_active=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    fd = FaceDetection(camera_id=cam.id, person_id=p.id, confidence=0.9, tracked_seconds=12.0)
    db.add(fd)
    db.commit()

    r = client.get("/api/face-detections", headers=_auth(admin_a))
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["person_name"] == "Beltrano"
    assert data[0]["tracked_seconds"] == 12.0


def test_list_face_detections_isolamento(client, db, admin_a, client_b):
    cam_b = _cam(db, client_b.id, name="CamB")
    fd = FaceDetection(camera_id=cam_b.id, confidence=0.9)
    db.add(fd)
    db.commit()

    r = client.get("/api/face-detections", headers=_auth(admin_a))
    assert r.status_code == 200
    assert r.json() == []
