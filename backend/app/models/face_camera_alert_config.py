"""Configuração de alertas de reconhecimento facial por câmera.

Controla:
- Alertas para faces NÃO cadastradas (unknown_face_active)
- Janela de horário e dias da semana (schedule_*)
- Cooldown entre alertas do mesmo track/pessoa (cooldown_minutes)

As regras de schedule e cooldown se aplicam tanto para faces cadastradas
quanto para faces desconhecidas.
"""
import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class FaceCameraAlertConfig(Base):
    __tablename__ = "face_camera_alert_configs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(Uuid(as_uuid=True), ForeignKey("cameras.id"), nullable=False, unique=True)

    # Alertas para faces desconhecidas (não cadastradas)
    unknown_face_active = Column(Boolean, nullable=False, default=False)
    unknown_face_email = Column(String(255), nullable=True)
    unknown_face_whatsapp = Column(String(30), nullable=True)

    # Janela de horário: início e duração (minutos). NULL = sem restrição.
    # Aplica-se a faces cadastradas E não cadastradas.
    schedule_start_time = Column(String(8), nullable=True)   # "HH:MM" ou "HH:MM:SS"
    schedule_duration_minutes = Column(Integer, nullable=True)
    # Dias da semana (JSON): "[0,1,2,3,4,5,6]" onde 0=segunda, 6=domingo. NULL = todos.
    schedule_days_of_week = Column(String(50), nullable=True)

    # Cooldown em minutos entre alertas da mesma pessoa/câmera. 0 = sem cooldown.
    cooldown_minutes = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    camera = relationship("Camera")
