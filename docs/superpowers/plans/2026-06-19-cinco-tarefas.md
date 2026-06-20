# 5 Tarefas — Modelos YOLO / Disco / Métricas / WhatsApp / Paginação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar 5 melhorias independentes: modelos YOLO L/XL, diagnóstico de disco, página de métricas dedicada, alertas WhatsApp e paginação melhorada.

**Architecture:** Backend FastAPI + Alembic, Frontend Next.js 14 + TypeScript. Cada tarefa tem seu próprio commit. Push + deploy ao final de todas.

**Tech Stack:** Python 3.11, FastAPI, Alembic, PostgreSQL, Next.js 14, TypeScript, shadcn/ui, Docker, pscp/plink (deploy VPS).

## Global Constraints

- Commit a cada tarefa concluída com mensagem `feat:` ou `fix:`
- TypeScript estrito (sem `any`)
- Toda requisição HTTP via `src/lib/api.ts`
- Sem migrations manuais — sempre via Alembic
- VPS: `root@192.168.0.115`, senha `12345678`
- Deploy com pscp + plink (PuTTY CLI, hostkey `SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38`)
- Pasta na VPS: `/root/monitoramento` (ou `/home/lundy/monitoramento` — verificar)

---

### Task 1: Modelos YOLO Large e Extra Large

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `frontend/src/app/admin/ocr-config/page.tsx` (texto descritivo)

**Interfaces:**
- Nenhuma mudança de API — `available_models()` já lê dinamicamente o diretório `/app/models/*.onnx`
- O admin verá `yolov8l` e `yolov8x` no dropdown após rebuild

- [ ] **Step 1: Atualizar Dockerfile — adicionar yolov8l e yolov8x**

Em `backend/Dockerfile`, linha com `ARG YOLO_MODELS="yolov8n yolov8s yolov8m"`:

```dockerfile
ARG YOLO_MODELS="yolov8n yolov8s yolov8m yolov8l yolov8x"
```

Os pesos `.pt` de `yolov8l` e `yolov8x` NÃO estão no repo (somente `n` e `s` estão). O `export_models.py` já lida com isso: se o `.pt` não estiver presente, o `ultralytics` baixa automaticamente durante o `docker build` (stage `model-export` tem internet). O estágio copia todos os `.onnx` para `/app/models/`.

- [ ] **Step 2: Atualizar descrição no frontend**

Em `frontend/src/app/admin/ocr-config/page.tsx`, linha 226-228:

```tsx
<p className="text-sm text-muted-foreground">
  Modelo usado para detectar veículos, pessoas e animais. Modelos maiores
  (x {">"} l {">"} m {">"} s {">"} n) acertam mais a classe, porém são mais lentos na CPU.
</p>
```

- [ ] **Step 3: Verificar que não há testes a rodar para esta tarefa**

Nenhum teste unitário cobre a lista de modelos disponíveis (é dinâmica de disco). A mudança só tem efeito após rebuild da imagem Docker.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile frontend/src/app/admin/ocr-config/page.tsx
git commit -m "feat: adiciona modelos YOLO Large e Extra Large (yolov8l, yolov8x)"
```

---

### Task 2: Diagnóstico e correção do disco na VPS

**Files:**
- Modify: `backend/app/services/system_metrics_service.py`
- Modify: `backend/app/schemas/ops.py`
- Modify: `frontend/src/components/live/SystemResources.tsx`
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- `GET /api/ops/system` passa a retornar `root_disk_total_gb`, `root_disk_used_gb`, `root_disk_free_gb`, `root_disk_percent`
- `SystemMetrics` (backend) ganha 4 novos campos
- `SystemMetricsRead` (schema Pydantic) idem
- `SystemMetrics` (TypeScript) idem

**Contexto:** O dashboard atual usa `psutil.disk_usage("/app/storage")` (volume Docker). Docker images/build-cache ficam em `/var/lib/docker/` no host, que pode estar em outra partição. Expor também a partição `/` (root) para diagnóstico completo.

- [ ] **Step 1: SSH na VPS para diagnóstico (não modifica código)**

```bash
plink -batch -pw 12345678 -hostkey "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38" root@192.168.0.115 "df -h && echo '---DOCKER---' && docker system df"
```

Registrar saída para entender qual partição tem espaço ocupado.

- [ ] **Step 2: Backend — adicionar root disk em `system_metrics_service.py`**

```python
@dataclass(slots=True)
class SystemMetrics:
    available: bool
    cpu_percent: float
    cpu_count: int
    load_avg_1m: float
    mem_total_mb: int
    mem_used_mb: int
    mem_available_mb: int
    mem_percent: float
    # storage volume disk (/app/storage)
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float
    # root filesystem disk (/) — inclui camadas Docker e sistema
    root_disk_total_gb: float
    root_disk_used_gb: float
    root_disk_free_gb: float
    root_disk_percent: float

    def as_dict(self) -> dict:
        return asdict(self)


