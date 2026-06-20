# Módulo de Reconhecimento Facial — Design

**Data:** 2026-06-20
**Status:** Aprovado (design) — pronto para plano de implementação

## Objetivo

Adicionar reconhecimento facial ao SaaS de monitoramento, seguindo as mesmas
bases do OCR de placas já existente. Ao detectar uma pessoa, o sistema detecta o
rosto, grava **um** registro por permanência no frame (por track), identifica
faces previamente cadastradas (exibindo o nome nas detecções) e dispara alertas
(e-mail / WhatsApp / WebSocket) para faces marcadas. Câmeras e planos passam a
escolher entre OCR, Faces ou ambos. Três motores pagos (AWS Rekognition, Luxand,
Face++) e um local opensource (OpenCV YuNet + SFace) ficam selecionáveis pelo
cliente/super_admin.

## Decisões-chave (confirmadas com o usuário)

- **Motor local:** OpenCV Zoo **YuNet** (detecção) + **SFace** (embedding) —
  licença permissiva para uso comercial; modelos ONNX pequenos (~38 MB) embutidos
  na imagem Docker (igual ao `yolov8`); reusa a stack onnxruntime/opencv. (O
  InsightFace seria mais preciso, mas seus modelos pré-treinados são
  não-comerciais → descartado para produto pago.)
- **Motores pagos:** AWS Rekognition (nº 1), **Luxand.cloud** e **Face++** — todos
  implementados como opções selecionáveis.
- **Duração do rastreio (tarefa 12):** implementar — `UPDATE` leve de
  `tracked_seconds` na expiração do track.
- **Troca de motor:** guardar a foto de referência de cada face cadastrada +
  ação "re-indexar tudo" que re-cadastra automaticamente no motor ativo.
- **Quem cadastra pessoas:** `client_admin` (no próprio cliente) e `super_admin`.

## Arquitetura

Espelha o pipeline de OCR existente (detecção YOLO → rastreador por track →
router de motor → ocorrência → alertas). O detector YOLO **já** produz a
categoria `person` (COCO 0) e o rastreador **já** mantém um track por objeto;
acrescentamos a camada facial sobre essa base.

### 1. Motores de faces (`face_service.FaceRouter`)

Espelha `ocr_service.OcrRouter`: resolve o motor ativo pelo plano da câmera (cache
de 60 s, sem hit de DB por frame), com fallback para o motor local quando a nuvem
falha. Interface comum:

```
class FaceEngine(Protocol):
    def detect(self, image_bytes) -> list[FaceBox]          # bbox + qualidade
    def enroll(self, client_id, person_id, image_bytes) -> EnrollResult  # ref/embedding
    def identify(self, client_id, image_bytes) -> Optional[Match]        # person_id + score
```

| Motor | Armazenamento / identificação |
|-------|-------------------------------|
| **OpenCVFaceEngine** (local) | `enroll` → embedding 128-d salvo em `person_faces.embedding` (JSON); `identify` → embedding do rosto + cosseno vs. embeddings do cliente (carregados/cacheados), threshold configurável |
| **RekognitionFaceEngine** | Collection por cliente (`face-{client_id}`); `IndexFaces` → FaceId em `person_faces.external_ref`; `SearchFacesByImage` |
| **LuxandFaceEngine** | subject/person por cliente; enroll guarda o uuid Luxand; `recognize` retorna o subject |
| **FaceppFaceEngine** | FaceSet (`outer_id=client_id`); `detect`→face_token→`faceset/addface`; `search` |

`face_detection_service.py` encapsula o motor **local** (YuNet+SFace via cv2 DNN /
onnxruntime, lazy import, mockável, modo degradado se faltar modelo — igual ao
`vehicle_detection_service`). Modelos baixados no build do Docker → runtime offline.
`boto3` (AWS) e `requests` (Luxand/Face++) são puro Python (PyPI alcançável pela VPS).

### 2. Integração no pipeline (`frame_processor.process_frame`)

Após a detecção/rastreio existente, **se** a câmera tem `enable_face` e o plano
tem `face_recognition_enabled`:

- Para cada **track de pessoa** confirmado, **uma única vez** (flag `face_saved`
  no estado do track): detecta o rosto no recorte; se houver rosto com qualidade
  suficiente, roda `identify` no motor ativo e grava **um** `FaceDetection`
  (imagem, bbox, confiança, `track_id`, `expires_at` pela retenção do plano,
  `face_engine_used`). Se casar com uma `Person`, grava `person_id`.
- Dispara `face_alert_service.process_face_alerts` na 1ª gravação.
- Na **expiração do track**, `UPDATE FaceDetection.tracked_seconds =
  last_seen - first_seen` (tarefa 12). O rastreador passa a expor os tracks
  expirados (lista de retorno em `update_tracks` ou varredura por idade).

OCR e Faces coexistem no mesmo frame: o loop de veículos continua igual; o bloco
de faces é adicional e só roda quando habilitado.

