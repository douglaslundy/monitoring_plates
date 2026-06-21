from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.face_engine_config import FaceEngineType


class FaceEngineConfigBase(BaseModel):
    engine_type: FaceEngineType
    mode: str = "cloud"
    is_active: bool = False
    api_token: Optional[str] = None
    api_secret: Optional[str] = None
    api_url: Optional[str] = None
    region: Optional[str] = None
    threshold: float = 0.80


class FaceEngineConfigCreate(FaceEngineConfigBase):
    pass


class FaceEngineConfigUpdate(BaseModel):
    mode: Optional[str] = None
    is_active: Optional[bool] = None
    api_token: Optional[str] = None
    api_secret: Optional[str] = None
    api_url: Optional[str] = None
    region: Optional[str] = None
    threshold: Optional[float] = None


class FaceEngineConfigRead(FaceEngineConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime

    # Nunca expõe segredos em texto puro.
    api_token: Optional[str] = None
    api_secret: Optional[str] = None

    @field_validator("api_token", "api_secret", mode="before")
    @classmethod
    def mask_secrets(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return "***configured***"
        return None


class FaceEngineTestResult(BaseModel):
    success: bool
    engine_type: FaceEngineType
    message: str
