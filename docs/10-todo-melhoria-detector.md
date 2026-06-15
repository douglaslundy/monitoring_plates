# Todo de melhoria do detector

## Fase 0. Baseline e medicao

- [x] Medir tempo atual de captura, OCR e persistencia por camera.
- [x] Registrar fps efetivo do preview.
- [x] Registrar taxa de sucesso do OCR.
- [x] Registrar taxa de falso positivo.
- [ ] Definir cameras piloto para teste.

## Fase 1. Separar preview da analise

- [x] Criar pipeline de preview independente do OCR.
- [x] Garantir que o preview sempre sirva o ultimo frame.
- [x] Reduzir ou remover fila de frames para visualizacao.
- [x] Definir taxa de atualizacao configuravel por camera.
- [ ] Testar live com latencia menor sem impactar OCR.

## Fase 2. Detector de veiculos

- [ ] Escolher modelo leve para inferencia em CPU.
- [ ] Criar servico de deteccao de veiculos.
- [ ] Normalizar saida com classe, confianca e box.
- [ ] Salvar metadados da deteccao por frame.
- [ ] Adicionar testes do detector com mocks.

## Fase 3. OCR guiado por veiculo

- [ ] Ajustar OCR para recortes menores da placa.
- [x] Reaproveitar o recorte do veiculo como entrada do OCR.
- [x] Rodar OCR apenas em recortes candidatos.
- [ ] Implementar score de qualidade do recorte.
- [ ] Ajustar preprocessamento por tipo de imagem.
- [ ] Aplicar allowlist de caracteres quando houver alta chance de placa.
- [ ] Medir ganho real de acerto frente ao baseline.

## Fase 4. Contagem e classificacao

- [x] Criar evento de passagem de veiculo.
- [x] Adicionar classe do veiculo na ocorrencia.
- [x] Implementar conteudo agregado por camera e periodo.
- [x] Evitar dupla contagem com tracker simples.
- [x] Exibir contadores no dashboard.

## Fase 5. Telemetria e alertas operacionais

- [x] Expor metricas de fps, latencia e fila.
- [x] Criar healthcheck do pipeline de OCR.
- [x] Alertar quando a camera estiver com baixa qualidade.
- [x] Alertar quando o worker ficar atrasado.
- [x] Alertar quando a taxa de OCR cair abaixo do esperado.

## Fase 6. Otimizacoes adicionais

- [ ] Cachear modelos na inicializacao do worker.
- [x] Diminuir inferencia em frames repetidos.
- [ ] Amostrar frames em cameras de alto volume.
- [x] Criar configuracao de ROI por camera.
- [x] Exportar eventos para analise externa.

## Fase 7. Produto e UX

- [x] Melhorar o live para parecer tempo real.
- [x] Mostrar status do detector por camera.
- [x] Mostrar ultima leitura, tipo do veiculo e confianca.
- [ ] Adicionar graficos de fluxo por hora.
- [x] Adicionar painel de saude operacional.

## Fase 8. Ajustes solicitados pelo dashboard

- [x] Diagnosticar por que o dashboard mostra "Sem conexao em tempo real".
- [x] Implementar reconexao do websocket com mensagem clara de falha.
- [x] Corrigir contagem excessiva de veiculos parados em frente a camera.
- [x] Ajustar tracker/deduplicacao para nao contar o mesmo veiculo duas vezes.
- [ ] Explicar e corrigir o status "degradado" da saude operacional.
- [x] Reduzir a fila OCR para um nivel compativel com tempo real.
- [x] Gatear OCR para rodar apenas apos capturar um veiculo candidato.
- [x] Exibir carros detectados mesmo quando a placa nao for reconhecida.
- [ ] Criar pagina historica de veiculos com frame, data/hora e camera.
- [ ] Adicionar filtros por tipo de veiculo, camera e periodo na pagina historica.

### Critérios de aceite da fase

- o dashboard indica conexao realtime de forma confiavel e explicavel;
- um veiculo parado nao infla a contagem semanal;
- o status operacional mostra causa clara e muda quando a causa for corrigida;
- a fila OCR para de crescer indefinidamente;
- o OCR so roda quando houver alvo util;
- o usuario ve veiculo detectado mesmo sem leitura de placa;
- a nova pagina historica exibe imagem, camera e horario do evento.

### Status da implementacao atual

- Preview ao vivo usa stream MJPEG com fallback automatico para o ultimo frame salvo.
- O recarregamento manual restaura o stream sem bloquear o OCR.
- O preview permanece desacoplado da fila de analise.
- A taxa de atualizacao do live agora pode ser ajustada por camera.
- O worker agora ignora frames repetidos em sequencia para reduzir inferencia desnecessaria.
- O dashboard agora exibe FPS efetivo, quadros por minuto e status operacional do preview por camera.
- O worker aplica ROI configurada na camera antes do detector e do OCR.
- O dashboard agora exibe telemetria de qualidade da imagem por camera.
- O dashboard agora exibe um status consolidado do detector por camera com base em online, preview e qualidade.
- Alertas em tempo real agora disparam quando a camera entra em estado degradado ou com imagem ruim.
- O painel live agora exibe saude operacional, fila OCR, FPS medio e latencia media.
- O painel live agora exibe tambem captura media, OCR medio, persistencia media e taxa de sucesso do OCR.
- O painel live agora exibe tambem o healthcheck do pipeline de OCR por camera e no resumo geral.
- O sistema agora emite alerta realtime quando a taxa de OCR fica abaixo do esperado.
- O backend agora publica alerta de worker atrasado quando a fila OCR acumula acima do limite configurado.
- O painel do cliente agora exibe fluxo de veiculos por tipo, por hora e a ultima leitura com confianca.
- O painel do cliente agora permite exportar os eventos de veiculos para analise externa.
- O realtime do dashboard agora compartilha uma unica conexao por sessao, com reconexao automatica e mensagem de estado clara.
- O tracker de veiculos agora evita contagem repetida do mesmo alvo parado em frente a camera.
- O worker de OCR agora dispara somente apos detectar um veiculo candidato, reduzindo a fila de frames sem alvo util.
- O sistema agora persiste evento de veiculo mesmo quando a placa nao e reconhecida.
- O OCR da VPS conseguiu abrir o motor, mas ainda nao confirmou placa valida no frame amplo.
- O recorte da placa retornou texto parcial, indicando que a proxima rodada deve focar em recortes menores e preprocessamento seletivo.

## Fase 9. Validacao final adicional

- [ ] Validar websocket realtime com usuario autenticado na VPS.
- [ ] Validar contagem de veiculos com carro parado em frente a camera.
- [ ] Validar fila OCR depois do gate por deteccao de veiculo.
- [ ] Validar leitura de carro em movimento com frame historico.
- [ ] Validar nova pagina historica de veiculos por tipo.

## Fase 10. Validacao final

- [ ] Rodar testes unitarios do backend.
- [ ] Rodar testes de integracao do OCR.
- [ ] Validar em camera real com placa pequena.
- [ ] Validar contagem com veiculos diferentes.
- [ ] Validar consumo de CPU e memoria antes de liberar.
