# Backlog de falhas legadas

Este arquivo concentra as pendências antigas que não fazem parte da entrega principal atual, mas que precisam ser endereçadas até o fechamento do projeto.

## Estado atual

- [x] Detector de veículos, contagem e OCR guiado por recorte
- [x] Preview ao vivo independente do OCR
- [ ] Suíte backend 100% verde em execução completa
- [ ] Padronizar compatibilidade de rotas com barra final
- [ ] Eliminar persistência indevida do banco de teste entre execuções
- [ ] Desabilitar rate limit em ambiente de teste
- [ ] Investigar warnings de bcrypt/passlib na stack de teste
- [ ] Revisar fixtures legadas que ainda dependem de estado compartilhado

## Falhas legadas já identificadas

### 1. Rotas com barra final

Sintoma:
- Alguns testes chamam endpoints como `/api/plans/`, `/api/alerts/` e `/api/monitored-plates/`, enquanto o app estava com `redirect_slashes=False`.

Status:
- Corrigido no app com `redirect_slashes=True`.

### 2. Banco de teste persistente

Sintoma:
- Execuções repetidas da suíte podiam reencontrar dados antigos no `test.db`, gerando `UNIQUE constraint failed`.

Status:
- Corrigido no setup de testes com `drop_all()` antes de `create_all()`.

### 3. Rate limit em testes

Sintoma:
- A suíte acumulava chamadas ao login e passava a receber `429 Rate limit exceeded`.

Status:
- Corrigido com limiter no-op quando `IS_TESTING=true`.

### 4. Warnings de bcrypt/passlib

Sintoma:
- O backend emite warning de compatibilidade do backend `bcrypt` durante os testes.

Status:
- Ainda aberto. Não quebra a suíte, mas deve ser saneado.

## Regra de continuidade

Ao final de cada nova entrega funcional:

1. Reexecutar a suíte dos testes afetados.
2. Registrar neste backlog qualquer falha legada que aparecer.
3. Corrigir primeiro a regressão nova, depois a falha legada de maior impacto.
4. Só considerar a etapa concluída quando as falhas legadas críticas estiverem zeradas ou explicitamente justificadas.
