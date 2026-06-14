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
    WORKER_DELAY_QUEUE_THRESHOLD: int = 20
    WORKER_DELAY_ALERT_COOLDOWN_SECONDS: int = 300

    def get_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
