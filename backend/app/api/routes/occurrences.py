import csv
import io
from collections import defaultdict
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
from app.schemas.occurrence import (
    CameraMin,
    OccurrencePage,
    OccurrenceSearch,
    OccurrenceStats,
    OccurrenceWithCamera,
    TopCamera,
    TopPlate,
    HourBucket,
)
from app.services.storage_service import get_url

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


# ── helpers ───────────────────────────────────────────────────────────────────


def _allowed_camera_ids(db: Session, user: User) -> Optional[List[UUID]]:
    """None = no restriction (super_admin). Otherwise list of UUIDs for the client."""
    if user.role == UserRole.super_admin:
        return None
    return [c.id for c in db.query(Camera).filter(Camera.client_id == user.client_id).all()]


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normaliza datetime para timezone-aware em UTC.

    Um datetime sem timezone (naive) comparado a uma coluna timestamptz é
    ambíguo no PostgreSQL. O frontend envia o instante já em UTC (ISO com 'Z'),
    mas, por robustez, datetimes naive são assumidos como UTC aqui.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _filter_query(
    db: Session,
    camera_ids: Optional[List[UUID]],
    plate: str = "",
    camera_id: Optional[UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
):
    date_from = _as_utc(date_from)
    date_to = _as_utc(date_to)
    q = db.query(Occurrence).options(joinedload(Occurrence.camera))
    if camera_ids is not None:
        q = q.filter(Occurrence.camera_id.in_(camera_ids))
    if plate:
        q = q.filter(Occurrence.plate.ilike(f"%{plate}%"))
    if camera_id:
        q = q.filter(Occurrence.camera_id == camera_id)
    if date_from:
        q = q.filter(Occurrence.detected_at >= date_from)
    if date_to:
        q = q.filter(Occurrence.detected_at <= date_to)
    return q


def _serialize(occ: Occurrence) -> OccurrenceWithCamera:
    cam = occ.camera
    return OccurrenceWithCamera(
        id=occ.id,
        plate=occ.plate,
        confidence=occ.confidence,
        image_path=occ.image_path,
        image_url=get_url(occ.image_path) if occ.image_path else "",
        detected_at=occ.detected_at,
        expires_at=occ.expires_at,
        camera=CameraMin(
            id=cam.id if cam else occ.camera_id,
            name=cam.name if cam else "Desconhecida",
            location=cam.location if cam else None,
        ),
    )


def _paginate(q, page: int, limit: int) -> OccurrencePage:
    total = q.count()
    offset = (page - 1) * limit
    pages = max(1, (total + limit - 1) // limit)
    items = q.order_by(Occurrence.detected_at.desc()).offset(offset).limit(limit).all()
    return OccurrencePage(
        items=[_serialize(occ) for occ in items],
        total=total,
        page=page,
        pages=pages,
    )


# ── endpoints — fixed paths before /{id} ─────────────────────────────────────


@router.get("/stats", response_model=OccurrenceStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    hour_24_ago = now - timedelta(hours=24)

    base = db.query(Occurrence)
    if camera_ids is not None:
        base = base.filter(Occurrence.camera_id.in_(camera_ids))

    total_today = base.filter(Occurrence.detected_at >= today_start).count()
    total_week = base.filter(Occurrence.detected_at >= week_start).count()

    # Top cameras
    cam_agg = (
        db.query(Occurrence.camera_id, func.count(Occurrence.id).label("cnt"))
        .filter(Occurrence.camera_id.in_(camera_ids) if camera_ids is not None else True)
        .group_by(Occurrence.camera_id)
        .order_by(func.count(Occurrence.id).desc())
        .limit(5)
        .all()
    )
    top_cameras: List[TopCamera] = []
    for row in cam_agg:
        cam = db.query(Camera).filter(Camera.id == row.camera_id).first()
        top_cameras.append(
            TopCamera(
                camera_id=str(row.camera_id),
                camera_name=cam.name if cam else str(row.camera_id),
                count=row.cnt,
            )
        )

    # Top plates
    plate_agg = (
        db.query(Occurrence.plate, func.count(Occurrence.id).label("cnt"))
        .filter(Occurrence.camera_id.in_(camera_ids) if camera_ids is not None else True)
        .group_by(Occurrence.plate)
        .order_by(func.count(Occurrence.id).desc())
        .limit(5)
        .all()
    )
    top_plates = [TopPlate(plate=r.plate, count=r.cnt) for r in plate_agg]

    # By hour (last 24 h) — computed in Python for SQLite/PostgreSQL compat
    recent = base.filter(Occurrence.detected_at >= hour_24_ago).all()
    counts: dict[int, int] = defaultdict(int)
    for occ in recent:
        if occ.detected_at:
            dt = occ.detected_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            counts[dt.hour] += 1
    by_hour = [HourBucket(hour=h, count=counts.get(h, 0)) for h in range(24)]

    return OccurrenceStats(
        total_today=total_today,
        total_week=total_week,
        top_cameras=top_cameras,
        top_plates=top_plates,
        by_hour=by_hour,
    )


@router.post("/search", response_model=OccurrencePage)
def search_occurrences(
    body: OccurrenceSearch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    q = _filter_query(db, camera_ids, plate=body.plate, date_from=body.date_from, date_to=body.date_to)

    if body.camera_ids:
        allowed_set = set(camera_ids) if camera_ids is not None else None
        scoped = [cid for cid in body.camera_ids if allowed_set is None or cid in allowed_set]
        q = q.filter(Occurrence.camera_id.in_(scoped))

    page = max(1, body.page)
    limit = min(100, max(1, body.limit))
    return _paginate(q, page, limit)


@router.get("/export")
def export_csv(
    plate: Optional[str] = Query(None),
    camera_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    q = _filter_query(db, camera_ids, plate=plate or "", camera_id=camera_id, date_from=date_from, date_to=date_to)
    occurrences = q.order_by(Occurrence.detected_at.desc()).limit(10_000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Placa", "Câmera", "Local", "Confiança (%)", "Detectado em", "Expira em"])
    for occ in occurrences:
        cam = occ.camera
        writer.writerow([
            str(occ.id),
            occ.plate,
            cam.name if cam else "",
            cam.location if cam else "",
            f"{occ.confidence * 100:.1f}",
            occ.detected_at.isoformat() if occ.detected_at else "",
            occ.expires_at.isoformat() if occ.expires_at else "",
        ])

    output.seek(0)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ocorrencias_{ts}.csv"'},
    )


@router.get("", response_model=OccurrencePage)
def list_occurrences(
    plate: Optional[str] = Query(None),
    camera_id: Optional[UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera_ids = _allowed_camera_ids(db, current_user)
    q = _filter_query(db, camera_ids, plate=plate or "", camera_id=camera_id, date_from=date_from, date_to=date_to)
    return _paginate(q, page, limit)


@router.get("/{occurrence_id}", response_model=OccurrenceWithCamera)
def get_occurrence(
    occurrence_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    occ = (
        db.query(Occurrence)
        .options(joinedload(Occurrence.camera))
        .filter(Occurrence.id == occurrence_id)
        .first()
    )
    if not occ:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    if current_user.role != UserRole.super_admin:
        cam = db.query(Camera).filter(Camera.id == occ.camera_id).first()
        if not cam or cam.client_id != current_user.client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
    return _serialize(occ)


class BulkDeleteOccurrenceRequest(BaseModel):
    ids: List[UUID]


@router.delete("/bulk", status_code=200)
def bulk_delete_occurrences(
    payload: BulkDeleteOccurrenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.super_admin, UserRole.client_admin):
        raise HTTPException(status_code=403, detail="Acesso negado")

    from app.services.storage_service import delete_file

    q = db.query(Occurrence).filter(Occurrence.id.in_(payload.ids))
    if current_user.role != UserRole.super_admin:
        allowed_ids = [
            c.id for c in db.query(Camera).filter(Camera.client_id == current_user.client_id).all()
        ]
        q = q.filter(Occurrence.camera_id.in_(allowed_ids))

    occs = q.all()
    deleted = 0
    seen_images: set = set()

    for occ in occs:
        if occ.image_path and occ.image_path not in seen_images:
            seen_images.add(occ.image_path)
            try:
                delete_file(occ.image_path)
            except Exception:
                pass
        db.query(VehicleEvent).filter(VehicleEvent.occurrence_id == occ.id).update(
            {"occurrence_id": None}, synchronize_session=False
        )
        db.delete(occ)
        deleted += 1

    db.commit()
    return {"deleted": deleted}
