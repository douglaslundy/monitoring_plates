# Detecção Multi-categoria (veículo/pessoa/animal) + Rastreamento + Histórico — Plano de Implementação

> **Para workers agênticos:** SUB-SKILL OBRIGATÓRIA: use `superpowers:executing-plans` (inline) ou `superpowers:subagent-driven-development` para executar tarefa a tarefa. Os passos usam checkbox (`- [ ]`). **Commit a cada tarefa concluída. NÃO fazer deploy até o usuário pedir.**

**Goal:** Adicionar rastreamento de objetos (sem contagem duplicada, inclusive de objetos parados) e estender a detecção para **pessoas** e **animais** (com tipo do animal), gravando o frame da detecção e exibindo contagem + histórico no sistema.

**Architecture:** O detector YOLOv8n já roda em ONNX (CPU) e devolve classes COCO; hoje só usa veículos. Vamos (1) generalizar o `vehicle_events` para um evento de detecção genérico com `category` (vehicle/person/animal) + `label` + `track_id`; (2) ampliar as classes do detector; (3) substituir o dedup de slot-único por um **rastreador multi-objeto por câmera (IoU + tempo)** que emite **um** evento por rastro (count-once) e mantém o rastro enquanto o objeto permanece no frame (inclusive parado); (4) expor contagem por categoria e exibir pessoas/animais no histórico.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Celery (worker solo), Redis, ONNX Runtime, Next.js 14 + TS + Tailwind. Testes: pytest (mockando libs pesadas — ver memória [[feedback_testes]]).

**Estado atual relevante (já no main):**
- `backend/app/services/vehicle_detection_service.py` — `VehicleDetector` (COCO `{2:car,3:motorcycle,5:bus,7:truck}`), `detect()` devolve top-3 `VehicleDetection`.
- `backend/app/workers/frame_processor.py` — `process_frame`: detecta → recorta → OCR; dedup de slot-único por câmera em Redis (`vehicle-track:{camera_id}`, IoU≥0.35 + `VEHICLE_EVENT_DEDUP_SECONDS`).
- `backend/app/models/vehicle_event.py` — `VehicleEvent(camera_id, occurrence_id, vehicle_type, confidence, bbox_*, image_path, detected_at)`.
- `backend/app/api/routes/vehicles.py` — `/vehicles` (lista paginada), `/vehicles/stats` (totais, by_type, top_cameras, by_hour), `/vehicles/export`.
- Frontend histórico: `frontend/src/app/{admin,client}/detections/page.tsx` consomem `/api/vehicles`.

---

## Tarefa 1 (explicação) — "OCR degradado (35)"

**Não é tarefa de código** (é pergunta). Significado, para registrar e opcionalmente exibir como tooltip:

- O badge mostra `status` + `ocr_pipeline_health_score`. `degradado` vem de `backend/app/services/ocr_pipeline_health_service.py`: a câmera está em estado ruim de leitura de placa porque **ao menos um** disparou: taxa de sucesso < 0.35, **ou** `avg_ocr_seconds` > 2.5, **ou** falso-positivo ≥ 0.35, **ou** sem leitura há > 15 min (stale).
- O `(35)` é o `ocr_pipeline_health_score` (0–100): 100 saudável, 65 atenção, **35 degradado**, 20 sem leituras (idle). É um índice fixo por faixa, não uma porcentagem.
- Causa prática neste projeto (ver memória [[deploy_vps]]): placas pequenas (veículo longe → ~34px) e/ou métrica contaminada por cold-start. Já houve correção da confiança do fast-alpr.

### (Opcional) Task 1.1: tooltip no badge de OCR
**Files:** Modify `frontend/src/components/live/LiveMonitor.tsx` (badge "OCR ...").
- [ ] Adicionar `title=` no badge de OCR com texto: `"Saúde da leitura de placa (0–100): 100 saudável, 65 atenção, 35 degradado, 20 sem leitura. 'degradado' = sucesso<35% ou leitura>2.5s ou sem leitura há 15min."`
- [ ] Commit: `git commit -m "feat: tooltip explicando o score de saude do OCR"`

---

