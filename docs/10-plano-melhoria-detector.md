# Plano de melhoria do detector de placas

## Objetivo

Evoluir o pipeline atual para:

1. Melhorar a taxa de acerto do OCR.
2. Reduzir falsos positivos.
3. Contar e classificar veiculos.
4. Tornar o live mais fluido.
5. Manter o custo computacional sob controle.

## Diagnostico atual

O fluxo atual ja tem:

- preprocessamento da imagem com grayscale e CLAHE;
- busca de ROI da placa;
- OCR com EasyOCR;
- deduplicacao de ocorrencias.

Pontos fracos identificados:

- o OCR ainda recebe frames amplos demais em varios cenarios;
- o live usa um fluxo simples de captura, com baixa taxa de quadros;
- nao existe detector de veiculos antes do OCR;
- nao existe contagem/classificacao de veiculos;
- nao existe telemetria do pipeline.

## Proposta de arquitetura

### Camada 1. Captura e preview

Responsavel por exibir frames em tempo quase real.

Regras:

- nao deve travar por causa do OCR;
- deve descartar frames antigos;
- deve servir sempre o frame mais recente disponivel;
- deve ter taxa configuravel por camera.

### Camada 2. Detector de veiculos

Responsavel por identificar:

- carro;
- moto;
- caminhao;
- onibus, se houver interesse depois.

Uso principal:

- recortar o veiculo antes do OCR;
- contar passagem de veiculos;
- registrar tipo de veiculo;
- gerar estatisticas por periodo.

### Camada 3. OCR de placas

Responsavel por:

- receber somente o recorte do veiculo ou a regiao mais provavel;
- aplicar preprocessamento local;
- rodar OCR somente quando a chance de placa for alta;
- devolver placa, confianca e metadados.

### Camada 4. Persistencia e analitica

Responsavel por:

- salvar ocorrencias;
- salvar tipo de veiculo;
- salvar confianca;
- salvar tempo de processamento;
- salvar eventos de contagem.

## Especificacao funcional

### 1. Detector de veiculos

Entrada:

- frame JPEG ou numpy image.

Saida:

- lista de boxes;
- classe do veiculo;
- score de confianca;
- timestamp.

Comportamento:

- rodar em frequencia menor que o preview;
- usar resolucao reduzida para inferencia;
- ignorar boxes com baixa confianca;
- priorizar area de interesse da camera quando configurada.

### 2. OCR com recorte inteligente

Entrada:

- frame original;
- box do veiculo;
- opcionalmente ROI da placa.

Saida:

- placa normalizada;
- confianca;
- engine usada;
- tempo de inferencia;
- metadados do recorte.

Comportamento:

- aplicar CLAHE, nitidez e resize apenas quando fizer sentido;
- tentar varios candidatos pequenos;
- nao processar frame inteiro sempre;
- abortar quando o custo estimado for alto demais.

### 3. Contagem de veiculos

Entrada:

- boxes e tracking curto.

Saida:

- total por camera;
- total por tipo;
- total por janela de tempo;
- total por sentido, se a camera tiver configuracao de linha/ROI.

Comportamento:

- evitar dupla contagem do mesmo veiculo;
- usar tracker simples para persistir identidade entre poucos frames;
- permitir reset por horario/dia.

### 4. Live em tempo real

Entrada:

- stream RTSP ou frame do agente.

Saida:

- preview com latencia baixa.

Comportamento:

- desacoplar preview da analise;
- manter apenas o ultimo frame;
- permitir taxa ajustavel por camera;
- evitar fila crescendo sem controle.

## Requisitos nao funcionais

### Performance

- OCR nao deve bloquear o preview;
- analise pesada deve rodar em worker separado;
- a carga deve escalar por camera e por plano.

### Confiabilidade

- se o detector falhar, o preview continua;
- se o OCR falhar, a contagem ainda pode seguir;
- se o Redis encher, nao pode derrubar o sistema inteiro.

### Observabilidade

Registrar por camera:

- fps efetivo;
- tempo medio de captura;
- tempo medio de OCR;
- tempo medio de persistencia;
- tempo medio de deteccao;
- taxa de sucesso do reconhecimento;
- taxa de falsos positivos;
- tamanho da fila;
- numero de frames descartados.
- estado do healthcheck do pipeline de OCR.

## Melhorias de valor agregado

As proximas features que mais agregam valor sao:

1. ROI por camera
   - permitir desenhar areas de interesse no painel;
   - reduzir custo e falsos positivos.

