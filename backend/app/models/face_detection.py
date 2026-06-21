import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class FaceDetection(Base):
    __tablename__ = "face_detections"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(Uuid(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    person_id = Column(Uuid(as_uuid=True), ForeignKey("persons.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    image_path = Column(String(500), nullable=True)
    bbox_x = Column(Integer, nullable=True)
    bbox_y = Column(Integer, nullable=True)
    bbox_w = Column(Integer, nullable=True)
    bbox_h = Column(Integer, nullable=True)
    track_id = Column(String(32), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    tracked_seconds = Column(Float, nullable=True)
    face_engine_used = Column(String(30), nullable=True)

    camera = relationship("Camera", back_populates="face_detections")
    person = relationship("Person", back_populates="detections")