_EMPTY = SystemMetrics(False, 0.0, 0, 0.0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
```

E em `get_system_metrics()`, após `du = psutil.disk_usage(_disk_path())`:

```python
        try:
            du_root = psutil.disk_usage("/")
        except Exception:
            du_root = du  # fallback: usa o mesmo que storage

        return SystemMetrics(
            # ... campos existentes ...
            root_disk_total_gb=round(du_root.total / _GB, 1),
            root_disk_used_gb=round(du_root.used / _GB, 1),
            root_disk_free_gb=round(du_root.free / _GB, 1),
            root_disk_percent=round(du_root.percent, 1),
        )
```

- [ ] **Step 3: Schema Pydantic — `backend/app/schemas/ops.py`**

Adicionar ao final de `SystemMetricsRead`:

```python
    root_disk_total_gb: float
    root_disk_used_gb: float
    root_disk_free_gb: float
    root_disk_percent: float
```

- [ ] **Step 4: TypeScript — atualizar `SystemMetrics` em `frontend/src/types/index.ts`**

Encontrar a interface `SystemMetrics` e adicionar:

```typescript
  root_disk_total_gb: number;
  root_disk_used_gb: number;
  root_disk_free_gb: number;
  root_disk_percent: number;
```

- [ ] **Step 5: Frontend — `SystemResources.tsx` mostra card extra "Disco Sistema"**

Adicionar um 4º `ResourceCard` (grid passa a `grid-cols-2 sm:grid-cols-4`):

```tsx
<ResourceCard
  icon={HardDrive}
  title="Disco (sistema)"
  percent={data.root_disk_percent}
  primary={`${data.root_disk_used_gb.toFixed(1)} / ${data.root_disk_total_gb.toFixed(1)} GB`}
  secondary={`${data.root_disk_free_gb.toFixed(1)} GB livre`}
/>
```

E no campo "Disco" existente, renomear `title` para `"Armazenamento"`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/system_metrics_service.py backend/app/schemas/ops.py frontend/src/components/live/SystemResources.tsx frontend/src/types/index.ts
git commit -m "feat: expoe disco raiz (sistema) no painel de recursos"
```

---

### Task 3: Página dedicada de Métricas

**Files:**
- Create: `frontend/src/app/admin/metricas/page.tsx`
- Create: `frontend/src/components/metrics/OperationalDashboard.tsx`
- Modify: `frontend/src/components/live/LiveMonitor.tsx` (remover métricas, manter câmeras)
- Modify: `frontend/src/components/ui/Sidebar.tsx` (adicionar link Métricas)

**Interfaces:**
- `OperationalDashboard` recebe `metrics: OperationalMetrics | null` e `canReset: boolean` e `onReset: () => void`
- Reutiliza os mesmos dados de `/api/ops/metrics` e `/api/ops/system`
- `LiveMonitor` chama `OperationalDashboard` ou apenas usa os dados das câmeras

**Design:**
- A nova página `/admin/metricas` vai conter `<OperationalDashboard>` que inclui:
  - Seção "Recursos do servidor" (`<SystemResources />`)
  - Seção "Saúde operacional" (MetricCards existentes com status/fila/FPS/latência)
  - Seção "Pipeline OCR" (MetricCards OCR)
  - Seção "Resumo" (badges de status)
  - Botão "Resetar métricas" (só para admins)
- A página `/admin/live` fica apenas com a grade de câmeras + botões de reload/reconectar

- [ ] **Step 1: Criar `OperationalDashboard.tsx`**

Criar `frontend/src/components/metrics/OperationalDashboard.tsx` extraindo os blocos de métricas de `LiveMonitor.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { getMe } from "@/lib/auth";
import type { OperationalMetrics } from "@/types";
import { MetricCard } from "@/components/ui/MetricCard";
import { Badge } from "@/components/ui/Badge";
import { SystemResources } from "@/components/live/SystemResources";
import { Trash2 } from "lucide-react";

// (copiar as funções ocrVariant, ocrLabel, operationalVariant, operationalLabel de LiveMonitor)

export function OperationalDashboard() {
  const [metrics, setMetrics] = useState<OperationalMetrics | null>(null);
  const [canReset, setCanReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");

  const loadMetrics = useCallback(async () => {
    try {
      const res = await api.get<OperationalMetrics>("/api/ops/metrics");
      setMetrics(res.data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadMetrics();
    getMe()
      .then((me) => setCanReset(me.role === "super_admin" || me.role === "client_admin"))
      .catch(() => setCanReset(false));
    const id = window.setInterval(loadMetrics, 5000);
    return () => window.clearInterval(id);
  }, [loadMetrics]);

  const resetMetrics = useCallback(async () => {
    if (resetting) return;
    setResetting(true);
    setError("");
    try {
      await api.post("/api/ops/metrics/reset");
      await loadMetrics();
    } catch {
      setError("Erro ao resetar metricas.");
    } finally {
      setResetting(false);
    }
  }, [resetting, loadMetrics]);

  // (mover as seções de MetricCard e Badge que estão no LiveMonitor aqui)
  // ...
  return (
    <div>
      <SystemResources />
      {/* ... blocos de MetricCard movidos do LiveMonitor ... */}
      {canReset && (
        <button onClick={() => void resetMetrics()} disabled={resetting} /* ... */>
          <Trash2 className="h-4 w-4" />
          {resetting ? "Resetando..." : "Resetar métricas"}
        </button>
      )}
      {error && <div className="...">{error}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Criar `frontend/src/app/admin/metricas/page.tsx`**

```tsx
import { PageHeader } from "@/components/ui/PageHeader";
import { OperationalDashboard } from "@/components/metrics/OperationalDashboard";

export default function MetricasPage() {
  return (
    <div className="p-6">
      <PageHeader
        title="Métricas"
        description="Saúde operacional, pipeline OCR e recursos do servidor"
      />
      <OperationalDashboard />
    </div>
  );
}
```

- [ ] **Step 3: Simplificar `LiveMonitor.tsx` (remover bloco de métricas)**

Remover de `LiveMonitor.tsx`:
- Import de `MetricCard`, `SystemResources`, `getMe`
- States: `metrics`, `canReset`, `resetting`
- `syncCameras` — manter, mas simplificar: não buscar mais `/api/ops/metrics`
- Todos os `{metrics && ...}` blocos de MetricCard
- O badge de status operacional
- O botão "Resetar métricas"
- Substituir o bloco de busca de métricas com apenas câmeras

`syncCameras` no LiveMonitor simplificado:

```typescript
const syncCameras = useCallback(async (initial: boolean) => {
  if (initial) setLoading(true);
  setError("");
  try {
    const camRes = await api.get<Camera[]>("/api/cameras");
    setCameras(camRes.data);
  } catch {
    setError("Erro ao carregar cameras.");
  } finally {
    if (initial) setLoading(false);
  }
}, []);
```

- [ ] **Step 4: Adicionar "Métricas" no Sidebar**

Em `frontend/src/components/ui/Sidebar.tsx`, em `ADMIN_NAV`:

```typescript
import { LayoutDashboard, ..., Activity } from "lucide-react";

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/clients", label: "Clientes", icon: Building2 },
  { href: "/admin/plans", label: "Planos", icon: CreditCard },
  { href: "/admin/users", label: "Usuarios", icon: Users },
  { href: "/admin/cameras", label: "Cameras", icon: Camera },
  { href: "/admin/live", label: "Live", icon: Radio },
  { href: "/admin/metricas", label: "Metricas", icon: Activity },   // <-- novo
  { href: "/admin/search", label: "Placas", icon: Search },
  { href: "/admin/detections", label: "Deteccoes", icon: ScanSearch },
  { href: "/admin/ocr-config", label: "Motores OCR", icon: ScanLine },
];
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/admin/metricas/ frontend/src/components/metrics/ frontend/src/components/live/LiveMonitor.tsx frontend/src/components/ui/Sidebar.tsx
git commit -m "feat: pagina dedicada de metricas operacionais e OCR"
```

---

### Task 4: Alertas via WhatsApp (Meta Cloud API)

**Files:**
- Modify: `backend/app/models/alert_sent.py`
- Modify: `backend/app/models/monitored_plate.py`
- Modify: `backend/app/schemas/monitored_plate.py`
- Create: `backend/alembic/versions/012_monitored_plate_whatsapp.py`
- Create: `backend/app/services/whatsapp_service.py`
- Modify: `backend/app/services/alert_service.py`
- Modify: `backend/app/api/routes/plates.py`
- Modify: `backend/app/core/config.py`
- Modify: `frontend/src/app/client/alerts/page.tsx`
- Modify: `frontend/src/types/index.ts`
- Modify: `.env.prod.example` (add WHATSAPP_* vars)

**Interfaces:**
- `MonitoredPlate.alert_whatsapp: str | None` — número E.164 (ex: `+5511999998888`)
- `AlertChannel.whatsapp = "whatsapp"` — novo valor do enum
- `whatsapp_service.send_whatsapp_alert(to, plate, camera_name, location, detected_at, image_url) -> bool`
- `alert_service.process_alerts()` chama WhatsApp após email, se `alert_whatsapp` configurado

**WhatsApp Cloud API (Meta):**
- Endpoint: `POST https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages`
- Header: `Authorization: Bearer {WHATSAPP_TOKEN}`
- Body:
```json
{
  "messaging_product": "whatsapp",
  "to": "5511999998888",
  "type": "text",
  "text": { "body": "🚗 Placa ABC1234 detectada\nCâmera: Entrada Principal\nLocal: Portaria\nHorário: 15/06/2026 14:30" }
}
```

- [ ] **Step 1: Adicionar `whatsapp` ao `AlertChannel` enum**

Em `backend/app/models/alert_sent.py`:

```python
class AlertChannel(str, enum.Enum):
    email = "email"
    websocket = "websocket"
    whatsapp = "whatsapp"
