"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import type {
  FaceEngineConfig,
  FaceEngineTestResult,
  FaceCameraAlertConfig,
  FaceImageTestResult,
} from "@/types";
import {
  ScanFace,
  CheckCircle2,
  XCircle,
  Plus,
  ImageIcon,
  Upload,
  Bell,
  Camera,
  ChevronDown,
  ChevronUp,
  Save,
  Pencil,
  Trash2,
} from "lucide-react";

type EngineType = "opencv" | "rekognition" | "luxand" | "facepp";

const ENGINES: { value: EngineType; label: string; desc: string }[] = [
  { value: "opencv", label: "OpenCV (local)", desc: "Motor local YuNet+SFace, sem credenciais." },
  { value: "rekognition", label: "AWS Rekognition", desc: "Access key, secret e região." },
  { value: "luxand", label: "Luxand", desc: "Token de API." },
  { value: "facepp", label: "Face++", desc: "API key e secret." },
];

const DAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

interface EngineForm {
  api_token: string;
  api_secret: string;
  api_url: string;
  region: string;
  threshold: string;
}

interface CameraBasic {
  id: string;
  name: string;
  location: string | null;
}

interface AlertForm {
  unknown_face_active: boolean;
  unknown_face_email: string;
  unknown_face_whatsapp: string;
  schedule_start_time: string;
  schedule_duration_minutes: string;
  schedule_days_of_week: number[];
  cooldown_minutes: string;
}

const EMPTY_FORM: EngineForm = { api_token: "", api_secret: "", api_url: "", region: "", threshold: "0.80" };
const EMPTY_ALERT: AlertForm = {
  unknown_face_active: false,
  unknown_face_email: "",
  unknown_face_whatsapp: "",
  schedule_start_time: "",
  schedule_duration_minutes: "",
  schedule_days_of_week: [0, 1, 2, 3, 4, 5, 6],
  cooldown_minutes: "0",
};

