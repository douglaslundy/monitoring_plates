# ETAPA 7 — Interface final e polimento

> Pré-requisito: Etapa 6 concluída. Cole este prompt no Claude Code.

IDENTIDADE VISUAL (tailwind.config.ts):
primary: navy (#1e3a8a / #1e40af). accent: laranja (#ea580c / #f97316)
Logo SVG: câmera + escudo

SIDEBAR:
Ícones Lucide em todos os itens. Indicador visual do item ativo. Badge contagem alertas não vistos.
Colapsa para ícones em telas menores com tooltip. Admin e cliente com menus diferentes.

ESTADOS em todos os componentes:
Loading: skeleton animado com formato similar ao conteúdo real (não spinner genérico)
Empty: SVG simples + texto + ação sugerida
Error: mensagem vermelha + "Tentar novamente"
Success: toast verde canto superior, auto-fecha 3s

MELHORIAS:
Login: toggle senha, animação de entrada
Câmeras: ponto pulsando CSS puro (animation: pulse)
Busca: highlight do termo buscado nos resultados
Tabelas: ordenação por coluna, busca local em tempo real
Modal foto: zoom ao clicar, botão baixar original
Dashboard: tooltip ao hover recharts

VALIDAÇÕES em tempo real (não só ao submeter):
URL RTSP: começa com rtsp:// ou rtsps://
Email: formato válido
Placa: só ABC1234 ou ABC1D23, converte para maiúsculas automaticamente
Senha: min 8, 1 maiúscula, 1 número

RESPONSIVIDADE:
375px (mobile), 768px (tablet), 1280px (desktop)
Tabelas → cards em mobile. Grid câmeras: 3→2→1 colunas.

ACESSIBILIDADE:
aria-label em botões, alt em imagens, outline visível no foco, aria-describedby nos erros

CONFIGURAÇÕES CLIENTE (src/app/client/settings/page.tsx):
Perfil (nome/senha), Plano atual (limites, validade), Notificações

Revise CADA tela existente. Liste ao final tudo que foi modificado.

## ✅ Checklist
- [ ] Todas as telas sem erros no console do browser
- [ ] Skeleton loading funciona
- [ ] Estados vazios com mensagem e ação
- [ ] Formulários validam em tempo real
- [ ] Interface em 375px (testar com DevTools)
