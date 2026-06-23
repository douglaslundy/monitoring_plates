from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.face_detection import FaceDetection
from app.models.camera import Camera
from app.models.person import Person
from app.models.user import User, UserRole
from app.schemas.face_detection import FaceDetectionRead
from app.services.storage_service import get_url, delete_file

router = APIRouter(prefix="/face-detections", tags=["face-detections"])


class BulkDeleteFaceRequest(BaseModel):
    ids: List[UUID]


def _serialize(fd: FaceDetection, camera: Camera, person: Optional[Person]) -> FaceDetectionRead:
    return FaceDetectionRead(
        id=fd.id,
        camera_id=fd.camera_id,
        camera_name=camera.name if camera else None,
        person_id=fd.person_id,
        person_name=person.name if person else None,
        confidence=fd.confidence,
        image_url=get_url(fd.image_path) if fd.image_path else None,
        bbox_x=fd.bbox_x,
        bbox_y=fd.bbox_y,
        bbox_w=fd.bbox_w,
        bbox_h=fd.bbox_h,
        track_id=fd.track_id,
        detected_at=fd.detected_at,
        tracked_seconds=fd.tracked_seconds,
        face_engine_used=fd.face_engine_used,
    )


@router.get("", response_model=List[FaceDetectionRead])
def list_face_detections(
    person_id: Optional[UUID] = Query(None),
    camera_id: Optional[UUID] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(FaceDetection, Camera, Person)
        .join(Camera, FaceDetection.camera_id == Camera.id)
        .outerjoin(Person, FaceDetection.person_id == Person.id)
    )
    if current_user.role != UserRole.super_admin:
        q = q.filter(Camera.client_id == current_user.client_id)
    if person_id is not None:
        q = q.filter(FaceDetection.person_id == person_id)
    if camera_id is not None:
        q = q.filter(FaceDetection.camera_id == camera_id)

    rows = (
        q.order_by(FaceDetection.detected_at.desc()).offset(skip).limit(limit).all()
    )
    return [_serialize(fd, camera, person) for fd, camera, person in rows]


@router.get("/{detection_id}", response_model=FaceDetectionRead)
def get_face_detection(
    detection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(FaceDetection, Camera, Person)
        .join(Camera, FaceDetection.camera_id == Camera.id)
        .outerjoin(Person, FaceDetection.person_id == Person.id)
        .filter(FaceDetection.id == detection_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Detecção não encontrada")
    fd, camera, person = row
    if current_user.role != UserRole.super_admin and camera.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return _serialize(fd, camera, person)


@router.delete("/bulk", status_code=200)
def bulk_delete_face_detections(
    payload: BulkDeleteFaceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.super_admin, UserRole.client_admin):
        raise HTTPException(status_code=403, detail="Acesso negado")

    query = db.query(FaceDetection).filter(FaceDetection.id.in_(payload.ids))
    if current_user.role == UserRole.client_admin:
        cam_ids = [
            c.id
            for c in db.query(Camera).filter(Camera.client_id == current_user.client_id).all()
        ]
        query = query.filter(FaceDetection.camera_id.in_(cam_ids))

    detections = query.all()
    seen_images: set[str] = set()
    deleted = 0

    for fd in detections:
        if fd.image_path and fd.image_path not in seen_images:
            seen_images.add(fd.image_path)
            try:
                delete_file(fd.image_path)
            except Exception:
                pass
        db.delete(fd)
        deleted += 1

    db.commit()
    return {"deleted": deleted}
