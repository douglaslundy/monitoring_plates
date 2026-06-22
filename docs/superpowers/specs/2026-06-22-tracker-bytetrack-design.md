# Tracker selecionável: ByteTrack (embutido) + rajada-no-movimento

Data: 2026-06-22
Status: aprovado

## Objetivo
Permitir ao admin escolher o algoritmo de rastreamento — o **legacy** atual
(IoU+centro+velocidade, frames esparsos) ou um **ByteTrack** embutido (numpy puro,
sem torch) que recebe frames em **rajada durante o movimento**. Medir/comparar na
câmera real sem rebuild (toggle por Redis).

## Decisões (do brainstorming)
- Algoritmo novo: **ByteTrack** (Kalman const-velocity + associação 2 estágios),
  **embutido** em numpy puro (sem `supervision`/`boxmot`/torch — não cresce a
  imagem CPU-only).
- **Toggle do admin** `tracker:backend = legacy | bytetrack` no Redis (mesmo
  padrão do `detector_model_service`), lido por todos os workers, fallback legacy.
- **Taxa de frames acompanha o backend:** `legacy` mantém o esparso atual;
  `bytetrack` envia rajada de frames seguidos enquanto há movimento (teto de fps
  e duração), cena parada segue no heartbeat. CPU só sobe com movimento.
- ByteTrack só faz a **associação** (IDs estáveis). Toda a máquina de estados
  existente (contagem-única, estacionário, OCR híbrido, voto de classe, faces) é
  reaproveitada, keyed por track_id.

## Requisitos explícitos (com testes) — válidos p/ AMBOS os backends
- **R1:** veículo PARADO já lido (read/dormant) NÃO é reenviado ao OCR quando
  outro objeto passa; o objeto novo (track novo) é que vai ao OCR.
- **R2:** se vários veículos passam no mesmo frame, TODOS são enviados ao OCR
  (uma ocorrência por track), respeitando `MAX_DETECTIONS_PER_FRAME`.

## Componentes
1. **`bytetrack_service.py`** (novo, numpy puro):
   - `KalmanBox` (estado 8d: cx,cy,a,h,vx,vy,va,vh) predict/update.
   - `ByteTracker.update(dets, now, frame_w, frame_h) -> det_index→track_id` com
     associação 2 estágios (alta conf via IoU, depois baixa conf), `track_buffer`
     (lost tracks reativáveis), nascimento/morte por idade. Associação gulosa por
     IoU (sem scipy). Estado serializável (JSON) p/ Redis por câmera.
2. **`object_tracker_service`** (estender): camada de **estado compartilhada**
   (`_apply_track_state`: EMA estacionário, voto de classe, hits, `_maybe_register`,
   campos de OCR) aplicada aos tracks independente do backend. `update_tracks`
   (legacy) e o caminho ByteTrack chamam o mesmo `_apply_track_state`.
3. **`tracker_backend_service.py`** (novo): get/set do backend no Redis (legacy|bytetrack).
4. **`frame_processor`**: lê o backend e despacha a associação; resto inalterado.
5. **`capture_runner`**: quando backend=bytetrack, rajada-no-movimento (fps/duração
   configuráveis); senão, comportamento atual.
6. **API + frontend**: endpoint `GET/PUT /api/detector/tracker` e seletor na página
   de OCR-config (ao lado do modelo YOLO).

## Config (novos)
- `TRACKER_BACKEND_DEFAULT = "legacy"`.
- `BYTETRACK_HIGH_THRESH=0.5`, `BYTETRACK_LOW_THRESH=0.2`, `BYTETRACK_MATCH_IOU=0.2`,
  `BYTETRACK_BUFFER_SECONDS` (lost-track buffer).
- `CAPTURE_BURST_FPS=8.0`, `CAPTURE_BURST_SECONDS=3.0` (rajada quando bytetrack).

## Testes
- ByteTrack puro: associa objeto em movimento por vários frames → 1 ID; 2 objetos
  distintos → 2 IDs; objeto some e volta dentro do buffer → mesmo ID.
- R1: parado read/dormant + objeto passando → OCR só no objeto novo (recognizer
  chamado 1x p/ o novo, 0x p/ o parado).
- R2: 3 veículos no frame → 3 ocorrências / 3 chamadas de OCR.
- Toggle: backend lido do Redis; fallback legacy.
- Suíte completa verde (processo único). Sem migration (config/Redis only).

## Não-objetivos
- Re-ID (aparência) / reassociação entre câmeras — passo futuro.
- Remover o tracker legacy — fica como opção até o ByteTrack provar-se.
