import base64
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user, require_client_admin
from app.models.camera import Camera
from app.models.client import Client
from app.models.occurrence import Occurrence
from app.models.user import User, UserRole
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate, CameraDetail, OccurrenceSmall
from app.services.camera_service import generate_agent_token, capture_rtsp_frame

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _get_camera_or_403(camera_id: UUID, current_user: User, db: Session) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    if current_user.role != UserRole.super_admin and camera.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return camera


@router.get("", response_model=List[CameraRead])
def list_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.super_admin:
        return db.query(Camera).all()
    return db.query(Camera).filter(Camera.client_id == current_user.client_id).all()


@router.post("", response_model=CameraRead, status_code=201)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    if current_user.role != UserRole.super_admin:
        if payload.client_id != current_user.client_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
        tenant = db.query(Client).filter(Client.id == payload.client_id).first()
        if tenant and tenant.plan and tenant.plan.max_cameras is not None:
            count = db.query(Camera).filter(
                Camera.client_id == payload.client_id,
                Camera.is_active == True,  # noqa: E712
            ).count()
            if count >= tenant.plan.max_cameras:
                raise HTTPException(
                    status_code=400,
                    detail=f"Limite de câmeras do plano atingido ({tenant.plan.max_cameras})",
                )

    token = generate_agent_token() if payload.connection_type == "agent" else None
    camera = Camera(**payload.model_dump(), agent_token=token)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraDetail)
def get_camera(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    occurrences = (
        db.query(Occurrence)
        .filter(Occurrence.camera_id == camera_id)
        .order_by(Occurrence.detected_at.desc())
        .limit(5)
        .all()
    )
    camera_data = CameraRead.model_validate(camera).model_dump()
    occ_list = [OccurrenceSmall.model_validate(o).model_dump() for o in occurrences]
    return CameraDetail(**camera_data, last_occurrences=occ_list)


@router.put("/{camera_id}", response_model=CameraRead)
@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: UUID,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(camera, k, v)
    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    db.delete(camera)
    db.commit()


@router.post("/{camera_id}/test")
def test_camera_connection(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    if camera.connection_type != "rtsp" or not camera.rtsp_url:
        raise HTTPException(status_code=400, detail="Teste disponível apenas para câmeras RTSP")
    frame = capture_rtsp_frame(camera.rtsp_url)
    if frame is None:
        raise HTTPException(status_code=503, detail="Não foi possível conectar à câmera RTSP")
    return {
        "frame_base64": base64.b64encode(frame).decode(),
        "content_type": "image/jpeg",
    }


@router.get("/{camera_id}/token")
def get_camera_token(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = _get_camera_or_403(camera_id, current_user, db)
    return {"agent_token": camera.agent_token, "camera_id": str(camera_id)}
