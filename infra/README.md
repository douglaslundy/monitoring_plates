# Infraestrutura

Configurações de infraestrutura para produção.

## nginx.conf

Proxy reverso que roteia:
- `/api/*`, `/health`, `/docs` → backend FastAPI (porta 8000)
- `/ws/*` → WebSocket do backend
- `/` → frontend Next.js (porta 3000)

## Uso em produção

Adicione um serviço nginx ao `docker-compose.yml` montando `infra/nginx.conf`.
