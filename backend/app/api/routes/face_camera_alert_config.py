"""CRUD de FaceCameraAlertConfig — configuração de alertas de face por câmera.

Acessível por super_admin e client_admin (apenas para câmeras do próprio cliente).
"""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.face_camera_alert_config import FaceCameraAlertConfig
from app.models.camera import Camera
from app.schemas.face_camera_alert_config import (
    FaceCameraAlertConfigCreate,
    FaceCameraAlertConfigRead,
    FaceCameraAlertConfigUpdate,
)

router = APIRouter(prefix="/face-alert-config", tags=["face-alert-config"])


def _get_camera_or_403(camera_id: UUID, db: Session, current_user) -> Camera:
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada.")
    if current_user.role == "super_admin":
        return camera
    if current_user.role in ("client_admin", "client_user"):
        if str(camera.client_id) != str(current_user.client_id):
            raise HTTPException(status_code=403, detail="Acesso negado.")
    return camera


@router.get("/{camera_id}", response_model=FaceCameraAlertConfigRead)
def get_config(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _get_camera_or_403(camera_id, db, current_user)
    config = (
        db.query(FaceCameraAlertConfig)
        .filter(FaceCameraAlertConfig.camera_id == camera_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada.")
    return config


@router.put("/{camera_id}", response_model=FaceCameraAlertConfigRead)
def upsert_config(
    camera_id: UUID,
    payload: FaceCameraAlertConfigCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "client_admin"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    _get_camera_or_403(camera_id, db, current_user)

    config = (
        db.query(FaceCameraAlertConfig)
        .filter(FaceCameraAlertConfig.camera_id == camera_id)
        .first()
    )
    data = payload.model_dump()
    if config is None:
        config = FaceCameraAlertConfig(id=uuid.uuid4(), camera_id=camera_id, **data)
        db.add(config)
    else:
        for k, v in data.items():
            setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{camera_id}", status_code=204)
def delete_config(
    camera_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "client_admin"):
        raise HTTPException(status_code=403, detail="Acesso negado.")
    _get_camera_or_403(camera_id, db, current_user)

    config = (
        db.query(FaceCameraAlertConfig)
        .filter(FaceCameraAlertConfig.camera_id == camera_id)
        .first()
    )
    if config:
        db.delete(config)
        db.commit()
