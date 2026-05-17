# ETAPA 2 — Banco de dados e autenticação

> Pré-requisito: Etapa 1 concluída e todos os itens do checklist marcados.
> Cole este prompt inteiro no Claude Code.

---

Com a estrutura criada, implemente os modelos de banco e autenticação completa.

MODELOS SQLAlchemy (backend/app/models/):

models/plan.py:
  id (UUID pk), name (String), max_cameras (Integer, null=ilimitado),
  retention_days (Integer, null=ilimitado), email_alerts (Boolean),
  realtime_alerts (Boolean), price_monthly (Numeric 10,2),
  is_active (Boolean default True), created_at (DateTime)

models/client.py:
  id (UUID pk), name (String 255), email (String 255 unique),
  plan_id (FK → plans), plan_expires_at (DateTime nullable),
  is_active (Boolean default True), created_at (DateTime)
  Relacionamento: plan, users, cameras

models/user.py:
  id (UUID pk), client_id (FK → clients, nullable — null = super_admin),
  name (String 255), email (String 255 unique index),
  password_hash (String), role (Enum: 'super_admin','client_admin','client_user'),
  is_active (Boolean default True), created_at (DateTime)
  Relacionamento: client

models/camera.py:
  id (UUID pk), client_id (FK → clients),
  name (String 255), location (String 500),
  connection_type (Enum: 'rtsp','agent'),
  rtsp_url (String 500, nullable), agent_token (String 64, nullable, unique),
  is_active (Boolean default True),
  last_seen_at (DateTime nullable), created_at (DateTime)

models/monitored_plate.py:
  id (UUID pk), client_id (FK → clients),
  plate (String 20), description (String 500 nullable),
  alert_email (String 255 nullable), is_active (Boolean default True),
  created_at (DateTime)

models/occurrence.py:
  id (UUID pk), camera_id (FK → cameras),
  plate (String 20 index), image_path (String 500),
  confidence (Float), detected_at (DateTime index),
  expires_at (DateTime nullable index), created_at (DateTime)
  Relacionamento: camera

models/alert_sent.py:
  id (UUID pk), occurrence_id (FK → occurrences),
  monitored_plate_id (FK → monitored_plates),
  channel (Enum: 'email','websocket'),
  sent_at (DateTime), status (String 50)

SCHEMAS Pydantic (backend/app/schemas/):
Para cada model: ModelCreate, ModelUpdate, ModelResponse
Extras:
  schemas/auth.py: LoginRequest, TokenResponse, UserMe

ALEMBIC:
- Configure alembic/env.py importando todos os models
- Crie a migration inicial com todas as tabelas
- Índices em: occurrences.plate, occurrences.detected_at, occurrences.expires_at, users.email

SEED (backend/app/core/seed.py):
Criar se não existir:
1. Planos:
   - Básico: max_cameras=3, retention_days=30, email_alerts=False, price=49.00
   - Profissional: max_cameras=10, retention_days=90, email_alerts=True, price=149.00
   - Enterprise: max_cameras=None, retention_days=None, email_alerts=True, price=399.00
2. Usuário super_admin: admin@sistema.com / Admin@123 (role=super_admin, client_id=None)
Chamar seed no startup do FastAPI.

AUTENTICAÇÃO (backend/app/api/routes/auth.py):
POST /api/auth/login
  Body: {email, password}
  Retorno: {access_token, token_type, user: {id,name,email,role,client_id}}
POST /api/auth/refresh → novo token a partir de token válido
GET  /api/auth/me → usuário atual com dados do cliente e plano se aplicável

DEPENDÊNCIAS (backend/app/api/deps.py):
- get_db() → sessão do banco
- get_current_user() → decodifica JWT, busca usuário ativo, lança 401 se inválido
- require_super_admin() → lança 403 se role != super_admin
- require_client_admin() → aceita super_admin ou client_admin
- require_any_auth() → qualquer autenticado

FRONTEND — Login (src/app/(auth)/login/page.tsx):
- Formulário com email e senha, validação em tempo real
- Botão com estado de loading durante requisição
- Mensagem de erro clara em caso de credenciais inválidas
- Após login: super_admin → /admin, outros → /client

src/lib/auth.ts:
- login(email, password) → chama POST /api/auth/login, salva token em cookie
- logout() → limpa cookie, redireciona /login
- getMe() → GET /api/auth/me
- getToken() → lê cookie

src/lib/api.ts:
- Cliente axios com baseURL=NEXT_PUBLIC_API_URL
- Interceptor de requisição: adiciona Authorization: Bearer {token}
- Interceptor de resposta: em 401 → redireciona para /login

middleware.ts (Next.js):
- /admin/* → exige role super_admin
- /client/* → exige qualquer autenticação
- / → redireciona para /admin ou /client conforme role

TESTES (backend/tests/test_auth.py):
- login com credenciais corretas retorna token
- login com senha errada retorna 401
- GET /api/auth/me sem token retorna 401
- GET /api/auth/me com token retorna dados corretos
- rota super_admin com token client retorna 403
Execute: pytest backend/tests/test_auth.py -v

---

## ✅ Checklist — confirme antes de ir para a Etapa 3

- [ ] Tabelas no banco: `docker-compose exec postgres psql -U user monitoramento -c "\dt"`
- [ ] Seed rodou: planos e admin criados
- [ ] POST /api/auth/login com admin@sistema.com / Admin@123 retorna token
- [ ] Tela de login funciona e redireciona corretamente
- [ ] Todos os testes passam
