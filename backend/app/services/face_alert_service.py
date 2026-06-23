"""Alertas de reconhecimento facial — espelha `alert_service` trocando
MonitoredPlate→Person e Occurrence→FaceDetection.

Quando um `FaceDetection` casa com uma `Person` que tem `alert_active`, envia
e-mail (se o plano permite e há `alert_email`), WhatsApp (se há `alert_whatsapp`)
e publica alerta realtime (`type="face_alert"`), com dedup via `AlertSent`
(usando `person_id`/`face_detection_id`). Também grava um `AlertSent` no canal
websocket para o match aparecer em "Alertas disparados".

Suporta também alertas para faces NÃO cadastradas (configurados por câmera em
`FaceCameraAlertConfig`), janela de horário/dias da semana e cooldown.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
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


def _build_unknown_message(camera: Camera, fd: FaceDetection) -> str:
    lines = ["Face não cadastrada detectada"]
    lines.append(f"Câmera: {camera.name}")
    if camera.location:
        lines.append(f"Local: {camera.location}")
    if fd.detected_at:
        lines.append(f"Quando: {fd.detected_at.strftime('%d/%m/%Y %H:%M')}")
    return "\n".join(lines)


# ── Schedule helpers ─────────────────────────────────────────────────────────

def _is_within_schedule(config) -> bool:
    """Verifica se o horário atual está dentro da janela configurada."""
    if config.schedule_start_time is None:
        return True  # Sem restrição de horário
    duration = config.schedule_duration_minutes
    if not duration or duration <= 0:
        return True

    now = datetime.now(timezone.utc)

    # Verifica dia da semana
    if config.schedule_days_of_week:
        try:
            days = json.loads(config.schedule_days_of_week)
            if days and now.weekday() not in days:
                return False
        except Exception:
            pass

    # Verifica janela de horário
    try:
        parts = config.schedule_start_time.split(":")
        start_hour, start_min = int(parts[0]), int(parts[1])
    except Exception:
        return True

    now_minutes = now.hour * 60 + now.minute
    start_minutes = start_hour * 60 + start_min
    end_minutes = start_minutes + duration

    if end_minutes >= 24 * 60:
        # Janela que cruza meia-noite
        end_minutes = end_minutes % (24 * 60)
        return now_minutes >= start_minutes or now_minutes < end_minutes

    return start_minutes <= now_minutes < end_minutes


def _load_camera_alert_config(camera_id, db: Session):
    """Carrega FaceCameraAlertConfig da câmera (None se não existir)."""
    try:
        from app.models.face_camera_alert_config import FaceCameraAlertConfig
        return (
            db.query(FaceCameraAlertConfig)
            .filter(FaceCameraAlertConfig.camera_id == camera_id)
            .first()
        )
    except Exception as exc:
        logger.debug("Não foi possível carregar face_camera_alert_config: %s", exc)
        return None


# ── Cooldown helpers ─────────────────────────────────────────────────────────

def _is_on_cooldown_known(db: Session, camera_id, person_id, cooldown_minutes: int) -> bool:
    """Verifica se já houve alerta desta pessoa nesta câmera dentro do cooldown."""
    if not cooldown_minutes or cooldown_minutes <= 0:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    exists = (
        db.query(AlertSent)
        .join(FaceDetection, AlertSent.face_detection_id == FaceDetection.id)
        .filter(
            AlertSent.person_id == person_id,
            FaceDetection.camera_id == camera_id,
            AlertSent.sent_at >= cutoff,
            AlertSent.status == "sent",
        )
        .first()
    )
    return exists is not None


def _is_on_cooldown_unknown(db: Session, camera_id, cooldown_minutes: int) -> bool:
    """Verifica se já houve alerta de face desconhecida nesta câmera dentro do cooldown."""
    if not cooldown_minutes or cooldown_minutes <= 0:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    exists = (
        db.query(AlertSent)
        .join(FaceDetection, AlertSent.face_detection_id == FaceDetection.id)
        .filter(
            AlertSent.person_id.is_(None),
            FaceDetection.camera_id == camera_id,
            AlertSent.channel == AlertChannel.websocket,
            AlertSent.sent_at >= cutoff,
            AlertSent.status == "sent",
        )
        .first()
    )
    return exists is not None


# ── Alerta de face CONHECIDA ─────────────────────────────────────────────────

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

    # Verifica schedule e cooldown da câmera (se configurado)
    cam_config = _load_camera_alert_config(camera.id, db)
    if cam_config:
        if not _is_within_schedule(cam_config):
            logger.debug(
                "face_alert suprimido (fora do horário) camera=%s person=%s",
                camera.id, person.id,
            )
            return
        if _is_on_cooldown_known(db, camera.id, person.id, cam_config.cooldown_minutes):
            logger.debug(
                "face_alert suprimido (cooldown %dmin) camera=%s person=%s",
                cam_config.cooldown_minutes, camera.id, person.id,
            )
            return

    client = camera.client
    plan = client.plan if client else None
    image_url = get_url(fd.image_path) if fd.image_path else ""
    image_bytes = read_file_bytes(fd.image_path) if fd.image_path else None
    message = _build_message(person, camera, fd)

    is_global = person.client_id is None

    if person.alert_email and (is_global or (plan and plan.email_alerts)):
        _send_email_alert(fd, person, camera, image_url, message, db)

    if is_global:
        _record_ws_alert(fd, person, message, db)
    elif plan and plan.realtime_alerts:
        _publish_ws_alert(fd, person, camera, image_url)
        _record_ws_alert(fd, person, message, db)

    if person.alert_whatsapp:
        _send_whatsapp_alert(fd, person, camera, image_url, image_bytes, message, db)

    db.commit()


# ── Alerta de face DESCONHECIDA ──────────────────────────────────────────────

def process_unknown_face_alert(face_detection_id: str, db: Session) -> None:
    """Dispara alerta para face não cadastrada, se a câmera tiver isso configurado."""
    fd_uuid = UUID(face_detection_id) if isinstance(face_detection_id, str) else face_detection_id
    fd = db.query(FaceDetection).filter(FaceDetection.id == fd_uuid).first()
    if not fd:
        return

    camera = db.query(Camera).filter(Camera.id == fd.camera_id).first()
    if not camera:
        return

    cam_config = _load_camera_alert_config(camera.id, db)
    if not cam_config or not cam_config.unknown_face_active:
        return

    # Verifica schedule
    if not _is_within_schedule(cam_config):
        logger.debug("unknown_face_alert suprimido (fora do horário) camera=%s", camera.id)
        return

    # Verifica cooldown (por câmera, para faces desconhecidas)
    if _is_on_cooldown_unknown(db, camera.id, cam_config.cooldown_minutes):
        logger.debug(
            "unknown_face_alert suprimido (cooldown %dmin) camera=%s",
            cam_config.cooldown_minutes, camera.id,
        )
        return

    client = camera.client
    plan = client.plan if client else None
    image_url = get_url(fd.image_path) if fd.image_path else ""
    image_bytes = read_file_bytes(fd.image_path) if fd.image_path else None
    message = _build_unknown_message(camera, fd)

    if cam_config.unknown_face_email and plan and plan.email_alerts:
        _send_unknown_email_alert(fd, camera, image_url, message, cam_config, db)

    if plan and plan.realtime_alerts:
        _publish_unknown_ws_alert(fd, camera, image_url)

    # Sempre grava websocket para aparecer em "Alertas disparados"
    _record_unknown_ws_alert(fd, message, db)

    if cam_config.unknown_face_whatsapp:
        _send_unknown_whatsapp_alert(fd, camera, image_url, image_bytes, message, cam_config, db)

    db.commit()


# ── Helpers: face CONHECIDA ──────────────────────────────────────────────────

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


# ── Helpers: face DESCONHECIDA ───────────────────────────────────────────────

def _already_sent_unknown(db: Session, fd: FaceDetection, channel: AlertChannel) -> bool:
    return (
        db.query(AlertSent)
        .filter(
            AlertSent.face_detection_id == fd.id,
            AlertSent.person_id.is_(None),
            AlertSent.channel == channel,
        )
        .first()
        is not None
    )


def _send_unknown_email_alert(fd, camera, image_url, message, cam_config, db) -> None:
    if _already_sent_unknown(db, fd, AlertChannel.email):
        return
    success = send_plate_alert(
        to=cam_config.unknown_face_email,
        plate="Face desconhecida",
        camera_name=camera.name,
        location=camera.location or "",
        detected_at=fd.detected_at.isoformat() if fd.detected_at else "",
        image_url=image_url,
    )
    db.add(
        AlertSent(
            face_detection_id=fd.id,
            person_id=None,
            channel=AlertChannel.email,
            status="sent" if success else "failed",
            message=message,
        )
    )


def _record_unknown_ws_alert(fd, message, db) -> None:
    if _already_sent_unknown(db, fd, AlertChannel.websocket):
        return
    db.add(
        AlertSent(
            face_detection_id=fd.id,
            person_id=None,
            channel=AlertChannel.websocket,
            status="sent",
            message=message,
        )
    )


def _send_unknown_whatsapp_alert(fd, camera, image_url, image_bytes, message, cam_config, db) -> None:
    from app.services.whatsapp_service import send_whatsapp_alert
    from app.services.whatsapp_settings_service import get_effective_whatsapp_delivery_config

    model, config = get_effective_whatsapp_delivery_config(db)
    if model is not None and not config.is_active:
        return
    if _already_sent_unknown(db, fd, AlertChannel.whatsapp):
        return

    detected_at_str = fd.detected_at.strftime("%d/%m/%Y %H:%M") if fd.detected_at else ""
    success = send_whatsapp_alert(
        to=cam_config.unknown_face_whatsapp,
        plate="Face desconhecida",
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
            person_id=None,
            channel=AlertChannel.whatsapp,
            status="sent" if success else "failed",
            message=message,
        )
    )


def _publish_unknown_ws_alert(fd, camera, image_url: str) -> None:
    try:
        import redis as redis_lib
        from app.core.config import settings

        payload = {
            "type": "face_alert",
            "face_detection_id": str(fd.id),
            "person_name": "Face desconhecida",
            "camera_name": camera.name,
            "location": camera.location or "",
            "detected_at": fd.detected_at.isoformat() if fd.detected_at else None,
            "image_url": image_url,
            "confidence": fd.confidence,
        }
        r = redis_lib.Redis.from_url(settings.REDIS_URL)
        r.publish(f"ws:alerts:{camera.client_id}", json.dumps(payload))
    except Exception:
        logger.warning("Could not publish unknown face WebSocket alert to Redis", exc_info=True)


# ── Alertas de teste (endpoint test-image, sem gravar no banco) ──────────────

def _send_test_face_alert_email(person: Person, detected_at: str) -> None:
    send_plate_alert(
        to=person.alert_email,
        plate=person.name or "Pessoa",
        camera_name="[TESTE]",
        location="Teste manual via painel",
        detected_at=detected_at,
        image_url="",
    )


def _send_test_face_alert_whatsapp(person: Person, image_bytes: bytes, detected_at: str, db: Session) -> None:
    from app.services.whatsapp_service import send_whatsapp_alert, build_whatsapp_message
    from app.services.whatsapp_settings_service import get_effective_whatsapp_delivery_config

    model, cfg = get_effective_whatsapp_delivery_config(db)
    if model is not None and not cfg.is_active:
        return
    msg = build_whatsapp_message(person.name or "Pessoa", "[TESTE]", "", detected_at)
    send_whatsapp_alert(
        phone=person.alert_whatsapp,
        message=msg,
        delivery_config=cfg,
        image_bytes=image_bytes,
    )
