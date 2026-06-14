import enum
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Float
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ConnectionType(str, enum.Enum):
    rtsp = "rtsp"
    agent = "agent"


class LensSide(str, enum.Enum):
    upper = "upper"
    lower = "lower"


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    location = Column(String(500), nullable=True)
    connection_type = Column(
        Enum(ConnectionType, native_enum=False, length=10),
        nullable=False,
    )
    rtsp_url = Column(String(500), nullable=True)
    agent_token = Column(String(64), unique=True, nullable=True)
    dual_lens = Column(Boolean, nullable=False, default=False)
    lens_side = Column(
        Enum(LensSide, native_enum=False, length=10),
        nullable=True,
    )
    roi_x = Column(Float, nullable=True)
    roi_y = Column(Float, nullable=True)
    roi_width = Column(Float, nullable=True)
    roi_height = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="cameras")
    occurrences = relationship("Occurrence", back_populates="camera")
    vehicle_events = relationship("VehicleEvent", back_populates="camera")

    @property
    def is_online(self) -> bool:
        if not self.is_active:
            return False
        if self.last_seen_at is None:
            return False
        lsa = self.last_seen_at
        if lsa.tzinfo is None:
            lsa = lsa.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - lsa < timedelta(minutes=2)
