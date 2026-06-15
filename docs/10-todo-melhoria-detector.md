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

- [ ] Reaproveitar o recorte do veiculo como entrada do OCR.
- [ ] Rodar OCR apenas em recortes candidatos.
- [ ] Implementar score de qualidade do recorte.
- [ ] Ajustar preprocessamento por tipo de imagem.
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

## Fase 8. Validacao final

- [ ] Rodar testes unitarios do backend.
- [ ] Rodar testes de integracao do OCR.
- [ ] Validar em camera real com placa pequena.
- [ ] Validar contagem com veiculos diferentes.
- [ ] Validar consumo de CPU e memoria antes de liberar.
