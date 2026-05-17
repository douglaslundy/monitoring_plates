# Deploy no Railway

## Pré-requisitos

- Conta no [Railway](https://railway.app) (plano Hobby: ~$5/mês)
- Repositório no GitHub com o código do projeto
- Conta no Resend (e-mails) e Cloudflare R2 (imagens)

## Passo a passo

### 1. Criar projeto no Railway

1. Acesse [railway.app](https://railway.app) → **New Project**
2. Selecione **Deploy from GitHub repo**
3. Autorize o Railway a acessar seu GitHub e selecione o repositório

### 2. Adicionar PostgreSQL

1. No projeto Railway → **+ New** → **Database** → **Add PostgreSQL**
2. Aguarde o banco inicializar
3. Clique no banco → aba **Variables** → copie a variável `DATABASE_URL`

### 3. Adicionar Redis

1. **+ New** → **Database** → **Add Redis**
2. Copie a variável `REDIS_URL`

### 4. Configurar o serviço Backend

1. **+ New** → **GitHub Repo** → selecione o repositório
2. Railway vai detectar o `Dockerfile` do backend automaticamente
3. Defina o **Root Directory** como `backend`
4. Vá em **Variables** e adicione:

```
DATABASE_URL=<valor copiado do PostgreSQL>
REDIS_URL=<valor copiado do Redis>
SECRET_KEY=<gere com: python -c "import secrets; print(secrets.token_hex(32))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
STORAGE_TYPE=s3
S3_BUCKET=monitoramento-frames
S3_ENDPOINT=https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com
S3_ACCESS_KEY=SEU_R2_ACCESS_KEY
S3_SECRET_KEY=SEU_R2_SECRET_KEY
RESEND_API_KEY=re_XXXXXXXX
RESEND_FROM_EMAIL=alertas@seudominio.com
CORS_ORIGINS=https://SEU_FRONTEND.up.railway.app
```

5. Defina o **Start Command**:
```
sh -c "alembic upgrade head && python -m app.core.seed && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

6. Defina **Health Check Path**: `/health`

### 5. Configurar o Worker Celery

1. **+ New** → **GitHub Repo** → mesmo repositório, **Root Directory** `backend`
2. Start Command:
```
celery -A app.workers.frame_processor worker --loglevel=warning -Q frames
```
3. Adicione as mesmas variáveis de ambiente do backend (sem a porta)

### 6. Configurar o Retention Worker

1. **+ New** → mesmo repositório, **Root Directory** `backend`
2. Start Command:
```
celery -A app.workers.retention_cleaner beat --loglevel=warning
```
3. Mesmas variáveis de ambiente

### 7. Configurar o Frontend

1. **+ New** → mesmo repositório, **Root Directory** `frontend`
2. Variáveis:
```
NEXT_PUBLIC_API_URL=https://SEU_BACKEND.up.railway.app
```
3. Build Command: `npm run build`
4. Start Command: `node server.js`

### 8. Domínio personalizado (opcional)

1. Clique no serviço Frontend → **Settings** → **Domains**
2. Adicione seu domínio e configure o DNS conforme instruído
3. Atualize `CORS_ORIGINS` no backend com o novo domínio

## Verificação pós-deploy

```bash
# Backend saudável
curl https://SEU_BACKEND.up.railway.app/health
# Resposta esperada: {"status":"ok","version":"1.0.0"}

# Frontend acessível
curl -I https://SEU_FRONTEND.up.railway.app
# Resposta esperada: HTTP/2 200
```

## Logs

- No Railway, clique em qualquer serviço → aba **Logs** para ver saída em tempo real
- Para ver logs de erros específicos: filtro por `ERROR` na barra de busca dos logs

## Estimativa de custo (Railway Hobby)

| Componente | Estimativa mensal |
|---|---|
| Backend (0.5 vCPU, 512 MB) | ~$5 |
| Worker OCR (1 vCPU, 1 GB) | ~$8 |
| Retention Worker (0.25 vCPU) | ~$2 |
| Frontend (0.5 vCPU, 512 MB) | ~$5 |
| PostgreSQL (1 GB) | ~$5 |
| Redis (256 MB) | ~$3 |
| **Total estimado** | **~$28/mês** |

> Para 10 clientes / 50 câmeras: escalar o Worker OCR para 2 vCPU / 2 GB → **~$40–50/mês**
