from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from uuid import UUID

from app.api.deps import get_db, require_super_admin
from app.core.security import hash_password
from app.models.client import Client
from app.models.camera import Camera
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
    if db.query(Client).filter(Client.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email de cliente já cadastrado")
    if db.query(User).filter(User.email == payload.admin_email).first():
        raise HTTPException(status_code=400, detail="Email do administrador já cadastrado")

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
        role=UserRole.client_admin,
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
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
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
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(client, k, v)
    db.commit()
    db.refresh(client)
    return _build_client_read(client, db)


@router.delete("/{client_id}", status_code=204)
def deactivate_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    client.is_active = False
    db.query(User).filter(User.client_id == client_id).update({"is_active": False})
    db.commit()
