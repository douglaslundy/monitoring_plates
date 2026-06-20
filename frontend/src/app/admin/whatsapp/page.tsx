"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/Toast";
import type { WhatsAppSettings, WhatsAppTestSendResult, WhatsAppInstanceStatus } from "@/types";
import { CheckCircle2, MessageCircle, Power, Radio, RefreshCw, Send, Shield, TriangleAlert, Wifi, WifiOff } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface WhatsAppSettingsForm {
  is_active: boolean;
  evolution_base_url: string;
  evolution_instance_name: string;
  evolution_api_key: string;
  request_timeout_seconds: string;
}

interface WhatsAppTestForm {
  recipient: string;
  message: string;
}

const DEFAULT_FORM: WhatsAppSettingsForm = {
  is_active: true,
  evolution_base_url: "http://192.168.0.115:8081",
  evolution_instance_name: "whatsapp",
  evolution_api_key: "",
  request_timeout_seconds: "20",
};

const DEFAULT_TEST_FORM: WhatsAppTestForm = {
  recipient: "+5511999998888",
  message: "Teste de envio do painel administrativo",
};

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function validateSettings(form: WhatsAppSettingsForm, apiKeyConfigured: boolean): string | null {
  if (!form.evolution_base_url.trim()) return "A base URL da Evolution é obrigatória.";
  try {
    new URL(normalizeBaseUrl(form.evolution_base_url));
  } catch {
    return "A base URL da Evolution é inválida.";
  }
  if (!form.evolution_instance_name.trim()) return "O nome da instância é obrigatório.";
  const timeout = Number(form.request_timeout_seconds);
  if (!Number.isInteger(timeout) || timeout < 1) return "O timeout precisa ser um número inteiro maior que zero.";
  if (!apiKeyConfigured && !form.evolution_api_key.trim()) {
    return "Informe a API key da Evolution para ativar o canal.";
  }
  return null;
}

function validateRecipient(recipient: string): string | null {
  const digits = recipient.replace(/\D/g, "");
  if (!digits) return "Informe um número para envio do teste.";
  if (digits.length < 10 || digits.length > 15) return "Use um número com 10 a 15 dígitos.";
  return null;
}

