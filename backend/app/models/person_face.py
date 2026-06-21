import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PersonFace(Base):
    __tablename__ = "person_faces"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id = Column(Uuid(as_uuid=True), ForeignKey("persons.id"), nullable=False)
    engine_type = Column(String(30), nullable=False)
    embedding = Column(JSON, nullable=True)           # vetor local (OpenCV)
    external_ref = Column(String(255), nullable=True)  # FaceId/face_token/uuid da nuvem
    image_path = Column(String(500), nullable=True)    # foto de referência p/ re-index
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    person = relationship("Person", back_populates="faces")
