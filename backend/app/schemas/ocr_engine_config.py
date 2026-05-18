from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from app.models.ocr_engine_config import OcrEngineType, OcrEngineMode

PLATE_RECOGNIZER_DEFAULT_URL = "https://api.platerecognizer.com/v1/plate-reader/"


class OcrEngineConfigBase(BaseModel):
    engine_type: OcrEngineType
    mode: OcrEngineMode = OcrEngineMode.cloud
    is_active: bool = False
    api_token: Optional[str] = None
    api_url: Optional[str] = None
    license_key: Optional[str] = None
    regions: Optional[List[str]] = None
    enable_mmc: bool = False

    @field_validator("api_url", mode="before")
    @classmethod
    def set_default_url(cls, v: Optional[str], info) -> Optional[str]:
        if v:
            return v
        data = info.data if hasattr(info, "data") else {}
        engine = data.get("engine_type")
        mode = data.get("mode", OcrEngineMode.cloud)
        if engine == OcrEngineType.plate_recognizer and mode == OcrEngineMode.cloud:
            return PLATE_RECOGNIZER_DEFAULT_URL
        return v


class OcrEngineConfigCreate(OcrEngineConfigBase):
    pass


class OcrEngineConfigUpdate(BaseModel):
    mode: Optional[OcrEngineMode] = None
    is_active: Optional[bool] = None
    api_token: Optional[str] = None
    api_url: Optional[str] = None
    license_key: Optional[str] = None
    regions: Optional[List[str]] = None
    enable_mmc: Optional[bool] = None


class OcrEngineConfigRead(OcrEngineConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime

    # Nunca expõe token/license_key em texto puro — mostra apenas se está configurado
    api_token: Optional[str] = None
    license_key: Optional[str] = None

    @field_validator("api_token", "license_key", mode="before")
    @classmethod
    def mask_secrets(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return "***configured***"
        return None


class OcrEngineTestResult(BaseModel):
    success: bool
    engine_type: OcrEngineType
    message: str
    sample_response: Optional[dict] = None
