from unittest.mock import patch

from app.models.plan import Plan
from app.models.client import Client
from app.models.camera import Camera, ConnectionType
from app.models.person import Person
from app.models.face_detection import FaceDetection
from app.models.alert_sent import AlertSent, AlertChannel


def _tenant(db, email_alerts=True, realtime_alerts=True):
    plan = Plan(name="P", max_cameras=5, retention_days=30, price_monthly=0,
                email_alerts=email_alerts, realtime_alerts=realtime_alerts,
                face_recognition_enabled=True, face_engine="opencv")
    db.add(plan)
    db.flush()
    c = Client(name="C", email="c@t.com", plan_id=plan.id, is_active=True)
    db.add(c)
    db.flush()
    cam = Camera(client_id=c.id, name="Cam", connection_type=ConnectionType.rtsp, enable_face=True)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return plan, c, cam


def _person(db, client, alert_active=True, email="p@t.com", whatsapp=None):
    p = Person(client_id=client.id, name="Fulano", is_active=True,
               alert_active=alert_active, alert_email=email, alert_whatsapp=whatsapp)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _fd(db, cam, person):
    fd = FaceDetection(camera_id=cam.id, person_id=person.id, confidence=0.95,
                       image_path="cameras/x/img.jpg", face_engine_used="opencv")
    db.add(fd)
    db.commit()
    db.refresh(fd)
    return fd


def test_alerta_face_envia_e_grava(db):
    _plan, c, cam = _tenant(db, email_alerts=True, realtime_alerts=True)
    person = _person(db, c, alert_active=True, email="p@t.com")
    fd = _fd(db, cam, person)

    with (
        patch("app.services.face_alert_service.send_plate_alert", return_value=True) as mock_email,
        patch("app.services.face_alert_service._publish_ws_alert"),
    ):
        from app.services.face_alert_service import process_face_alerts

        process_face_alerts(str(fd.id), db)

    assert mock_email.call_count == 1
    email_alert = (
        db.query(AlertSent)
        .filter(AlertSent.face_detection_id == fd.id, AlertSent.channel == AlertChannel.email)
        .first()
    )
    assert email_alert is not None
    assert email_alert.person_id == person.id
    # websocket também gravado (aparece em Alertas disparados)
    ws = (
        db.query(AlertSent)
        .filter(AlertSent.face_detection_id == fd.id, AlertSent.channel == AlertChannel.websocket)
        .count()
    )
    assert ws == 1


def test_alerta_face_nao_envia_se_inativo(db):
    _plan, c, cam = _tenant(db, email_alerts=True, realtime_alerts=True)
    person = _person(db, c, alert_active=False)
    fd = _fd(db, cam, person)

    with (
        patch("app.services.face_alert_service.send_plate_alert") as mock_email,
        patch("app.services.face_alert_service._publish_ws_alert") as mock_ws,
    ):
        from app.services.face_alert_service import process_face_alerts

        process_face_alerts(str(fd.id), db)

    assert mock_email.call_count == 0
    assert mock_ws.call_count == 0
    assert db.query(AlertSent).count() == 0