// ── Sub-componente: config de alertas por câmera ─────────────────────────────
function CameraAlertRow({ cam }: { cam: CameraBasic }) {
  const [config, setConfig] = useState<FaceCameraAlertConfig | null>(null);
  const [form, setForm] = useState<AlertForm>(EMPTY_ALERT);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    api
      .get<FaceCameraAlertConfig>(`/api/face-alert-config/${cam.id}`)
      .then((r) => {
        const c = r.data;
        setConfig(c);
        let days = [0, 1, 2, 3, 4, 5, 6];
        try { if (c.schedule_days_of_week) days = JSON.parse(c.schedule_days_of_week); } catch {}
        setForm({
          unknown_face_active: c.unknown_face_active,
          unknown_face_email: c.unknown_face_email ?? "",
          unknown_face_whatsapp: c.unknown_face_whatsapp ?? "",
          schedule_start_time: c.schedule_start_time ?? "",
          schedule_duration_minutes: c.schedule_duration_minutes?.toString() ?? "",
          schedule_days_of_week: days,
          cooldown_minutes: c.cooldown_minutes?.toString() ?? "0",
        });
      })
      .catch(() => {
        setConfig(null);
        setForm(EMPTY_ALERT);
      });
  }, [open, cam.id]);

  function toggleDay(d: number) {
    setForm((f) => ({
      ...f,
      schedule_days_of_week: f.schedule_days_of_week.includes(d)
        ? f.schedule_days_of_week.filter((x) => x !== d)
        : [...f.schedule_days_of_week, d].sort(),
    }));
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      const payload = {
        unknown_face_active: form.unknown_face_active,
        unknown_face_email: form.unknown_face_email.trim() || null,
        unknown_face_whatsapp: form.unknown_face_whatsapp.trim() || null,
        schedule_start_time: form.schedule_start_time.trim() || null,
        schedule_duration_minutes: form.schedule_duration_minutes ? Number(form.schedule_duration_minutes) : null,
        schedule_days_of_week: JSON.stringify(form.schedule_days_of_week),
        cooldown_minutes: Number(form.cooldown_minutes) || 0,
      };
      const r = await api.put<FaceCameraAlertConfig>(`/api/face-alert-config/${cam.id}`, payload);
      setConfig(r.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setErr(extractErrorMessage(e, "Erro ao salvar."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border rounded-xl bg-white overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition text-left"
      >
        <div className="flex items-center gap-3">
          <Camera className="h-4 w-4 text-muted-foreground" />
          <div>
            <span className="font-medium text-sm">{cam.name}</span>
            {cam.location && <span className="text-xs text-muted-foreground ml-2">{cam.location}</span>}
          </div>
          {config && (config.unknown_face_active || config.cooldown_minutes > 0 || config.schedule_start_time) && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">configurado</span>
          )}
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t pt-4">
          {/* Alerta de face desconhecida */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold flex items-center gap-2">
              <Bell className="h-4 w-4" /> Alerta de face desconhecida
            </h4>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.unknown_face_active}
                onChange={(e) => setForm((f) => ({ ...f, unknown_face_active: e.target.checked }))}
                className="h-4 w-4 rounded"
              />
              <span className="text-sm">Ativar alertas para faces não cadastradas</span>
            </label>
            {form.unknown_face_active && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pl-6">
                <div>
                  <label className="block text-xs font-medium mb-1">E-mail de alerta</label>
                  <input
                    type="email"
                    value={form.unknown_face_email}
                    onChange={(e) => setForm((f) => ({ ...f, unknown_face_email: e.target.value }))}
                    placeholder="alerta@empresa.com"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1">WhatsApp de alerta</label>
                  <input
                    type="tel"
                    value={form.unknown_face_whatsapp}
                    onChange={(e) => setForm((f) => ({ ...f, unknown_face_whatsapp: e.target.value }))}
                    placeholder="+5511999999999"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Janela de horário */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Janela de horário (aplica a faces cadastradas e desconhecidas)</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1">Horário de início</label>
                <input
                  type="time"
                  value={form.schedule_start_time}
                  onChange={(e) => setForm((f) => ({ ...f, schedule_start_time: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Duração (minutos após início)</label>
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={form.schedule_duration_minutes}
                  onChange={(e) => setForm((f) => ({ ...f, schedule_duration_minutes: e.target.value }))}
                  placeholder="ex: 480 (8h)"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-2">Dias da semana ativos</label>
              <div className="flex gap-2 flex-wrap">
                {DAYS.map((label, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => toggleDay(idx)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                      form.schedule_days_of_week.includes(idx)
                        ? "bg-primary text-primary-foreground"
                        : "border bg-white text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Deixe horário e duração em branco para alertar 24h/dia.
            </p>
          </div>

          {/* Cooldown */}
          <div>
            <label className="block text-sm font-semibold mb-1">
              Cooldown entre alertas (minutos) — por câmera
            </label>
            <input
              type="number"
              min={0}
              max={10080}
              value={form.cooldown_minutes}
              onChange={(e) => setForm((f) => ({ ...f, cooldown_minutes: e.target.value }))}
              className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Após disparar um alerta para esta câmera, aguarda X minutos antes do próximo (0 = sem cooldown).
            </p>
          </div>

          {err && <p className="text-sm text-red-600">{err}</p>}

          <div className="flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {saving ? "Salvando…" : "Salvar"}
            </button>
            {saved && (
              <span className="flex items-center gap-1 text-sm text-green-700">
                <CheckCircle2 className="h-4 w-4" /> Salvo!
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Componente principal ─────────────────────────────────────────────────────
export function FaceConfigManager() {
  const [configs, setConfigs] = useState<FaceEngineConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<EngineType>("rekognition");
  const [form, setForm] = useState<EngineForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, FaceEngineTestResult>>({});
  const [editing, setEditing] = useState<FaceEngineConfig | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<FaceEngineConfig | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Câmeras (para alertas por câmera)
  const [cameras, setCameras] = useState<CameraBasic[]>([]);

  // Teste com imagem
  const [imageTestResult, setImageTestResult] = useState<FaceImageTestResult | null>(null);
  const [imageTesting, setImageTesting] = useState(false);
  const [imageTestError, setImageTestError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [cfgRes, camRes] = await Promise.all([
        api.get<FaceEngineConfig[]>("/api/face-config"),
        api.get<CameraBasic[]>("/api/cameras"),
      ]);
      setConfigs(cfgRes.data);
      setCameras(camRes.data.filter((c: CameraBasic & { enable_face?: boolean }) => true));
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Não foi possível carregar configurações."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function existing(engine: EngineType): FaceEngineConfig | undefined {
    return configs.find((c) => c.engine_type === engine);
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, string | number | null> = {
        api_token: form.api_token.trim() || null,
        api_secret: form.api_secret.trim() || null,
        api_url: form.api_url.trim() || null,
        region: form.region.trim() || null,
        threshold: Number(form.threshold) || 0.8,
      };
      if (editing) {
        await api.patch(`/api/face-config/${editing.id}`, payload);
        setEditing(null);
      } else {
        const current = existing(selected);
        if (current) {
          await api.patch(`/api/face-config/${current.id}`, payload);
        } else {
          await api.post("/api/face-config", { engine_type: selected, ...payload });
        }
      }
      setForm(EMPTY_FORM);
      await load();
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Erro ao salvar configuração."));
    } finally {
      setSaving(false);
    }
  }

  function openEdit(c: FaceEngineConfig) {
    setEditing(c);
    setSelected(c.engine_type as EngineType);
    setForm({
      api_token: "",
      api_secret: "",
      api_url: c.api_url ?? "",
      region: c.region ?? "",
      threshold: String(c.threshold ?? 0.8),
    });
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  async function deleteEngine() {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await api.delete(`/api/face-config/${deleteConfirm.id}`);
      setDeleteConfirm(null);
      await load();
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Erro ao remover motor."));
      setDeleteConfirm(null);
    } finally {
      setDeleting(false);
    }
  }

  async function activate(c: FaceEngineConfig) {
    try {
      await api.post(`/api/face-config/${c.id}/activate`);
      await load();
    } catch { /* ignore */ }
  }

  async function runTest(c: FaceEngineConfig) {
    try {
      const res = await api.post<FaceEngineTestResult>(`/api/face-config/${c.id}/test`);
      setTestResult((prev) => ({ ...prev, [c.id]: res.data }));
    } catch (e: unknown) {
      setTestResult((prev) => ({
        ...prev,
        [c.id]: { success: false, engine_type: c.engine_type, message: extractErrorMessage(e, "Falha no teste.") },
      }));
    }
  }

  async function testWithImage(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageTesting(true);
    setImageTestError("");
    setImageTestResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await api.post<FaceImageTestResult>("/api/face-config/test-image", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImageTestResult(data);
    } catch {
      setImageTestError("Erro ao processar a imagem.");
    } finally {
      setImageTesting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Motores de Reconhecimento Facial" description="Configure e ative o motor de faces do sistema" />

      {error && <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">{error}</div>}

      {/* Motores configurados */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {configs.length === 0 ? (
            <div className="bg-white rounded-xl border shadow-sm p-8 text-center text-muted-foreground">
              <ScanFace className="h-12 w-12 mx-auto mb-3 opacity-15" />
              <p className="text-sm">Nenhum motor configurado. Adicione abaixo.</p>
            </div>
          ) : (
            configs.map((c) => (
              <div key={c.id} className="bg-white rounded-xl border shadow-sm p-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold capitalize">{c.engine_type}</span>
                      {c.is_active && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">ativo</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Threshold: {c.threshold}
                      {c.region ? ` · região: ${c.region}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => runTest(c)}
                      className="px-3 py-1.5 border rounded-lg text-sm hover:bg-gray-50 transition"
                    >
                      Testar
                    </button>
                    <button
                      onClick={() => openEdit(c)}
                      className="p-1.5 border rounded-lg hover:bg-gray-50 transition"
                      title="Editar"
                    >
                      <Pencil className="h-4 w-4 text-gray-500" />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(c)}
                      className="p-1.5 border rounded-lg hover:bg-red-50 transition"
                      title="Excluir"
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </button>
                    <button
                      onClick={() => activate(c)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        c.is_active
                          ? "border hover:bg-gray-50"
                          : "bg-primary text-primary-foreground hover:bg-primary/90"
                      }`}
                    >
                      {c.is_active ? "Desativar" : "Ativar"}
                    </button>
                  </div>
                </div>
                {testResult[c.id] && (
                  <div
                    className={`mt-3 flex items-center gap-2 text-sm ${
                      testResult[c.id].success ? "text-green-700" : "text-red-700"
                    }`}
                  >
                    {testResult[c.id].success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                    {testResult[c.id].message}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Testar com imagem */}
      <section className="bg-white rounded-xl border shadow-sm p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ImageIcon className="h-4 w-4 text-amber-500" /> Testar com imagem
        </div>
        <p className="text-xs text-muted-foreground">
          Envie uma foto para verificar se o motor detecta e reconhece o rosto (sem salvar no banco).
        </p>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={testWithImage}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={imageTesting}
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600 transition disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {imageTesting ? "Processando..." : "Enviar imagem"}
          </button>
        </div>
        {imageTestError && <p className="text-sm text-red-600">{imageTestError}</p>}
        {imageTestResult && (
          <div className="space-y-3">
            <p className="text-sm font-medium">{imageTestResult.message}</p>

            {/* Imagem anotada com bboxes */}
            {imageTestResult.annotated_image && (
              <div className="rounded-lg overflow-hidden border">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/jpeg;base64,${imageTestResult.annotated_image}`}
                  alt="Resultado da detecção"
                  className="w-full object-contain max-h-96"
                />
              </div>
            )}

            {/* Alertas disparados */}
            {imageTestResult.alerts_fired?.length > 0 && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
                <Bell className="h-4 w-4 shrink-0" />
                <span className="font-medium">Alertas disparados:</span>
                <span>{imageTestResult.alerts_fired.join(", ")}</span>
              </div>
            )}

            {imageTestResult.faces.map((f, i) => (
              <div key={i} className={`p-3 rounded-lg border text-sm ${f.match.person_id ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"}`}>
                <div className="flex items-center gap-2">
                  {f.match.person_id
                    ? <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    : <XCircle className="h-4 w-4 text-gray-400 shrink-0" />}
                  <span className="font-medium">
                    {f.match.person?.name ?? "Face desconhecida"}
                  </span>
                  {f.match.match_confidence !== null && (
                    <span className="text-xs text-muted-foreground">
                      {(f.match.match_confidence * 100).toFixed(0)}% confiança
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    bbox {f.bbox.w}×{f.bbox.h}px
                  </span>
                </div>
                {f.match.person?.alert_active && (
                  <p className="mt-1 text-xs text-amber-700 font-medium">⚠ Alerta ativo — notificações enviadas</p>
                )}
              </div>
            ))}
            {!imageTestResult.found && (
              <div className="p-3 rounded-lg bg-gray-50 border text-sm text-gray-600">
                Nenhum rosto detectado pelo YuNet. Tente uma foto com rosto visível e frontal.
              </div>
            )}
          </div>
        )}
      </section>

      {/* Modal de confirmação de exclusão */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full space-y-4">
            <h3 className="font-semibold text-base">Remover motor</h3>
            <p className="text-sm text-muted-foreground">
              Tem certeza que deseja remover o motor <strong className="capitalize">{deleteConfirm.engine_type}</strong>? Esta ação não pode ser desfeita.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 transition"
              >
                Cancelar
              </button>
              <button
                onClick={deleteEngine}
                disabled={deleting}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleting ? "Removendo…" : "Remover"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Adicionar / editar motor */}
      <section className="bg-white rounded-xl border shadow-sm p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium">
            {editing ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {editing ? `Editar motor: ${editing.engine_type}` : "Configurar motor"}
          </div>
          {editing && (
            <button
              onClick={() => { setEditing(null); setForm(EMPTY_FORM); }}
              className="text-xs text-muted-foreground hover:text-foreground transition"
            >
              Cancelar edição
            </button>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium mb-1.5">Motor</label>
          <select
            value={selected}
            disabled={!!editing}
            onChange={(e) => {
              setSelected(e.target.value as EngineType);
              setForm(EMPTY_FORM);
            }}
            className="w-full border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {ENGINES.map((eng) => (
              <option key={eng.value} value={eng.value}>
                {eng.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground mt-1">{ENGINES.find((e) => e.value === selected)?.desc}</p>
        </div>

        {selected !== "opencv" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1.5">
                {selected === "rekognition" ? "Access Key" : selected === "luxand" ? "Token" : "API Key"}
              </label>
              <input
                value={form.api_token}
                onChange={(e) => setForm((p) => ({ ...p, api_token: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            {(selected === "rekognition" || selected === "facepp") && (
              <div>
                <label className="block text-xs font-medium mb-1.5">Secret</label>
                <input
                  type="password"
                  value={form.api_secret}
                  onChange={(e) => setForm((p) => ({ ...p, api_secret: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
            )}
            {selected === "rekognition" && (
              <div>
                <label className="block text-xs font-medium mb-1.5">Região</label>
                <input
                  value={form.region}
                  onChange={(e) => setForm((p) => ({ ...p, region: e.target.value }))}
                  placeholder="us-east-1"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
            )}
            {(selected === "luxand" || selected === "facepp") && (
              <div>
                <label className="block text-xs font-medium mb-1.5">URL da API (opcional)</label>
                <input
                  value={form.api_url}
                  onChange={(e) => setForm((p) => ({ ...p, api_url: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
            )}
          </div>
        )}

        <div className="max-w-[200px]">
          <label className="block text-xs font-medium mb-1.5">Threshold (0–1)</label>
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={form.threshold}
            onChange={(e) => setForm((p) => ({ ...p, threshold: e.target.value }))}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition disabled:opacity-50"
        >
          {saving ? "Salvando…" : editing ? "Salvar alterações" : existing(selected) ? "Atualizar motor" : "Adicionar motor"}
        </button>
      </section>

      {/* Alertas de face por câmera */}
      {cameras.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            <h2 className="font-semibold text-base">Alertas de face por câmera</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Configure alertas para faces não cadastradas, janela de horário e cooldown separadamente para cada câmera.
          </p>
          <div className="space-y-2">
            {cameras.map((cam) => (
              <CameraAlertRow key={cam.id} cam={cam} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