## Fundação compartilhada (pré-requisito de Tarefas 2, 3 e 4)

### Task F1: Generalizar o evento de detecção (migration + modelo)

**Files:**
- Modify: `backend/app/models/vehicle_event.py`
- Create: `backend/alembic/versions/007_detection_event_fields.py`
- Test: `backend/tests/test_detection_events.py`

Decisão: manter a tabela `vehicle_events` (evita rename grande) e usá-la como **evento de detecção genérico**, adicionando:
- `category` String(10) NOT NULL default `'vehicle'` (valores: `vehicle`|`person`|`animal`), index.
- `track_id` String(40) NULL, index (id do rastro que originou o evento; permite auditar count-once).
- `vehicle_type` passa a ser o **label** (car/truck/person/dog/cat/...). Mantém o nome da coluna por compatibilidade; documentar no modelo.

- [ ] **Step 1 — Migration.** Criar `007_detection_event_fields.py` (revisão `007`, down_revision `006`), idempotente como as outras (checar colunas existentes via `sa.inspect`):

```python
"""add detection category/track_id to vehicle_events

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("vehicle_events")}
    if "category" not in cols:
        op.add_column("vehicle_events", sa.Column("category", sa.String(length=10), nullable=False, server_default="vehicle"))
        op.create_index("ix_vehicle_events_category", "vehicle_events", ["category"])
    if "track_id" not in cols:
        op.add_column("vehicle_events", sa.Column("track_id", sa.String(length=40), nullable=True))
        op.create_index("ix_vehicle_events_track_id", "vehicle_events", ["track_id"])


def downgrade() -> None:
    op.drop_index("ix_vehicle_events_track_id", table_name="vehicle_events")
    op.drop_index("ix_vehicle_events_category", table_name="vehicle_events")
    op.drop_column("vehicle_events", "track_id")
    op.drop_column("vehicle_events", "category")
```

- [ ] **Step 2 — Modelo.** Em `vehicle_event.py`, adicionar as colunas (depois de `vehicle_type`):

```python
    category = Column(String(10), nullable=False, default="vehicle", server_default="vehicle", index=True)
    track_id = Column(String(40), nullable=True, index=True)
```
E um comentário acima de `vehicle_type`: `# label da deteccao (car/truck/person/dog/...). Nome mantido por compat.`

- [ ] **Step 3 — Teste** `test_detection_events.py`: cria 1 evento `category="person"`, 1 `category="animal", vehicle_type="dog"`, 1 `category="vehicle"`; consulta `group_by(category)` e afirma contagens. (Usar a fixture `db` dos testes existentes — ver `tests/conftest.py`.)
- [ ] **Step 4 — Rodar:** `docker exec -w /app -e PYTHONPATH=/app monitoramento-worker-1 python -m pytest tests/test_detection_events.py -q` (ou local quando houver env). Esperado: PASS.
- [ ] **Step 5 — Commit:** `git commit -m "feat: vehicle_events vira evento de deteccao generico (category, track_id)"`

### Task F2: Ampliar as classes do detector (config-driven)

**Files:**
- Modify: `backend/app/services/vehicle_detection_service.py`
- Modify: `backend/app/core/config.py` (flags de habilitar pessoa/animal)
- Modify: `backend/app/services/vehicle_detection_service.py` (mapa COCO→(category,label))
- Test: `backend/tests/test_vehicles.py` (novos casos)

Mapa COCO (80 classes) por categoria:

```python
# category, label
_COCO_CLASSES: dict[int, tuple[str, str]] = {
    0:  ("person", "person"),
    2:  ("vehicle", "car"),
    3:  ("vehicle", "motorcycle"),
    5:  ("vehicle", "bus"),
    7:  ("vehicle", "truck"),
    14: ("animal", "bird"),
    15: ("animal", "cat"),
    16: ("animal", "dog"),
    17: ("animal", "horse"),
    18: ("animal", "sheep"),
    19: ("animal", "cow"),
    20: ("animal", "elephant"),
    21: ("animal", "bear"),
    22: ("animal", "zebra"),
    23: ("animal", "giraffe"),
}
```

