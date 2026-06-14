# Backlog de falhas legadas

Este arquivo concentra as pendências antigas que não fazem parte da entrega principal atual, mas que precisam ser endereçadas até o fechamento do projeto.

## Estado atual

- [x] Detector de veículos, contagem e OCR guiado por recorte
- [x] Preview ao vivo independente do OCR
- [x] Suíte backend 100% verde em execução completa
- [ ] Padronizar compatibilidade de rotas com barra final
- [ ] Eliminar persistência indevida do banco de teste entre execuções
- [ ] Desabilitar rate limit em ambiente de teste
- [x] Investigar warnings de bcrypt/passlib na stack de teste
- [x] Ajustar `pytest-asyncio` para loop scope explícito
- [x] Neutralizar cache provider do pytest no ambiente de teste
- [ ] Acompanhar deprecations upstream de `fastapi`, `starlette`, `pytest-asyncio` e `python-jose`
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
- Corrigido com shim de compatibilidade no `backend/app/core/security.py`.

### 5. Cache do pytest no Windows

Sintoma:
- O `pytest` tentava gravar arquivos de cache em um diretório que passava a falhar com `Permission denied` durante a execução repetida da suíte.

Status:
- Corrigido desativando o `cacheprovider` na configuração de testes.

### 6. Warnings de deprecation em dependências upstream

Sintoma:
- A suíte ainda registra warnings de `asyncio.iscoroutinefunction`, `asyncio.get_event_loop_policy` e `datetime.utcnow()` vindos de bibliotecas de terceiros.

Status:
- Ainda aberto. Não quebra a suíte, mas vale acompanhar em uma atualização coordenada de dependências.

## Regra de continuidade

Ao final de cada nova entrega funcional:

1. Reexecutar a suíte dos testes afetados.
2. Registrar neste backlog qualquer falha legada que aparecer.
3. Corrigir primeiro a regressão nova, depois a falha legada de maior impacto.
4. Só considerar a etapa concluída quando as falhas legadas críticas estiverem zeradas ou explicitamente justificadas.