```

- [ ] **Step 2: Adicionar coluna `alert_whatsapp` ao modelo `MonitoredPlate`**

Em `backend/app/models/monitored_plate.py`:

```python
alert_whatsapp = Column(String(30), nullable=True)
```

(Adicionar após `alert_email`, antes de `is_active`)

- [ ] **Step 3: Criar migration `012_monitored_plate_whatsapp.py`**

```python
"""add alert_whatsapp to monitored_plates

Revision ID: 012
Revises: 011
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitored_plates",
        sa.Column("alert_whatsapp", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitored_plates", "alert_whatsapp")
```

- [ ] **Step 4: Atualizar schemas Pydantic**

Em `backend/app/schemas/monitored_plate.py`, adicionar `alert_whatsapp: Optional[str] = None` a:
- `MonitoredPlateCreate`
- `MonitoredPlateUpdate`
- `MonitoredPlateRead`
- `MonitoredPlateBase`

- [ ] **Step 5: Adicionar settings para WhatsApp em `backend/app/core/config.py`**

```python
WHATSAPP_TOKEN: str = ""
WHATSAPP_PHONE_NUMBER_ID: str = ""
```

- [ ] **Step 6: Criar `backend/app/services/whatsapp_service.py`**

```python
"""Envio de alertas via WhatsApp Business Cloud API (Meta).

