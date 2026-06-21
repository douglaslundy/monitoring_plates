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

    WHATSAPP_EVOLUTION_API_KEY: str = ""
    WHATSAPP_EVOLUTION_BASE_URL: str = "http://192.168.0.115:8081"
    WHATSAPP_EVOLUTION_INSTANCE_NAME: str = "whatsapp"
    WHATSAPP_FRAME_MAX_SIDE: int = 1280
    WHATSAPP_FRAME_JPEG_QUALITY: int = 82
    WHATSAPP_WEBHOOK_TIMEOUT_SECONDS: int = 20

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
    # Confiança mínima por categoria. Elevadas (T4) para reduzir classificações
    # erradas de baixa confiança (homem como urso, cão como pessoa). O voto de
    # classe ao longo do track (object_tracker_service) corrige o resto: um erro
    # pontual de 1 frame é vencido pela maioria.
    PERSON_CONF_THRESHOLD: float = 0.55
    ANIMAL_CONF_THRESHOLD: float = 0.55

    # Qualidade das imagens (reduz perda por recompressão JPEG na cadeia
    # captura -> análise -> recorte salvo).
    CAPTURE_JPEG_QUALITY: int = 92
    DETECTION_JPEG_QUALITY: int = 95
    # Upscale (cúbico) de recortes cujo maior lado seja menor que isto, p/ a
    # imagem salva ficar maior e mais legível a olho. 0 desliga.
    DETECTION_MIN_CROP_SIDE: int = 320

    # Reconhecimento facial (motor local OpenCV: YuNet detecção + SFace embedding).
    # Os .onnx são embutidos na imagem Docker; FACE_MODEL_DIR cai p/ MODELS_DIR.
    FACE_MODEL_DIR: str = ""  # vazio -> usa MODELS_DIR no serviço
    FACE_DETECTOR_MODEL: str = "face_detection_yunet_2023mar.onnx"
    FACE_RECOGNIZER_MODEL: str = "face_recognition_sface_2021dec.onnx"
    FACE_MIN_DETECT_SCORE: float = 0.7
    FACE_MATCH_THRESHOLD: float = 0.36  # similaridade de cosseno SFace
    FACE_MIN_CROP_SIDE: int = 80

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
    # Gate = este fator × tamanho médio do bbox (px). Maior = associa objetos que
    # se deslocam mais entre frames processados (o worker processa < captura por
    # causa do OCR), evitando fragmentar em vários tracks (3-4 registros). Usado
    # junto com a previsão por velocidade (_predict_bbox).
    TRACK_CENTER_DIST_GATE: float = 2.5
    # Re-save por mudança de classe só dispara quando a nova classe votada tem ESTE
    # nº de votos a mais que a salva — evita re-save a cada flicker (bus<->car).
    TRACK_CLASS_CHANGE_MARGIN: int = 3
    # Associação CROSS-CATEGORY (T4): sobreposição (IoU) >= este limiar ALTO entre
    # uma detecção e um track de categoria diferente = mesmo objeto físico
    # classificado de formas diferentes entre frames (cão/pessoa, homem/urso).
    # Permite ao track VOTAR a classe correta sem fundir objetos distintos.
    TRACK_SAME_OBJECT_IOU: float = 0.70
    # Margem (fração da dimensão do frame) para considerar o objeto "inteiro no
    # frame": o bbox não pode tocar as bordas. O frame só é salvo quando o objeto
    # confirmado aparece por completo (ou após TRACK_FORCE_SAVE_HITS).
    TRACK_EDGE_MARGIN_RATIO: float = 0.02
    # Fallback: se o objeto for confirmado mas nunca couber inteiro no frame
    # (veículo grande/cortado), salva mesmo assim após este nº de frames vistos.
    TRACK_FORCE_SAVE_HITS: int = 4
    # Objeto PARADO: um track cujo centro praticamente não se move é considerado
    # estacionário e ganha uma sobrevida bem maior, para não ser "redescoberto"
    # como novo (e re-salvo) quando algo passa após um longo período sem
    # movimento. Um veículo que apenas passou (estava em movimento) expira no
    # TRACK_MAX_AGE_SECONDS normal — então um novo veículo no mesmo ponto ainda
    # é contado.
    TRACK_STATIONARY_MAX_AGE_SECONDS: float = 300.0
    # Estacionário = deslocamento médio do centro por frame <= este fator × tamanho
    # médio do bbox, após TRACK_STATIONARY_MIN_HITS frames.
    TRACK_STATIONARY_RADIUS_RATIO: float = 0.25
    TRACK_STATIONARY_MIN_HITS: int = 3
    # Votos mínimos da classe vencedora para REGISTRAR uma pessoa/animal. Separa o
    # limiar de RASTREAR (baixo, no detector — captura objeto pequeno/distante) do
    # de REGISTRAR (estável): um erro de classe de 1 frame (cão<->pessoa) não vira
    # registro; só a maioria ao longo do track conta. Veículos não usam isto (a
    # placa é o sinal). Diferente do gating "inteiro no frame", pessoa/animal NÃO
    # precisa caber inteiro p/ contar — corrige animais que cruzam rápido na borda.
    TRACK_MIN_REGISTER_VOTES: int = 2

    # ── Política de OCR híbrida (frame_processor) ──────────────────────────────
    # Qualidade mínima do recorte (0..1, frame_quality_service) para disparar o
    # OCR de um track ainda não lido. Evita rodar OCR em frame borrado/minúsculo.
    OCR_MIN_QUALITY: float = 0.30
    # Margem de qualidade para RE-OCR (refino): só reprocessa um track já lido se
    # surgir um frame com qualidade pelo menos esta fração melhor que a do melhor
    # frame já usado. Evita reprocessar a cada pequena variação.
    OCR_REFINE_MARGIN: float = 0.15
    # Agrupamento piloto+moto (T5): uma pessoa é considerada PILOTO de uma moto
    # quando seu bbox sobrepõe a moto em >= esta fração da área da pessoa e seu
    # centro horizontal cai dentro da moto. Vira UMA detecção (moto principal +
    # pessoa como companion), contando os dois nas estatísticas.
    RIDER_OVERLAP_MIN: float = 0.30

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
