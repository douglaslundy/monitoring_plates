from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.schemas.ops import OpsMetricsRead, OpsMetricsResetRead, SystemMetricsRead
from app.services.operational_metrics_service import build_operational_metrics, reset_camera_metrics
from app.services.system_metrics_service import get_system_metrics
from app.core.config import settings

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/metrics", response_model=OpsMetricsRead)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = build_operational_metrics(db, current_user)
    return OpsMetricsRead.model_validate(metrics.as_dict())


@router.post("/metrics/reset", response_model=OpsMetricsResetRead)
def reset_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Zera as métricas acumuladas (telemetria no Redis) das câmeras do escopo.

    Restrito a administradores: client_user só visualiza. Não afeta a fila do OCR.
    """
    if current_user.role not in (UserRole.super_admin, UserRole.client_admin):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
    cameras_reset = reset_camera_metrics(db, current_user)
    return OpsMetricsResetRead(cameras_reset=cameras_reset)


@router.post("/queue/flush")
def flush_queue(
    current_user: User = Depends(get_current_user),
):
    """Esvazia a fila OCR (Redis list 'frames'). Restrito a super_admin."""
    if current_user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito ao super_admin.")
    import redis as redis_lib
    r = redis_lib.from_url(settings.REDIS_URL)
    removed = r.llen("frames")
    r.delete("frames")
    return {"removed": removed}


@router.get("/system", response_model=SystemMetricsRead)
def get_system(
    current_user: User = Depends(get_current_user),
):
    """Recursos do host (CPU/RAM/disco). Restrito a super_admin (infra)."""
    if current_user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito ao super_admin.")
    return SystemMetricsRead.model_validate(get_system_metrics().as_dict())
