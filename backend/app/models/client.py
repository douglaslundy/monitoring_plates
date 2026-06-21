import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    plan_id = Column(Uuid(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Data de ativação do plano atual (preenchida no cadastro e atualizada
    # quando o plano do cliente muda).
    plan_activated_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("Plan", back_populates="clients")
    users = relationship("User", back_populates="client")
    cameras = relationship("Camera", back_populates="client")
    monitored_plates = relationship("MonitoredPlate", back_populates="client")
    persons = relationship("Person", back_populates="client")
