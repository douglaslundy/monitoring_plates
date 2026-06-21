import uuid
from sqlalchemy import Column, String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Person(Base):
    __tablename__ = "persons"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # NULL = pessoa "global" do super_admin (sem cliente): reconhecida em todas as
    # câmeras e só o super_admin a vê. Ver face_alert_service / face_service.
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    name = Column(String(255), nullable=False)
    birth_date = Column(Date, nullable=True)
    cpf = Column(String(14), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    photo_path = Column(String(500), nullable=True)
    alert_active = Column(Boolean, nullable=False, default=False)
    alert_email = Column(String(255), nullable=True)
    alert_whatsapp = Column(String(30), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="persons")
    faces = relationship("PersonFace", back_populates="person", cascade="all, delete-orphan")
    detections = relationship("FaceDetection", back_populates="person")
