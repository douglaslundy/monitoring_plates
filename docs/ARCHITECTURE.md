# Arquitetura do Sistema

## Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENTE (browser)                          │
│                     Next.js 14 + TypeScript                         │
│          JWT cookie httpOnly │ WebSocket para alertas em tempo real │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          nginx (proxy)                              │
│         /api/* → backend:8000   │   /* → frontend:3000             │
│              /ws/* → backend:8000 (WebSocket upgrade)              │
└──────────┬───────────────────────────────────────────┬─────────────┘
           │                                           │
           ▼                                           ▼
┌──────────────────────┐                   ┌──────────────────────────┐
│   Backend FastAPI    │                   │    Frontend Next.js       │
│   Python 3.11        │                   │    Node 20 (standalone)  │
│                      │                   └──────────────────────────┘
│  Routers:            │
│  /auth /users        │   ┌─────────────────────────────────────────┐
│  /clients /cameras   │──▶│          PostgreSQL 15                  │
│  /occurrences        │   │  Multi-tenant com client_id em todas    │
│  /plates /alerts     │   │  as tabelas de dados                    │
│  /plans /agent       │   └─────────────────────────────────────────┘
│  /ws (WebSocket)     │
│                      │   ┌─────────────────────────────────────────┐
│  Middlewares:        │──▶│              Redis 7                    │
│  CORS / Rate limit   │   │  • Broker Celery (fila "frames")        │
│  Security headers    │   │  • Pub/Sub ws:alerts:{client_id}        │
└──────────┬───────────┘   └─────────────────────────────────────────┘
           │
           │ Celery task (base64 frame)
           ▼
┌──────────────────────┐
│   Worker OCR         │   ┌─────────────────────────────────────────┐
│   Celery + EasyOCR   │──▶│    Armazenamento de Imagens             │
│                      │   │  Dev: volume local /app/storage         │
│  pipeline:           │   │  Prod: Cloudflare R2 (S3-compatible)    │
│  resize → gray →     │   └─────────────────────────────────────────┘
│  CLAHE → bilateral → │
│  Canny → ROI →       │
│  EasyOCR → regex     │
└──────────┬───────────┘
           │ plate detectada
           ▼
┌──────────────────────┐
│  Alert Service       │
│  • verifica          │
│    monitored_plates  │
│  • e-mail (Resend)   │
│  • Redis pub/sub     │
│    → WebSocket       │
└──────────────────────┘

┌───────────────────────────────────┐
│   Agente Local (cliente)          │
│   Python + OpenCV (.exe Windows)  │
│                                   │
│   config.json                     │
│   ┌──────────────────────────┐    │
│   │ server_url               │    │
│   │ token (agent_token)      │    │
│   │ camera_rtsp              │    │
│   │ frame_interval (seg)     │    │
│   └──────────────────────────┘    │
│                                   │
│   Loop:                           │
│   1. captura frame da câmera RTSP │
│   2. POST /api/agent/frame        │
│      Authorization: Bearer {token}│
│   3. aguarda frame_interval       │
└───────────────────────────────────┘
```

## Fluxo completo de uma detecção

```
Câmera RTSP
    │
    │ frame JPEG
    ▼
Agente local (Python)
    │
    │ POST /api/agent/frame  (multipart + Bearer token)
    ▼
Backend FastAPI
    │
    │ valida agent_token → camera_id
    │ process_frame.delay(camera_id, base64_frame)
    ▼
Redis (fila "frames")
    │
    ▼
Worker Celery + EasyOCR
    │
    │ OCR → placa "ABC1234" (confidence 0.87)
    │ dedup: já processado nos últimos 30s? → descarta
    │ salva JPEG → /storage/cameras/{camera_id}/{timestamp}.jpg
    │ cria Occurrence no PostgreSQL
    ▼
Alert Service
    │
    ├── "ABC1234" está em monitored_plates deste cliente?
    │       ├── Sim, plano tem email_alerts? → Resend API → e-mail
    │       └── Sim, plano tem realtime_alerts? → Redis PUBLISH ws:alerts:{client_id}
    │
    └── Backend (subscriber) → WebSocket → browser do cliente
```

## Modelo de dados (resumido)

```
Plan ──< Client ──< User
                 ──< Camera ──< Occurrence ──< AlertSent
                 ──< MonitoredPlate
```

## Decisões de arquitetura

| Decisão | Justificativa |
|---|---|
| EasyOCR sobre Tesseract | Melhor precisão para placas brasileiras, suporte nativo a modelos pré-treinados |
| Celery + Redis | Processamento OCR assíncrono: o agente recebe ACK imediato, não espera 2-3s do OCR |
| Redis Pub/Sub para WebSocket | Suporta múltiplas réplicas do backend sem estado compartilhado em memória |
| JWT em cookie httpOnly | Proteção contra XSS; o frontend nunca acessa o token via JS |
| native_enum=False | Compatibilidade do modelo com SQLite nos testes sem alterar produção PostgreSQL |
| agent_token separado de JWT | Token de longa duração para agentes físicos; JWT expira em 8h para humanos |
| Isolamento por client_id | Toda query filtra pelo client_id do usuário autenticado; super_admin bypassa |
