# Backlog de falhas legadas

Este arquivo concentra as pendencias antigas que nao fazem parte da entrega principal atual, mas que precisam ser enderecadas ate o fechamento do projeto.

## Estado atual

- [x] Detector de veiculos, contagem e OCR guiado por recorte
- [x] Preview ao vivo independente do OCR
- [x] Suite backend 100% verde em execucao completa
- [x] Padronizar compatibilidade de rotas com barra final
- [x] Eliminar persistencia indevida do banco de teste entre execucoes
- [x] Desabilitar rate limit em ambiente de teste
- [x] Investigar warnings de bcrypt/passlib na stack de teste
- [x] Ajustar `pytest-asyncio` para loop scope explicito
- [x] Neutralizar cache provider do pytest no ambiente de teste
- [ ] Acompanhar deprecations upstream de `fastapi`, `starlette`, `pytest-asyncio` e `python-jose`
- [ ] Revisar fixtures legadas que ainda dependem de estado compartilhado

## Falhas legadas ja identificadas

### 1. Rotas com barra final

Sintoma:
- Alguns testes chamavam endpoints como `/api/plans/`, `/api/alerts/` e `/api/monitored-plates/`, enquanto o app estava com `redirect_slashes=False`.

Status:
- Corrigido no app com `redirect_slashes=True`.

### 2. Banco de teste persistente

Sintoma:
- Execucoes repetidas da suite podiam reencontrar dados antigos no `test.db`, gerando `UNIQUE constraint failed`.

Status:
- Corrigido no setup de testes com `drop_all()` antes de `create_all()`.

### 3. Rate limit em testes

Sintoma:
- A suite acumulava chamadas ao login e passava a receber `429 Rate limit exceeded`.

Status:
- Corrigido com limiter no-op quando `IS_TESTING=true`.

### 4. Fixture compartilhada do worker

Sintoma:
- Um teste de `process_frame` precisava neutralizar `db.close()` para nao fechar a sessao compartilhada da fixture.

Status:
- Corrigido no teste usando uma `SessionLocal` propria para o worker, sem acoplar o worker a sessao principal da fixture.

### 5. Warnings de bcrypt/passlib

Sintoma:
- O backend emite warning de compatibilidade do backend `bcrypt` durante os testes.

Status:
- Corrigido com shim de compatibilidade no `backend/app/core/security.py`.

### 6. Cache do pytest no Windows

Sintoma:
- O `pytest` tentava gravar arquivos de cache em um diretorio que passava a falhar com `Permission denied` durante a execucao repetida da suite.

Status:
- Corrigido desativando o `cacheprovider` na configuracao de testes.

### 7. Warnings de deprecation em dependencias upstream

Sintoma:
- A suite ainda registra warnings de `asyncio.iscoroutinefunction`, `asyncio.get_event_loop_policy` e `datetime.utcnow()` vindos de bibliotecas de terceiros.

Status:
- Ainda aberto. Nao quebra a suite, mas vale acompanhar em uma atualizacao coordenada de dependencias.

### 8. WebSocket realtime dependente de autenticacao pronta

Sintoma:
- O dashboard pode mostrar "Sem conexao em tempo real" quando o `clientId` ou o token nao estao disponiveis no momento certo da montagem.

Status:
- Aberto como melhoria de produto. Precisa de retry, telemetria de conexao e mensagem de erro mais clara.

### 9. Contagem inflada por veiculo parado

Sintoma:
- Um veiculo parado em frente a camera pode gerar muitas passagens se o tracker nao persistir bem a identidade.

Status:
- Aberto como melhoria de contagem. Exige ajuste de tracker, janela de deduplicacao e possivel linha de passagem.

### 10. Saude operacional degradada sem explicacao clara

Sintoma:
- O painel marca "degradado", mas o usuario nao sabe se a causa e fila alta, latencia ou qualidade de imagem.

Status:
- Aberto como melhoria de UX e observabilidade. A causa precisa aparecer no dashboard.

### 11. Fila OCR alta em modo nao real-time

Sintoma:
- A fila OCR cresce muito quando todo frame vira tentativa de analise.

Status:
- Corrigido parcialmente com gate por veiculo e descarte de frames repetidos. Ainda vale observar cameras de alto volume e amostragem futura.

### 12. Evento visual sem placa nao fica evidente

Sintoma:
- Quando a placa falha, o usuario pode nao ver claramente que o veiculo foi capturado.

Status:
- Aberto como melhoria de produto. Deve existir exibicao do evento do veiculo mesmo sem OCR bem-sucedido.

### 13. Pagina historica de veiculos por frame

Sintoma:
- Existe resumo e estatistica, mas falta uma pagina dedicada com imagem por evento.

Status:
- Aberto como nova funcionalidade. Deve mostrar frame, data/hora e camera, com filtros por tipo e periodo.

## Regra de continuidade

Ao final de cada nova entrega funcional:

1. Reexecutar a suite dos testes afetados.
2. Registrar neste backlog qualquer falha legada que aparecer.
3. Corrigir primeiro a regressao nova, depois a falha legada de maior impacto.
4. So considerar a etapa concluida quando as falhas legadas criticas estiverem zeradas ou explicitamente justificadas.
