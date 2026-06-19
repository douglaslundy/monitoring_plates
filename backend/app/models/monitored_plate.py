import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MonitoredPlate(Base):
    __tablename__ = "monitored_plates"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    plate = Column(String(20), nullable=False)
    description = Column(String(500), nullable=True)
    alert_email = Column(String(255), nullable=True)
    alert_whatsapp = Column(String(30), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="monitored_plates")
    alerts_sent = relationship("AlertSent", back_populates="monitored_plate")
