"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Camera, Client } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { MetricCard } from "@/components/ui/MetricCard";
import { useToast } from "@/components/ui/Toast";
import {
  Camera as CameraIcon,
  Plus,
  Video,
  Cpu,
  Copy,
  Check,
  Trash2,
  Pencil,
} from "lucide-react";

type WizardStep = 1 | 2;

interface CreateForm {
  client_id: string;
  name: string;
  location: string;
  connection_type: "rtsp" | "agent";
  rtsp_url: string;
  dual_lens: boolean;
  lens_side: "upper" | "lower";
}

interface FormErrors {
  client_id?: string;
  name?: string;
  rtsp_url?: string;
}

interface EditForm {
  name: string;
  location: string;
  connection_type: "rtsp" | "agent";
  rtsp_url: string;
  dual_lens: boolean;
  lens_side: "upper" | "lower";
  is_active: boolean;
}

const emptyForm: CreateForm = {
  client_id: "",
  name: "",
  location: "",
  connection_type: "rtsp",
  rtsp_url: "",
  dual_lens: false,
  lens_side: "upper",
};

function validateRtsp(url: string): string {
  if (!url.trim()) return "URL RTSP obrigatória";
  if (!url.startsWith("rtsp://") && !url.startsWith("rtsps://")) {
    return "Deve começar com rtsp:// ou rtsps://";
  }
  return "";
}

