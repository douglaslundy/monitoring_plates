import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy import Uuid
from sqlalchemy.sql import func

from app.core.database import Base


class OcrEngineType(str, enum.Enum):
    easyocr = "easyocr"
    plate_recognizer = "plate_recognizer"


class OcrEngineMode(str, enum.Enum):
    cloud = "cloud"
    onpremise = "onpremise"


class OcrEngineConfig(Base):
    __tablename__ = "ocr_engine_configs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine_type = Column(String(30), nullable=False)
    mode = Column(String(15), nullable=False, default=OcrEngineMode.cloud)
    is_active = Column(Boolean, nullable=False, default=False)
    api_token = Column(String(255), nullable=True)
    api_url = Column(String(500), nullable=True)
    license_key = Column(String(255), nullable=True)
    regions = Column(JSON, nullable=True)
    enable_mmc = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