Requer WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID no .env.
Número do destinatário no formato E.164 sem '+' (ex: 5511999998888).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_API_VERSION = "v20.0"
_BASE_URL = "https://graph.facebook.com"


def _to_digits(number: str) -> str:
    """Remove '+', espaços e traços; mantém só dígitos."""
    return "".join(c for c in number if c.isdigit())


def send_whatsapp_alert(
    *,
    to: str,
    plate: str,
    camera_name: str,
    location: str,
    detected_at: str,
    image_url: str,
) -> bool:
    from app.core.config import settings

    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp não configurado (WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID ausentes)")
        return False

    try:
        import httpx

        recipient = _to_digits(to)
        body = (
            f"🚗 Placa {plate} detectada\n"
            f"📷 Câmera: {camera_name}\n"
            f"📍 Local: {location or 'não informado'}\n"
            f"🕐 Horário: {detected_at}"
        )
        if image_url:
            body += f"\n🔗 Imagem: {image_url}"

        url = f"{_BASE_URL}/{_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": body},
        }
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        return True
    except Exception:
        logger.warning("Falha ao enviar alerta WhatsApp", exc_info=True)
        return False
```

- [ ] **Step 7: Atualizar `alert_service.py` — chamar WhatsApp**

Em `process_alerts()`, após o bloco de email, adicionar:

```python
        if mp.alert_whatsapp:
            _send_whatsapp_alert(occ, camera, mp, image_url, db)
