import csv
import io
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, get_current_user
from app.models.camera import Camera
from app.models.occurrence import Occurrence
from app.models.user import User, UserRole
from app.models.vehicle_event import VehicleEvent
from app.schemas.vehicle_event import (
    CategoryCount,
    HourBucket,
    LatestVehicleEvent,
    TopVehicleCamera,
    VehicleCameraMin,
    VehicleEventPage,
    VehicleEventStats,
    VehicleEventTypeCount,
    VehicleEventWithCamera,
)
from app.services.storage_service import get_url

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _allowed_camera_ids(db: Session, user: User) -> Optional[List[UUID]]:
    if user.role == UserRole.super_admin:
        return None
    return [c.id for c in db.query(Camera).filter(Camera.client_id == user.client_id).all()]


def _filter_query(
    db: Session,
    camera_ids: Optional[List[UUID]],
    *,
    camera_id: Optional[UUID] = None,
    vehicle_type: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
):
    q = db.query(VehicleEvent).options(joinedload(VehicleEvent.camera), joinedload(VehicleEvent.occurrence))
    if camera_ids is not None:
        q = q.filter(VehicleEvent.camera_id.in_(camera_ids))
    if camera_id is not None:
        q = q.filter(VehicleEvent.camera_id == camera_id)
    if category:
        q = q.filter(VehicleEvent.category == category)
    if vehicle_type:
        q = q.filter(VehicleEvent.vehicle_type == vehicle_type)
    if date_from is not None:
        q = q.filter(VehicleEvent.detected_at >= date_from)
    if date_to is not None:
        q = q.filter(VehicleEvent.detected_at <= date_to)
    return q


def _serialize_event(event: VehicleEvent) -> VehicleEventWithCamera:
    camera = event.camera
    image_path = event.image_path
    plate = None
    if not image_path and event.occurrence and event.occurrence.image_path:
        image_path = event.occurrence.image_path
    if event.occurrence and event.occurrence.plate:
        plate = event.occurrence.plate
    return VehicleEventWithCamera(
        id=event.id,
        camera_id=event.camera_id,
        occurrence_id=event.occurrence_id,
        category=event.category,
        vehicle_type=event.vehicle_type,
        companion_category=event.companion_category,
        companion_type=event.companion_type,
        confidence=event.confidence,
        bbox_x=event.bbox_x,
        bbox_y=event.bbox_y,
        bbox_w=event.bbox_w,
        bbox_h=event.bbox_h,
        image_path=image_path,
        detected_at=event.detected_at,
        created_at=event.created_at,
        image_url=get_url(image_path) if image_path else "",
        plate=plate,
        camera=VehicleCameraMin(
            id=camera.id if camera else event.camera_id,
            name=camera.name if camera else "Desconhecida",
            location=camera.location if camera else None,
        ),
    )


