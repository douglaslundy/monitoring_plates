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

    # Detecção de objetos (YOLOv8s ONNX, COCO)
    VEHICLE_CONF_THRESHOLD: float = 0.35
    VEHICLE_IOU_THRESHOLD: float = 0.45
    VEHICLE_DETECTOR_THREADS: int = 1
    # Máximo de objetos retornados por frame (cada um vira um track contado uma
    # vez). Mais alto p/ não descartar objetos pequenos em cenas com vários alvos.
    MAX_DETECTIONS_PER_FRAME: int = 10
    # Categorias extras de detecção (mesmo modelo YOLOv8s/COCO).
    DETECT_PERSONS: bool = True
    DETECT_ANIMALS: bool = True
    # Confiança mínima por categoria. Animal mais baixo (recall): o yolov8s erra
    # menos que o nano antigo, então 0.55 perdia cachorros legítimos. Pessoa segue
    # um pouco mais alta p/ reduzir cachorro classificado como pessoa à distância.
    PERSON_CONF_THRESHOLD: float = 0.50
    ANIMAL_CONF_THRESHOLD: float = 0.40

    # Qualidade das imagens (reduz perda por recompressão JPEG na cadeia
    # captura -> análise -> recorte salvo).
    CAPTURE_JPEG_QUALITY: int = 92
    DETECTION_JPEG_QUALITY: int = 95
    # Upscale (cúbico) de recortes cujo maior lado seja menor que isto, p/ a
    # imagem salva ficar maior e mais legível a olho. 0 desliga.
    DETECTION_MIN_CROP_SIDE: int = 320

    # Rastreador multi-objeto (object_tracker_service)
    TRACK_IOU_MIN: float = 0.20
    # Tempo de vida do track sem ser visto. Generoso de propósito: com motion
    # gating uma cena estática não atualiza os tracks, então um carro PARADO
    # precisa sobreviver aos intervalos sem movimento para não ser redescoberto
    # como novo (e re-salvo) toda vez que algo passa. Quanto maior, menos
    # re-salvamento de objeto parado — mas dois veículos distintos no MESMO ponto
    # dentro desta janela podem ser fundidos (subcontagem). Ajuste por câmera.
    TRACK_MAX_AGE_SECONDS: float = 30.0
    # Frames mínimos para CONFIRMAR um track. 1 = confirma ao aparecer (não
    # subconta objetos vistos em um único frame amostrado e não exige estado
    # SEMPRE no Redis). A contagem-única vem do flag `counted` do track + a
    # máquina de salvamento (só salva quando o objeto aparece inteiro no frame e
    # re-salva só em mudança de classe/placa), não de exigir vários frames.
    TRACK_MIN_HITS: int = 1
    # Associação por proximidade do centro (além do IoU): um objeto em movimento
    # pode não ter IoU entre frames amostrados, mas seu centro continua próximo.
    # Gate = este fator × tamanho médio do bbox (px). Mantém o mesmo track.
    TRACK_CENTER_DIST_GATE: float = 1.5
    # Margem (fração da dimensão do frame) para considerar o objeto "inteiro no
    # frame": o bbox não pode tocar as bordas. O frame só é salvo quando o objeto
    # confirmado aparece por completo (ou após TRACK_FORCE_SAVE_HITS).
    TRACK_EDGE_MARGIN_RATIO: float = 0.02
    # Fallback: se o objeto for confirmado mas nunca couber inteiro no frame
    # (veículo grande/cortado), salva mesmo assim após este nº de frames vistos.
    TRACK_FORCE_SAVE_HITS: int = 4

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
