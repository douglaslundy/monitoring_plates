from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from uuid import UUID

from app.api.deps import get_db, require_super_admin
from app.core.security import hash_password
from app.models.client import Client
from app.models.camera import Camera
from app.models.occurrence import Occurrence
from app.models.monitored_plate import MonitoredPlate
from app.models.alert_sent import AlertSent
from app.models.user import User, UserRole
from app.schemas.client import ClientCreateWithAdmin, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])


def _build_client_read(client: Client, db: Session) -> ClientRead:
    count = db.query(func.count(Camera.id)).filter(Camera.client_id == client.id).scalar() or 0
    result = ClientRead.model_validate(client)
    result.camera_count = count
    return result


@router.get("", response_model=List[ClientRead])
def list_clients(
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    clients = db.query(Client).options(joinedload(Client.plan)).all()
    return [_build_client_read(c, db) for c in clients]


@router.post("", response_model=ClientRead, status_code=201)
def create_client(
    payload: ClientCreateWithAdmin,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    # Papel do usuário de acesso: admin do cliente ou usuário comum (nunca
    # super_admin via este fluxo).
    try:
        access_role = UserRole(payload.admin_role)
    except ValueError:
        access_role = UserRole.client_admin
    if access_role == UserRole.super_admin:
        raise HTTPException(status_code=400, detail="Papel inválido para usuário de cliente")

    if db.query(Client).filter(Client.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email de cliente ja cadastrado")
    if db.query(User).filter(User.email == payload.admin_email).first():
        raise HTTPException(status_code=400, detail="Email do usuário de acesso ja cadastrado")

    client = Client(
        name=payload.name,
        email=payload.email,
        plan_id=payload.plan_id,
        plan_expires_at=payload.plan_expires_at,
        is_active=payload.is_active,
    )
    db.add(client)
    db.flush()

    admin = User(
        name=payload.admin_name,
        email=payload.admin_email,
        password_hash=hash_password(payload.admin_password),
        role=access_role,
        client_id=client.id,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(client)

    result = ClientRead.model_validate(client)
    result.camera_count = 0
    return result


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    client = (
        db.query(Client).options(joinedload(Client.plan)).filter(Client.id == client_id).first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return _build_client_read(client, db)


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    client = (
        db.query(Client).options(joinedload(Client.plan)).filter(Client.id == client_id).first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(client, k, v)
    db.commit()
    db.refresh(client)
    return _build_client_read(client, db)


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")

    camera_ids = [row.id for row in db.query(Camera.id).filter(Camera.client_id == client_id).all()]
    plate_ids = [row.id for row in db.query(MonitoredPlate.id).filter(MonitoredPlate.client_id == client_id).all()]

    if camera_ids:
        occ_ids = [row.id for row in db.query(Occurrence.id).filter(Occurrence.camera_id.in_(camera_ids)).all()]
        if occ_ids:
            db.query(AlertSent).filter(AlertSent.occurrence_id.in_(occ_ids)).delete(synchronize_session=False)
            db.query(Occurrence).filter(Occurrence.id.in_(occ_ids)).delete(synchronize_session=False)

    if plate_ids:
        db.query(AlertSent).filter(AlertSent.monitored_plate_id.in_(plate_ids)).delete(synchronize_session=False)
        db.query(MonitoredPlate).filter(MonitoredPlate.id.in_(plate_ids)).delete(synchronize_session=False)

    if camera_ids:
        db.query(Camera).filter(Camera.id.in_(camera_ids)).delete(synchronize_session=False)

    db.query(User).filter(User.client_id == client_id).delete(synchronize_session=False)
    db.delete(client)
    db.commit()