- [ ] **Step 1 — Config.** Em `config.py`, adicionar (com defaults): `DETECT_PERSONS: bool = True`, `DETECT_ANIMALS: bool = True`. (Permite desligar por env sem mexer em código.)
- [ ] **Step 2 — Detector.** Substituir `_COCO_VEHICLE_CLASSES` por `_COCO_CLASSES` acima; em `VehicleDetection`, adicionar campo `category: str` (default `"vehicle"`). Em `_postprocess`/`detect`, montar o conjunto de classes ativas a partir das flags (`vehicle` sempre; `person` se `DETECT_PERSONS`; `animal` se `DETECT_ANIMALS`), e setar `category`/`label` (no campo `vehicle_type`) por classe. Manter `detect()` devolvendo top-N por score, agora multi-categoria.
- [ ] **Step 3 — Teste.** Em `test_vehicles.py`, mockar a saída ONNX com uma caixa classe 0 (person) e uma classe 16 (dog) e afirmar que `detect()` devolve `category` correta. (Seguir o estilo de mock já usado para veículos.)
- [ ] **Step 4 — Rodar:** `pytest tests/test_vehicles.py -q`. Esperado: PASS.
- [ ] **Step 5 — Commit:** `git commit -m "feat: detector reconhece pessoa e animais (classes COCO, config-driven)"`

---

## Tarefa 2 — Rastreador (sem contagem duplicada; objetos parados)

### Task 2.1: Serviço de rastreamento multi-objeto por câmera

**Files:**
- Create: `backend/app/services/object_tracker_service.py`
- Test: `backend/tests/test_object_tracker.py`

Algoritmo (IoU greedy + tempo, estado em Redis por câmera; chave `camera-tracks:{camera_id}`):
- Estado: lista de tracks `{track_id, category, label, bbox, first_seen_at, last_seen_at, hits, counted}`.
- A cada frame, recebe as detecções atuais (lista de `{category,label,bbox,confidence}`):
  1. Expira tracks com `now - last_seen_at > TRACK_MAX_AGE_SECONDS` (objeto saiu).
  2. Associa cada detecção ao track de **maior IoU ≥ TRACK_IOU_MIN** e mesma `category` (greedy, 1-para-1). Atualiza bbox/last_seen/hits do track casado.
  3. Detecção sem match → novo track (`track_id=uuid4().hex[:16]`, `hits=1`, `counted=False`).
  4. Um track vira "**contável**" quando `hits >= TRACK_MIN_HITS` e ainda `counted=False` → marca `counted=True` e entra na lista de retorno `newly_counted`.
- Retorna `(updated_state, newly_counted_tracks)`. Persiste estado no Redis com TTL `max(TRACK_MAX_AGE_SECONDS*4, 120)`.
- **Objeto parado:** como o bbox quase não muda, o IoU permanece alto → continua o **mesmo** track → `counted` continua `True` → **não conta de novo**, enquanto permanecer no frame. Só conta de novo se sair (track expira) e voltar (novo track).

Config novas (em `config.py`): `TRACK_IOU_MIN: float = 0.30`, `TRACK_MAX_AGE_SECONDS: float = 3.0`, `TRACK_MIN_HITS: int = 2`.

- [ ] **Step 1 — Teste primeiro** (`test_object_tracker.py`), sem Redis (injetar um fake store / ou função pura). Casos:
  - Mesma caixa em 3 frames consecutivos → `newly_counted` ocorre **uma única vez** (no frame em que `hits>=TRACK_MIN_HITS`).
  - Caixa “parada” por 10 frames → ainda **um** count total.
  - Caixa some por > `TRACK_MAX_AGE_SECONDS` e volta → conta de novo (2 no total).
  - Duas caixas distintas (IoU baixo) no mesmo frame → 2 tracks, 2 counts.

```python
def test_objeto_parado_conta_uma_vez(monkeypatch):
    from app.services.object_tracker_service import update_tracks
    box = {"category": "vehicle", "label": "car", "bbox": {"bbox_x":100,"bbox_y":100,"bbox_w":50,"bbox_h":50}, "confidence":0.8}
    state = []
    total = 0
    for i in range(10):
        state, newly = update_tracks(state, [box], now=1000.0 + i*0.5)
        total += len(newly)
    assert total == 1
```