### 3. Modelos de dados (Alembic, head atual = 015)

- **`Person`**: `client_id`, `name`, `birth_date`, `cpf`, `address`, `phone`,
  `notes`, `photo_path`, `alert_active`, `alert_email`, `alert_whatsapp`,
  `is_active`, `created_at`.
- **`PersonFace`**: `person_id`, `engine_type`, `embedding` (JSON, p/ local),
  `external_ref` (str, p/ nuvem), `image_path` (foto de referência p/ re-index),
  `created_at`.
- **`FaceDetection`**: `camera_id`, `person_id` (nullable), `confidence`,
  `image_path`, `bbox_x/y/w/h`, `track_id`, `detected_at`, `expires_at`,
  `tracked_seconds` (nullable), `face_engine_used`.
- **`FaceEngineConfig`**: espelha `OcrEngineConfig` — `engine_type`, `mode`,
  `is_active`, credenciais (`api_token`, `api_secret`, `region`, `api_url`),
  `threshold`, `created_at`, `updated_at`.
- **`Camera`** +`enable_ocr` (default true), +`enable_face` (default false).
- **`Plan`** +`ocr_enabled` (default true), +`face_recognition_enabled`
  (default false), +`face_engine` (default `system_default`).
- **`AlertSent`** ganha `person_id` e `face_detection_id` nullable; e
  `occurrence_id`/`monitored_plate_id` passam a nullable (registrar alertas de
  face reaproveitando a tabela).

Isolamento multi-tenant: toda query de `Person`/`FaceDetection` filtra por
`client_id` (direto ou via câmera), igual às placas.

### 4. Alertas (`face_alert_service.py`)

Espelha `alert_service`: ao gravar um `FaceDetection` com `person_id` cuja
`Person.alert_active` é true, envia e-mail (se `plan.email_alerts`), WhatsApp (se
`alert_whatsapp`) e WebSocket (se `plan.realtime_alerts`), com dedup via
`AlertSent`. Payload WebSocket `type="face_alert"`. A página de Alertas ganha um
**filtro Placas / Faces / Todos** (mesma página, mesmo feed).

### 5. API (FastAPI)

- `/api/persons` — CRUD client-scoped (`client_admin` no próprio cliente,
  `super_admin` em todos) + upload de foto + `POST /{id}/reindex`.
- `/api/face-detections` — listagem/busca client-scoped (espelha
  `occurrences`/`vehicles`), traz o nome da pessoa.
- `/api/face-config` — `super_admin`: CRUD + activate + test (espelha
  `ocr-config`).
- `cameras` create/update aceitam `enable_ocr`/`enable_face`; `plans`
  create/update aceitam os campos de face.

### 6. Frontend (Next.js, admin + client)

- Página **Pessoas** (CRUD, formulário com nome/nascimento/cpf/endereço/telefone,
  upload de foto, toggle de alerta + e-mail/WhatsApp), validação em tempo real.
- Página **Detecções de Faces** (lista com nome da pessoa, imagem, duração),
  com loading/error/empty.
- Página **Alertas** com filtro placas/faces/todos.
- Formulário de **Câmera**: checkboxes *Ativar OCR* / *Ativar Faces*.
- Formulário de **Plano** (admin): toggles OCR/Faces + select de motor.
- Página **Config de Faces** (super_admin): escolher motor, credenciais, testar,
  ativar (espelha a de OCR).
- `src/lib/api.ts` ganha os métodos; sidebar ganha os links.

### 7. Entrega e operação

- Modelos YuNet+SFace baixados no estágio de build do Docker (mirror não-github,
  ex. HuggingFace/opencv_zoo) e copiados p/ `MODELS_DIR`.
- Dependências novas: `boto3` (AWS). `requests` já existe.
- Testes pytest espelhando os existentes: motores (cv2/onnxruntime/boto3/requests
  mockados via `sys.modules`), rotas, pipeline, alertas, isolamento multi-tenant.
- **Commit por tarefa**; push ao final; deploy na VPS 192.168.0.115 (user lundy)
  via `deploy.sh` (cópia de arquivos + rebuild do `docker-compose.prod.yml`),
  migration sobe no boot.

## Não-escopo (YAGNI)

- Sem treino de modelos próprios; usamos pesos prontos.
- Sem busca facial 1:N entre clientes (sempre dentro do `client_id`).
- Sem reconhecimento em vídeo/streams da nuvem (processamos os frames já
  capturados pelo pipeline atual).
- Sem re-identificação cross-câmera (cada track é local à câmera, como hoje).

## Riscos / mitigações

- **Licença de modelos:** uso de OpenCV Zoo (permissivo) em vez de InsightFace.
- **VPS sem github:** modelos embutidos no build (como yolov8); libs via PyPI.
- **Peso na VPS:** faces só rodam quando a câmera/plano habilitam; uma
  identificação por track (não por frame); modelos CPU leves.
- **Qualidade de rosto:** gate de qualidade/tamanho mínimo antes de gravar/identificar.