export default function AdminCamerasPage() {
  const { toast } = useToast();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [agentCamera, setAgentCamera] = useState<Camera | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [configCopied, setConfigCopied] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null);
  const [editTarget, setEditTarget] = useState<Camera | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [camRes, clientRes] = await Promise.all([
        api.get<Camera[]>("/api/cameras"),
        api.get<Client[]>("/api/clients"),
      ]);
      setCameras(camRes.data);
      setClients(clientRes.data);
    } catch {
      setError("Erro ao carregar dados. Verifique sua conexão.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function setField<K extends keyof CreateForm>(key: K, value: CreateForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    // Real-time validation
    if (key === "rtsp_url" && form.connection_type === "rtsp") {
      setFormErrors((prev) => ({
        ...prev,
        rtsp_url: validateRtsp(value as string),
      }));
    }
    if (key === "name") {
      setFormErrors((prev) => ({
        ...prev,
        name: !(value as string).trim() ? "Campo obrigatório" : "",
      }));
    }
    if (key === "client_id") {
      setFormErrors((prev) => ({
        ...prev,
        client_id: !(value as string) ? "Selecione um cliente" : "",
      }));
    }
  }

  function validate(): boolean {
    const errs: FormErrors = {};
    if (!form.client_id) errs.client_id = "Selecione um cliente";
    if (!form.name.trim()) errs.name = "Campo obrigatório";
    if (form.connection_type === "rtsp") {
      const e = validateRtsp(form.rtsp_url);
      if (e) errs.rtsp_url = e;
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const payload = {
        client_id: form.client_id,
        name: form.name,
        location: form.location || null,
        connection_type: form.connection_type,
        rtsp_url: form.connection_type === "rtsp" ? form.rtsp_url : null,
        dual_lens: form.connection_type === "agent" ? form.dual_lens : false,
        lens_side: form.connection_type === "agent" && form.dual_lens ? form.lens_side : null,
        is_active: true,
      };
      const res = await api.post<Camera>("/api/cameras", payload);
      closeWizard();
      await fetchData();
      toast("Câmera criada com sucesso");
      if (form.connection_type === "agent") {
        setAgentCamera(res.data);
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setSubmitError(detail ?? "Erro ao criar câmera");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(camera: Camera) {
    try {
      await api.delete(`/api/cameras/${camera.id}`);
      toast(`Câmera "${camera.name}" removida`);
      setDeleteTarget(null);
      fetchData();
    } catch {
      toast("Erro ao remover câmera", "error");
      setDeleteTarget(null);
    }
  }

  function openEdit(camera: Camera) {
    setEditTarget(camera);
    setEditForm({
      name: camera.name,
      location: camera.location ?? "",
      connection_type: camera.connection_type,
      rtsp_url: camera.rtsp_url ?? "",
      dual_lens: camera.dual_lens ?? false,
      lens_side: camera.lens_side ?? "upper",
      is_active: camera.is_active,
    });
    setEditError("");
  }

  function closeEdit() {
    setEditTarget(null);
    setEditForm(null);
    setEditError("");
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editTarget || !editForm) return;
    if (!editForm.name.trim()) {
      setEditError("Nome da câmera é obrigatório.");
      return;
    }
    if (editForm.connection_type === "rtsp" && !editForm.rtsp_url.trim()) {
      setEditError("URL RTSP é obrigatória para câmera RTSP.");
      return;
    }
    setEditSubmitting(true);
    setEditError("");
    try {
      await api.patch(`/api/cameras/${editTarget.id}`, {
        name: editForm.name.trim(),
        location: editForm.location.trim() || null,
        connection_type: editForm.connection_type,
        rtsp_url: editForm.connection_type === "rtsp" ? editForm.rtsp_url.trim() : null,
        dual_lens: editForm.connection_type === "agent" ? editForm.dual_lens : false,
        lens_side:
          editForm.connection_type === "agent" && editForm.dual_lens
            ? editForm.lens_side
            : null,
        is_active: editForm.is_active,
      });
      toast("Câmera atualizada");
      closeEdit();
      await fetchData();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setEditError(detail ?? "Erro ao editar câmera.");
    } finally {
      setEditSubmitting(false);
    }
  }

  function closeWizard() {
    setWizardOpen(false);
    setWizardStep(1);
    setForm(emptyForm);
    setFormErrors({});
    setSubmitError("");
  }

  async function copyText(text: string, setCopied: (v: boolean) => void) {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function buildConfigJson(cam: Camera) {
    return JSON.stringify(
      {
        server_url: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
        token: cam.agent_token,
        camera_rtsp: "",
        frame_interval: 1,
      },
      null,
      2
    );
  }

  function formatLastSeen(dateStr: string | null) {
    if (!dateStr) return "Nunca";
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000);
    if (diff < 1) return "Agora mesmo";
    if (diff < 60) return `${diff}m atrás`;
    const h = Math.floor(diff / 60);
    if (h < 24) return `${h}h atrás`;
    return new Date(dateStr).toLocaleDateString("pt-BR");
  }

  const inputCls = (err?: string) =>
    `w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 ${
      err ? "border-red-400" : "border-gray-300"
    }`;

  const online = cameras.filter((c) => c.is_online).length;

  return (
    <div className="p-6">
      <PageHeader
        title="Câmeras"
        description="Gerencie as câmeras de monitoramento"
        action={{ label: "Nova Câmera", icon: Plus, onClick: () => setWizardOpen(true) }}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <MetricCard title="Total" value={cameras.length} icon={CameraIcon} />
        <MetricCard title="Online" value={online} description="Ativas agora" />
        <MetricCard title="Offline" value={cameras.length - online} description="Sem sinal" />
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center justify-between"
        >
          <span>{error}</span>
          <button onClick={fetchData} className="underline text-xs ml-4">
            Tentar novamente
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="border rounded-xl p-4 animate-pulse bg-gray-50 h-40" />
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CameraIcon className="h-12 w-12 mx-auto mb-3 opacity-30" aria-hidden="true" />
          <p className="font-medium">Nenhuma câmera cadastrada</p>
          <p className="text-sm mt-1">Adicione a primeira câmera para começar.</p>
          <button
            onClick={() => setWizardOpen(true)}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nova Câmera
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              className="border rounded-xl p-4 bg-white shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate">{cam.name}</p>
                  {cam.location && (
                    <p className="text-xs text-muted-foreground truncate">{cam.location}</p>
                  )}
                </div>
                <div className="ml-2 shrink-0">
                  {cam.is_online ? (
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <span className="relative flex h-2 w-2" aria-hidden="true">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                      Online
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <span className="h-2 w-2 rounded-full bg-gray-300" aria-hidden="true" />
                      Offline
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 mb-3">
                <Badge variant={cam.connection_type === "rtsp" ? "default" : "secondary"}>
                  <span className="flex items-center gap-1">
                    {cam.connection_type === "rtsp" ? (
                      <><Video className="h-3 w-3" aria-hidden="true" /> RTSP</>
                    ) : (
                      <><Cpu className="h-3 w-3" aria-hidden="true" /> Agente</>
                    )}
                  </span>
                </Badge>
                <Badge variant={cam.is_active ? "success" : "danger"}>
                  {cam.is_active ? "Ativa" : "Inativa"}
                </Badge>
              </div>

              <p className="text-xs text-muted-foreground mb-3">
                Última atividade: {formatLastSeen(cam.last_seen_at)}
              </p>

              <div className="flex gap-3">
                <button
                  onClick={() => openEdit(cam)}
                  aria-label={`Editar câmera ${cam.name}`}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors focus:outline-none focus:underline"
                >
                  <Pencil className="h-3 w-3" aria-hidden="true" />
                  Editar
                </button>
                <button
                  onClick={() => setDeleteTarget(cam)}
                  aria-label={`Remover câmera ${cam.name}`}
                  className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 transition-colors focus:outline-none focus:underline"
                >
                  <Trash2 className="h-3 w-3" aria-hidden="true" />
                  Remover
                </button>
                {cam.connection_type === "agent" && cam.agent_token && (
                  <button
                    onClick={() => setAgentCamera(cam)}
                    aria-label={`Ver token da câmera ${cam.name}`}
                    className="flex items-center gap-1 text-xs text-primary hover:underline focus:outline-none focus:underline"
                  >
                    <Cpu className="h-3 w-3" aria-hidden="true" />
                    Ver token
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Delete confirm ── */}
      <Modal
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}
        title="Remover câmera"
      >
        <p className="text-sm text-muted-foreground mb-5">
          Tem certeza que deseja remover a câmera{" "}
          <strong>&ldquo;{deleteTarget?.name}&rdquo;</strong>? Esta ação não pode ser desfeita.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => setDeleteTarget(null)}
            className="flex-1 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => deleteTarget && handleDelete(deleteTarget)}
            className="flex-1 py-2 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors"
          >
            Remover
          </button>
        </div>
      </Modal>

      <Modal
        open={!!editTarget && !!editForm}
        onOpenChange={(o) => {
          if (!o) closeEdit();
        }}
        title="Editar câmera"
      >
        {editForm && (
          <form onSubmit={handleEditSave} className="space-y-4">
            {editError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {editError}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium mb-1">Nome da câmera *</label>
              <input value={editForm.name} onChange={(e) => setEditForm((p) => (p ? { ...p, name: e.target.value } : p))} className={inputCls()} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Localização</label>
              <input value={editForm.location} onChange={(e) => setEditForm((p) => (p ? { ...p, location: e.target.value } : p))} className={inputCls()} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tipo de conexão</label>
              <select value={editForm.connection_type} onChange={(e) => setEditForm((p) => (p ? { ...p, connection_type: e.target.value as "rtsp" | "agent" } : p))} className={inputCls()}>
                <option value="rtsp">RTSP</option>
                <option value="agent">Agente</option>
              </select>
            </div>
            {editForm.connection_type === "rtsp" && (
              <div>
                <label className="block text-sm font-medium mb-1">URL RTSP *</label>
                <input value={editForm.rtsp_url} onChange={(e) => setEditForm((p) => (p ? { ...p, rtsp_url: e.target.value } : p))} className={inputCls()} />
              </div>
            )}
            {editForm.connection_type === "agent" && (
              <div className="rounded border p-3 bg-gray-50 space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={editForm.dual_lens} onChange={(e) => setEditForm((p) => (p ? { ...p, dual_lens: e.target.checked } : p))} />
                  Câmera de 2 lentes
                </label>
                {editForm.dual_lens && (
                  <select value={editForm.lens_side} onChange={(e) => setEditForm((p) => (p ? { ...p, lens_side: e.target.value as "upper" | "lower" } : p))} className={inputCls()}>
                    <option value="upper">Lente 1 (superior)</option>
                    <option value="lower">Lente 2 (inferior)</option>
                  </select>
                )}
              </div>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm((p) => (p ? { ...p, is_active: e.target.checked } : p))} />
              Câmera ativa
            </label>
            <div className="flex gap-3">
              <button type="button" onClick={closeEdit} className="flex-1 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors">
                Cancelar
              </button>
              <button type="submit" disabled={editSubmitting} className="flex-1 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
                {editSubmitting ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Wizard: Nova Câmera ── */}
      <Modal
        open={wizardOpen}
        onOpenChange={(o) => { if (!o) closeWizard(); else setWizardOpen(true); }}
        title={
          wizardStep === 1
            ? "Nova Câmera — Tipo de conexão"
            : "Nova Câmera — Configurações"
        }
        description={
          wizardStep === 1
            ? "Como esta câmera será conectada ao sistema?"
            : "Preencha os dados da câmera"
        }
      >
        {wizardStep === 1 ? (
          <div className="space-y-3">
            <button
              onClick={() => { setField("connection_type", "rtsp"); setWizardStep(2); }}
              className="w-full flex items-start gap-4 border-2 border-gray-200 hover:border-primary rounded-lg p-4 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              <Video className="h-8 w-8 text-primary shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p className="font-semibold">Câmera RTSP / IP</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Câmera IP com URL RTSP. O servidor conecta diretamente à câmera pela rede.
                </p>
              </div>
            </button>
            <button
              onClick={() => { setField("connection_type", "agent"); setWizardStep(2); }}
              className="w-full flex items-start gap-4 border-2 border-gray-200 hover:border-primary rounded-lg p-4 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              <Cpu className="h-8 w-8 text-primary shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p className="font-semibold">Agente Local (Windows)</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Instale o agent.exe no computador do cliente. Ideal para redes locais isoladas.
                </p>
              </div>
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {submitError && (
              <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {submitError}
              </div>
            )}

            <div>
              <label htmlFor="cam-client" className="block text-sm font-medium mb-1">
                Cliente *
              </label>
              <select
                id="cam-client"
                value={form.client_id}
                onChange={(e) => setField("client_id", e.target.value)}
                aria-describedby={formErrors.client_id ? "cam-client-err" : undefined}
                className={inputCls(formErrors.client_id)}
              >
                <option value="">Selecione o cliente</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              {formErrors.client_id && (
                <p id="cam-client-err" className="mt-1 text-xs text-red-600">{formErrors.client_id}</p>
              )}
            </div>

            <div>
              <label htmlFor="cam-name" className="block text-sm font-medium mb-1">
                Nome da câmera *
              </label>
              <input
                id="cam-name"
                type="text"
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
                aria-describedby={formErrors.name ? "cam-name-err" : undefined}
                className={inputCls(formErrors.name)}
                placeholder="Ex: Entrada Principal"
              />
              {formErrors.name && (
                <p id="cam-name-err" className="mt-1 text-xs text-red-600">{formErrors.name}</p>
              )}
            </div>

            <div>
              <label htmlFor="cam-location" className="block text-sm font-medium mb-1">
                Localização
              </label>
              <input
                id="cam-location"
                type="text"
                value={form.location}
                onChange={(e) => setField("location", e.target.value)}
                className={inputCls()}
                placeholder="Ex: Portaria, Estacionamento B2"
              />
            </div>

            {form.connection_type === "rtsp" && (
              <div>
                <label htmlFor="cam-rtsp" className="block text-sm font-medium mb-1">
                  URL RTSP *
                </label>
                <input
                  id="cam-rtsp"
                  type="text"
                  value={form.rtsp_url}
                  onChange={(e) => setField("rtsp_url", e.target.value)}
                  aria-describedby={formErrors.rtsp_url ? "cam-rtsp-err" : "cam-rtsp-hint"}
                  className={inputCls(formErrors.rtsp_url)}
                  placeholder="rtsp://usuario:senha@192.168.0.100:554/stream"
                />
                {formErrors.rtsp_url ? (
                  <p id="cam-rtsp-err" className="mt-1 text-xs text-red-600">{formErrors.rtsp_url}</p>
                ) : (
                  <p id="cam-rtsp-hint" className="mt-1 text-xs text-muted-foreground">
                    Deve começar com rtsp:// ou rtsps://
                  </p>
                )}
              </div>
            )}

            {form.connection_type === "agent" && (
              <div className="rounded border p-3 bg-gray-50 space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.dual_lens}
                    onChange={(e) => setField("dual_lens", e.target.checked)}
                  />
                  Câmera de 2 lentes
                </label>
                {form.dual_lens && (
                  <select
                    value={form.lens_side}
                    onChange={(e) => setField("lens_side", e.target.value as "upper" | "lower")}
                    className={inputCls()}
                  >
                    <option value="upper">Lente 1 (superior)</option>
                    <option value="lower">Lente 2 (inferior)</option>
                  </select>
                )}
              </div>
            )}

            <div className="flex justify-between pt-2">
              <button
                type="button"
                onClick={() => setWizardStep(1)}
                className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Voltar
              </button>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={closeWizard}
                  className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {submitting ? "Criando…" : "Criar Câmera"}
                </button>
              </div>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Agent Instructions ── */}
      {agentCamera && (
        <Modal
          open={!!agentCamera}
          onOpenChange={(o) => { if (!o) setAgentCamera(null); }}
          title="Instalar Agente Local"
          description={`Configure o agente para a câmera "${agentCamera.name}"`}
        >
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium mb-1">Token de autenticação</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-gray-100 rounded px-3 py-2 text-xs font-mono break-all">
                  {agentCamera.agent_token}
                </code>
                <button
                  onClick={() => copyText(agentCamera.agent_token!, setTokenCopied)}
                  aria-label="Copiar token"
                  className="shrink-0 p-2 rounded hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {tokenCopied ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4 text-gray-500" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium">config.json</p>
                <button
                  onClick={() => copyText(buildConfigJson(agentCamera), setConfigCopied)}
                  className="flex items-center gap-1 text-xs text-primary hover:underline focus:outline-none focus:underline"
                >
                  {configCopied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                  {configCopied ? "Copiado!" : "Copiar"}
                </button>
              </div>
              <pre className="bg-gray-100 rounded p-3 text-xs font-mono overflow-auto max-h-40">
                {buildConfigJson(agentCamera)}
              </pre>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <p className="text-sm font-semibold text-blue-800 mb-2">Passo a passo:</p>
              <ol className="list-decimal list-inside space-y-1 text-xs text-blue-700">
                <li>Baixe o <strong>agent.exe</strong> e salve em <code className="bg-blue-100 px-1 rounded">C:\Monitoramento\</code></li>
                <li>Crie <code className="bg-blue-100 px-1 rounded">config.json</code> na mesma pasta</li>
                <li>Cole o conteúdo acima e preencha <code className="bg-blue-100 px-1 rounded">camera_rtsp</code></li>
                <li>Execute: <code className="bg-blue-100 px-1 rounded">agent.exe</code></li>
                <li>A câmera aparecerá como <strong>Online</strong> em até 30 segundos</li>
              </ol>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setAgentCamera(null)}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
              >
                Entendido
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
