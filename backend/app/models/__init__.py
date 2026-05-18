from app.models.plan import Plan
from app.models.client import Client
from app.models.user import User
from app.models.camera import Camera
from app.models.monitored_plate import MonitoredPlate
from app.models.occurrence import Occurrence
from app.models.alert_sent import AlertSent
from app.models.ocr_engine_config import OcrEngineConfig

__all__ = [
    "Plan",
    "Client",
    "User",
    "Camera",
    "MonitoredPlate",
    "Occurrence",
    "AlertSent",
    "OcrEngineConfig",
]
