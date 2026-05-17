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


@router.get("/", response_model=List[PlanRead])
def list_plans(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    plans = db.query(Plan).filter(Plan.is_active == True).all()  # noqa: E712
    return [_build_plan_read(p, db) for p in plans]


@router.post("/", response_model=PlanRead, status_code=201)
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
    for k, v in payload.model_dump(exclude_none=True).items():
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
    db.delete(plan)
    db.commit()
