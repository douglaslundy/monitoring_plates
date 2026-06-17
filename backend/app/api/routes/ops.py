from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.schemas.ops import OpsMetricsRead, SystemMetricsRead
from app.services.operational_metrics_service import build_operational_metrics
from app.services.system_metrics_service import get_system_metrics

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/metrics", response_model=OpsMetricsRead)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = build_operational_metrics(db, current_user)
    return OpsMetricsRead.model_validate(metrics.as_dict())


@router.get("/system", response_model=SystemMetricsRead)
def get_system(
    current_user: User = Depends(get_current_user),
):
    """Recursos do host (CPU/RAM/disco). Restrito a super_admin (infra)."""
    if current_user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito ao super_admin.")
    return SystemMetricsRead.model_validate(get_system_metrics().as_dict())
