# Pipeline centrado no track — detecção/OCR robustos

Data: 2026-06-21
Status: aprovado (decisões: OCR **híbrido**; acurácia por **ajustes lógicos**, mantendo YOLOv8s)

## Problema

Câmeras com objetos parados (ex.: caminhão estacionado em frente) geram captura
repetida (~1x/min), e cada objeto que passa re-dispara a detecção do objeto
parado. Consequências:

1. Caminhão parado é re-detectado/re-OCR'd indefinidamente (poluição + custo CPU).
2. Veículo que passa é submetido ao OCR várias vezes, sem escolher o melhor frame.
3. Animais que cruzam são detectados raramente.
4. Cães classificados como pessoas e vice-versa.

## Causa-raiz (código atual)

O OCR é disparado por **frame/detecção**, não por **objeto (track)**:

- `capture_runner.py:41,134` — `_FORCE_SEND_SECONDS=8.0`: cena parada é empurrada
  ao pipeline inteiro a cada 8 s.
- `capture_runner.py:143` — motion gating de quadro inteiro: algo que passa traz o
  objeto parado junto ao YOLO de novo.
- `frame_processor.py:253` — "pular OCR de parado" exige `plate_confidence ≥ 0.98`
  (fast-alpr quase nunca atinge): OCR nunca é pulado.
- `frame_processor.py:349-371` — imagem da ocorrência é reescrita a cada placa
  *diferente* com conf maior (misread reescreve).
- `frame_processor.py:268,270,278` — **bug**: usa `now`, só existe `now_ts`
  (`NameError`); a lógica de parado está quebrada.
- `object_tracker_service.py:229` — para registrar, o track precisa estar inteiro
  no frame OU ter 4 hits; objeto que cruza rápido (1-3 frames, borda) **nunca**
  é registrado → animais raros.
- Confusão cão↔pessoa: voto cross-category existe mas só atua com track
  multi-frame e sobreposição ≥0.70; caso de 1 frame salva o rótulo errado.

## Solução: o track é a unidade de trabalho

Máquina de estados por track. OCR/registro/alerta/imagem são disparados por
transição de estado, não por frame.

### Estado por track (novo)
- `ocr_state`: `pending → read → dormant`
- `best_crop` (bytes) + `best_quality` (float)
- `plate`, `plate_confidence`, `occurrence_id`
- `votes` / categoria-label votados (já existe)
- `stationary`, `stationary_since` (já existe parcialmente)
- `registered` (evento criado)

### Fluxo (híbrido)
```
frame → YOLO (conf baixa p/ rastrear) → tracker (associa, guarda melhor crop,
                                                  vota classe, marca parado)
  veículo pending + qualidade do crop ≥ limiar  → OCR → ocorrência + ALERTA → read
  veículo read    + crop MUITO melhor (margem)  → re-OCR → refina imagem/placa
                                                  (mesma ocorrência; novo alerta só
                                                   se placa mudar)
  veículo read    + parado                       → dormant → nunca mais OCR
  pessoa/animal                                  → registra a CLASSE VOTADA uma vez
                                                   (ao confirmar OU no fim do track)
```

### Componentes
1. **`frame_quality_service`** (novo, puro): score = nitidez (variância do
   Laplaciano, reaproveitando a base de `image_quality_service`) × área ×
   centralidade × confiança do detector × inteiro-no-frame.
2. **`object_tracker_service`** (estender): guarda melhor crop por track; separa
   conf de **rastreio** (baixa) do **registro** (por voto de classe); registra no
   fim do track objetos que cruzaram rápido; expõe `ocr_state`.
3. **`frame_processor`** (reescrever trecho OCR/persistência): política híbrida;
   corrige `now`/`now_ts`; reescrita de imagem por **qualidade**; dormant.
4. **`capture_runner`** (heartbeat inteligente): elimina force-send cego; envia ao
   pipeline só com movimento ou track ativo não-finalizado; liveness raro (sem
   spammar OCR).
5. **Tuning** (config + tracker): threshold de animal mais baixo p/ rastrear; voto
   mínimo de classe antes de registrar; amostragem track-aware.

### Não-objetivos (YAGNI)
- Trocar de modelo (YOLOv8m) ou SAHI/tiling: fora de escopo agora (decisão:
  ajustes lógicos primeiro). Reavaliar depois de medir o efeito dos ajustes.
- Trocar o tracker por ByteTrack: o atual (IoU+centro+velocidade+voto) é suficiente.

## Testes
- Funções puras (quality, tracker state machine, OCR-once com `recognizer`
  mockado) rodam no `.venv-test` local.
- Pipeline/integração e cv2 rodam no Docker.
- Suíte atual (179 testes) deve permanecer verde.

## Tarefas
T1 bugs imediatos · T2 frame_quality_service · T3 melhor-crop+ocr_state ·
T4 conf rastreio vs registro+voto · T5 registrar-no-fim · T6 OCR híbrida ·
T7 heartbeat · T8 amostragem track-aware+thresholds · T9 testes integração.

Commit por tarefa. **Sem deploy até o usuário pedir.**
