# ETAPA 1 — Estrutura base e infraestrutura

> Cole este prompt inteiro no Claude Code e aguarde terminar antes de avançar.

---

Vamos construir um sistema SaaS de monitoramento de trânsito com reconhecimento de placas.
É um sistema multi-tenant (vários clientes) com planos de assinatura.

Crie a estrutura completa do projeto com esta organização:

PASTAS RAIZ:
- backend/       → API Python/FastAPI
- frontend/      → Next.js 14
- agent/         → Software leve para instalar no cliente
- infra/         → Configurações de infraestrutura
- docs/          → já existe, não apagar

BACKEND (backend/):
Estrutura de pastas:
  app/
    api/routes/         → auth, users, clients, cameras, occurrences, plates, alerts, plans, agent
    api/deps.py         → dependências compartilhadas (get_db, get_current_user, require_role)
    core/
      config.py         → Settings com pydantic-settings
      database.py       → engine, SessionLocal, Base
      security.py       → hash senha, JWT, verificar token
    models/             → SQLAlchemy: Plan, Client, User, Camera, MonitoredPlate, Occurrence, AlertSent
    schemas/            → Pydantic para cada model
    services/
      ocr_service.py
      camera_service.py
      storage_service.py
      email_service.py
      alert_service.py
    workers/
      frame_processor.py
      retention_cleaner.py
    websocket/
      manager.py
    main.py
  alembic/
  tests/
  requirements.txt
  Dockerfile
  .env.example

requirements.txt deve incluir:
fastapi, uvicorn[standard], sqlalchemy, alembic, psycopg2-binary,
python-jose[cryptography], passlib[bcrypt], python-multipart,
celery[redis], redis, opencv-python-headless, easyocr, pillow,
boto3, python-dotenv, pydantic-settings, websockets, resend,
pytest, httpx, pytest-asyncio

FRONTEND (frontend/):
Next.js 14 com TypeScript, Tailwind CSS, shadcn/ui
Estrutura src/app/:
  (auth)/login/
  (auth)/forgot-password/
  admin/
    page.tsx
    clients/
    cameras/
    users/
    plans/
    search/
  client/
    page.tsx
    cameras/
    search/
    alerts/
    settings/

AGENT (agent/):
  main.py
  config.py
  capture.py
  uploader.py
  requirements.txt
  build.sh
  README.md

INFRA:
  docker-compose.yml com serviços:
  - postgres:15 com healthcheck e volume persistente
  - redis:7-alpine com volume persistente
  - backend: build ./backend, porta 8000
    command: sh -c "alembic upgrade head && python -m app.core.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    depende do postgres saudável
  - worker: mesmo Dockerfile do backend
    command: celery -A app.workers.frame_processor worker --loglevel=info -Q frames
  - retention-worker: celery -A app.workers.retention_cleaner beat --loglevel=info
  - frontend: build ./frontend, porta 3000, NEXT_PUBLIC_API_URL=http://localhost:8000
  Rede compartilhada para todos os serviços.

.env.example com todas as variáveis:
DATABASE_URL=postgresql://user:pass@postgres:5432/monitoramento
REDIS_URL=redis://redis:6379
SECRET_KEY=troque-esta-chave-em-producao
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
STORAGE_TYPE=local
STORAGE_PATH=./storage
S3_BUCKET=
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
RESEND_API_KEY=
RESEND_FROM_EMAIL=alertas@seudominio.com
CORS_ORIGINS=http://localhost:3000
AGENT_FRAME_INTERVAL=1
AGENT_MIN_CONFIDENCE=0.70
AGENT_DEDUP_SECONDS=30

backend/app/main.py:
- FastAPI com CORS configurado lendo CORS_ORIGINS do .env
- GET /health retorna {"status": "ok", "version": "1.0.0"}
- Incluir todos os routers (mesmo que vazios por ora)

backend/app/core/config.py:
- Classe Settings com pydantic-settings lendo todas as variáveis do .env

backend/app/core/database.py:
- engine SQLAlchemy, SessionLocal, Base declarativa

backend/app/core/security.py:
- hash_password(password) → str
- verify_password(plain, hashed) → bool
- create_access_token(data, expires_delta) → str
- decode_token(token) → dict

backend/Dockerfile:
FROM python:3.11-slim
Instalar dependências do sistema para opencv e easyocr (libgl1, libglib2.0-0)
Copiar requirements e instalar
Expor porta 8000

.gitignore cobrindo Python, Node, .env, __pycache__, .next, node_modules

Ao final:
1. Liste cada arquivo criado
2. Mostre o comando exato para rodar: docker-compose up --build
3. Confirme o que verificar para saber que funcionou

---

## ✅ Checklist — confirme antes de ir para a Etapa 2

- [ ] `docker-compose up --build` roda sem erros
- [ ] `http://localhost:8000/health` retorna `{"status":"ok"}`
- [ ] `http://localhost:3000` abre no navegador
- [ ] `http://localhost:8000/docs` mostra o Swagger (mesmo que vazio)
