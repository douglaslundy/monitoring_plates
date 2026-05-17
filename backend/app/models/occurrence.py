import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Occurrence(Base):
    __tablename__ = "occurrences"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(Uuid(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    plate = Column(String(20), nullable=False, index=True)
    image_path = Column(String(500), nullable=False)
    confidence = Column(Float, nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    camera = relationship("Camera", back_populates="occurrences")
    alerts_sent = relationship("AlertSent", back_populates="occurrence")
