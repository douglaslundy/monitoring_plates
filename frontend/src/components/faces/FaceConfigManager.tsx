"use client";

import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import type { FaceEngineConfig, FaceEngineTestResult } from "@/types";
import { ScanFace, CheckCircle2, XCircle, Plus } from "lucide-react";

type EngineType = "opencv" | "rekognition" | "luxand" | "facepp";

const ENGINES: { value: EngineType; label: string; desc: string }[] = [
  { value: "opencv", label: "OpenCV (local)", desc: "Motor local YuNet+SFace, sem credenciais." },
  { value: "rekognition", label: "AWS Rekognition", desc: "Access key, secret e região." },
  { value: "luxand", label: "Luxand", desc: "Token de API." },
  { value: "facepp", label: "Face++", desc: "API key e secret." },
];

interface EngineForm {
  api_token: string;
  api_secret: string;
  api_url: string;
  region: string;
  threshold: string;
}

const EMPTY: EngineForm = { api_token: "", api_secret: "", api_url: "", region: "", threshold: "0.80" };

export function FaceConfigManager() {
  const [configs, setConfigs] = useState<FaceEngineConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<EngineType>("rekognition");
  const [form, setForm] = useState<EngineForm>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, FaceEngineTestResult>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<FaceEngineConfig[]>("/api/face-config");
      setConfigs(res.data);
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Não foi possível carregar os motores de face."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function existing(engine: EngineType): FaceEngineConfig | undefined {
    return configs.find((c) => c.engine_type === engine);
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const current = existing(selected);
      const payload: Record<string, string | number | null> = {
        api_token: form.api_token.trim() || null,
        api_secret: form.api_secret.trim() || null,
        api_url: form.api_url.trim() || null,
        region: form.region.trim() || null,
        threshold: Number(form.threshold) || 0.8,
      };
      if (current) {
        await api.patch(`/api/face-config/${current.id}`, payload);
      } else {
        await api.post("/api/face-config", { engine_type: selected, ...payload });
      }
      setForm(EMPTY);
      await load();
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Erro ao salvar configuração."));
    } finally {
      setSaving(false);
    }
  }

  async function activate(c: FaceEngineConfig) {
    try {
      await api.post(`/api/face-config/${c.id}/activate`);
      await load();
    } catch {
      /* ignore */
    }
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

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Motores de Reconhecimento Facial" description="Configure e ative o motor de faces do sistema" />

      {error && <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">{error}</div>}

      {/* Configurados */}
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

      {/* Adicionar / editar */}
      <section className="bg-white rounded-xl border shadow-sm p-4 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Plus className="h-4 w-4" /> Configurar motor
        </div>

        <div>
          <label className="block text-xs font-medium mb-1.5">Motor</label>
          <select
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value as EngineType);
              setForm(EMPTY);
            }}
            className="w-full border rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/50"
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
          {saving ? "Salvando…" : existing(selected) ? "Atualizar motor" : "Adicionar motor"}
        </button>
      </section>
    </div>
  );
}