```

E adicionar função `_send_whatsapp_alert`:

```python
def _send_whatsapp_alert(occ, camera, mp, image_url: str, db: Session) -> None:
    from app.services.whatsapp_service import send_whatsapp_alert

    already = (
        db.query(AlertSent)
        .filter(
            AlertSent.occurrence_id == occ.id,
            AlertSent.monitored_plate_id == mp.id,
            AlertSent.channel == AlertChannel.whatsapp,
        )
        .first()
    )
    if already:
        return

    success = send_whatsapp_alert(
        to=mp.alert_whatsapp,
        plate=occ.plate,
        camera_name=camera.name,
        location=camera.location or "",
        detected_at=occ.detected_at.strftime("%d/%m/%Y %H:%M") if occ.detected_at else "",
        image_url=image_url,
    )

    db.add(
        AlertSent(
            occurrence_id=occ.id,
            monitored_plate_id=mp.id,
            channel=AlertChannel.whatsapp,
            status="sent" if success else "failed",
        )
    )
```

- [ ] **Step 8: Atualizar `plates.py` — aceitar `alert_whatsapp`**

Em `create_plate()`:

```python
    plate = MonitoredPlate(
        client_id=client_id,
        plate=payload.plate.upper().strip(),
        description=payload.description,
        alert_email=payload.alert_email,
        alert_whatsapp=payload.alert_whatsapp,
        is_active=payload.is_active,
    )
```

- [ ] **Step 9: TypeScript — atualizar `MonitoredPlate` em `frontend/src/types/index.ts`**

```typescript
export interface MonitoredPlate {
  id: string;
  client_id: string;
  plate: string;
  description: string | null;
  alert_email: string | null;
  alert_whatsapp: string | null;   // <-- novo
  is_active: boolean;
  created_at: string;
}
```

- [ ] **Step 10: Frontend — adicionar campo WhatsApp em `client/alerts/page.tsx`**

Em `PlateForm`, adicionar `alert_whatsapp: string`:

```typescript
interface PlateForm {
  plate: string;
  description: string;
  alert_email: string;
  alert_whatsapp: string;   // <-- novo
}