- [ ] **Step 2 — Rodar p/ falhar:** `pytest tests/test_object_tracker.py -q` → FAIL (módulo inexistente).
- [ ] **Step 3 — Implementar** `object_tracker_service.py`. Funções:
  - `_iou(a, b) -> float` (reusar a lógica de `_vehicle_box_iou` do frame_processor — extrair/duplicar como helper).
  - `update_tracks(state: list[dict], detections: list[dict], now: float) -> tuple[list[dict], list[dict]]` (função PURA, testável sem Redis).
  - `load_tracks(camera_id) / save_tracks(camera_id, state)` (Redis, best-effort; reutilizar `_redis_client` pattern dos outros services).
  - `track_camera(camera_id, detections, now) -> list[dict]` (carrega, `update_tracks`, salva, devolve `newly_counted`).
- [ ] **Step 4 — Rodar:** `pytest tests/test_object_tracker.py -q` → PASS.
- [ ] **Step 5 — Commit:** `git commit -m "feat: rastreador multi-objeto por camera (IoU+tempo, count-once)"`

### Task 2.2: Integrar o rastreador no pipeline (substitui o dedup de slot-único)

**Files:**
- Modify: `backend/app/workers/frame_processor.py` (bloco de dedup ~linhas 219–280)
- Test: `backend/tests/test_services.py` (ajustar mocks do process_frame)

- [ ] **Step 1 — Detecções multi.** Trocar `vehicle = vehicle_detector.best_detection(...)` por `detections = vehicle_detector.detect(analysis_bytes)`. Manter `vehicle = melhor detecção de category=='vehicle'` (para o OCR de placa). Construir a lista p/ o tracker a partir de `detections`.
- [ ] **Step 2 — Rastrear.** Chamar `track_camera(str(camera.id), tracker_detections, now_ts)`; remover o bloco antigo de `vehicle-track` (slot-único). Para **cada** track em `newly_counted`: recortar o frame do bbox (reusar `VehicleDetector._crop_with_padding` via a própria detecção correspondente — guardar `crop_bytes` por detecção), `save_bytes(...)`, e criar **um** `VehicleEvent(category, vehicle_type=label, track_id, bbox, image_path, ...)`. Para `category=='vehicle'`, seguir com o OCR/occurrence como hoje (ligando `occurrence_id`).
- [ ] **Step 3 — Teste.** Ajustar `test_services.py` p/ o novo fluxo: simular 2 frames do mesmo carro parado → **1** `VehicleEvent`. Simular 1 pessoa → 1 evento `category=person`.
- [ ] **Step 4 — Rodar:** `pytest tests/test_services.py tests/test_vehicles.py -q` → PASS.
- [ ] **Step 5 — Commit:** `git commit -m "feat: pipeline usa rastreador (sem contagem duplicada, inclusive parado)"`

---

## Tarefa 3 — Detecção de pessoas (contagem + frame + histórico)

> Depende de F1, F2, 2.1, 2.2 (pessoas já passam a gerar `VehicleEvent` category=person com frame). Falta expor contagem e histórico.

### Task 3.1: Contagem por categoria na API

**Files:**
- Modify: `backend/app/api/routes/vehicles.py`
- Modify: `backend/app/schemas/vehicle_event.py`
- Test: `backend/tests/test_vehicles.py`

- [ ] **Step 1 — Filtro por categoria.** Em `_filter_query` e `list_events`, adicionar `category: Optional[str]` (Query). Em `_serialize_event`, incluir `category`.
- [ ] **Step 2 — Stats por categoria.** Em `VehicleEventStats` (schema), adicionar `by_category: list[CategoryCount]` (novo schema `{category:str, count:int}`). Em `get_stats`, agregar `group_by(VehicleEvent.category)`.
- [ ] **Step 3 — Teste.** Criar eventos de 3 categorias e afirmar `by_category` + filtro `category=person` na listagem.
- [ ] **Step 4 — Rodar:** `pytest tests/test_vehicles.py -q` → PASS.
- [ ] **Step 5 — Commit:** `git commit -m "feat: API de deteccoes com contagem e filtro por categoria"`

