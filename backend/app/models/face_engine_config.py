import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, Float
from sqlalchemy import Uuid
from sqlalchemy.sql import func

from app.core.database import Base


class FaceEngineType(str, enum.Enum):
    opencv = "opencv"
    insightface = "insightface"
    deepface = "deepface"
    rekognition = "rekognition"
    luxand = "luxand"
    facepp = "facepp"


class FaceEngineConfig(Base):
    __tablename__ = "face_engine_configs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine_type = Column(String(30), nullable=False)
    mode = Column(String(15), nullable=False, default="cloud")
    is_active = Column(Boolean, nullable=False, default=False)
    api_token = Column(String(255), nullable=True)     # AWS access key / Luxand token / Face++ key
    api_secret = Column(String(255), nullable=True)    # AWS secret / Face++ secret
    api_url = Column(String(500), nullable=True)        # endpoint Luxand/Face++ (opcional)
    region = Column(String(50), nullable=True)          # AWS region
    threshold = Column(Float, nullable=False, default=0.80)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
