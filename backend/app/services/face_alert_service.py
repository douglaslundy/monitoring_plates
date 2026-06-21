"""Alertas de reconhecimento facial — espelha `alert_service` trocando
MonitoredPlate→Person e Occurrence→FaceDetection.

Quando um `FaceDetection` casa com uma `Person` que tem `alert_active`, envia
e-mail (se o plano permite e há `alert_email`), WhatsApp (se há `alert_whatsapp`)
e publica alerta realtime (`type="face_alert"`), com dedup via `AlertSent`
(usando `person_id`/`face_detection_id`). Também grava um `AlertSent` no canal
websocket para o match aparecer em "Alertas disparados".
"""
import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.face_detection import FaceDetection
from app.models.person import Person
from app.models.camera import Camera
from app.models.alert_sent import AlertSent, AlertChannel
from app.services.email_service import send_plate_alert
from app.services.storage_service import get_url, read_file_bytes

logger = logging.getLogger(__name__)


def _person_name(person: Person) -> str:
    return person.name or "Pessoa"


def _build_message(person: Person, camera: Camera, fd: FaceDetection) -> str:
    lines = [f"{_person_name(person)} reconhecido(a)"]
    lines.append(f"Câmera: {camera.name}")
    if camera.location:
        lines.append(f"Local: {camera.location}")
    if fd.detected_at:
        lines.append(f"Quando: {fd.detected_at.strftime('%d/%m/%Y %H:%M')}")
    return "\n".join(lines)


def process_face_alerts(face_detection_id: str, db: Session) -> None:
    fd_uuid = UUID(face_detection_id) if isinstance(face_detection_id, str) else face_detection_id
    fd = db.query(FaceDetection).filter(FaceDetection.id == fd_uuid).first()
    if not fd or not fd.person_id:
        return

    person = db.query(Person).filter(Person.id == fd.person_id).first()
    if not person or not person.alert_active:
        return

    camera = db.query(Camera).filter(Camera.id == fd.camera_id).first()
    if not camera:
        return

    client = camera.client
    plan = client.plan if client else None
    image_url = get_url(fd.image_path) if fd.image_path else ""
    image_bytes = read_file_bytes(fd.image_path) if fd.image_path else None
    message = _build_message(person, camera, fd)

    # Pessoa global do admin (client_id NULL): dispara sempre, independente do
    # plano do cliente dono da câmera. Pessoa de cliente: respeita o plano.
    is_global = person.client_id is None

    if person.alert_email and (is_global or (plan and plan.email_alerts)):
        _send_email_alert(fd, person, camera, image_url, message, db)

    if is_global:
        # Só registra (não publica no canal do cliente) p/ aparecer em "Alertas disparados".
        _record_ws_alert(fd, person, message, db)
    elif plan and plan.realtime_alerts:
        _publish_ws_alert(fd, person, camera, image_url)
        _record_ws_alert(fd, person, message, db)

    if person.alert_whatsapp:
        _send_whatsapp_alert(fd, person, camera, image_url, image_bytes, message, db)

    db.commit()


def _already_sent(db: Session, fd: FaceDetection, person: Person, channel: AlertChannel) -> bool:
    return (
        db.query(AlertSent)
        .filter(
            AlertSent.face_detection_id == fd.id,
            AlertSent.person_id == person.id,
            AlertSent.channel == channel,
        )
        .first()
        is not None
    )


def _send_email_alert(fd, person, camera, image_url, message, db) -> None:
    if _already_sent(db, fd, person, AlertChannel.email):
        return
    success = send_plate_alert(
        to=person.alert_email,
        plate=_person_name(person),
        camera_name=camera.name,
        location=camera.location or "",
        detected_at=fd.detected_at.isoformat() if fd.detected_at else "",
        image_url=image_url,
    )
    db.add(
        AlertSent(
            face_detection_id=fd.id,
            person_id=person.id,
            channel=AlertChannel.email,
            status="sent" if success else "failed",
            message=message,
        )
    )


def _record_ws_alert(fd, person, message, db) -> None:
    if _already_sent(db, fd, person, AlertChannel.websocket):
        return
    db.add(
        AlertSent(
            face_detection_id=fd.id,
            person_id=person.id,
            channel=AlertChannel.websocket,
            status="sent",
            message=message,
        )
    )


def _send_whatsapp_alert(fd, person, camera, image_url, image_bytes, message, db) -> None:
    from app.services.whatsapp_service import send_whatsapp_alert
    from app.services.whatsapp_settings_service import get_effective_whatsapp_delivery_config

    model, config = get_effective_whatsapp_delivery_config(db)
    if model is not None and not config.is_active:
        return
    if _already_sent(db, fd, person, AlertChannel.whatsapp):
        return

    detected_at_str = fd.detected_at.strftime("%d/%m/%Y %H:%M") if fd.detected_at else ""
    success = send_whatsapp_alert(
        to=person.alert_whatsapp,
        plate=_person_name(person),
        camera_name=camera.name,
        location=camera.location or "",
        detected_at=detected_at_str,
        image_url=image_url,
        confidence=fd.confidence,
        image_bytes=image_bytes,
        message=message,
        config=config,
    )
    db.add(
        AlertSent(
            face_detection_id=fd.id,
            person_id=person.id,
            channel=AlertChannel.whatsapp,
            status="sent" if success else "failed",
            message=message,
        )
    )


def _publish_ws_alert(fd, person, camera, image_url: str) -> None:
    try:
        import redis as redis_lib
        from app.core.config import settings

        payload = {
            "type": "face_alert",
            "face_detection_id": str(fd.id),
            "person_name": _person_name(person),
            "camera_name": camera.name,
            "location": camera.location or "",
            "detected_at": fd.detected_at.isoformat() if fd.detected_at else None,
            "image_url": image_url,
            "confidence": fd.confidence,
        }
        r = redis_lib.Redis.from_url(settings.REDIS_URL)
        r.publish(f"ws:alerts:{camera.client_id}", json.dumps(payload))
    except Exception:
        logger.warning("Could not publish face WebSocket alert to Redis", exc_info=True)
