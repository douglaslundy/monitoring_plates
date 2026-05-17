# Documentação da API

## Swagger UI

Acesse a documentação interativa completa em:

- **Desenvolvimento:** http://localhost:8000/docs
- **Produção:** https://SEU_BACKEND.up.railway.app/docs

## Autenticação

Todas as rotas (exceto `/health` e `/api/auth/login`) exigem JWT no header:

```
Authorization: Bearer <token>
```

O token é retornado pelo endpoint de login e tem validade de 8 horas.

---

## Exemplos de uso com curl

### Health check

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0"}
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@sistema.com","password":"Admin@123"}'
```

Resposta:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "name": "Admin",
    "email": "admin@sistema.com",
    "role": "super_admin",
    "client_id": null
  }
}
```

### Listar clientes (super_admin)

```bash
TOKEN="eyJhbGciOiJIUzI1NiJ9..."

curl http://localhost:8000/api/clients \
  -H "Authorization: Bearer $TOKEN"
```

### Criar cliente

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Empresa Teste",
    "email": "contato@empresa.com",
    "plan_id": "uuid-do-plano"
  }'
```

### Criar câmera

```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Entrada Principal",
    "rtsp_url": "rtsp://usuario:senha@192.168.1.100:554/stream",
    "client_id": "uuid-do-cliente"
  }'
```

Resposta inclui `agent_token` para configurar o agente local.

### Enviar frame (agente)

```bash
AGENT_TOKEN="token-gerado-na-criacao-da-camera"

curl -X POST http://localhost:8000/api/agent/frame \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -F "frame=@/caminho/para/frame.jpg"
```

### Buscar ocorrências por placa

```bash
curl "http://localhost:8000/api/occurrences?plate=ABC1234&start=2026-01-01T00:00:00&end=2026-12-31T23:59:59" \
  -H "Authorization: Bearer $TOKEN"
```

### Criar placa monitorada

```bash
curl -X POST http://localhost:8000/api/plates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plate": "ABC1234",
    "description": "Veículo suspeito",
    "alert_email": "seguranca@empresa.com"
  }'
```

### Listar planos disponíveis

```bash
curl http://localhost:8000/api/plans \
  -H "Authorization: Bearer $TOKEN"
```

---

## Resumo de endpoints

| Método | Endpoint | Acesso | Descrição |
|---|---|---|---|
| GET | `/health` | Público | Status da API |
| POST | `/api/auth/login` | Público | Autenticação |
| GET | `/api/auth/me` | Autenticado | Dados do usuário atual |
| POST | `/api/auth/change-password` | Autenticado | Alterar senha |
| GET/POST | `/api/clients` | super_admin | Listar/criar clientes |
| GET/PUT/DELETE | `/api/clients/{id}` | super_admin | Gerenciar cliente |
| GET/POST | `/api/users` | admin | Listar/criar usuários |
| GET/POST | `/api/cameras` | admin | Listar/criar câmeras |
| GET/DELETE | `/api/cameras/{id}` | admin | Gerenciar câmera |
| GET | `/api/occurrences` | client | Buscar ocorrências |
| GET/POST | `/api/plates` | client | Listar/criar placas monitoradas |
| GET | `/api/alerts` | client | Listar alertas disparados |
| GET | `/api/plans` | super_admin | Listar planos |
| POST | `/api/agent/heartbeat` | agent_token | Heartbeat do agente |
| POST | `/api/agent/frame` | agent_token | Enviar frame para OCR |
| WS | `/api/ws/{client_id}?token=` | JWT | Alertas em tempo real |
| GET | `/api/images/{path}` | Autenticado | Servir imagem de ocorrência |
