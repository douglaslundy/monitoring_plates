"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import {
  ScanLine,
  Plus,
  Pencil,
  Trash2,
  PlayCircle,
  CheckCircle2,
  XCircle,
  FlaskConical,
  Power,
  Cpu,
} from "lucide-react";

type EngineType = "easyocr" | "plate_recognizer";
type EngineMode = "cloud" | "onpremise";

interface OcrEngineConfig {
  id: string;
  engine_type: EngineType;
  mode: EngineMode;
  is_active: boolean;
  api_token: string | null;
  api_url: string | null;
  license_key: string | null;
  regions: string[] | null;
  enable_mmc: boolean;
  created_at: string;
  updated_at: string;
}

interface TestResult {
  success: boolean;
  message: string;
  sample_response?: Record<string, unknown>;
}

const BR_STATES = [
  "br", "br-sp", "br-rj", "br-mg", "br-ba", "br-rs", "br-pr", "br-pe",
  "br-ce", "br-pa", "br-sc", "br-go", "br-pb", "br-ma", "br-es", "br-pi",
  "br-rn", "br-al", "br-mt", "br-df", "br-to", "br-ac", "br-am", "br-ap",
  "br-ro", "br-rr", "br-se", "br-ms",
];

const ENGINE_LABELS: Record<EngineType, string> = {
  easyocr: "EasyOCR",
  plate_recognizer: "Plate Recognizer",
};

const DEFAULT_PR_URL = "https://api.platerecognizer.com/v1/plate-reader/";

function emptyForm() {
  return {
    engine_type: "plate_recognizer" as EngineType,
    mode: "cloud" as EngineMode,
    api_token: "",
    api_url: DEFAULT_PR_URL,
    license_key: "",
    regions: ["br"] as string[],
    enable_mmc: false,
  };
}

