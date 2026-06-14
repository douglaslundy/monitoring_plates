from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.camera import Camera
from app.models.user import User, UserRole
from app.models.vehicle_event import VehicleEvent
from app.schemas.vehicle_event import (
    VehicleEventStats,
    VehicleEventTypeCount,
    TopVehicleCamera,
    HourBucket,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _allowed_camera_ids(db: Session, user: User) -> Optional[List[UUID]]:
    if user.role == UserRole.super_admin:
        return None
    return [c.id for c in db.query(Camera).filter(Camera.client_id == user.client_id).all()]


@router.get("/stats", response_model=VehicleEventStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    hour_24_ago = now - timedelta(hours=24)

    base = db.query(VehicleEvent)
    if camera_ids is not None:
        base = base.filter(VehicleEvent.camera_id.in_(camera_ids))

    total_today = base.filter(VehicleEvent.detected_at >= today_start).count()
    total_week = base.filter(VehicleEvent.detected_at >= week_start).count()

    type_query = db.query(VehicleEvent.vehicle_type, func.count(VehicleEvent.id).label("cnt"))
    if camera_ids is not None:
        type_query = type_query.filter(VehicleEvent.camera_id.in_(camera_ids))
    type_agg = type_query.group_by(VehicleEvent.vehicle_type).order_by(func.count(VehicleEvent.id).desc()).all()
    by_type = [VehicleEventTypeCount(vehicle_type=row.vehicle_type, count=row.cnt) for row in type_agg]

    cam_query = db.query(VehicleEvent.camera_id, func.count(VehicleEvent.id).label("cnt"))
    if camera_ids is not None:
        cam_query = cam_query.filter(VehicleEvent.camera_id.in_(camera_ids))
    cam_agg = cam_query.group_by(VehicleEvent.camera_id).order_by(func.count(VehicleEvent.id).desc()).limit(5).all()
    top_cameras: List[TopVehicleCamera] = []
    for row in cam_agg:
        cam = db.query(Camera).filter(Camera.id == row.camera_id).first()
        top_cameras.append(
            TopVehicleCamera(
                camera_id=str(row.camera_id),
                camera_name=cam.name if cam else str(row.camera_id),
                count=row.cnt,
            )
        )

    recent = base.filter(VehicleEvent.detected_at >= hour_24_ago).all()
    counts: dict[int, int] = {}
    for event in recent:
        dt = event.detected_at
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        counts[dt.hour] = counts.get(dt.hour, 0) + 1
    by_hour = [HourBucket(hour=h, count=counts.get(h, 0)) for h in range(24)]

    return VehicleEventStats(
        total_today=total_today,
        total_week=total_week,
        by_type=by_type,
        top_cameras=top_cameras,
        by_hour=by_hour,
    )
