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
