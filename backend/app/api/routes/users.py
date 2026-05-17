from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.deps import get_db, get_current_user, require_client_admin
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserRead])
def list_users(
    client_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.super_admin:
        q = db.query(User)
        if client_id:
            q = q.filter(User.client_id == client_id)
        return q.all()
    if current_user.role == UserRole.client_admin:
        return db.query(User).filter(User.client_id == current_user.client_id).all()
    raise HTTPException(status_code=403, detail="Acesso não autorizado")


@router.post("/", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    if current_user.role != UserRole.super_admin:
        if payload.client_id and payload.client_id != current_user.client_id:
            raise HTTPException(status_code=403, detail="Não é possível criar usuário para outro cliente")
        if payload.role == UserRole.super_admin:
            raise HTTPException(status_code=403, detail="Permissão insuficiente para criar super_admin")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    effective_client_id = payload.client_id
    if current_user.role == UserRole.client_admin and not effective_client_id:
        effective_client_id = current_user.client_id

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        client_id=effective_client_id,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if current_user.role != UserRole.super_admin and user.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if current_user.role != UserRole.super_admin and user.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    data = payload.model_dump(exclude_none=True)
    if "password" in data:
        data["password_hash"] = hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if current_user.role != UserRole.super_admin and user.client_id != current_user.client_id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    db.delete(user)
    db.commit()
