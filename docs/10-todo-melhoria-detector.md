# Todo de melhoria do detector

## Fase 0. Baseline e medicao

- [ ] Medir tempo atual de captura, OCR e persistencia por camera.
- [x] Registrar fps efetivo do preview.
- [ ] Registrar taxa de sucesso do OCR.
- [ ] Registrar taxa de falso positivo.
- [ ] Definir cameras piloto para teste.

## Fase 1. Separar preview da analise

- [x] Criar pipeline de preview independente do OCR.
- [x] Garantir que o preview sempre sirva o ultimo frame.
- [x] Reduzir ou remover fila de frames para visualizacao.
- [ ] Definir taxa de atualizacao configuravel por camera.
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

- [ ] Criar evento de passagem de veiculo.
- [ ] Adicionar classe do veiculo na ocorrencia.
- [ ] Implementar conteudo agregado por camera e periodo.
- [ ] Evitar dupla contagem com tracker simples.
- [ ] Exibir contadores no dashboard.

## Fase 5. Telemetria e alertas operacionais

- [ ] Expor metricas de fps, latencia e fila.
- [ ] Criar healthcheck do pipeline de OCR.
- [ ] Alertar quando a camera estiver com baixa qualidade.
- [ ] Alertar quando o worker ficar atrasado.
- [ ] Alertar quando a taxa de OCR cair abaixo do esperado.

## Fase 6. Otimizacoes adicionais

- [ ] Cachear modelos na inicializacao do worker.
- [ ] Diminuir inferencia em frames repetidos.
- [ ] Amostrar frames em cameras de alto volume.
- [ ] Criar configuracao de ROI por camera.
- [ ] Exportar eventos para analise externa.

## Fase 7. Produto e UX

- [x] Melhorar o live para parecer tempo real.
- [ ] Mostrar status do detector por camera.
- [ ] Mostrar ultima leitura, tipo do veiculo e confianca.
- [ ] Adicionar graficos de fluxo por hora.
- [ ] Adicionar painel de saude operacional.

### Status da implementacao atual

- Preview ao vivo usa stream MJPEG com fallback automatico para o ultimo frame salvo.
- O recarregamento manual restaura o stream sem bloquear o OCR.
- O preview permanece desacoplado da fila de analise.
- O dashboard agora exibe FPS efetivo, quadros por minuto e status operacional do preview por camera.

## Fase 8. Validacao final

- [ ] Rodar testes unitarios do backend.
- [ ] Rodar testes de integracao do OCR.
- [ ] Validar em camera real com placa pequena.
- [ ] Validar contagem com veiculos diferentes.
- [ ] Validar consumo de CPU e memoria antes de liberar.
