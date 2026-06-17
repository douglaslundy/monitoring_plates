"""Configuração do modelo de detecção (YOLO) usado pelo detector (Tarefa A).

O admin escolhe qual modelo (yolov8n/s/m...) o detector usa. A seleção é
persistida no Redis e lida pelos workers, que recarregam o modelo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User, UserRole
from app.services.detector_model_service import (
    available_models,
    default_model,
    get_selected_model,
    set_selected_model,
)

router = APIRouter(prefix="/detector", tags=["detector"])


class DetectorModelRead(BaseModel):
    current: str
    default: str
    available: list[str]


class DetectorModelUpdate(BaseModel):
    model: str


@router.get("/model", response_model=DetectorModelRead)
def get_model(current_user: User = Depends(get_current_user)):
    return DetectorModelRead(
        current=get_selected_model(),
        default=default_model(),
        available=available_models(),
    )


@router.put("/model", response_model=DetectorModelRead)
def update_model(
    payload: DetectorModelUpdate,
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito ao super_admin.")
    avail = available_models()
    if payload.model not in avail:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo '{payload.model}' indisponível. Disponíveis: {', '.join(avail) or 'nenhum'}.",
        )
    if not set_selected_model(payload.model):
        raise HTTPException(status_code=503, detail="Não foi possível salvar a seleção (Redis indisponível).")
    return DetectorModelRead(
        current=get_selected_model(),
        default=default_model(),
        available=avail,
    )
