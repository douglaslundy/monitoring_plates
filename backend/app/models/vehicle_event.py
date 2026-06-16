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
    # Categoria da detecção: vehicle | person | animal.
    category = Column(String(10), nullable=False, default="vehicle", server_default="vehicle", index=True)
    # Label da detecção (car/truck/person/dog/cat/...). Nome mantido por compat.
    vehicle_type = Column(String(20), nullable=False, index=True)
    # Id do rastro (object_tracker_service) que originou o evento — count-once.
    track_id = Column(String(40), nullable=True, index=True)
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
