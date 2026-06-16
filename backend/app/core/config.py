from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/monitoramento"
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str = "troque-esta-chave-em-producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    STORAGE_TYPE: str = "local"
    STORAGE_PATH: str = "./storage"
    S3_BUCKET: str = ""
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "alertas@seudominio.com"

    CORS_ORIGINS: str = "http://localhost:3000"

    AGENT_FRAME_INTERVAL: int = 1
    AGENT_MIN_CONFIDENCE: float = 0.70
    AGENT_DEDUP_SECONDS: int = 30
    VEHICLE_EVENT_DEDUP_SECONDS: int = 45
    PILOT_CAMERA_IDS: str = ""
    HIGH_VOLUME_PREVIEW_FPS_THRESHOLD: int = 18
    HIGH_VOLUME_SAMPLE_EVERY: int = 3
    WORKER_DELAY_QUEUE_THRESHOLD: int = 20
    WORKER_DELAY_ALERT_COOLDOWN_SECONDS: int = 300
    OCR_PIPELINE_ALERT_COOLDOWN_SECONDS: int = 300
    OCR_ALLOWLIST: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    # Detecção de veículos (YOLOv8n ONNX)
    VEHICLE_CONF_THRESHOLD: float = 0.35
    VEHICLE_IOU_THRESHOLD: float = 0.45
    VEHICLE_DETECTOR_THREADS: int = 1
    # Categorias extras de detecção (mesmo modelo YOLOv8n/COCO).
    DETECT_PERSONS: bool = True
    DETECT_ANIMALS: bool = True
    # Confiança mínima por categoria. Pessoa/animal mais altos porque o YOLOv8n
    # (nano) os confunde a distância (ex.: cachorro detectado como pessoa).
    PERSON_CONF_THRESHOLD: float = 0.55
    ANIMAL_CONF_THRESHOLD: float = 0.55

    # Qualidade das imagens (reduz perda por recompressão JPEG na cadeia
    # captura -> análise -> recorte salvo).
    CAPTURE_JPEG_QUALITY: int = 92
    DETECTION_JPEG_QUALITY: int = 95
    # Upscale (cúbico) de recortes cujo maior lado seja menor que isto, p/ a
    # imagem salva ficar maior e mais legível a olho. 0 desliga.
    DETECTION_MIN_CROP_SIDE: int = 320
    # Margem simétrica ao redor do objeto na imagem de exibição (centraliza o
    # objeto com contexto). 0.5 = recorte ~1.5x o bbox em cada eixo.
    DETECTION_DISPLAY_MARGIN: float = 0.5

    # Rastreador multi-objeto (object_tracker_service)
    TRACK_IOU_MIN: float = 0.30
    TRACK_MAX_AGE_SECONDS: float = 3.0
    # Frames mínimos para confirmar/contar um track. 1 = conta ao aparecer (o
    # próprio track impede recontagem enquanto o objeto permanece). Aumente para
    # filtrar detecções espúrias de 1 frame.
    TRACK_MIN_HITS: int = 1

    # Captura RTSP + motion gating (capture-runner)
    CAPTURE_FPS: float = 6.0
    MOTION_MIN_AREA_RATIO: float = 0.0035
    MOTION_COOLDOWN_SECONDS: float = 0.0

    # Live WebRTC (go2rtc). GO2RTC_URL = endpoint interno p/ a API (sync de
    # streams); GO2RTC_PUBLIC_URL = base acessada pelo navegador do operador.
    GO2RTC_URL: str = "http://go2rtc:1984"
    GO2RTC_PUBLIC_URL: str = "http://192.168.0.115:1984"
    GO2RTC_ENABLED: bool = True

    def get_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    def get_pilot_camera_ids(self) -> List[str]:
        return [camera_id.strip() for camera_id in self.PILOT_CAMERA_IDS.split(",") if camera_id.strip()]


settings = Settings()
