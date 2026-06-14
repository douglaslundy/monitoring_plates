import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class VehicleEvent(Base):
    __tablename__ = "vehicle_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(Uuid(as_uuid=True), ForeignKey("cameras.id"), nullable=False, index=True)
    occurrence_id = Column(Uuid(as_uuid=True), ForeignKey("occurrences.id"), nullable=True, index=True)
    vehicle_type = Column(String(20), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    image_path = Column(String(500), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    camera = relationship("Camera", back_populates="vehicle_events")
    occurrence = relationship("Occurrence")
