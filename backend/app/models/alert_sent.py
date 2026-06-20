import enum
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AlertChannel(str, enum.Enum):
    email = "email"
    websocket = "websocket"
    whatsapp = "whatsapp"


class AlertSent(Base):
    __tablename__ = "alerts_sent"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurrence_id = Column(Uuid(as_uuid=True), ForeignKey("occurrences.id"), nullable=False)
    monitored_plate_id = Column(Uuid(as_uuid=True), ForeignKey("monitored_plates.id"), nullable=False)
    channel = Column(
        Enum(AlertChannel, native_enum=False, length=15),
        nullable=False,
    )
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)

    occurrence = relationship("Occurrence", back_populates="alerts_sent")
    monitored_plate = relationship("MonitoredPlate", back_populates="alerts_sent")
