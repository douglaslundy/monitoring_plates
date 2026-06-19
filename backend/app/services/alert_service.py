import json
import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.occurrence import Occurrence
from app.models.monitored_plate import MonitoredPlate
from app.models.alert_sent import AlertSent, AlertChannel
from app.models.camera import Camera
from app.services.email_service import send_plate_alert

logger = logging.getLogger(__name__)


def process_alerts(occurrence_id: str, db: Session) -> None:
    occ_uuid = UUID(occurrence_id) if isinstance(occurrence_id, str) else occurrence_id
    occ = db.query(Occurrence).filter(Occurrence.id == occ_uuid).first()
    if not occ:
        return

    camera = db.query(Camera).filter(Camera.id == occ.camera_id).first()
    if not camera:
        return

    client = camera.client
    plan = client.plan

    matches = (
        db.query(MonitoredPlate)
        .filter(
            MonitoredPlate.plate == occ.plate,
            MonitoredPlate.client_id == camera.client_id,
            MonitoredPlate.is_active == True,  # noqa: E712
        )
        .all()
    )

    from app.services.storage_service import get_url
    image_url = get_url(occ.image_path) if occ.image_path else ""

    for mp in matches:
        if plan.email_alerts and mp.alert_email:
            _send_email_alert(occ, camera, mp, image_url, db)

        if plan.realtime_alerts:
            _publish_ws_alert(occ, camera, image_url)

        if mp.alert_whatsapp:
            _send_whatsapp_alert(occ, camera, mp, image_url, db)

    db.commit()


def _send_email_alert(occ, camera, mp, image_url: str, db: Session) -> None:
    already = (
        db.query(AlertSent)
        .filter(
            AlertSent.occurrence_id == occ.id,
            AlertSent.monitored_plate_id == mp.id,
            AlertSent.channel == AlertChannel.email,
        )
        .first()
    )
    if already:
        return

    success = send_plate_alert(
        to=mp.alert_email,
        plate=occ.plate,
        camera_name=camera.name,
        location=camera.location or "",
        detected_at=occ.detected_at.isoformat() if occ.detected_at else "",
        image_url=image_url,
    )

    db.add(
        AlertSent(
            occurrence_id=occ.id,
            monitored_plate_id=mp.id,
            channel=AlertChannel.email,
            status="sent" if success else "failed",
        )
    )


def _send_whatsapp_alert(occ, camera, mp, image_url: str, db: Session) -> None:
    from app.services.whatsapp_service import send_whatsapp_alert

    already = (
        db.query(AlertSent)
        .filter(
            AlertSent.occurrence_id == occ.id,
            AlertSent.monitored_plate_id == mp.id,
            AlertSent.channel == AlertChannel.whatsapp,
        )
        .first()
    )
    if already:
        return

    detected_at_str = occ.detected_at.strftime("%d/%m/%Y %H:%M") if occ.detected_at else ""
    success = send_whatsapp_alert(
        to=mp.alert_whatsapp,
        plate=occ.plate,
        camera_name=camera.name,
        location=camera.location or "",
        detected_at=detected_at_str,
        image_url=image_url,
    )

    db.add(
        AlertSent(
            occurrence_id=occ.id,
            monitored_plate_id=mp.id,
            channel=AlertChannel.whatsapp,
            status="sent" if success else "failed",
        )
    )


def _publish_ws_alert(occ, camera, image_url: str) -> None:
    try:
        import redis as redis_lib
        from app.core.config import settings

        payload = {
            "type": "plate_alert",
            "occurrence_id": str(occ.id),
            "plate": occ.plate,
            "camera_name": camera.name,
            "location": camera.location or "",
            "detected_at": occ.detected_at.isoformat() if occ.detected_at else None,
            "image_url": image_url,
            "confidence": occ.confidence,
        }
        r = redis_lib.Redis.from_url(settings.REDIS_URL)
        r.publish(f"ws:alerts:{camera.client_id}", json.dumps(payload))
    except Exception:
        logger.warning("Could not publish WebSocket alert to Redis", exc_info=True)