const EMPTY_FORM: PlateForm = { plate: "", description: "", alert_email: "", alert_whatsapp: "" };
```

Em `validate()`, adicionar validação básica do número:

```typescript
  if (form.alert_whatsapp && !/^\+?\d{10,15}$/.test(form.alert_whatsapp.replace(/[\s\-()]/g, ""))) {
    return "Número WhatsApp inválido. Use o formato +5511999998888.";
  }
```

Em `handleCreate()`, incluir `alert_whatsapp` no POST:

```typescript
      await api.post("/api/monitored-plates", {
        plate: form.plate.trim(),
        description: form.description.trim() || null,
        alert_email: form.alert_email.trim() || null,
        alert_whatsapp: form.alert_whatsapp.trim() || null,
      });
```

No Modal, adicionar campo após o campo de e-mail:

```tsx
          <div>
            <label className="block text-sm font-medium mb-1.5">WhatsApp para alertas</label>
            <input
              type="tel"
              value={form.alert_whatsapp}
              onChange={(e) => handleChange("alert_whatsapp", e.target.value)}
              placeholder="+5511999998888 (opcional)"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Requer WhatsApp Business API configurada pelo administrador
            </p>
          </div>
```

No card de exibição da placa, mostrar ícone WhatsApp quando configurado (importar `MessageCircle` do lucide):

```tsx
                {p.alert_whatsapp && (
                  <p className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                    <MessageCircle className="h-3 w-3 shrink-0" />
                    <span className="truncate">{p.alert_whatsapp}</span>
                  </p>
                )}
```

- [ ] **Step 11: Adicionar `httpx` ao `requirements.txt` (se ausente)**

```bash
grep -q "httpx" backend/requirements.txt || echo "httpx>=0.27" >> backend/requirements.txt
```

- [ ] **Step 12: Atualizar `.env.prod.example` com variáveis WhatsApp**

Adicionar:
```
WHATSAPP_TOKEN=seu_token_aqui
WHATSAPP_PHONE_NUMBER_ID=seu_phone_number_id_aqui
```

- [ ] **Step 13: Commit**

```bash
git add backend/app/models/ backend/alembic/versions/012_monitored_plate_whatsapp.py backend/app/services/whatsapp_service.py backend/app/services/alert_service.py backend/app/api/routes/plates.py backend/app/core/config.py backend/requirements.txt .env.prod.example frontend/src/app/client/alerts/page.tsx frontend/src/types/index.ts
git commit -m "feat: alertas WhatsApp via Meta Cloud API nas placas monitoradas"
```

---

### Task 5: Paginação avançada — seletor de página e tamanho

**Files:**
- Modify: `frontend/src/components/detections/DetectionHistory.tsx`
- Modify: `frontend/src/app/admin/search/page.tsx`
- Modify: `frontend/src/app/client/search/page.tsx`

**Interfaces:**
- Backends já aceitam `limit` até 100 (`le=100` no Query) — nenhuma mudança de backend necessária
- Frontend: adicionar `pageSize` state (padrão 50) e `goToPage` input

**Comportamento:**
- Seletor de itens por página: `[25, 50, 100]` — muda `limit` na requisição
- Input "Ir para página": campo numérico com `onKeyDown Enter` e botão "Ir"
- Mostrar botões de primeira e última página além dos existentes

- [ ] **Step 1: Atualizar `DetectionHistory.tsx` — paginação avançada**

Adicionar state e controles de paginação:

```typescript
  const [pageSize, setPageSize] = useState(50);
  const [goTo, setGoTo] = useState("");
