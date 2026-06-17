from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID

from app.api.deps import get_db, get_current_user, require_super_admin
from app.models.plan import Plan
from app.models.client import Client
from app.schemas.plan import PlanCreate, PlanRead, PlanUpdate

router = APIRouter(prefix="/plans", tags=["plans"])


def _build_plan_read(plan: Plan, db: Session) -> PlanRead:
    count = (
        db.query(func.count(Client.id))
        .filter(Client.plan_id == plan.id, Client.is_active == True)  # noqa: E712
        .scalar()
        or 0
    )
    result = PlanRead.model_validate(plan)
    result.client_count = count
    return result


@router.get("", response_model=List[PlanRead])
def list_plans(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Por padrão só planos ativos (seleção de plano no cadastro de cliente). A
    # tela de gestão usa include_inactive=true para administrar todos.
    query = db.query(Plan)
    if not include_inactive:
        query = query.filter(Plan.is_active == True)  # noqa: E712
    plans = query.order_by(Plan.price_monthly.asc()).all()
    return [_build_plan_read(p, db) for p in plans]


@router.post("", response_model=PlanRead, status_code=201)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    result = PlanRead.model_validate(plan)
    result.client_count = 0
    return result


@router.patch("/{plan_id}", response_model=PlanRead)
def update_plan(
    plan_id: UUID,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    # exclude_unset: aplica apenas os campos enviados (permite setar null p/
    # ilimitado em max_cameras/retention_days, sem zerar os demais campos).
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return _build_plan_read(plan, db)


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_super_admin),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    # Não permite excluir um plano em uso (FK clients.plan_id); orienta a
    # migrar os clientes antes. Evita IntegrityError no commit.
    in_use = db.query(func.count(Client.id)).filter(Client.plan_id == plan.id).scalar() or 0
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Plano em uso por {in_use} cliente(s). Migre-os para outro plano antes de excluir.",
        )
    db.delete(plan)
    db.commit()
