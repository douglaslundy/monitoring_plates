from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.alert_sent import AlertSent
from app.models.alert_sent import AlertChannel
from app.models.camera import Camera
from app.models.occurrence import Occurrence
from app.models.monitored_plate import MonitoredPlate
from app.models.face_detection import FaceDetection
from app.models.person import Person
from app.models.user import User, UserRole
from app.schemas.alert import AlertSentLogRead, AlertSentRead
from app.services.storage_service import get_url

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertSentRead])
def list_alerts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(AlertSent)
    if current_user.role != UserRole.super_admin:
        from app.models.monitored_plate import MonitoredPlate

        plate_ids = [
            p.id
            for p in db.query(MonitoredPlate)
            .filter(MonitoredPlate.client_id == current_user.client_id)
            .all()
        ]
        q = q.filter(AlertSent.monitored_plate_id.in_(plate_ids))
    return q.order_by(AlertSent.sent_at.desc()).offset(skip).limit(limit).all()


@router.get("/sent", response_model=List[AlertSentLogRead])
def list_sent_alert_logs(
    channel: AlertChannel | None = None,
    event_type: str | None = None,
    message: str | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plate_rows = []
    if event_type in (None, "", "vehicle"):
        plate_q = (
            db.query(AlertSent, Occurrence, Camera, MonitoredPlate)
            .join(Occurrence, AlertSent.occurrence_id == Occurrence.id)
            .join(Camera, Occurrence.camera_id == Camera.id)
            .join(MonitoredPlate, AlertSent.monitored_plate_id == MonitoredPlate.id)
        )

        if current_user.role != UserRole.super_admin:
            plate_q = plate_q.filter(MonitoredPlate.client_id == current_user.client_id)

        if channel is not None:
            plate_q = plate_q.filter(AlertSent.channel == channel)
        if message:
            plate_q = plate_q.filter(AlertSent.message.ilike(f"%{message.strip()}%"))
        if sent_from is not None:
            plate_q = plate_q.filter(AlertSent.sent_at >= sent_from)
        if sent_to is not None:
            plate_q = plate_q.filter(AlertSent.sent_at <= sent_to)

        plate_rows = plate_q.order_by(AlertSent.sent_at.desc()).all()

    face_rows = []
    if event_type in (None, "", "face"):
        face_q = (
            db.query(AlertSent, FaceDetection, Camera, Person)
            .join(FaceDetection, AlertSent.face_detection_id == FaceDetection.id)
            .join(Camera, FaceDetection.camera_id == Camera.id)
            .outerjoin(Person, AlertSent.person_id == Person.id)
        )

        if current_user.role != UserRole.super_admin:
            face_q = face_q.filter(Camera.client_id == current_user.client_id)

        if channel is not None:
            face_q = face_q.filter(AlertSent.channel == channel)
        if message:
            face_q = face_q.filter(AlertSent.message.ilike(f"%{message.strip()}%"))
        if sent_from is not None:
            face_q = face_q.filter(AlertSent.sent_at >= sent_from)
        if sent_to is not None:
            face_q = face_q.filter(AlertSent.sent_at <= sent_to)

        face_rows = face_q.order_by(AlertSent.sent_at.desc()).all()

    logs = [
        AlertSentLogRead(
            id=alert.id,
            occurrence_id=alert.occurrence_id,
            monitored_plate_id=alert.monitored_plate_id,
            event_type="vehicle",
            plate=occ.plate,
            camera_name=camera.name,
            location=camera.location,
            channel=alert.channel.value if hasattr(alert.channel, "value") else str(alert.channel),
            sent_at=alert.sent_at,
            status=alert.status,
            message=alert.message,
            image_url=get_url(occ.image_path) if occ.image_path else None,
        )
        for alert, occ, camera, _mp in plate_rows
    ]
    logs.extend(
        AlertSentLogRead(
            id=alert.id,
            occurrence_id=alert.occurrence_id,
            monitored_plate_id=alert.monitored_plate_id,
            event_type="face",
            plate=person.name if person else "Face desconhecida",
            camera_name=camera.name,
            location=camera.location,
            channel=alert.channel.value if hasattr(alert.channel, "value") else str(alert.channel),
            sent_at=alert.sent_at,
            status=alert.status,
            message=alert.message,
            image_url=get_url(fd.image_path) if fd.image_path else None,
        )
        for alert, fd, camera, person in face_rows
    )
    logs.sort(key=lambda item: item.sent_at, reverse=True)
    return logs[skip : skip + limit]