2. Calibracao de linha de passagem
   - contar veiculos que cruzam um ponto;
   - evitar dupla contagem.

3. Qualidade de imagem
   - medir blur, brilho, contraste e ruido;
   - avisar quando a camera estiver ruim para OCR.

4. Reprocessamento retroativo
   - reexecutar OCR em eventos gravados;
   - corrigir falhas sem depender do tempo real.

5. Alertas inteligentes
   - alertar so em placas de interesse;
   - alertar por tipo de veiculo;
   - alertar por horario.

6. Dashboard operacional
   - cameras online/offline;
   - fps por camera;
   - ultimas placas;
   - contagem diaria;
   - top cameras mais ativas.

7. Exportacao de dados
   - CSV;
   - PDF;
   - API para integracao.

## Critérios de aceite

O plano sera considerado bem-sucedido quando:

- o OCR reconhecer melhor placas pequenas;
- o preview ficar visivelmente mais fluido;
- for possivel contar veiculos por tipo;
- a fila nao crescer sem controle;
- os logs mostrarem tempo e taxa de acerto por camera;
- o sistema seguir operando mesmo com falhas parciais.

## Riscos

- detector pesado demais para CPU;
- custo alto se cada frame virar inferencia;
- mais complexidade de deploy;
- necessidade de ajustar GPU no futuro;
- cameras com angulo ruim ainda podem limitar a leitura.

## Estrategia recomendada

Prioridade de implementacao:

1. separar preview de analise;
2. adicionar detector leve de veiculos;
3. recortar veiculo antes do OCR;
4. medir qualidade e performance;
5. adicionar contagem/classificacao;
6. criar dashboard e alertas inteligentes.

## Novas demandas de produto

### 1. Status "Sem conexao em tempo real" no dashboard

Diagnostico provavel:
- o hook de websocket nao conecta se `clientId` ou `token` ainda nao estiverem prontos;
- o backend exige `token` valido na query string da rota `/ws/{client_id}`;
- o proxy/reverse proxy pode nao estar repassando a conexao WebSocket corretamente.

Especificacao:
- a pagina deve tentar abrir websocket assim que o `clientId` estiver disponivel;
- se o websocket falhar, o dashboard deve indicar o motivo e fazer retry automatico;
- deve existir fallback visual para polling/ping quando o canal realtime nao estiver pronto;
- a UX nao deve depender de recarregar a pagina para conectar.

Implementacao sugerida:
- registrar estado de conexao e motivo da falha no hook;
- reconectar com backoff curto;
- validar token, clientId e URL antes de abrir a conexao;
- confirmar configuracao do proxy para upgrade websocket.

Aceite:
- o dashboard deixa de mostrar "Sem conexao em tempo real" em ambiente saudável;
- quando houver falha, o motivo fica claro e a reconexao acontece sem acao manual.

Status atual:
- Implementado no frontend com uma conexao compartilhada por sessao, reconexao automatica e texto de estado explicavel.
- Ainda precisa de validacao final na VPS para confirmar o upgrade websocket no caminho real.

### 2. Contagem excessiva de veiculos

Diagnostico provavel:
- o mesmo veiculo parado em frente a camera pode estar gerando multiplos eventos;
- o tracker atual pode nao segurar identidade por tempo suficiente;
- o filtro por area/linha de passagem pode estar frouxo demais.

Especificacao:
- um veiculo parado nao deve inflar a contagem semanal;
- o sistema deve unir eventos repetidos do mesmo alvo em uma janela curta;
- a contagem deve depender de rastreio, nao apenas de frame isolado.

Implementacao sugerida:
- ajustar o dedupe temporal e espacial do tracker;
- usar linha de passagem ou zona de interesse para considerar "passagem";
- registrar id temporario do rastreio por camera;
- medir o impacto antes de mudar o contador final.

Aceite:
- um carro ou caminhao parado nao gera dezenas de contagens;
- a contagem semanal fica coerente com o volume real da rua.

Status atual:
- Implementado no worker com deduplicacao espacial e temporal por camera.
- Falta validar em camera real se a janela atual cobre bem os casos de parada longa e pequeno deslocamento.

### 3. Saude operacional "degradado"

Diagnostico provavel:
- a fila OCR esta acima do limiar;
- a latencia media do preview ou do OCR esta alta;
- alguma camera esta enviando frames lentos ou com baixa qualidade.

