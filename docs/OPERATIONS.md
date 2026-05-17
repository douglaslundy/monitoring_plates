# Guia de Operações

## Monitoramento do sistema

### Verificar saúde dos serviços

```bash
# Todos os containers rodando?
docker-compose ps

# Backend respondendo?
curl http://localhost:8000/health

# Redis conectado?
docker-compose exec redis redis-cli ping
# Resposta esperada: PONG

# PostgreSQL acessível?
docker-compose exec postgres pg_isready -U user -d monitoramento
# Resposta esperada: accepting connections
```

### Ver logs em tempo real

```bash
# Todos os serviços
docker-compose logs -f

# Só o backend
docker-compose logs -f backend

# Só o worker OCR
docker-compose logs -f worker

# Últimas 100 linhas do backend
docker-compose logs --tail=100 backend
```

### Monitorar filas Celery

```bash
# Status das filas
docker-compose exec worker celery -A app.workers.frame_processor inspect active

# Estatísticas (tasks processadas, erros)
docker-compose exec worker celery -A app.workers.frame_processor inspect stats
```

---

## Erros comuns e soluções

### Backend não inicia — "could not connect to server"

**Sintoma:** Backend falha ao iniciar com erro de conexão ao PostgreSQL.

**Solução:**
```bash
# Verificar se o Postgres subiu
docker-compose ps postgres
# Se não estiver healthy:
docker-compose restart postgres
docker-compose restart backend
```

### Worker parado — frames não sendo processados

**Sintoma:** Câmeras enviam frames, mas nenhuma ocorrência é criada.

**Diagnóstico:**
```bash
# Verificar se o worker está rodando
docker-compose ps worker

# Ver fila acumulada no Redis
docker-compose exec redis redis-cli llen celery

# Ver erros no worker
docker-compose logs --tail=50 worker
```

**Solução:**
```bash
docker-compose restart worker
```

### Alertas por e-mail não chegam

**Diagnóstico:**
1. Verifique o log do backend: `docker-compose logs backend | grep -i resend`
2. Verifique se `RESEND_API_KEY` está configurado
3. Verifique se o plano do cliente tem `email_alerts=true`
4. Verifique o dashboard do Resend em [resend.com](https://resend.com)

### WebSocket desconecta constantemente

**Diagnóstico:**
```bash
# Redis pub/sub funcionando?
docker-compose exec redis redis-cli monitor | grep ws:alerts
```

**Solução:** Verificar se o backend consegue conectar ao Redis e se o subscriber está rodando.

### Imagens não aparecem (404)

**Sintoma:** Ocorrências criadas mas imagens retornam 404.

**Diagnóstico:**
```bash
# Verificar se o volume de storage está montado
docker-compose exec backend ls /app/storage/cameras/

# Verificar permissões
docker-compose exec backend ls -la /app/storage/
```

### "disk quota exceeded" — armazenamento cheio

**Diagnóstico:**
```bash
# Ver uso do volume Docker
docker system df -v | grep storage_data
```

**Solução:** O retention worker deve limpar automaticamente. Se necessário:
```bash
# Forçar limpeza manual (requer acesso ao banco)
docker-compose exec backend python -c "
from app.core.database import SessionLocal
from app.workers.retention_cleaner import cleanup_expired
db = SessionLocal()
cleanup_expired(db)
db.close()
"
```

---

## Operações de manutenção

### Backup do banco de dados

```bash
# Criar backup
docker-compose exec postgres pg_dump -U user monitoramento > backup_$(date +%Y%m%d).sql

# Restaurar backup
docker-compose exec -T postgres psql -U user monitoramento < backup_20260101.sql
```

### Aplicar migrações após atualização

```bash
docker-compose exec backend alembic upgrade head
```

### Reiniciar todos os serviços

```bash
docker-compose restart
```

### Atualizar a aplicação (nova versão)

```bash
git pull origin main
docker-compose build
docker-compose up -d
```

### Trocar a SECRET_KEY (rotate JWT)

> Atenção: todos os usuários serão deslogados.

1. Gere nova chave: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Atualize `SECRET_KEY` no `.env`
3. Reinicie o backend: `docker-compose restart backend`

---

## Métricas úteis para acompanhar

| Métrica | Como verificar | Alerta se |
|---|---|---|
| Frames na fila Redis | `redis-cli llen celery` | > 1000 |
| Uso de disco | `docker system df` | > 80% |
| Memória do worker | `docker stats worker` | > 1.5 GB |
| Erros no backend | `docker logs backend \| grep ERROR` | qualquer |
| Câmeras offline | Sistema → admin/cameras, coluna "Último contato" | > 5 minutos |

---

## Variáveis de ambiente importantes

| Variável | Descrição | Padrão |
|---|---|---|
| `AGENT_DEDUP_SECONDS` | Ignorar mesma placa por N segundos | 30 |
| `AGENT_MIN_CONFIDENCE` | Confiança mínima para aceitar detecção | 0.70 |
| `AGENT_FRAME_INTERVAL` | Intervalo entre frames (no agente local) | 1 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração do JWT de usuário | 480 (8h) |

Para ajustar volume de processamento sem alterar o código, modifique `AGENT_DEDUP_SECONDS` e `AGENT_FRAME_INTERVAL`.
