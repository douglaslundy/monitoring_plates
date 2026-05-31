from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.alert_sent import AlertSent
from app.models.user import User, UserRole
from app.schemas.alert import AlertSentRead

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
