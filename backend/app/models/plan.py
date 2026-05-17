import uuid
import enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Numeric, Enum
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    max_cameras = Column(Integer, nullable=True)
    retention_days = Column(Integer, nullable=True)
    email_alerts = Column(Boolean, nullable=False, default=False)
    realtime_alerts = Column(Boolean, nullable=False, default=True)
    price_monthly = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    clients = relationship("Client", back_populates="plan")