def _paginate(q, page: int, limit: int) -> VehicleEventPage:
    total = q.count()
    pages = max(1, (total + limit - 1) // limit)
    offset = (page - 1) * limit
    items = q.order_by(VehicleEvent.detected_at.desc(), VehicleEvent.created_at.desc()).offset(offset).limit(limit).all()
    return VehicleEventPage(items=[_serialize_event(item) for item in items], total=total, page=page, pages=pages)


@router.get("/stats", response_model=VehicleEventStats)
def get_stats(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    hour_24_ago = now - timedelta(hours=24)

    def _scoped(q):
        """Escopo por câmera (multi-tenant) + filtro opcional de categoria."""
        if camera_ids is not None:
            q = q.filter(VehicleEvent.camera_id.in_(camera_ids))
        if category:
            q = q.filter(VehicleEvent.category == category)
        return q

    base = _scoped(db.query(VehicleEvent))

    total_today = base.filter(VehicleEvent.detected_at >= today_start).count()
    total_week = base.filter(VehicleEvent.detected_at >= week_start).count()

    # Contagem por tipo. Inclui o COMPANION (T5): a pessoa-piloto agrupada na moto
    # também é contada (a moto é o registro, mas os dois entram nas estatísticas).
    type_counts: dict[str, int] = {}
    type_query = _scoped(db.query(VehicleEvent.vehicle_type, func.count(VehicleEvent.id).label("cnt")))
    for row in type_query.group_by(VehicleEvent.vehicle_type).all():
        type_counts[row.vehicle_type] = type_counts.get(row.vehicle_type, 0) + row.cnt
    comp_type_q = db.query(VehicleEvent.companion_type, func.count(VehicleEvent.id).label("cnt")).filter(
        VehicleEvent.companion_type.isnot(None)
    )
    if camera_ids is not None:
        comp_type_q = comp_type_q.filter(VehicleEvent.camera_id.in_(camera_ids))
    if category:  # filtro por categoria: companion conta se a categoria dele bate
        comp_type_q = comp_type_q.filter(VehicleEvent.companion_category == category)
    for row in comp_type_q.group_by(VehicleEvent.companion_type).all():
        type_counts[row.companion_type] = type_counts.get(row.companion_type, 0) + row.cnt
    by_type = [
        VehicleEventTypeCount(vehicle_type=t, count=c)
        for t, c in sorted(type_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # by_category ignora o filtro de categoria (mostra todas, p/ as abas), mas
    # respeita o escopo de câmera. Também inclui o companion (piloto).
    cat_counts: dict[str, int] = {}
    cat_query = db.query(VehicleEvent.category, func.count(VehicleEvent.id).label("cnt"))
    if camera_ids is not None:
        cat_query = cat_query.filter(VehicleEvent.camera_id.in_(camera_ids))
    for row in cat_query.group_by(VehicleEvent.category).all():
        cat_counts[row.category] = cat_counts.get(row.category, 0) + row.cnt
    comp_cat_q = db.query(VehicleEvent.companion_category, func.count(VehicleEvent.id).label("cnt")).filter(
        VehicleEvent.companion_category.isnot(None)
    )
    if camera_ids is not None:
        comp_cat_q = comp_cat_q.filter(VehicleEvent.camera_id.in_(camera_ids))
    for row in comp_cat_q.group_by(VehicleEvent.companion_category).all():
        cat_counts[row.companion_category] = cat_counts.get(row.companion_category, 0) + row.cnt
    by_category = [
        CategoryCount(category=c, count=n)
        for c, n in sorted(cat_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    cam_query = _scoped(db.query(VehicleEvent.camera_id, func.count(VehicleEvent.id).label("cnt")))
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

    latest_event_row = (
        base.order_by(VehicleEvent.detected_at.desc(), VehicleEvent.created_at.desc())
        .first()
    )
    latest_event = None
    if latest_event_row is not None:
        camera = db.query(Camera).filter(Camera.id == latest_event_row.camera_id).first()
        latest_event = LatestVehicleEvent(
            id=latest_event_row.id,
            camera_id=latest_event_row.camera_id,
            camera_name=camera.name if camera else str(latest_event_row.camera_id),
            camera_location=camera.location if camera else None,
            category=latest_event_row.category,
            vehicle_type=latest_event_row.vehicle_type,
            confidence=latest_event_row.confidence,
            detected_at=latest_event_row.detected_at,
        )

    return VehicleEventStats(
        total_today=total_today,
        total_week=total_week,
        by_type=by_type,
        by_category=by_category,
        top_cameras=top_cameras,
        by_hour=by_hour,
        latest_event=latest_event,
    )


@router.get("", response_model=VehicleEventPage)
def list_events(
    camera_id: Optional[UUID] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    q = _filter_query(
        db,
        camera_ids,
        camera_id=camera_id,
        vehicle_type=vehicle_type,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )
    return _paginate(q, page, limit)


@router.get("/export")
def export_events(
    camera_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    q = db.query(VehicleEvent)

    if camera_ids is not None:
        q = q.filter(VehicleEvent.camera_id.in_(camera_ids))
    if camera_id is not None:
        q = q.filter(VehicleEvent.camera_id == camera_id)
    if category:
        q = q.filter(VehicleEvent.category == category)
    if date_from is not None:
        q = q.filter(VehicleEvent.detected_at >= date_from)
    if date_to is not None:
        q = q.filter(VehicleEvent.detected_at <= date_to)
    if vehicle_type:
        q = q.filter(VehicleEvent.vehicle_type == vehicle_type)

    events = q.order_by(VehicleEvent.detected_at.desc(), VehicleEvent.created_at.desc()).limit(10_000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Camera",
            "Local",
            "Categoria",
            "Tipo",
            "Confiança (%)",
            "BBox X",
            "BBox Y",
            "BBox W",
            "BBox H",
            "Detectado em",
            "Criado em",
        ]
    )
    for event in events:
        camera = event.camera
        writer.writerow(
            [
                str(event.id),
                camera.name if camera else "",
                camera.location if camera else "",
                event.category,
                event.vehicle_type,
                f"{event.confidence * 100:.1f}",
                event.bbox_x,
                event.bbox_y,
                event.bbox_w,
                event.bbox_h,
                event.detected_at.isoformat() if event.detected_at else "",
                event.created_at.isoformat() if event.created_at else "",
            ]
        )

    output.seek(0)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="vehicle_events_{ts}.csv"'},
    )


class BulkDeleteRequest(BaseModel):
    ids: List[UUID]


@router.delete("/bulk", status_code=200)
def bulk_delete_vehicles(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.super_admin, UserRole.client_admin):
        raise HTTPException(status_code=403, detail="Acesso negado")

    from app.services.storage_service import delete_file

    q = db.query(VehicleEvent).filter(VehicleEvent.id.in_(payload.ids))
    if current_user.role != UserRole.super_admin:
        allowed_ids = [
            c.id for c in db.query(Camera).filter(Camera.client_id == current_user.client_id).all()
        ]
        q = q.filter(VehicleEvent.camera_id.in_(allowed_ids))

    events = q.all()
    deleted = 0
    seen_images: set = set()

    for event in events:
        if event.image_path and event.image_path not in seen_images:
            seen_images.add(event.image_path)
            try:
                delete_file(event.image_path)
            except Exception:
                pass
        if event.occurrence_id:
            occ = db.query(Occurrence).filter(Occurrence.id == event.occurrence_id).first()
            if occ:
                if occ.image_path and occ.image_path not in seen_images:
                    seen_images.add(occ.image_path)
                    try:
                        delete_file(occ.image_path)
                    except Exception:
                        pass
                db.delete(occ)
        db.delete(event)
        deleted += 1

    db.commit()
    return {"deleted": deleted}
