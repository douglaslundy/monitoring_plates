# Sistema de Monitoramento de Trânsito com Reconhecimento de Placas

SaaS multi-tenant para monitoramento de trânsito com reconhecimento automático de placas via câmeras IP. Alertas em tempo real, portal administrativo e agente leve para Windows.

## Funcionalidades

- **Reconhecimento de placas** via EasyOCR em frames capturados por câmeras RTSP
- **Multi-tenant**: isolamento completo de dados entre clientes
- **Alertas em tempo real** via WebSocket quando uma placa monitorada é detectada
- **Alertas por e-mail** (planos Profissional e Enterprise)
- **Busca de ocorrências** com filtro por placa, câmera e período, com lightbox de imagem
- **Portal administrativo** para gerenciar clientes, câmeras, planos e usuários
- **Agente local (.exe)** instalado nos clientes — captura e envia frames automaticamente
- **Retenção automática** de imagens por período conforme o plano

## Requisitos

Apenas **Docker** e **Docker Compose**.

## Como rodar

```bash
cp .env.example .env
docker-compose up --build
```

Aguarde todos os serviços ficarem saudáveis (cerca de 2 minutos na primeira vez).

## Acesso inicial

| Recurso | Endereço |
|---|---|
| Frontend | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

**Login padrão:** `admin@sistema.com` / `Admin@123`

## Primeiros passos após o login

### 1. Criar um cliente

1. Acesse **Clientes** → **Novo cliente**
2. Preencha nome, e-mail e selecione um plano
3. Salve

### 2. Cadastrar uma câmera

1. Acesse **Câmeras** → **Nova câmera**
2. Preencha o nome e o endereço RTSP da câmera
3. Copie o **Token do Agente** gerado

### 3. Instalar o agente na câmera do cliente

Consulte o guia completo em [docs/AGENT.md](docs/AGENT.md).

Resumo:
1. Baixe o agente ou compile com `cd agent && python build.sh`
2. Configure `config.json` com `server_url`, `token` e `camera_rtsp`
3. Execute `monitoramento-agent.exe`

### 4. Criar placas monitoradas e configurar alertas

1. Acesse **Placas Monitoradas** → **Nova placa**
2. Digite a placa (formato `ABC1234` ou `ABC1D23`)
3. Informe um e-mail para receber alertas (planos Profissional/Enterprise)

## Deploy em produção

Consulte [infra/railway.md](infra/railway.md) para deploy no Railway.

Para armazenamento de imagens em produção, consulte [infra/cloudflare-r2.md](infra/cloudflare-r2.md).

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic |
| OCR | EasyOCR, OpenCV |
| Filas | Celery + Redis |
| Banco | PostgreSQL 15 |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| Agente | Python + OpenCV (PyInstaller .exe) |
| E-mail | Resend |
| Alertas RT | WebSocket + Redis Pub/Sub |
| Imagens prod | Cloudflare R2 (S3-compatible) |
| Infra | Docker + Docker Compose + nginx |

## Estrutura do projeto

```
monitoramento/
├── backend/           API FastAPI + workers Celery
│   ├── app/
│   │   ├── api/       Routers e dependências
│   │   ├── core/      Config, segurança, banco, seed
│   │   ├── models/    SQLAlchemy models
│   │   ├── schemas/   Pydantic schemas
│   │   ├── services/  OCR, storage, e-mail, alertas
│   │   ├── workers/   frame_processor, retention_cleaner
│   │   └── websocket/ Connection manager
│   └── tests/         109 testes, 83% cobertura
├── frontend/          Next.js 14 (TypeScript)
│   └── src/
│       ├── app/       Rotas (admin/, client/, auth/)
│       ├── components/ Componentes UI
│       └── lib/       API client, WebSocket, auth
├── agent/             Agente local Python (.exe)
├── infra/             nginx, guias de deploy
└── docs/              Arquitetura, API, agente, operações
```

## Documentação adicional

- [Arquitetura detalhada](docs/ARCHITECTURE.md)
- [API — endpoints e exemplos](docs/API.md)
- [Instalação do agente (usuário final)](docs/AGENT.md)
- [Guia de operações e troubleshooting](docs/OPERATIONS.md)
- [Deploy no Railway](infra/railway.md)
- [Cloudflare R2 — armazenamento](infra/cloudflare-r2.md)