export default function OcrConfigPage() {
  const [configs, setConfigs] = useState<OcrEngineConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<OcrEngineConfig | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [testing, setTesting] = useState<string | null>(null);
  // Modelo de detecção (YOLO) — Tarefa A.
  const [detModel, setDetModel] = useState<{ current: string; default: string; available: string[] } | null>(null);
  const [savingModel, setSavingModel] = useState(false);

  const load = () => {
    setLoading(true);
    api
      .get<OcrEngineConfig[]>("/api/ocr-config")
      .then((r) => setConfigs(r.data))
      .catch(() => setError("Erro ao carregar configurações"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    api
      .get<{ current: string; default: string; available: string[] }>("/api/detector/model")
      .then((r) => setDetModel(r.data))
      .catch(() => setDetModel(null));
  }, []);

  async function changeDetectorModel(model: string) {
    setSavingModel(true);
    setError("");
    try {
      const r = await api.put<{ current: string; default: string; available: string[] }>(
        "/api/detector/model",
        { model }
      );
      setDetModel(r.data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Erro ao alterar o modelo de detecção");
    } finally {
      setSavingModel(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setForm(emptyForm());
    setShowModal(true);
  }

  function openEdit(cfg: OcrEngineConfig) {
    setEditing(cfg);
    setForm({
      engine_type: cfg.engine_type,
      mode: cfg.mode,
      api_token: "",
      api_url: cfg.api_url || DEFAULT_PR_URL,
      license_key: "",
      regions: cfg.regions || ["br"],
      enable_mmc: cfg.enable_mmc,
    });
    setShowModal(true);
  }

  async function save() {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        mode: form.mode,
        regions: form.regions,
        enable_mmc: form.enable_mmc,
      };
      if (form.api_token) payload.api_token = form.api_token;
      if (form.api_url) payload.api_url = form.api_url;
      if (form.license_key) payload.license_key = form.license_key;

      if (editing) {
        await api.patch(`/api/ocr-config/${editing.id}`, payload);
      } else {
        await api.post("/api/ocr-config", { ...payload, engine_type: form.engine_type });
      }
      setShowModal(false);
      load();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Erro ao salvar configuração");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(cfg: OcrEngineConfig) {
    await api.post(`/api/ocr-config/${cfg.id}/activate`);
    load();
  }

  async function remove(cfg: OcrEngineConfig) {
    if (!confirm(`Remover configuração de ${ENGINE_LABELS[cfg.engine_type]}?`)) return;
    await api.delete(`/api/ocr-config/${cfg.id}`);
    load();
  }

  async function testConnection(cfg: OcrEngineConfig) {
    setTesting(cfg.id);
    try {
      const { data } = await api.post<TestResult>(`/api/ocr-config/${cfg.id}/test`);
      setTestResults((prev) => ({ ...prev, [cfg.id]: data }));
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [cfg.id]: { success: false, message: "Erro ao testar conexão" },
      }));
    } finally {
      setTesting(null);
    }
  }

  function toggleRegion(region: string) {
    setForm((f) => ({
      ...f,
      regions: f.regions.includes(region)
        ? f.regions.filter((r) => r !== region)
        : [...f.regions, region],
    }));
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <PageHeader
        title="Motores OCR"
        description="Configure e gerencie os motores de reconhecimento de placas"
        action={{ label: "Adicionar motor", icon: Plus, onClick: openCreate }}
      />

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Modelo de detecção de objetos (YOLO) — Tarefa A */}
      {detModel && (
        <div className="mb-6 bg-white border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
              <Cpu className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold">Modelo de detecção (YOLO)</h3>
              <p className="text-sm text-muted-foreground">
                Modelo usado para detectar veículos, pessoas e animais. Modelos maiores
                (x {">"} l {">"} m {">"} s {">"} n) acertam mais a classe, porém são mais lentos na CPU.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <select
              value={detModel.current}
              disabled={savingModel || detModel.available.length === 0}
              onChange={(e) => changeDetectorModel(e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
            >
              {[...detModel.available]
                .sort((a, b) => {
                  const ORDER = ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"];
                  return ORDER.indexOf(a) - ORDER.indexOf(b);
                })
                .map((m) => (
                <option key={m} value={m}>
                  {m}
                  {m === detModel.default ? " (padrão)" : ""}
                </option>
              ))}
            </select>
            {savingModel && <span className="text-sm text-muted-foreground">Aplicando…</span>}
            <Badge variant="info">Atual: {detModel.current}</Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            A troca vale para novas detecções (os workers recarregam o modelo em alguns segundos).
          </p>
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="bg-white border rounded-xl p-6 animate-pulse h-32" />
          ))}
        </div>
      ) : configs.length === 0 ? (
        <div className="bg-white border rounded-xl p-12 text-center text-muted-foreground">
          <ScanLine className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>Nenhum motor configurado</p>
        </div>
      ) : (
        <div className="space-y-4">
          {configs.map((cfg) => {
            const testResult = testResults[cfg.id];
            return (
              <div key={cfg.id} className="bg-white border rounded-xl p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className={`h-10 w-10 rounded-full flex items-center justify-center ${cfg.is_active ? "bg-green-100" : "bg-gray-100"}`}>
                      <ScanLine className={`h-5 w-5 ${cfg.is_active ? "text-green-600" : "text-gray-400"}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{ENGINE_LABELS[cfg.engine_type]}</h3>
                        <Badge variant={cfg.is_active ? "success" : "default"}>
                          {cfg.is_active ? "Ativo" : "Inativo"}
                        </Badge>
                        {cfg.engine_type === "plate_recognizer" && (
                          <Badge variant="info">{cfg.mode === "cloud" ? "Cloud" : "On-premise"}</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {cfg.engine_type === "easyocr"
                          ? "Motor local, sem custos externos"
                          : cfg.api_token
                          ? "Credenciais configuradas"
                          : "Credenciais não configuradas"}
                        {cfg.regions && cfg.regions.length > 0 && ` · Regiões: ${cfg.regions.join(", ")}`}
                        {cfg.enable_mmc && " · MMC ativo"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {cfg.engine_type === "plate_recognizer" && (
                      <button
                        onClick={() => testConnection(cfg)}
                        disabled={testing === cfg.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                      >
                        <FlaskConical className="h-3.5 w-3.5" />
                        {testing === cfg.id ? "Testando..." : "Testar"}
                      </button>
                    )}
                    <button
                      onClick={() => toggleActive(cfg)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Power className="h-3.5 w-3.5" />
                      {cfg.is_active ? "Desativar" : "Ativar"}
                    </button>
                    <button
                      onClick={() => openEdit(cfg)}
                      className="p-1.5 border rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    {cfg.engine_type !== "easyocr" && (
                      <button
                        onClick={() => remove(cfg)}
                        className="p-1.5 border rounded-lg hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {testResult && (
                  <div className={`mt-4 p-3 rounded-lg flex items-start gap-2 text-sm ${testResult.success ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                    {testResult.success
                      ? <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                      : <XCircle className="h-4 w-4 shrink-0 mt-0.5" />}
                    {testResult.message}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <Modal
        open={showModal}
        onOpenChange={setShowModal}
        title={editing ? `Editar ${ENGINE_LABELS[editing.engine_type]}` : "Adicionar motor OCR"}
      >
        <div className="space-y-4">
          {!editing && (
            <div>
              <label className="block text-sm font-medium mb-1">Motor</label>
              <select
                value={form.engine_type}
                onChange={(e) => setForm((f) => ({ ...f, engine_type: e.target.value as EngineType }))}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="plate_recognizer">Plate Recognizer</option>
                <option value="easyocr">EasyOCR</option>
              </select>
            </div>
          )}

          {(form.engine_type === "plate_recognizer") && (
            <>
              <div>
                <label className="block text-sm font-medium mb-1">Modo</label>
                <select
                  value={form.mode}
                  onChange={(e) => {
                    const mode = e.target.value as EngineMode;
                    setForm((f) => ({
                      ...f,
                      mode,
                      api_url: mode === "cloud" ? DEFAULT_PR_URL : "http://localhost:8080/v1/plate-reader/",
                    }));
                  }}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <option value="cloud">Cloud (API externa)</option>
                  <option value="onpremise">On-premise (Docker local)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  API Token {editing && <span className="text-muted-foreground font-normal">(deixe vazio para manter)</span>}
                </label>
                <input
                  type="password"
                  value={form.api_token}
                  onChange={(e) => setForm((f) => ({ ...f, api_token: e.target.value }))}
                  placeholder={editing ? "••••••••••••" : "Cole seu token aqui"}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">URL da API</label>
                <input
                  type="text"
                  value={form.api_url}
                  onChange={(e) => setForm((f) => ({ ...f, api_url: e.target.value }))}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>

              {form.mode === "onpremise" && (
                <div>
                  <label className="block text-sm font-medium mb-1">
                    License Key {editing && <span className="text-muted-foreground font-normal">(deixe vazio para manter)</span>}
                  </label>
                  <input
                    type="password"
                    value={form.license_key}
                    onChange={(e) => setForm((f) => ({ ...f, license_key: e.target.value }))}
                    placeholder={editing ? "••••••••••••" : "Chave de licença SDK"}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium mb-2">Regiões Brasil</label>
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 border rounded-lg">
                  {BR_STATES.map((state) => (
                    <button
                      key={state}
                      type="button"
                      onClick={() => toggleRegion(state)}
                      className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                        form.regions.includes(state)
                          ? "bg-primary text-primary-foreground"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {state}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="enable_mmc"
                  checked={form.enable_mmc}
                  onChange={(e) => setForm((f) => ({ ...f, enable_mmc: e.target.checked }))}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="enable_mmc" className="text-sm">
                  Habilitar MMC (make/model/cor do veículo)
                  <span className="text-muted-foreground ml-1">+50% no custo por consulta</span>
                </label>
              </div>
            </>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => setShowModal(false)}
              className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
