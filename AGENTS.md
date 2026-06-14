# Sistema de Monitoramento de Trânsito com Reconhecimento de Placas

## O que é este projeto
Sistema SaaS web completo para monitoramento de trânsito com reconhecimento automático de placas via câmeras IP. Multi-tenant (vários clientes), com planos de assinatura, alertas em tempo real e portal administrativo.

## Stack de tecnologias
- **Backend:** Python 3.11 + FastAPI
- **OCR:** EasyOCR (reconhecimento de placas)
- **Filas:** Celery + Redis
- **Banco:** PostgreSQL 15
- **Imagens:** Armazenamento local (desenvolvimento) / Cloudflare R2 (produção)
- **Frontend:** Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui
- **Agente Local:** Python empacotado com PyInstaller (.exe para Windows)
- **E-mail:** Resend
- **Alertas tempo real:** WebSocket (FastAPI + Redis Pub/Sub)
- **Infra:** Docker + Docker Compose

## Arquitetura de pastas
```
monitoramento-transito/
├── AGENTS.md              ← você está aqui
├── backend/               ← API FastAPI + workers
├── frontend/              ← Next.js
├── agent/                 ← software instalado no cliente
├── infra/                 ← configurações de infra
├── docs/                  ← prompts de cada etapa do desenvolvimento
└── docker-compose.yml
```

## Regras obrigatórias para todo o desenvolvimento

### Backend
- Sempre usar tipagem completa no Python (type hints em tudo)
- Nunca expor dados de um cliente para outro (isolamento por client_id)
- Toda rota deve ter autenticação, exceto /health e /api/auth/login
- Usar Alembic para TODA alteração no banco (nunca editar tabelas manualmente)
- Variáveis de ambiente sempre via Settings (pydantic-settings), nunca hardcoded
- Testes com pytest. Rodar `pytest backend/tests/ -v` antes de considerar qualquer etapa concluída

### Frontend
- TypeScript estrito (sem `any`)
- Toda requisição HTTP via src/lib/api.ts (nunca fetch direto)
- Tratamento de loading, error e empty state em todos os componentes
- Validação de formulários em tempo real (não só ao submeter)
- Responsivo: funcionar em 375px (mobile), 768px (tablet), 1280px (desktop)

### Segurança
- JWT para autenticação, token no cookie httpOnly
- Isolamento multi-tenant verificado em TODA rota que acessa dados
- Senhas sempre com bcrypt (nunca MD5, SHA1, ou texto puro)
- Imagens servidas com verificação de acesso

### Git
- Commit após cada etapa concluída e testada
- Mensagens no padrão: `feat: descrição` / `fix: descrição` / `test: descrição`

## Perfis de usuário
| Role | Acesso |
|------|--------|
| `super_admin` | Tudo — gerencia clientes, planos, todas as câmeras |
| `client_admin` | Gerencia usuários e câmeras do próprio cliente |
| `client_user` | Apenas visualiza câmeras e busca ocorrências do próprio cliente |

## Planos do sistema
| Plano | Câmeras | Retenção | E-mail alerts |
|-------|---------|----------|---------------|
| Básico | 3 | 30 dias | Não |
| Profissional | 10 | 90 dias | Sim |
| Enterprise | Ilimitado | Ilimitado | Sim |

## Credenciais padrão de desenvolvimento
- URL: http://localhost:3000
- Admin: admin@sistema.com / Admin@123
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Como rodar em desenvolvimento
```bash
cp .env.example .env
docker-compose up --build
```

## Roteiro de desenvolvimento — etapas
Cada etapa tem um arquivo de prompt em docs/. Execute na ordem:

| Etapa | Arquivo | O que faz |
|-------|---------|-----------|
| 1 | docs/01-estrutura-base.md | Estrutura de pastas, Docker, configurações |
| 2 | docs/02-banco-autenticacao.md | Modelos de banco, JWT, login |
| 3 | docs/03-clientes-usuarios-planos.md | Gestão multi-tenant e planos |
| 4 | docs/04-cameras.md | Cadastro RTSP, agente local, token |
| 5 | docs/05-ocr-processamento.md | Motor OCR, workers, alertas |
| 6 | docs/06-busca-ocorrencias.md | Busca de placas, WebSocket, e-mail |
| 7 | docs/07-interface-polimento.md | UI final, responsividade, UX |
| 8 | docs/08-testes.md | Testes automatizados completos |
| 9 | docs/09-deploy.md | Deploy Railway, documentação final |

## Como usar cada prompt
1. Abra o arquivo da etapa atual (ex: docs/01-estrutura-base.md)
2. Copie todo o conteúdo
3. Cole no Codex e pressione Enter
4. Aguarde terminar completamente
5. Confira o checklist no final do arquivo
6. Só então abra o próximo arquivo

**Nunca pule etapas. Cada uma depende da anterior.**
