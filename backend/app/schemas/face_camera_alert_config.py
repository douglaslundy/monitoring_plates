from typing import Optional, List
from pydantic import BaseModel, field_validator
import json


class FaceCameraAlertConfigBase(BaseModel):
    unknown_face_active: bool = False
    unknown_face_email: Optional[str] = None
    unknown_face_whatsapp: Optional[str] = None
    schedule_start_time: Optional[str] = None
    schedule_duration_minutes: Optional[int] = None
    schedule_days_of_week: Optional[str] = None  # JSON string "[0,1,2,3,4]"
    cooldown_minutes: int = 0

    @field_validator("schedule_days_of_week", mode="before")
    @classmethod
    def validate_days(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            return json.dumps(v)
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if not isinstance(parsed, list):
                    raise ValueError
                return json.dumps([int(d) for d in parsed])
            except Exception:
                raise ValueError("schedule_days_of_week deve ser uma lista JSON de inteiros 0-6")
        return v


class FaceCameraAlertConfigCreate(FaceCameraAlertConfigBase):
    pass


class FaceCameraAlertConfigUpdate(FaceCameraAlertConfigBase):
    pass


class FaceCameraAlertConfigRead(FaceCameraAlertConfigBase):
    id: str
    camera_id: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @field_validator("id", "camera_id", mode="before")
    @classmethod
    def uuid_to_str(cls, v):
        return str(v)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def dt_to_str(cls, v):
        return v.isoformat() if v else ""
