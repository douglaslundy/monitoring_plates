# Reconhecimento Facial — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar reconhecimento facial ao SaaS, espelhando o pipeline de OCR: detectar pessoa → detectar rosto → gravar 1 registro por track → identificar faces cadastradas (mostrar nome) → alertar (e-mail/WhatsApp/WebSocket), com 1 motor local (OpenCV YuNet+SFace) e 3 pagos (AWS Rekognition, Luxand, Face++) selecionáveis por plano.

**Architecture:** Reusa YOLO `person` + rastreador por track já existentes. Acrescenta `FaceRouter` (espelha `OcrRouter`), modelos `Person`/`PersonFace`/`FaceDetection`/`FaceEngineConfig`, bloco facial no `frame_processor`, `face_alert_service`, rotas e telas (admin+client). Câmera escolhe OCR/Faces; plano habilita OCR/Faces e o motor.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / Alembic / Celery / Redis / OpenCV (YuNet+SFace ONNX) / boto3 (AWS) / requests (Luxand, Face++) / Next.js 14 / TypeScript / Tailwind.

## Global Constraints

- Type hints completos em todo Python.
- Isolamento multi-tenant: TODA query de `Person`/`FaceDetection` filtra por `client_id` (direto ou via câmera).
- Toda alteração de banco via Alembic. Head atual = `015`. Novas migrations encadeiam a partir daí (`016`...).
- Enums/colunas com defaults compatíveis com SQLite (testes) e Postgres.
- Settings via `app.core.config.settings` (pydantic-settings), nunca hardcoded.
- Frontend: TypeScript sem `any`; toda chamada via `src/lib/api.ts`; loading/error/empty em todo componente; validação em tempo real; responsivo 375/768/1280.
- `pytest backend/tests/ -v` deve passar antes de cada conclusão de tarefa.
- Libs pesadas (cv2/onnxruntime/boto3/requests) com import lazy e mockáveis via `patch.dict(sys.modules, ...)`.
- **Commit a cada tarefa concluída** (mensagem `feat:`/`fix:`/`test:`). Push só ao final. Deploy só quando todas concluídas.

---

## Task 1: Colunas de Plano e Câmera (OCR/Faces toggles)

**Files:**
- Modify: `backend/app/models/plan.py`
- Modify: `backend/app/models/camera.py`
- Modify: `backend/app/schemas/plan.py`, `backend/app/schemas/camera.py`
- Create: `backend/alembic/versions/016_face_toggles.py`
- Test: `backend/tests/test_face_toggles.py`

**Interfaces:**
- Produces: `Plan.ocr_enabled: bool`, `Plan.face_recognition_enabled: bool`, `Plan.face_engine: str`; `Camera.enable_ocr: bool`, `Camera.enable_face: bool`. Schemas `PlanCreate/Update/Read` e `CameraCreate/Update/Read` expõem os campos.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_face_toggles.py
import uuid
from app.models.plan import Plan
from app.models.camera import Camera, ConnectionType


def test_plan_has_face_columns(db_session):
    plan = Plan(name="FaceTest", price_monthly=10, face_recognition_enabled=True, face_engine="system_default")
    db_session.add(plan); db_session.commit(); db_session.refresh(plan)
    assert plan.ocr_enabled is True
    assert plan.face_recognition_enabled is True
    assert plan.face_engine == "system_default"


def test_camera_has_face_toggles(db_session, sample_client):
    cam = Camera(client_id=sample_client.id, name="C1", connection_type=ConnectionType.rtsp, enable_face=True)
    db_session.add(cam); db_session.commit(); db_session.refresh(cam)
    assert cam.enable_ocr is True
    assert cam.enable_face is True
```

(Use as fixtures `db_session`/`sample_client` já existentes em `backend/tests/conftest.py`; se `sample_client` não existir, crie um `Client` inline com um `Plan`.)

- [ ] **Step 2: Run test to verify it fails** — `pytest backend/tests/test_face_toggles.py -v` → FAIL (coluna inexistente).

- [ ] **Step 3: Add columns to models**

```python
# plan.py — dentro de class Plan, após ocr_engine:
ocr_enabled = Column(Boolean, nullable=False, default=True, server_default=text("1"))
face_recognition_enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"))
face_engine = Column(String(30), nullable=False, default="system_default", server_default="system_default")
```
(import `text` de sqlalchemy.)

```python
# camera.py — dentro de class Camera, após is_active:
enable_ocr = Column(Boolean, nullable=False, default=True, server_default=text("1"))
enable_face = Column(Boolean, nullable=False, default=False, server_default=text("0"))
```

- [ ] **Step 4: Add fields to schemas** — em `PlanCreate/PlanUpdate/PlanRead` acrescentar `ocr_enabled: bool = True`, `face_recognition_enabled: bool = False`, `face_engine: str = "system_default"` (no Update, todos `Optional[...] = None`). Em `CameraCreate/CameraUpdate/CameraRead` acrescentar `enable_ocr: bool = True`, `enable_face: bool = False` (Update Optional).

- [ ] **Step 5: Write the Alembic migration**

```python
# backend/alembic/versions/016_face_toggles.py
"""face toggles on plan and camera"""
from alembic import op
import sqlalchemy as sa

