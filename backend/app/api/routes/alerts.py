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
from app.models.user import User, UserRole
from app.schemas.alert import AlertSentLogRead, AlertSentRead

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
    message: str | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(AlertSent, Occurrence, Camera, MonitoredPlate)
        .join(Occurrence, AlertSent.occurrence_id == Occurrence.id)
        .join(Camera, Occurrence.camera_id == Camera.id)
        .join(MonitoredPlate, AlertSent.monitored_plate_id == MonitoredPlate.id)
    )

    if current_user.role != UserRole.super_admin:
        q = q.filter(MonitoredPlate.client_id == current_user.client_id)

    if channel is not None:
        q = q.filter(AlertSent.channel == channel)
    if message:
        q = q.filter(AlertSent.message.ilike(f"%{message.strip()}%"))
    if sent_from is not None:
        q = q.filter(AlertSent.sent_at >= sent_from)
    if sent_to is not None:
        q = q.filter(AlertSent.sent_at <= sent_to)

    rows = q.order_by(AlertSent.sent_at.desc()).offset(skip).limit(limit).all()
    return [
        AlertSentLogRead(
            id=alert.id,
            occurrence_id=alert.occurrence_id,
            monitored_plate_id=alert.monitored_plate_id,
            plate=occ.plate,
            camera_name=camera.name,
            location=camera.location,
            channel=alert.channel.value if hasattr(alert.channel, "value") else str(alert.channel),
            sent_at=alert.sent_at,
            status=alert.status,
            message=alert.message,
        )
        for alert, occ, camera, _mp in rows
    ]
