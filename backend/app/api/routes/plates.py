from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.deps import get_db, get_current_user
from app.models.monitored_plate import MonitoredPlate
from app.models.user import User, UserRole
from app.schemas.monitored_plate import MonitoredPlateCreate, MonitoredPlateRead, MonitoredPlateUpdate

router = APIRouter(prefix="/monitored-plates", tags=["monitored-plates"])


@router.get("", response_model=List[MonitoredPlateRead])
def list_plates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.super_admin:
        return db.query(MonitoredPlate).all()
    return (
        db.query(MonitoredPlate)
        .filter(MonitoredPlate.client_id == current_user.client_id)
        .all()
    )


@router.post("", response_model=MonitoredPlateRead, status_code=201)
def create_plate(
    payload: MonitoredPlateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # client_id vem do usuário logado; super_admin pode informá-lo no corpo.
    if current_user.role == UserRole.super_admin:
        if payload.client_id is None:
            raise HTTPException(
                status_code=400,
                detail="client_id é obrigatório para super_admin. Selecione um cliente.",
            )
        client_id = payload.client_id
    else:
        if current_user.client_id is None:
            raise HTTPException(
                status_code=400,
                detail="Seu usuário não está vinculado a um cliente. Contate o administrador.",
            )
        client_id = current_user.client_id

    plate = MonitoredPlate(
        client_id=client_id,
        plate=payload.plate.upper().strip(),
        description=payload.description,
        alert_email=payload.alert_email,
        alert_whatsapp=payload.alert_whatsapp,
        is_active=payload.is_active,
    )
    db.add(plate)
    db.commit()
    db.refresh(plate)
    return plate


@router.patch("/{plate_id}", response_model=MonitoredPlateRead)
def update_plate(
    plate_id: UUID,
    payload: MonitoredPlateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plate = db.query(MonitoredPlate).filter(MonitoredPlate.id == plate_id).first()
    if not plate:
        raise HTTPException(status_code=404, detail="Placa não encontrada")
    if current_user.role != UserRole.super_admin and plate.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(plate, k, v)
    db.commit()
    db.refresh(plate)
    return plate


@router.delete("/{plate_id}", status_code=204)
def delete_plate(
    plate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plate = db.query(MonitoredPlate).filter(MonitoredPlate.id == plate_id).first()
    if not plate:
        raise HTTPException(status_code=404, detail="Placa não encontrada")
    if current_user.role != UserRole.super_admin and plate.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    db.delete(plate)
    db.commit()
