from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.ops import OpsMetricsRead
from app.services.operational_metrics_service import build_operational_metrics

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/metrics", response_model=OpsMetricsRead)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = build_operational_metrics(db, current_user)
    return OpsMetricsRead.model_validate(metrics.as_dict())
