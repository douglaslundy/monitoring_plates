# ETAPA 3 — Clientes, usuários e planos

> Pré-requisito: Etapa 2 concluída. Cole este prompt no Claude Code.

Implemente os módulos de gestão que o super_admin usa para administrar o SaaS.

ROTAS DE PLANOS (/api/plans — apenas super_admin):
GET / | POST / | PUT /{id} | DELETE /{id}

ROTAS DE CLIENTES (/api/clients — apenas super_admin):
GET / com plano e contagem de câmeras
POST / cria cliente + admin junto: {name, email, plan_id, admin_name, admin_email, admin_password, plan_expires_at}
GET /{id} | PUT /{id} | DELETE /{id} desativa cliente e todos os usuários

ROTAS DE USUÁRIOS (/api/users — isolamento automático por client_id):
GET / | POST / | GET /{id} | PUT /{id} | DELETE /{id}

FRONTEND:
src/app/admin/layout.tsx: sidebar com ícones Lucide, avatar, responsivo
src/app/admin/page.tsx: cards de métricas, últimas 10 ocorrências, clientes com plano expirando
src/app/admin/clients/page.tsx: tabela, modal criar cliente + admin juntos, ações por linha
src/app/admin/plans/page.tsx: cards por plano com contagem de clientes
src/app/admin/users/page.tsx: tabela com filtro por cliente e role

COMPONENTES (src/components/ui/):
DataTable.tsx, Modal.tsx, Badge.tsx, MetricCard.tsx, Sidebar.tsx, PageHeader.tsx

TESTES:
- super_admin cria cliente → cliente e admin criados
- client_admin não acessa dados de outro cliente
Execute: pytest backend/tests/ -v

## ✅ Checklist
- [ ] Super admin cria cliente via interface
- [ ] Login como cliente redireciona para /client
- [ ] Sidebar e navegação sem erros