### Task 3.2: Histórico e contagem de pessoas no frontend

**Files:**
- Modify: `frontend/src/app/admin/detections/page.tsx` e `frontend/src/app/client/detections/page.tsx`
- Modify: `frontend/src/types/index.ts` (tipos `category`, `by_category`)
- Modify: `frontend/src/lib/api.ts` chamadas (se necessário; usar `api`)

- [ ] **Step 1 — Tipos.** Adicionar `category` em `VehicleEvent` e `by_category` em `VehicleEventStats` no `types/index.ts`.
- [ ] **Step 2 — UI.** Adicionar um seletor/aba de categoria (Veículos | Pessoas | Animais) que passa `?category=` para `/api/vehicles`; e cards de contagem por categoria a partir de `stats.by_category`. Reusar o card/grid de imagens existente (o `image_url` já vem do frame da detecção).
- [ ] **Step 3 — Estados.** Garantir loading/empty/error (regra do projeto).
- [ ] **Step 4 — Verificar:** `cd frontend && npx tsc --noEmit` → sem erros.
- [ ] **Step 5 — Commit:** `git commit -m "feat: historico e contagem de pessoas no painel"`

---

## Tarefa 4 — Detecção de animais (tipo + contagem + frame + histórico)

> O detector (F2) já devolve `category=animal` com o **tipo** no `label` (dog/cat/horse/...). 2.x já gera evento + frame. 3.1 já expõe contagem/filtro por categoria. Falta só o recorte de UI específico de animais + (opcional) sub-agрupar por tipo.

### Task 4.1: Sub-contagem por tipo de animal

**Files:**
- Modify: `backend/app/api/routes/vehicles.py` (stats já tem `by_type`; garantir que funciona filtrando `category=animal`)
- Modify: frontend detections page

- [ ] **Step 1 — Backend.** Garantir que `by_type` respeita o filtro `category` (se passado) — ajustar `get_stats` p/ aceitar `category` opcional e filtrar antes de agregar `by_type`. (Assim "animais por tipo" sai de graça.)
- [ ] **Step 2 — Teste.** Eventos `animal/dog`(x2) e `animal/cat`(x1); `stats?category=animal` → `by_type` = dog:2, cat:1.
- [ ] **Step 3 — Rodar:** `pytest tests/test_vehicles.py -q` → PASS.
- [ ] **Step 4 — Frontend.** Na aba "Animais", exibir contagem total + breakdown por tipo (de `by_type`) + grid de frames.
- [ ] **Step 5 — Verificar:** `npx tsc --noEmit`.
- [ ] **Step 6 — Commit:** `git commit -m "feat: deteccao e contagem de animais por tipo no historico"`

---

## Notas de execução
- **Worker é `--pool=solo --concurrency=1`** → estado por processo é serial; ainda assim o rastreador usa Redis (sobrevive a restart e mantém o padrão dos outros serviços).
- **Imagens**: produção usa `STORAGE_TYPE=s3` (R2). `save_bytes`/`get_url`/`read_file_bytes` já abstraem local vs S3 — usar sempre essas funções.
- **Performance**: ampliar classes não muda o custo do YOLO (sempre roda as 80 classes; só filtramos a saída). O recorte/gravação extra por categoria é por **rastro novo** (count-once), não por frame.
- **Migração**: rodar via `alembic upgrade head` (sobe sozinho no boot do backend). Nunca editar tabela na mão (regra do projeto).
- **Testes**: `pytest backend/tests/ -v` deve passar inteiro antes de considerar cada tarefa concluída.

## Checklist de cobertura do spec
- [x] Tarefa 1 (explicação OCR degradado) — documentada + tooltip opcional (1.1)
- [x] Tarefa 2 (rastreador, sem duplicar, objetos parados) — F2, 2.1, 2.2
- [x] Tarefa 3 (pessoas: contagem + frame + histórico) — F1, F2, 2.x, 3.1, 3.2
- [x] Tarefa 4 (animais: tipo + contagem + frame + histórico) — F2, 2.x, 3.1, 4.1