```

Em `loadEvents`, mudar `limit: 24` para `limit: pageSize`.

Na paginação, substituir o bloco atual por:

```tsx
          {result.pages > 1 && (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              {/* Primeira */}
              <button
                onClick={() => void loadEvents(1)}
                disabled={page <= 1 || loadingPage}
                className="inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
                title="Primeira página"
              >
                «
              </button>
              <button
                onClick={() => void loadEvents(page - 1)}
                disabled={page <= 1 || loadingPage}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                Anterior
              </button>
              <span className="rounded-lg border bg-white px-3 py-2 text-sm text-muted-foreground">
                Página {page} de {result.pages}
              </span>
              <button
                onClick={() => void loadEvents(page + 1)}
                disabled={page >= result.pages || loadingPage}
                className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
              >
                Próxima
                <ChevronRight className="h-4 w-4" />
              </button>
              {/* Última */}
              <button
                onClick={() => void loadEvents(result.pages)}
                disabled={page >= result.pages || loadingPage}
                className="inline-flex items-center gap-1 rounded-lg border px-3 py-2 text-sm disabled:opacity-40"
                title="Última página"
              >
                »
              </button>
              {/* Ir para página */}
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min={1}
                  max={result.pages}
                  value={goTo}
                  onChange={(e) => setGoTo(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const p = Math.min(result.pages, Math.max(1, Number(goTo)));
                      if (p) void loadEvents(p);
                    }
                  }}
                  placeholder="Ir para…"
                  className="w-24 rounded-lg border px-2 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
                <button
                  onClick={() => {
                    const p = Math.min(result.pages, Math.max(1, Number(goTo)));
                    if (p) void loadEvents(p);
                  }}
                  disabled={!goTo || loadingPage}
                  className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-40"
                >
                  Ir
                </button>
              </div>
              {/* Itens por página */}
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="rounded-lg border px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                {[25, 50, 100].map((s) => (
                  <option key={s} value={s}>{s} por página</option>
                ))}
              </select>
            </div>
          )}
```

Adicionar `useEffect` para recarregar quando `pageSize` muda:

```typescript
  useEffect(() => {
    void loadEvents(1);
  }, [pageSize, loadEvents]);
```

- [ ] **Step 2: Aplicar mesmas mudanças em `admin/search/page.tsx`**

Adicionar `pageSize` state (padrão 50), mudar `limit: 20` para `limit: pageSize`, e adicionar os botões «/» + input "Ir para" + seletor de tamanho.

Manter o estilo de botões de página existente (±2 páginas) mas adicionar « e » e o input "Ir para".

- [ ] **Step 3: Verificar `client/search/page.tsx` e `client/detections/page.tsx`**

`client/search/page.tsx` usa o mesmo componente de `admin/search/page.tsx`? Não — é uma página separada. Aplicar as mesmas mudanças.

`client/detections/page.tsx` usa `<DetectionHistory>` — já coberto pelo Step 1.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/detections/DetectionHistory.tsx frontend/src/app/admin/search/page.tsx frontend/src/app/client/search/page.tsx
git commit -m "feat: paginacao avancada com seletor de tamanho e ir-para-pagina"
```

---

## Deploy Final

Após todas as 5 tarefas concluídas:

- [ ] **Push**
```bash
git push origin main
```

- [ ] **Sync arquivos na VPS via pscp**

```bash
# Sincronizar todos os arquivos alterados
pscp -batch -pw 12345678 -hostkey "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38" -r backend root@192.168.0.115:/root/monitoramento/
pscp -batch -pw 12345678 -hostkey "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38" -r frontend root@192.168.0.115:/root/monitoramento/
pscp -batch -pw 12345678 -hostkey "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38" docker-compose.prod.yml root@192.168.0.115:/root/monitoramento/
```

- [ ] **Rebuild e restart na VPS**

```bash
plink -batch -pw 12345678 -hostkey "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38" root@192.168.0.115 "cd /root/monitoramento && docker compose -f docker-compose.prod.yml up -d --build && docker compose -f docker-compose.prod.yml ps"
```

- [ ] **Verificar logs (migrações 011 e 012)**

```bash
plink -batch -pw 12345678 -hostkey "SHA256:AcKGZMXhBZ0+sV8wW371/wJHmES3JC58Ka8A1aPGC38" root@192.168.0.115 "cd /root/monitoramento && docker compose -f docker-compose.prod.yml logs backend --tail=50"
```
