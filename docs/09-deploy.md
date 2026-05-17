# ETAPA 9 — Deploy e documentação final

> Pré-requisito: Etapa 8 concluída. Cole este prompt no Claude Code.

DOCUMENTAÇÃO DE DEPLOY:
infra/railway.md: passo a passo Railway (conta, projeto, plugins postgres+redis,
deploy backend+frontend+worker, variáveis, logs)
infra/cloudflare-r2.md: passo a passo bucket R2 gratuito (10GB/mês)

SEGURANÇA — revisão final:
Nenhuma senha/chave hardcoded | CORS só domínio de produção | rate limit login 10/min/IP
Headers de segurança HTTP | logs sem dados sensíveis

docker-compose.prod.yml: sem hot-reload, restart: always, healthchecks, .env.prod

DOCUMENTAÇÃO:
docs/ARCHITECTURE.md: diagrama texto, decisões e justificativas
docs/API.md: link Swagger + exemplos curl principais rotas
docs/AGENT.md: instalação do agente para usuário não técnico
docs/OPERATIONS.md: monitoramento, erros comuns, como ver logs

README.md completo: o que é (3 linhas), funcionalidades, requisitos (só Docker),
como rodar (3 comandos), acesso inicial, cadastrar câmera, instalar agente,
configurar alertas, deploy (link infra/), tecnologias, estrutura do projeto.

VALIDAÇÃO FINAL — execute na ordem:
1. docker-compose down -v
2. docker-compose up --build
3. Aguardar todos saudáveis
4. GET /health → {"status":"ok"}
5. http://localhost:3000 → login
6. Login admin@sistema.com / Admin@123 → /admin
7. Criar cliente "Empresa Teste" plano Profissional
8. Criar câmera agent → copiar token
9. Criar placa monitorada "ABC1234" com email de teste
10. POST /api/agent/frame com token + JPEG de teste
11. Verificar occurrence no banco
12. Verificar alerta na tela
13. Verificar email recebido
14. Buscar "ABC1234" → occurrence com foto

Se qualquer passo falhar → corrija e refaça do passo 1.

RELATÓRIO FINAL:
✅ Funcionalidades implementadas
📊 Cobertura de testes
⚠️ Limitações conhecidas
🚀 Próximos passos sugeridos
💰 Estimativa custo mensal Railway para 10 clientes / 50 câmeras

## ✅ Checklist Final
- [ ] Sistema roda do zero com docker-compose up --build
- [ ] Roteiro de validação sem falhas
- [ ] README claro para outra pessoa instalar
- [ ] Documentação do agente para usuário não técnico
- [ ] Relatório final gerado
