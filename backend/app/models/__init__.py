from app.models.plan import Plan
from app.models.client import Client
from app.models.user import User
from app.models.camera import Camera
from app.models.monitored_plate import MonitoredPlate
from app.models.occurrence import Occurrence
from app.models.alert_sent import AlertSent
from app.models.ocr_engine_config import OcrEngineConfig
from app.models.vehicle_event import VehicleEvent
from app.models.whatsapp_channel_settings import WhatsAppChannelSettings
from app.models.person import Person
from app.models.person_face import PersonFace
from app.models.face_detection import FaceDetection
from app.models.face_engine_config import FaceEngineConfig
from app.models.face_camera_alert_config import FaceCameraAlertConfig

__all__ = [
    "Plan",
    "Client",
    "User",
    "Camera",
    "MonitoredPlate",
    "Occurrence",
    "AlertSent",
    "OcrEngineConfig",
    "VehicleEvent",
    "WhatsAppChannelSettings",
    "Person",
    "PersonFace",
    "FaceDetection",
    "FaceEngineConfig",
    "FaceCameraAlertConfig",
]