Especificacao:
- o status deve refletir regras objetivas;
- "degradado" precisa informar qual metrica causou o estado;
- o dashboard deve sugerir a acao correta: reduzir carga, ajustar camera ou revisar OCR.

Implementacao sugerida:
- exibir detalhamento de qual metrica piorou;
- separar alerta de camera ruim, fila alta e OCR lento;
- considerar degradado apenas quando a anomalia persistir por janela minima.

Aceite:
- o usuario entende por que esta degradado;
- o status muda quando a causa real for corrigida.

### 4. Fila OCR acumulando demais

Diagnostico provavel:
- o worker produz mais rapido do que processa;
- toda captura vira tentativa de OCR;
- falta amostragem por camera e priorizacao por evento real.

Especificacao:
- a fila deve permanecer sob controle para manter comportamento quase em tempo real;
- frames redundantes devem ser descartados;
- OCR deve ser disparado apenas quando houver chance real de deteccao.

Implementacao sugerida:
- reduzir amostragem em cameras de alto volume;
- processar OCR apenas apos detector confirmar veiculo;
- ignorar frames repetidos;
- expor alerta de backlog e tempo medio de fila.

Aceite:
- a fila cai para um nivel estável;
- o sistema responde em tempo util sem crescer sem limite.

Status atual:
- Implementado o gate por veiculo candidato e o descarte de frames repetidos.
- Fica pendente observar cameras de alto volume para decidir se precisamos de amostragem adicional.

### 5. OCR apenas apos capturar veiculo

Diagnostico provavel:
- o OCR ainda esta recebendo frames amplos ou capturas sem alvo;
- isso aumenta custo e reduz confianca.

Especificacao:
- frames sem veiculo relevante nao devem ir para OCR;
- o OCR deve usar recorte do veiculo e, quando possivel, da area frontal/placa;
- a imagem deve ser pre-processada so quando houver alvo util.

Implementacao sugerida:
- gatear OCR com detector de veiculos;
- recortar a regiao mais provavel da placa;
- manter allowlist e resize apenas em candidatos promissores.

Aceite:
- o OCR roda menos vezes, mas com melhor taxa de acerto;
- frames vazios nao entram na fila OCR.

Status atual:
- Implementado no worker: OCR so roda quando o detector encontra um veiculo.
- Ainda falta refinar o recorte da placa e medir ganho real com imagens de campo.

### 6. Carro passou, mas nao apareceu

Diagnostico provavel:
- a camera pode nao estar gerando evento de veiculo porque o detector nao viu a zona certa;
- o OCR pode ter falhado antes de persistir;
- pode haver problema de angulo, recorte ou regra de confidence.

Especificacao:
- o sistema precisa mostrar quando houve passagem de veiculo mesmo sem placa;
- o dashboard deve distinguir "veiculo detectado" de "placa reconhecida".

Implementacao sugerida:
- persistir evento de veiculo mesmo sem OCR bem-sucedido;
- exibir cards separados para passagem e para placa;
- guardar foto do frame do veiculo detectado.

Aceite:
- o usuario ve pelo menos o veiculo capturado mesmo quando a placa falhar;
- a ausencia de placa nao apaga o evento visual.

### 7. Pagina de fluxo por tipo com frame do evento

Diagnostico provavel:
- hoje existe resumo e ultima leitura, mas falta uma pagina historica dedicada a eventos de veiculos.

Especificacao:
- criar pagina com filtros por tipo de veiculo, camera e periodo;
- exibir frame de cada evento com foto, data/hora e nome da camera;
- permitir navegação igual a pagina de detecções.

Implementacao sugerida:
- novo endpoint ou reaproveitamento do evento de veiculos;
- cards/lista com thumbnail, metadata e paginação;
- filtros de carro, moto, caminhao e outros tipos suportados.

Aceite:
- o usuario consegue abrir uma pagina historica de veiculos;
- cada item mostra imagem, camera e timestamp do evento.

## Prompts de execucao

Use estes prompts como tarefas diretas na proxima rodada:

1. "Explique e corrija o status degradado da saude operacional, vinculando a causa exata da metrica que disparou o alerta."
2. "Crie a pagina historica de veiculos com frame, data/hora e camera, com filtros por tipo e periodo."
3. "Adicione filtros por tipo de veiculo, camera e periodo na nova pagina historica."
4. "Valide em camera real o comportamento do tracker para veiculo parado e ajuste a janela se houver novo excesso de contagem."
5. "Valide na VPS o websocket realtime, a fila OCR reduzida e a experiencia do painel ao vivo."