function SectionCard({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <section className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

export default function AdminWhatsAppPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [settings, setSettings] = useState<WhatsAppSettings | null>(null);
  const [form, setForm] = useState<WhatsAppSettingsForm>(DEFAULT_FORM);
  const [testForm, setTestForm] = useState<WhatsAppTestForm>(DEFAULT_TEST_FORM);
  const [formError, setFormError] = useState("");
  const [testError, setTestError] = useState("");
  const [lastTestResult, setLastTestResult] = useState<WhatsAppTestSendResult | null>(null);

  const [instanceStatus, setInstanceStatus] = useState<WhatsAppInstanceStatus | null>(null);
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [instanceAction, setInstanceAction] = useState<"connect" | "disconnect" | "restart" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get<WhatsAppSettings>("/api/whatsapp-settings");
      setSettings(data);
      setForm({
        is_active: data.is_active,
        evolution_base_url: data.evolution_base_url,
        evolution_instance_name: data.evolution_instance_name,
        evolution_api_key: "",
        request_timeout_seconds: String(data.request_timeout_seconds),
      });
      setTestForm((prev) => ({
        ...prev,
        recipient: data.test_recipient?.trim() || DEFAULT_TEST_FORM.recipient,
      }));
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Erro ao carregar as configurações de WhatsApp."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const fetchInstanceStatus = useCallback(async () => {
    try {
      const { data } = await api.get<WhatsAppInstanceStatus>("/api/whatsapp-settings/instance/status");
      setInstanceStatus(data);
    } catch {
      setInstanceStatus({ state: "unknown", qr_code: null });
    }
  }, []);

  useEffect(() => {
    fetchInstanceStatus();
  }, [fetchInstanceStatus]);

  // Poll every 3s while connecting (waiting for QR scan)
  useEffect(() => {
    if (instanceStatus?.state !== "connecting") return;
    const id = setInterval(fetchInstanceStatus, 3000);
    return () => clearInterval(id);
  }, [instanceStatus?.state, fetchInstanceStatus]);

  async function handleInstanceAction(action: "connect" | "disconnect" | "restart") {
    setInstanceAction(action);
    setInstanceLoading(true);
    try {
      const { data } = await api.post<WhatsAppInstanceStatus>(`/api/whatsapp-settings/instance/${action}`);
      setInstanceStatus(data);
      if (action === "restart") {
        toast("Instância reiniciada");
        setTimeout(fetchInstanceStatus, 3000);
      }
    } catch {
      toast(`Falha ao ${action === "connect" ? "conectar" : action === "disconnect" ? "desconectar" : "reiniciar"} instância`, "error");
    } finally {
      setInstanceLoading(false);
      setInstanceAction(null);
    }
  }

  const settingsError = useMemo(() => validateSettings(form, settings?.api_key_configured ?? false), [form, settings?.api_key_configured]);
  const recipientError = useMemo(() => validateRecipient(testForm.recipient), [testForm.recipient]);

  function updateForm<K extends keyof WhatsAppSettingsForm>(field: K, value: WhatsAppSettingsForm[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (formError) setFormError("");
  }

  function updateTestForm<K extends keyof WhatsAppTestForm>(field: K, value: WhatsAppTestForm[K]) {
    setTestForm((prev) => ({ ...prev, [field]: value }));
    if (testError) setTestError("");
  }

  async function persistTestRecipient(recipient: string) {
    const normalized = recipient.trim();
    if (!normalized) {
      return;
    }

    const validation = validateRecipient(normalized);
    if (validation) {
      return;
    }

    try {
      const { data } = await api.put<WhatsAppSettings>("/api/whatsapp-settings", {
        test_recipient: normalized,
      });
      setSettings(data);
    } catch (e: unknown) {
      const message = extractErrorMessage(e, "Não foi possível salvar o número de teste.");
      setTestError(message);
      toast(message, "error");
    }
  }

  async function handleSave() {
    const validation = validateSettings(form, settings?.api_key_configured ?? false);
    if (validation) {
      setFormError(validation);
      return;
    }

    setSaving(true);
    setFormError("");
    try {
      const payload: Record<string, unknown> = {
        is_active: form.is_active,
        evolution_base_url: normalizeBaseUrl(form.evolution_base_url),
        evolution_instance_name: form.evolution_instance_name.trim(),
        request_timeout_seconds: Number(form.request_timeout_seconds),
      };
      if (form.evolution_api_key.trim()) {
        payload.evolution_api_key = form.evolution_api_key.trim();
      }

      const { data } = await api.put<WhatsAppSettings>("/api/whatsapp-settings", payload);
      setSettings(data);
      setForm((prev) => ({
        ...prev,
        evolution_api_key: "",
        evolution_base_url: data.evolution_base_url,
        evolution_instance_name: data.evolution_instance_name,
        request_timeout_seconds: String(data.request_timeout_seconds),
      }));
      toast("Configuração do WhatsApp salva com sucesso");
    } catch (e: unknown) {
      setFormError(extractErrorMessage(e, "Erro ao salvar a configuração de WhatsApp."));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    const validation = validateRecipient(testForm.recipient);
    if (validation) {
      setTestError(validation);
      return;
    }

    setTesting(true);
    setTestError("");
    setLastTestResult(null);
    try {
      const { data } = await api.post<WhatsAppTestSendResult>("/api/whatsapp-settings/test", {
        recipient: testForm.recipient.trim(),
        message: testForm.message.trim() || null,
      });
      setLastTestResult(data);
      toast("Mensagem de teste enviada com sucesso");
    } catch (e: unknown) {
      const message = extractErrorMessage(e, "Falha ao enviar mensagem de teste.");
      setTestError(message);
      toast(message, "error");
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-4xl space-y-6">
        <div className="h-9 w-72 bg-gray-100 rounded animate-pulse" />
        <div className="h-4 w-96 bg-gray-100 rounded animate-pulse" />
        <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl space-y-6">
      <PageHeader
        title="WhatsApp"
        description="Configure o envio de alertas via Evolution API."
      />

      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard
          title="Canal WhatsApp"
          description="Defina a base URL, a instância ativa e a chave da Evolution API."
          icon={Shield}
        >
          <div className="flex items-center justify-between gap-3 rounded-lg bg-gray-50 border px-4 py-3">
            <div>
              <p className="text-sm font-medium">Status do canal</p>
              <p className="text-xs text-muted-foreground">Quando desativado, o alerta não é disparado.</p>
            </div>
            <button
              type="button"
              onClick={() => updateForm("is_active", !form.is_active)}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                form.is_active
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-200 text-gray-700"
              }`}
            >
              <span className={`h-2.5 w-2.5 rounded-full ${form.is_active ? "bg-green-500" : "bg-gray-500"}`} />
              {form.is_active ? "Ativo" : "Inativo"}
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5">Evolution base URL</label>
              <input
                value={form.evolution_base_url}
                onChange={(e) => updateForm("evolution_base_url", e.target.value)}
                onBlur={(e) => updateForm("evolution_base_url", normalizeBaseUrl(e.target.value))}
                placeholder="http://192.168.0.115:8081"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5">Nome da instância</label>
              <input
                value={form.evolution_instance_name}
                onChange={(e) => updateForm("evolution_instance_name", e.target.value)}
                placeholder="whatsapp"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5">
                API key da Evolution
                {settings?.api_key_configured ? (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    (deixe em branco para manter a atual)
                  </span>
                ) : null}
              </label>
              <input
                type="password"
                value={form.evolution_api_key}
                onChange={(e) => updateForm("evolution_api_key", e.target.value)}
                placeholder={settings?.api_key_configured ? "••••••••••••" : "Cole a API key aqui"}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5">Timeout da requisição</label>
              <input
                type="number"
                min={1}
                step={1}
                value={form.request_timeout_seconds}
                onChange={(e) => updateForm("request_timeout_seconds", e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
            <TriangleAlert className="h-4 w-4 text-blue-600 shrink-0" />
            O painel não mostra a API key salva; ele só indica se já existe uma credencial configurada.
          </div>

          {formError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {formError}
            </p>
          )}

          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-2">
              <Badge variant={form.is_active ? "success" : "secondary"}>
                {form.is_active ? "Canal ativo" : "Canal inativo"}
              </Badge>
              {settings?.api_key_configured ? <Badge variant="info">API key salva</Badge> : <Badge variant="warning">API key ausente</Badge>}
            </div>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !!settingsError}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              <CheckCircle2 className="h-4 w-4" />
              {saving ? "Salvando..." : "Salvar configuração"}
            </button>
          </div>
          {settingsError && !formError && (
            <p className="text-xs text-muted-foreground">{settingsError}</p>
          )}
        </SectionCard>

        <SectionCard
          title="Teste de envio"
          description="Envie uma mensagem para um número real e valide a credencial da Evolution."
          icon={Radio}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5">Número de destino</label>
              <input
                value={testForm.recipient}
                onChange={(e) => updateTestForm("recipient", e.target.value)}
                onBlur={(e) => {
                  void persistTestRecipient(e.target.value);
                }}
                placeholder="+5511999998888"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Use DDI + DDD + número. O backend remove símbolos antes do envio.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5">Mensagem de teste</label>
              <textarea
                value={testForm.message}
                onChange={(e) => updateTestForm("message", e.target.value)}
                rows={4}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            {testError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {testError}
              </p>
            )}

            {lastTestResult && lastTestResult.success && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
                {lastTestResult.message}
              </div>
            )}

            <button
              type="button"
              onClick={handleTest}
              disabled={testing || !!recipientError}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              {testing ? "Testando..." : "Enviar teste"}
            </button>

            {recipientError && !testError && (
              <p className="text-xs text-muted-foreground">{recipientError}</p>
            )}
          </div>
        </SectionCard>
      </div>

      {/* ── Conexão da instância ── */}
      <SectionCard
        title="Conexão da instância"
        description="Gerencie a conexão do WhatsApp na Evolution API."
        icon={Wifi}
      >
        {/* Status badge */}
        <div className="flex items-center gap-3">
          {instanceStatus === null ? (
            <span className="text-sm text-muted-foreground">Carregando…</span>
          ) : (
            <>
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${
                  instanceStatus.state === "open"
                    ? "bg-green-100 text-green-700"
                    : instanceStatus.state === "connecting"
                      ? "bg-yellow-100 text-yellow-700"
                      : "bg-gray-100 text-gray-600"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    instanceStatus.state === "open"
                      ? "bg-green-500"
                      : instanceStatus.state === "connecting"
                        ? "bg-yellow-400 animate-pulse"
                        : "bg-gray-400"
                  }`}
                />
                {instanceStatus.state === "open"
                  ? "Conectado"
                  : instanceStatus.state === "connecting"
                    ? "Aguardando QR Code"
                    : instanceStatus.state === "close"
                      ? "Desconectado"
                      : "Desconhecido"}
              </span>
              <button
                onClick={fetchInstanceStatus}
                disabled={instanceLoading}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                title="Atualizar status"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${instanceLoading ? "animate-spin" : ""}`} />
              </button>
            </>
          )}
        </div>

        {/* QR Code */}
        {instanceStatus?.state === "connecting" && instanceStatus.qr_code && (
          <div className="flex flex-col items-center gap-2 py-2">
            <p className="text-sm text-muted-foreground">Escaneie o QR Code com o WhatsApp</p>
            <img
              src={instanceStatus.qr_code}
              alt="QR Code WhatsApp"
              className="w-56 h-56 rounded-lg border shadow-sm"
            />
            <p className="text-xs text-muted-foreground animate-pulse">Aguardando leitura…</p>
          </div>
        )}

        {/* Ações */}
        <div className="flex flex-wrap gap-2 pt-1">
          {instanceStatus?.state !== "open" && (
            <button
              onClick={() => handleInstanceAction("connect")}
              disabled={instanceLoading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              <Wifi className="h-4 w-4" />
              {instanceAction === "connect" ? "Conectando…" : "Conectar"}
            </button>
          )}
          {instanceStatus?.state === "open" && (
            <button
              onClick={() => handleInstanceAction("disconnect")}
              disabled={instanceLoading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 disabled:opacity-50 transition-colors"
            >
              <WifiOff className="h-4 w-4" />
              {instanceAction === "disconnect" ? "Desconectando…" : "Desconectar"}
            </button>
          )}
          <button
            onClick={() => handleInstanceAction("restart")}
            disabled={instanceLoading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-gray-200 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            <Power className="h-4 w-4" />
            {instanceAction === "restart" ? "Reiniciando…" : "Reiniciar"}
          </button>
        </div>
      </SectionCard>

      <section className="bg-white rounded-xl border shadow-sm p-6">
        <div className="flex items-center gap-2 mb-3">
          <MessageCircle className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Como o alerta é montado</h2>
        </div>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-muted-foreground">
          <li className="rounded-lg bg-gray-50 border px-3 py-2">Placa, câmera, local, horário e confiança entram no texto.</li>
          <li className="rounded-lg bg-gray-50 border px-3 py-2">Quando houver frame disponível, a Evolution recebe mídia com legenda.</li>
          <li className="rounded-lg bg-gray-50 border px-3 py-2">Cada envio é registrado em <code>alerts_sent</code> com status sent/failed.</li>
          <li className="rounded-lg bg-gray-50 border px-3 py-2">Se o canal estiver inativo, o worker não dispara o WhatsApp.</li>
        </ul>
      </section>
    </div>
  );
}