revision = "016_face_toggles"
down_revision = "015_alerts_sent_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("ocr_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("plans", sa.Column("face_recognition_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("plans", sa.Column("face_engine", sa.String(length=30), nullable=False, server_default="system_default"))
    op.add_column("cameras", sa.Column("enable_ocr", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("cameras", sa.Column("enable_face", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    for col in ("enable_face", "enable_ocr"):
        op.drop_column("cameras", col)
    for col in ("face_engine", "face_recognition_enabled", "ocr_enabled"):
        op.drop_column("plans", col)
```
(Confirme o `down_revision` real lendo o topo de `015_alerts_sent_message.py` — use exatamente o `revision` declarado lá.)

- [ ] **Step 6: Run tests** — `pytest backend/tests/test_face_toggles.py -v` → PASS. Rode também `pytest backend/tests/ -q` para garantir que nada quebrou.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat: toggles de OCR/Faces em plano e camera (migration 016)"`

---

## Task 2: Modelos Person e PersonFace

**Files:**
- Create: `backend/app/models/person.py`, `backend/app/models/person_face.py`
- Modify: `backend/app/models/__init__.py` (importar p/ Alembic autogenerate/metadata), `backend/app/models/client.py` (relationship `persons`)
- Create: `backend/alembic/versions/017_persons.py`
- Test: `backend/tests/test_person_model.py`

**Interfaces:**
- Produces: `Person(id, client_id, name, birth_date, cpf, address, phone, notes, photo_path, alert_active, alert_email, alert_whatsapp, is_active, created_at)`; `PersonFace(id, person_id, engine_type, embedding(JSON), external_ref(str), image_path, created_at)`. `Client.persons` relationship.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_person_model.py
from datetime import date
from app.models.person import Person
from app.models.person_face import PersonFace


def test_create_person_with_face(db_session, sample_client):
    p = Person(client_id=sample_client.id, name="Joao Silva", cpf="12345678900",
               birth_date=date(1990, 5, 1), phone="11999998888", address="Rua A, 10",
               alert_active=True, alert_email="a@b.com")
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    face = PersonFace(person_id=p.id, engine_type="opencv", embedding=[0.1, 0.2], image_path="x.jpg")
    db_session.add(face); db_session.commit()
    assert p.is_active is True
    assert p.faces[0].engine_type == "opencv"
```

- [ ] **Step 2: Run** → FAIL (módulo inexistente).

- [ ] **Step 3: Create `person.py`**

```python
import uuid
from sqlalchemy import Column, String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Person(Base):
    __tablename__ = "persons"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(Uuid(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    birth_date = Column(Date, nullable=True)
    cpf = Column(String(14), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    photo_path = Column(String(500), nullable=True)
    alert_active = Column(Boolean, nullable=False, default=False)
    alert_email = Column(String(255), nullable=True)
    alert_whatsapp = Column(String(30), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="persons")
    faces = relationship("PersonFace", back_populates="person", cascade="all, delete-orphan")
    detections = relationship("FaceDetection", back_populates="person")
```

- [ ] **Step 4: Create `person_face.py`**

```python
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class PersonFace(Base):
    __tablename__ = "person_faces"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id = Column(Uuid(as_uuid=True), ForeignKey("persons.id"), nullable=False)
    engine_type = Column(String(30), nullable=False)
    embedding = Column(JSON, nullable=True)        # vetor local (OpenCV)
    external_ref = Column(String(255), nullable=True)  # FaceId/face_token/uuid da nuvem
    image_path = Column(String(500), nullable=True)    # foto de referência p/ re-index
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    person = relationship("Person", back_populates="faces")
```

- [ ] **Step 5: Wire relationships/imports** — em `client.py` adicionar `persons = relationship("Person", back_populates="client")`. Em `models/__init__.py` importar `Person`, `PersonFace` (seguindo o padrão dos imports existentes).

- [ ] **Step 6: Migration `017_persons.py`** — `down_revision = "016_face_toggles"`. `create_table("persons", ...)` e `create_table("person_faces", ...)` com as colunas acima (use `sa.Uuid`, `sa.JSON`, FKs para `clients.id` e `persons.id`). `downgrade` faz drop na ordem inversa.

- [ ] **Step 7: Run** `pytest backend/tests/test_person_model.py -v` → PASS; depois `pytest backend/tests/ -q`.

- [ ] **Step 8: Commit** — `feat: modelos Person e PersonFace (migration 017)`

---

## Task 3: Modelo FaceDetection

**Files:**
- Create: `backend/app/models/face_detection.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/camera.py` (relationship `face_detections`)
- Create: `backend/alembic/versions/018_face_detections.py`
- Test: `backend/tests/test_face_detection_model.py`

**Interfaces:**
- Produces: `FaceDetection(id, camera_id, person_id?, confidence, image_path, bbox_x/y/w/h, track_id, detected_at, expires_at?, tracked_seconds?, face_engine_used)`. `Camera.face_detections`, `Person.detections`.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_face_detection_model.py
from app.models.face_detection import FaceDetection
from app.models.camera import Camera, ConnectionType


def test_create_face_detection(db_session, sample_client):
    cam = Camera(client_id=sample_client.id, name="C", connection_type=ConnectionType.rtsp)
    db_session.add(cam); db_session.commit(); db_session.refresh(cam)
    fd = FaceDetection(camera_id=cam.id, confidence=0.9, track_id="abc123",
                       bbox_x=1, bbox_y=2, bbox_w=3, bbox_h=4, face_engine_used="opencv")
    db_session.add(fd); db_session.commit(); db_session.refresh(fd)
    assert fd.person_id is None
    assert fd.detected_at is not None
    assert fd.tracked_seconds is None
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create model**

```python
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class FaceDetection(Base):
    __tablename__ = "face_detections"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(Uuid(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    person_id = Column(Uuid(as_uuid=True), ForeignKey("persons.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    image_path = Column(String(500), nullable=True)
    bbox_x = Column(Integer, nullable=True)
    bbox_y = Column(Integer, nullable=True)
    bbox_w = Column(Integer, nullable=True)
    bbox_h = Column(Integer, nullable=True)
    track_id = Column(String(32), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    tracked_seconds = Column(Float, nullable=True)
    face_engine_used = Column(String(30), nullable=True)

    camera = relationship("Camera", back_populates="face_detections")
    person = relationship("Person", back_populates="detections")
```

- [ ] **Step 4: Wire** — `Camera.face_detections = relationship("FaceDetection", back_populates="camera")`; import em `__init__.py`.

- [ ] **Step 5: Migration `018_face_detections.py`** — `down_revision="017_persons"`. `create_table("face_detections", ...)`.

- [ ] **Step 6: Run** test + suíte.

- [ ] **Step 7: Commit** — `feat: modelo FaceDetection (migration 018)`

---

## Task 4: Modelo FaceEngineConfig

**Files:**
- Create: `backend/app/models/face_engine_config.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/019_face_engine_config.py`
- Test: `backend/tests/test_face_engine_config_model.py`

**Interfaces:**
- Produces: `FaceEngineType` enum (`opencv`, `rekognition`, `luxand`, `facepp`); `FaceEngineConfig(id, engine_type, mode, is_active, api_token, api_secret, api_url, region, threshold, created_at, updated_at)`.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_face_engine_config_model.py
from app.models.face_engine_config import FaceEngineConfig, FaceEngineType


def test_create_face_engine_config(db_session):
    cfg = FaceEngineConfig(engine_type=FaceEngineType.rekognition.value, is_active=True,
                           api_token="AKIA...", api_secret="secret", region="us-east-1", threshold=0.85)
    db_session.add(cfg); db_session.commit(); db_session.refresh(cfg)
    assert cfg.is_active is True
    assert cfg.threshold == 0.85
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create model** (espelha `ocr_engine_config.py`)

```python
import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, Float
from sqlalchemy import Uuid
from sqlalchemy.sql import func
from app.core.database import Base


class FaceEngineType(str, enum.Enum):
    opencv = "opencv"
    rekognition = "rekognition"
    luxand = "luxand"
    facepp = "facepp"


class FaceEngineConfig(Base):
    __tablename__ = "face_engine_configs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine_type = Column(String(30), nullable=False)
    mode = Column(String(15), nullable=False, default="cloud")
    is_active = Column(Boolean, nullable=False, default=False)
    api_token = Column(String(255), nullable=True)     # AWS access key / Luxand token / Face++ key
    api_secret = Column(String(255), nullable=True)    # AWS secret / Face++ secret
    api_url = Column(String(500), nullable=True)        # endpoint Luxand/Face++ (opcional)
    region = Column(String(50), nullable=True)          # AWS region
    threshold = Column(Float, nullable=False, default=0.80)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Migration `019_face_engine_config.py`** — `down_revision="018_face_detections"`.

- [ ] **Step 5: Run** test + suíte.

- [ ] **Step 6: Commit** — `feat: modelo FaceEngineConfig (migration 019)`

---

## Task 5: Colunas de face em AlertSent

**Files:**
- Modify: `backend/app/models/alert_sent.py`
- Create: `backend/alembic/versions/020_alert_sent_face.py`
- Test: `backend/tests/test_alert_sent_face.py`

**Interfaces:**
- Produces: `AlertSent.person_id?`, `AlertSent.face_detection_id?`; `occurrence_id`/`monitored_plate_id` passam a nullable.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_alert_sent_face.py
from app.models.alert_sent import AlertSent, AlertChannel


def test_alert_sent_face_only(db_session):
    a = AlertSent(channel=AlertChannel.email, status="sent",
                  person_id=None, face_detection_id=None)
    db_session.add(a); db_session.commit(); db_session.refresh(a)
    assert a.occurrence_id is None  # agora nullable
```

- [ ] **Step 2: Run** → FAIL (NOT NULL / coluna inexistente).

- [ ] **Step 3: Edit model** — em `alert_sent.py` tornar `occurrence_id` e `monitored_plate_id` `nullable=True`; adicionar `person_id = Column(Uuid(as_uuid=True), ForeignKey("persons.id"), nullable=True)` e `face_detection_id = Column(Uuid(as_uuid=True), ForeignKey("face_detections.id"), nullable=True)`.

- [ ] **Step 4: Migration `020_alert_sent_face.py`** — `down_revision="019_face_engine_config"`. `add_column` para `person_id`/`face_detection_id`; `alter_column(..., nullable=True)` para `occurrence_id`/`monitored_plate_id` (em SQLite o alter de nullable é no-op aceitável — proteja com `if op.get_bind().dialect.name != "sqlite":`).

- [ ] **Step 5: Run** test + suíte.

- [ ] **Step 6: Commit** — `feat: AlertSent suporta alertas de face (migration 020)`

---

## Task 6: Motor local de faces (OpenCV YuNet + SFace)

**Files:**
- Create: `backend/app/services/face_detection_service.py`
- Modify: `backend/app/core/config.py` (settings de face)
- Test: `backend/tests/test_face_detection_service.py`

**Interfaces:**
- Produces:
  - `@dataclass FaceBox(bbox_x, bbox_y, bbox_w, bbox_h, confidence, crop_bytes)`
  - `class OpenCVFaceEngine` com `detect(image_bytes) -> list[FaceBox]`, `embed(image_bytes) -> list[float] | None`, `warmup()`.
  - `cosine_similarity(a: list[float], b: list[float]) -> float`.
  - settings: `FACE_MODEL_DIR`, `FACE_DETECTOR_MODEL` (yunet onnx), `FACE_RECOGNIZER_MODEL` (sface onnx), `FACE_MIN_DETECT_SCORE=0.7`, `FACE_MATCH_THRESHOLD=0.36` (cosseno SFace), `FACE_MIN_CROP_SIDE=80`.

- [ ] **Step 1: Add settings** em `config.py` (junto às demais), com defaults acima e `FACE_MODEL_DIR` derivado de `MODELS_DIR`.

- [ ] **Step 2: Failing test** (cv2 mockado — segue o padrão de `test_vehicle_detection_service.py`)

```python
# backend/tests/test_face_detection_service.py
from app.services.face_detection_service import cosine_similarity


def test_cosine_similarity_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal():
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_engine_degraded_without_model(monkeypatch):
    # Sem modelo/cv2 -> detect retorna [] e embed retorna None (modo degradado)
    from app.services.face_detection_service import OpenCVFaceEngine
    eng = OpenCVFaceEngine()
    monkeypatch.setattr(eng, "_get_detector", lambda: None)
    assert eng.detect(b"notanimage") == []
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Implement** `face_detection_service.py`. Padrão idêntico ao `vehicle_detection_service` (lazy import cv2, lock, `_unavailable`, modo degradado). Use `cv2.FaceDetectorYN_create(yunet_path, "", (w,h), score_threshold)` para detecção e `cv2.FaceRecognizerSF_create(sface_path, "")` para `feature()` (embedding 128-d). `embed` faz: decode → detect maior rosto → `alignCrop` → `feature` → `feature.flatten().tolist()`. `cosine_similarity` em puro Python (sem numpy obrigatório):

```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0
```

`detect` retorna `FaceBox` com `crop_bytes` (recorte JPEG do rosto, ampliado p/ `FACE_MIN_CROP_SIDE` reusando a lógica de `_upscale_to_min`/`_encode_jpeg` — copie o padrão). Modo degradado (sem modelo) → `detect`=[], `embed`=None.

- [ ] **Step 5: Run** `pytest backend/tests/test_face_detection_service.py -v` → PASS; suíte completa.

- [ ] **Step 6: Commit** — `feat: motor local de faces OpenCV YuNet+SFace`

---

## Task 7: FaceRouter + motores de nuvem (AWS, Luxand, Face++)

**Files:**
- Create: `backend/app/services/face_service.py`
- Test: `backend/tests/test_face_service.py`

**Interfaces:**
- Consumes: `OpenCVFaceEngine`, `cosine_similarity` (Task 6); `FaceEngineConfig`, `FaceEngineType` (Task 4); `Person`, `PersonFace` (Task 2); `Camera`/`Plan` (Task 1).
- Produces:
  - `@dataclass EnrollResult(engine_type: str, embedding: list[float] | None, external_ref: str | None)`
  - `@dataclass FaceMatch(person_id: str, confidence: float)`
  - `class FaceRouter` com:
    - `enroll(client_id: str, person_id: str, image_bytes: bytes) -> EnrollResult` (no motor ativo do cliente)
    - `identify(client_id: str, image_bytes: bytes) -> Optional[FaceMatch]`
    - `resolve_engine_type(client_id: str | None) -> str` (cacheado 60s, igual ao OcrRouter)
  - instância global `face_recognizer = FaceRouter()`.

**Notas de implementação por motor:**
- **opencv (local):** `enroll` → `embed`; grava embedding (via caller). `identify` → `embed` da imagem + cosseno contra `PersonFace.embedding` das pessoas ativas do cliente (carregadas do DB, cache 60s por client), match se `>= FACE_MATCH_THRESHOLD`.
- **rekognition (boto3):** collection `face-{client_id}` (cria idempotente). `enroll`=`index_faces(ExternalImageId=person_id)`→retorna `FaceId`. `identify`=`search_faces_by_image(FaceMatchThreshold=threshold*100)`→`ExternalImageId` é o person_id; confidence/100.
- **luxand (requests):** `enroll`=cria subject/`person` (POST /v2/person) e adiciona foto, guarda uuid; `identify`=POST /photo/search/v2 retorna lista com `uuid`+`probability` → mapear uuid→person via `PersonFace.external_ref`.
- **facepp (requests):** `enroll`=`detect`→`face_token`; `faceset/addface` (outer_id=client_id, cria faceset idempotente). `identify`=`search` (faceset outer_id)→`face_token`+`confidence` → mapear via external_ref.

Todos os motores de nuvem: leem credenciais de `FaceEngineConfig` (is_active, engine_type), import lazy de boto3/requests, falha → log + retorno None (com fallback p/ local em `identify`, igual ao OcrRouter).

- [ ] **Step 1: Failing test** (motores de nuvem mockados via `patch.dict(sys.modules,...)`; local via embeddings em memória)

```python
# backend/tests/test_face_service.py
from app.services.face_service import FaceRouter, FaceMatch


def test_identify_local_matches_enrolled(db_session, monkeypatch, sample_client_with_opencv_plan):
    router = FaceRouter()
    # força motor local
    monkeypatch.setattr(router, "resolve_engine_type", lambda cid: "opencv")
    # embed determinístico
    monkeypatch.setattr("app.services.face_service._local_engine.embed", lambda b: [1.0, 0.0, 0.0])
    # cadastra pessoa com embedding idêntico
    from app.models.person import Person
    from app.models.person_face import PersonFace
    p = Person(client_id=sample_client_with_opencv_plan.id, name="X", is_active=True)
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    db_session.add(PersonFace(person_id=p.id, engine_type="opencv", embedding=[1.0, 0.0, 0.0]))
    db_session.commit()
    match = router.identify(str(sample_client_with_opencv_plan.id), b"img")
    assert isinstance(match, FaceMatch)
    assert match.person_id == str(p.id)
    assert match.confidence > 0.99


def test_identify_no_match_returns_none(db_session, monkeypatch, sample_client_with_opencv_plan):
    router = FaceRouter()
    monkeypatch.setattr(router, "resolve_engine_type", lambda cid: "opencv")
    monkeypatch.setattr("app.services.face_service._local_engine.embed", lambda b: None)
    assert router.identify(str(sample_client_with_opencv_plan.id), b"img") is None
```
(Adicione a fixture `sample_client_with_opencv_plan` em `conftest.py`: client com plano `face_engine="opencv"`, `face_recognition_enabled=True`.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** `face_service.py` conforme as notas. `resolve_engine_type` espelha `OcrRouter._build_engine`/`_get_system_default` (plano da câmera/cliente → `face_engine`; `system_default` → `FaceEngineConfig` ativo; senão `opencv`). Cache de embeddings do cliente com TTL 60s e invalidável.

- [ ] **Step 4: Run** test + suíte.

- [ ] **Step 5: Commit** — `feat: FaceRouter com motores OpenCV/AWS/Luxand/Face++`

---

## Task 8: Rotas e schemas de Pessoas (cadastro + enroll + reindex)

**Files:**
- Create: `backend/app/schemas/person.py`, `backend/app/api/routes/persons.py`
- Modify: `backend/app/main.py` (incluir router), `backend/app/services/storage_service.py` (se faltar helper p/ salvar foto — reuse `save_bytes`)
- Test: `backend/tests/test_persons_api.py`

**Interfaces:**
- Consumes: `FaceRouter.enroll` (Task 7), `Person`/`PersonFace` (Task 2), `save_bytes`/`get_url` (existentes).
- Produces: rotas `GET/POST/GET{id}/PATCH{id}/DELETE{id} /api/persons`, `POST /api/persons/{id}/face` (upload foto → enroll → grava PersonFace + photo_path), `POST /api/persons/{id}/reindex` (re-enroll de todas as PersonFace a partir de `image_path`). Schemas `PersonCreate/Update/Read`.

- [ ] **Step 1: Failing tests** (cobrir: criar pessoa, isolamento multi-tenant, upload de face chama enroll mockado, list só do próprio cliente). Use `client` (TestClient) + auth fixtures existentes (veja `test_*_api.py`).

```python
# backend/tests/test_persons_api.py (esqueleto — complete com as fixtures de auth existentes)
def test_create_and_list_person(client, auth_headers_client_admin):
    r = client.post("/api/persons", json={"name": "Maria", "cpf": "11122233344"}, headers=auth_headers_client_admin)
    assert r.status_code == 201
    pid = r.json()["id"]
    r2 = client.get("/api/persons", headers=auth_headers_client_admin)
    assert any(p["id"] == pid for p in r2.json())


def test_person_tenant_isolation(client, auth_headers_client_admin, other_client_person):
    r = client.get(f"/api/persons/{other_client_person.id}", headers=auth_headers_client_admin)
    assert r.status_code in (403, 404)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement schemas** `person.py` (`PersonCreate`: name obrigatório + demais opcionais; `PersonUpdate` tudo Optional; `PersonRead` inclui `id`, `photo_url`, contagem de faces, `created_at`).

- [ ] **Step 4: Implement router** `persons.py` espelhando `cameras.py` para escopo multi-tenant (`_get_person_or_403` análogo a `_get_camera_or_403`; super_admin vê todos, client_admin/user só o próprio `client_id`; **escrita** restrita a `super_admin`/`client_admin` via checagem de role). `POST /{id}/face`: recebe `UploadFile`, salva via `save_bytes(bytes, f"persons/{id}")`, chama `face_recognizer.enroll(client_id, person_id, bytes)`, grava `PersonFace(engine_type=result.engine_type, embedding=result.embedding, external_ref=result.external_ref, image_path=path)` e seta `person.photo_path`. `POST /{id}/reindex`: para cada PersonFace, recarrega bytes de `image_path` (via `read_file_bytes`) e re-chama enroll, atualizando a linha.

- [ ] **Step 5: Register router** em `main.py` (`app.include_router(persons.router, prefix="/api")` seguindo o padrão dos outros).

- [ ] **Step 6: Run** test + suíte.

- [ ] **Step 7: Commit** — `feat: API de cadastro de pessoas + enroll/reindex de faces`

---

## Task 9: Rota de configuração de motores de face (super_admin)

**Files:**
- Create: `backend/app/schemas/face_engine_config.py`, `backend/app/api/routes/face_config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_face_config_api.py`

**Interfaces:**
- Produces: `/api/face-config` CRUD + `POST /{id}/activate` + `POST /{id}/test` (espelha `ocr_config.py`). `test` para `opencv` retorna sucesso sem credenciais; para nuvem valida credenciais (AWS: `list_collections`; Luxand/Face++: chamada de auth leve) — todas mockadas no teste.

- [ ] **Step 1: Failing test** — criar config rekognition, ativar, listar; `require_super_admin` barra client_admin.

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement schemas + router** espelhando `ocr_config.py` (mesma estrutura de create/patch/delete/activate/test, `Depends(require_super_admin)`).

- [ ] **Step 4: Register** em `main.py`.

- [ ] **Step 5: Run** test + suíte.

- [ ] **Step 6: Commit** — `feat: API de configuracao de motores de face (super_admin)`

---

## Task 10: Rastreador expõe tracks expirados

**Files:**
- Modify: `backend/app/services/object_tracker_service.py`
- Test: `backend/tests/test_object_tracker_expiry.py`

**Interfaces:**
- Produces: `update_tracks(...)` passa a retornar **4-tupla** `(novo_estado, newly, det_to_track, expired)` onde `expired: list[dict]` são os tracks removidos por idade nesta chamada (cada um com `track_id`, `first_seen_at`, `last_seen_at`, `category`).

⚠️ **Compatibilidade:** `update_tracks` é chamado em `frame_processor` e em `track_camera`. Atualize **ambos** os call sites para desempacotar 4 valores.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_object_tracker_expiry.py
from app.services.object_tracker_service import update_tracks
from app.core.config import settings


def test_expired_tracks_returned(monkeypatch):
    monkeypatch.setattr(settings, "TRACK_MAX_AGE_SECONDS", 5)
    det = [{"category": "person", "label": "person", "confidence": 0.9,
            "bbox": {"bbox_x": 0, "bbox_y": 0, "bbox_w": 10, "bbox_h": 10}}]
    state, newly, d2t, expired = update_tracks([], det, now=100.0)
    assert expired == []
    # nenhum match no próximo frame, muito depois -> expira
    state2, newly2, d2t2, expired2 = update_tracks(state, [], now=200.0)
    assert len(expired2) == 1
    assert expired2[0]["category"] == "person"
```

- [ ] **Step 2: Run** → FAIL (desempacota 3, recebe 4 / função retorna 3).

- [ ] **Step 3: Implement** — no passo 1 de `update_tracks`, capture os tracks removidos: `expired = [t for t in state if now - float(t["last_seen_at"]) > _eff_max_age(t)]` antes de filtrar `tracks`. Retorne `tracks, newly, det_to_track, expired`. Em `track_camera`, ajuste para `state, newly, _d2t, _exp = update_tracks(...)`.

- [ ] **Step 4: Update frame_processor call site** — `track_state, newly, det_to_track, expired = update_tracks(...)` (o uso de `expired` vem na Task 11; por ora só desempacote para não quebrar).

- [ ] **Step 5: Run** test + `pytest backend/tests/ -q` (garanta que os testes do tracker existentes que chamam `update_tracks` foram ajustados — busque por `update_tracks(` em `backend/tests/`).

- [ ] **Step 6: Commit** — `feat: rastreador expoe tracks expirados`

---

## Task 11: Bloco facial no frame_processor (gravar 1x por track + duração)

**Files:**
- Modify: `backend/app/workers/frame_processor.py`
- Create: `backend/app/services/face_pipeline_service.py` (lógica testável, fora da task Celery)
- Test: `backend/tests/test_face_pipeline_service.py`

**Interfaces:**
- Consumes: `FaceRouter.identify` (Task 7), `face_detection_service` (Task 6), `FaceDetection` (Task 3), tracker `expired` (Task 10), `face_alert_service.process_face_alerts` (Task 12 — import lazy).
- Produces:
  - `face_pipeline_service.process_faces(db, camera, detections, det_to_track, display_image_fn, now_ts) -> None` — para cada detecção `person` cujo track está `counted` e ainda sem `face_saved`: detecta rosto no `crop_bytes`; se houver rosto válido, roda `identify`, cria `FaceDetection` (1x), marca `track["face_saved"]=True` e `track["face_detection_id"]=str(id)`, dispara alertas.
  - `face_pipeline_service.finalize_expired_faces(db, expired) -> None` — para cada track expirado com `face_detection_id`, `UPDATE tracked_seconds = last_seen_at - first_seen_at`.

**Gating:** só roda se `camera.enable_face` e `camera.client.plan.face_recognition_enabled`.

- [ ] **Step 1: Failing tests** (com DB de teste; `identify` e `face_detection_service.detect` mockados)

```python
# backend/tests/test_face_pipeline_service.py (esqueleto)
def test_process_faces_creates_one_detection_per_track(db_session, monkeypatch, face_camera, person_detection_with_track):
    from app.services import face_pipeline_service as fps
    from app.models.face_detection import FaceDetection
    monkeypatch.setattr(fps, "_detect_face_crop", lambda crop: b"facecrop")  # rosto presente
    monkeypatch.setattr("app.services.face_pipeline_service.face_recognizer.identify", lambda cid, b: None)
    detections, det_to_track = person_detection_with_track  # track counted=True, face_saved ausente
    fps.process_faces(db_session, face_camera, detections, det_to_track, lambda: "img.jpg", now_ts=100.0)
    assert db_session.query(FaceDetection).count() == 1
    # 2ª passada no mesmo track NÃO cria outra
    fps.process_faces(db_session, face_camera, detections, det_to_track, lambda: "img.jpg", now_ts=101.0)
    assert db_session.query(FaceDetection).count() == 1


def test_finalize_expired_sets_duration(db_session, face_camera):
    from app.services import face_pipeline_service as fps
    from app.models.face_detection import FaceDetection
    fd = FaceDetection(camera_id=face_camera.id, track_id="t1", face_engine_used="opencv")
    db_session.add(fd); db_session.commit(); db_session.refresh(fd)
    expired = [{"track_id": "t1", "first_seen_at": 100.0, "last_seen_at": 142.0,
                "category": "person", "face_detection_id": str(fd.id)}]
    fps.finalize_expired_faces(db_session, expired)
    db_session.refresh(fd)
    assert fd.tracked_seconds == 42.0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** `face_pipeline_service.py`. `process_faces`: itera `detections`; para `d.category == "person"`, pega `tr = det_to_track.get(idx)`; pula se `tr is None or not tr.get("counted") or tr.get("face_saved")`; `crop = _detect_face_crop(d.crop_bytes)` (usa `face_detection_service` local só p/ achar/encaixotar o rosto — a identificação usa o motor do plano); se `crop is None` continua; `match = face_recognizer.identify(client_id, crop)`; calcula `expires_at` pelo plano; cria `FaceDetection(camera_id, person_id=match.person_id se houver, confidence, image_path=display_image_fn(), bbox..., track_id=tr["track_id"], expires_at, face_engine_used=resolve_engine_type)`; `db.flush()`; `tr["face_saved"]=True; tr["face_detection_id"]=str(fd.id)`; se `match`, chama `process_face_alerts(str(fd.id), db)`. `finalize_expired_faces`: para cada `e` com `face_detection_id`, busca o FaceDetection e seta `tracked_seconds = float(e["last_seen_at"]) - float(e["first_seen_at"])` quando `>0`.

- [ ] **Step 4: Wire no `frame_processor`** — após o bloco de eventos de detecção e antes/depois do `db.commit()`: guard `if camera.enable_face and camera.client.plan and camera.client.plan.face_recognition_enabled:` chamar `process_faces(db, camera, detections, det_to_track, _display_image, now_ts)` e `finalize_expired_faces(db, expired)`. Garanta que `expired` (Task 10) está no escopo. Imports lazy dentro da task Celery (como os demais).

- [ ] **Step 5: Run** `pytest backend/tests/test_face_pipeline_service.py -v` + suíte.

- [ ] **Step 6: Commit** — `feat: bloco facial no pipeline (1 registro por track + duracao)`

---

## Task 12: Serviço de alertas de face + rota de detecções de face

**Files:**
- Create: `backend/app/services/face_alert_service.py`, `backend/app/schemas/face_detection.py`, `backend/app/api/routes/face_detections.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_face_alert_service.py`, `backend/tests/test_face_detections_api.py`

**Interfaces:**
- Consumes: `FaceDetection`/`Person` (Tasks 2-3), `send_*`/whatsapp/email + redis pub/sub (existentes em `alert_service`).
- Produces:
  - `face_alert_service.process_face_alerts(face_detection_id: str, db) -> None` — espelha `process_alerts`: se a `Person` casada tem `alert_active`, envia e-mail (se `plan.email_alerts` e `alert_email`), WhatsApp (se `alert_whatsapp`), WebSocket (se `plan.realtime_alerts`, payload `type="face_alert"` com `person_name`, `camera_name`, `image_url`, `detected_at`), dedup via `AlertSent` (usando `face_detection_id`/`person_id`).
  - rotas `GET /api/face-detections` (lista/busca client-scoped, inclui `person_name`) e `GET /api/face-detections/{id}`.

- [ ] **Step 1: Failing tests** — (a) alerta envia e grava AlertSent quando person.alert_active (email/whatsapp mockados); (b) não envia quando alert_active=False; (c) lista de detecções respeita isolamento por client.

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement** `face_alert_service.py` (espelha `alert_service.py`, trocando MonitoredPlate→Person e Occurrence→FaceDetection; reusa `send_plate_alert`/`send_whatsapp_alert` ou cria mensagens análogas com nome da pessoa). Implemente `_publish_ws_alert` com `type="face_alert"`.

- [ ] **Step 4: Implement** schema + router `face_detections.py` (espelha `occurrences`/`vehicles`: filtro por `client_id` via join em Camera; `person_name` via join em Person; paginação/ordenação por `detected_at desc`).

- [ ] **Step 5: Register** router em `main.py`.

- [ ] **Step 6: Run** ambos os testes + suíte completa.

- [ ] **Step 7: Commit** — `feat: alertas de face + API de deteccoes de face`

---

## Task 13: Frontend — api.ts + tipos

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/types/*` (ou onde os tipos vivem)
- Test: (sem teste unitário de front; valide via build/typecheck `npm run build` no diretório frontend ao final)

**Interfaces:**
- Produces: funções `listPersons/createPerson/updatePerson/deletePerson/getPerson/uploadPersonFace/reindexPerson`, `listFaceDetections`, `listFaceConfigs/createFaceConfig/updateFaceConfig/activateFaceConfig/testFaceConfig`; tipos `Person`, `FaceDetection`, `FaceEngineConfig`. Campos novos em `Camera` (enable_ocr/enable_face) e `Plan` (ocr_enabled/face_recognition_enabled/face_engine).

- [ ] **Step 1:** Adicionar tipos TS espelhando os schemas Pydantic (sem `any`).
- [ ] **Step 2:** Adicionar as funções no `api.ts` seguindo o padrão das existentes (mesma instância axios, mesmos headers/erros). Upload de face usa `FormData`.
- [ ] **Step 3:** `cd frontend && npm run build` → sem erros de tipo.
- [ ] **Step 4: Commit** — `feat: frontend api + tipos para faces`

---

## Task 14: Frontend — páginas de Pessoas (admin + client)

**Files:**
- Create: `frontend/src/app/(client)/client/persons/page.tsx` e `frontend/src/app/(admin)/admin/persons/page.tsx` (confira a estrutura real de rotas existentes — espelhe a de `monitored plates`/`cameras`)
- Create: componente de formulário reutilizável `frontend/src/components/persons/PersonForm.tsx`
- Modify: sidebar(s) para incluir o link

**Interfaces:**
- Consumes: api.ts (Task 13).

- [ ] **Step 1:** Criar `PersonForm` (campos nome/nascimento/cpf/endereço/telefone + upload de foto + toggle de alerta com e-mail/WhatsApp), validação em tempo real (CPF, e-mail), loading/error.
- [ ] **Step 2:** Página client: tabela/cards (reuse `DataTable`/`useViewMode`), criar/editar/excluir (modal confirm), toast de sucesso; estados loading/error/empty.
- [ ] **Step 3:** Página admin: igual, com seleção de cliente (super_admin).
- [ ] **Step 4:** Link na sidebar (admin e client) com aria-label.
- [ ] **Step 5:** `npm run build` ok.
- [ ] **Step 6: Commit** — `feat: telas de cadastro de pessoas (admin e client)`

---

## Task 15: Frontend — páginas de Detecções de Faces

**Files:**
- Create: `frontend/src/app/(client)/client/face-detections/page.tsx` e equivalente admin
- Modify: sidebar

**Interfaces:**
- Consumes: `listFaceDetections` (Task 13).

- [ ] **Step 1:** Lista (cards/lista via `useViewMode`) mostrando **nome da pessoa** (ou "Desconhecido"), imagem (lightbox reusado), câmera, data e **duração rastreada** (`tracked_seconds` formatado). Loading/error/empty.
- [ ] **Step 2:** Link na sidebar.
- [ ] **Step 3:** `npm run build` ok.
- [ ] **Step 4: Commit** — `feat: telas de deteccoes de faces`

---

## Task 16: Frontend — filtro Placas/Faces/Todos na página de Alertas

**Files:**
- Modify: página(s) de alertas existentes (`.../alerts/page.tsx` admin e client), handler de WebSocket (em `ClientLayout`/provider) para aceitar `type="face_alert"`.

**Interfaces:**
- Consumes: payloads WS `plate_alert` e `face_alert` (Task 12).

- [ ] **Step 1:** Adicionar um toggle/segmented `Todos | Placas | Faces` que filtra o feed por `type`.
- [ ] **Step 2:** Tratar `face_alert` no listener WS (mostrar nome da pessoa) e no contador de não-vistos.
- [ ] **Step 3:** `npm run build` ok.
- [ ] **Step 4: Commit** — `feat: filtro placas/faces na pagina de alertas`

---

## Task 17: Frontend — toggles OCR/Faces no formulário de Câmera

**Files:**
- Modify: formulário de câmera (admin e/ou client) onde câmeras são criadas/editadas.

- [ ] **Step 1:** Checkboxes "Ativar OCR (placas)" e "Ativar Reconhecimento Facial" mapeando `enable_ocr`/`enable_face`; enviar no create/update.
- [ ] **Step 2:** `npm run build` ok.
- [ ] **Step 3: Commit** — `feat: escolha de OCR/Faces no cadastro de camera`

---

## Task 18: Frontend — toggles e motor de face no formulário de Plano

**Files:**
- Modify: formulário de planos (admin) — `.../admin/plans/...`.

- [ ] **Step 1:** Toggles `ocr_enabled`/`face_recognition_enabled` + select `face_engine` (system_default/opencv/rekognition/luxand/facepp); enviar no create/update.
- [ ] **Step 2:** `npm run build` ok.
- [ ] **Step 3: Commit** — `feat: configuracao de OCR/Faces e motor no plano`

---

## Task 19: Frontend — página de Configuração de Motores de Face (super_admin)

**Files:**
- Create: `frontend/src/app/(admin)/admin/face-config/page.tsx` (espelha a tela de ocr-config existente)
- Modify: sidebar admin

**Interfaces:**
- Consumes: `listFaceConfigs/...` (Task 13).

- [ ] **Step 1:** Tela espelhando a de OCR: lista de motores, formulário de credenciais por motor (AWS: access key/secret/region; Luxand: token; Face++: key/secret), botões Testar e Ativar, threshold.
- [ ] **Step 2:** Link na sidebar admin (super_admin only).
- [ ] **Step 3:** `npm run build` ok.
- [ ] **Step 4: Commit** — `feat: tela de configuracao de motores de face`

---

## Task 20: Docker — empacotar modelos YuNet/SFace + dependências

**Files:**
- Modify: `backend/Dockerfile`, `backend/requirements.txt`, `docker-compose.yml`/`docker-compose.prod.yml` (se necessário passar `FACE_MODEL_DIR`)
- Test: validar import + carregamento no container ao final.

**Interfaces:**
- Produces: imagem com `face_detection_yunet_2023mar.onnx` e `face_recognition_sface_2021dec.onnx` em `MODELS_DIR`; `boto3` instalado.

- [ ] **Step 1:** Em `requirements.txt` adicionar `boto3`. (cv2/onnxruntime/requests já presentes.)
- [ ] **Step 2:** No estágio de build do `Dockerfile` (que tem internet/HuggingFace), baixar os dois ONNX de um mirror **não-github** (HuggingFace, ex. `opencv/...` ou mirror conhecido) para `MODELS_DIR`; copiar para o runtime (mesmo padrão do `yolov8n.onnx`). Documentar a URL usada. Defina `FACE_DETECTOR_MODEL`/`FACE_RECOGNIZER_MODEL` apontando para esses arquivos.
- [ ] **Step 3:** Build local: `docker compose build backend` (ou o serviço de worker) → sucesso; `docker compose run --rm backend python -c "import boto3, cv2; print('ok')"`.
- [ ] **Step 4: Commit** — `chore: empacota modelos de face e boto3 no build`

---

## Task 21: Suíte completa, seed e push

**Files:**
- Modify: `backend/app/core/seed.py` (se quiser semear um `FaceEngineConfig opencv` ativo e flags de plano — opcional, não-bloqueante)
- Test: suíte inteira.

- [ ] **Step 1:** `pytest backend/tests/ -v` no ambiente que tem as deps (ou via container, conforme `feedback_testes`) → **tudo verde**. Corrija o que quebrar.
- [ ] **Step 2:** `cd frontend && npm run build` → sem erros.
- [ ] **Step 3:** Atualizar `CLAUDE.md`/docs se necessário (tabela de planos com OCR/Faces).
- [ ] **Step 4: Commit final** — `test: suite completa do modulo de faces` (se houver mudanças).
- [ ] **Step 5: Push** — `git push origin main`.

---

## Task 22: Deploy na VPS

- [ ] **Step 1:** Deploy via `deploy.sh` (ou o método pscp + rebuild do `docker-compose.prod.yml` registrado em `deploy_vps`). Host `192.168.0.115`, user `lundy`.
- [ ] **Step 2:** Migrations sobem no boot (`alembic upgrade head`) — confirmar nos logs que `016`→`020` aplicaram.
- [ ] **Step 3:** Smoke test: backend healthy, `/api/face-config` responde, criar uma pessoa + upload de foto (motor opencv) e ver `FaceDetection` ao passar alguém numa câmera com Faces ativo.
- [ ] **Step 4:** Reportar status ao usuário.

---

## Self-Review (cobertura do spec)

- Tarefas 1-6 do usuário (detectar pessoa→rosto, gravar 1x/track, cadastro com nome/nascimento/cpf/endereço/telefone, mostrar nome, alertas e-mail/WhatsApp): Tasks 2, 8, 11, 12. ✅
- Tarefa 7 (página de detecção de faces + filtro na página de alertas): Tasks 15, 16. ✅
- Tarefas 8-9 (2 APIs pagas + 1 local; cliente escolhe e configura): Tasks 6, 7, 9, 19. (3 pagas: AWS+Luxand+Face++.) ✅
- Tarefa 10 (câmera escolhe OCR/Faces/ambos): Tasks 1, 17. ✅
- Tarefa 11 (planos com OCR/Faces): Tasks 1, 18. ✅
- Tarefa 12 (duração de rastreio): Tasks 10, 11. ✅
- Tarefa 12-13 (plano + todo; commit por tarefa; push e deploy): este plano + Tasks 21, 22; atualizar memória TODO. ✅
