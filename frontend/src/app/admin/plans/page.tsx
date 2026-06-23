"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Plan } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import {
  CreditCard,
  Users,
  Camera,
  Clock,
  Mail,
  Wifi,
  ScanLine,
  Plus,
  Pencil,
  Trash2,
} from "lucide-react";

interface PlanForm {
  name: string;
  max_cameras: string; // "" = ilimitado
  retention_days: string; // "" = ilimitado
  email_alerts: boolean;
  realtime_alerts: boolean;
  price_monthly: string;
  ocr_engine: "system_default" | "fast_alpr" | "plate_recognizer";
  ocr_enabled: boolean;
  face_recognition_enabled: boolean;
  face_engine: "system_default" | "opencv" | "rekognition" | "luxand" | "facepp";
  is_active: boolean;
}

const emptyForm: PlanForm = {
  name: "",
  max_cameras: "",
  retention_days: "",
  email_alerts: false,
  realtime_alerts: true,
  price_monthly: "",
  ocr_engine: "system_default",
  ocr_enabled: true,
  face_recognition_enabled: false,
  face_engine: "system_default",
  is_active: true,
};

function planToForm(p: Plan): PlanForm {
  return {
    name: p.name,
    max_cameras: p.max_cameras != null ? String(p.max_cameras) : "",
    retention_days: p.retention_days != null ? String(p.retention_days) : "",
    email_alerts: p.email_alerts,
    realtime_alerts: p.realtime_alerts,
    price_monthly: String(p.price_monthly),
    ocr_engine: (p.ocr_engine === "easyocr" ? "fast_alpr" : p.ocr_engine) as PlanForm["ocr_engine"],
    ocr_enabled: p.ocr_enabled,
    face_recognition_enabled: p.face_recognition_enabled,
    face_engine: p.face_engine,
    is_active: p.is_active,
  };
}

export default function PlansPage() {
  const { toast } = useToast();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<PlanForm>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    fetchPlans();
  }, []);

  async function fetchPlans() {
    setLoading(true);
    setError("");
    try {
      const r = await api.get<Plan[]>("/api/plans?include_inactive=true");
      setPlans(r.data);
    } catch {
      setError("Erro ao carregar planos");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setSubmitError("");
    setModalOpen(true);
  }

  function openEdit(p: Plan) {
    setEditingId(p.id);
    setForm(planToForm(p));
    setSubmitError("");
    setModalOpen(true);
  }

  const nameValid = form.name.trim().length > 0;
  const priceValid =
    form.price_monthly.trim() !== "" && !Number.isNaN(Number(form.price_monthly)) && Number(form.price_monthly) >= 0;
  const formValid = nameValid && priceValid;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formValid) return;
    setSubmitting(true);
    setSubmitError("");
    const payload = {
      name: form.name.trim(),
      max_cameras: form.max_cameras.trim() === "" ? null : parseInt(form.max_cameras, 10),
      retention_days: form.retention_days.trim() === "" ? null : parseInt(form.retention_days, 10),
      email_alerts: form.email_alerts,
      realtime_alerts: form.realtime_alerts,
      price_monthly: Number(form.price_monthly),
      ocr_engine: form.ocr_engine,
      ocr_enabled: form.ocr_enabled,
      face_recognition_enabled: form.face_recognition_enabled,
      face_engine: form.face_engine,
      is_active: form.is_active,
    };
    try {
      if (editingId) {
        await api.patch(`/api/plans/${editingId}`, payload);
        toast("Plano atualizado");
      } else {
        await api.post("/api/plans", payload);
        toast("Plano criado");
      }
      setModalOpen(false);
      fetchPlans();
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail || "Erro ao salvar plano");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(p: Plan) {
    if (!confirm(`Excluir o plano "${p.name}"?`)) return;
    try {
      await api.delete(`/api/plans/${p.id}`);
      toast("Plano excluido");
      fetchPlans();
    } catch (err: any) {
      toast(err?.response?.data?.detail || "Falha ao excluir plano");
    }
  }

  return (
    <div className="p-6">
      <PageHeader
        title="Planos"
        description="Gerencie os planos do sistema"
        action={{ label: "Novo Plano", icon: Plus, onClick: openCreate }}
      />

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white border rounded-xl p-6 animate-pulse space-y-4">
              <div className="h-6 bg-gray-100 rounded w-1/2" />
              <div className="h-10 bg-gray-100 rounded w-2/3" />
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((j) => (
                  <div key={j} className="h-4 bg-gray-100 rounded" />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className="bg-white border rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow flex flex-col"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-bold">{plan.name}</h3>
                  <p className="mt-1">
                    <span className="text-3xl font-bold text-primary">
                      R$ {Number(plan.price_monthly).toFixed(2)}
                    </span>
                    <span className="text-sm text-muted-foreground">/mês</span>
                  </p>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => openEdit(plan)}
                    className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                    title="Editar plano"
                  >
                    <Pencil className="h-4 w-4 text-blue-600" />
                  </button>
                  <button
                    onClick={() => handleDelete(plan)}
                    className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                    title="Excluir plano"
                  >
                    <Trash2 className="h-4 w-4 text-red-600" />
                  </button>
                </div>
              </div>

              <div className="space-y-2.5 border-t pt-4 flex-1">
                <div className="flex items-center gap-2 text-sm">
                  <Camera className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className={!plan.max_cameras ? "font-semibold text-primary" : ""}>
                    {plan.max_cameras ? `${plan.max_cameras} câmeras` : "Câmeras ilimitadas"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className={!plan.retention_days ? "font-semibold text-primary" : ""}>
                    {plan.retention_days
                      ? `${plan.retention_days} dias de retenção`
                      : "Retenção ilimitada"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-muted-foreground">Alertas email:</span>
                  <Badge variant={plan.email_alerts ? "success" : "secondary"}>
                    {plan.email_alerts ? "Sim" : "Não"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Wifi className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-muted-foreground">Tempo real:</span>
                  <Badge variant={plan.realtime_alerts ? "success" : "secondary"}>
                    {plan.realtime_alerts ? "Sim" : "Não"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <ScanLine className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="text-muted-foreground">Motor OCR:</span>
                  <Badge variant={plan.ocr_engine === "plate_recognizer" ? "info" : "secondary"}>
                    {plan.ocr_engine === "plate_recognizer"
                      ? "Plate Recognizer"
                      : plan.ocr_engine === "fast_alpr" || plan.ocr_engine === "easyocr"
                      ? "Fast-ALPR (local)"
                      : "Padrão do sistema"}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-sm pt-1">
                  <Users className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="font-medium">
                    {plan.client_count ?? 0} cliente
                    {(plan.client_count ?? 0) !== 1 ? "s" : ""} ativo
                    {(plan.client_count ?? 0) !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t">
                <Badge variant={plan.is_active ? "success" : "danger"}>
                  {plan.is_active ? "Disponível" : "Inativo"}
                </Badge>
              </div>
            </div>
          ))}

          {plans.length === 0 && (
            <div className="col-span-3 text-center py-12 text-muted-foreground">
              Nenhum plano cadastrado
            </div>
          )}
        </div>
      )}

      <Modal
        open={modalOpen}
        onOpenChange={setModalOpen}
        title={editingId ? "Editar Plano" : "Novo Plano"}
        description="Configure câmeras, retenção, alertas e preço"
      >
        <form onSubmit={handleSubmit} className="space-y-3">
          {submitError && (
            <div className="p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{submitError}</div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Nome</label>
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="Ex: Profissional"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            {!nameValid && form.name.length > 0 && (
              <p className="text-xs text-red-600 mt-1">Informe um nome.</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Câmeras</label>
              <input
                type="number"
                min={0}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Ilimitado"
                value={form.max_cameras}
                onChange={(e) => setForm({ ...form, max_cameras: e.target.value })}
              />
              <p className="text-xs text-muted-foreground mt-1">Vazio = ilimitado</p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Retenção (dias)</label>
              <input
                type="number"
                min={0}
                className="w-full border rounded px-3 py-2 text-sm"
                placeholder="Ilimitado"
                value={form.retention_days}
                onChange={(e) => setForm({ ...form, retention_days: e.target.value })}
              />
              <p className="text-xs text-muted-foreground mt-1">Vazio = ilimitado</p>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Preço mensal (R$)</label>
            <input
              type="number"
              min={0}
              step="0.01"
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="0.00"
              value={form.price_monthly}
              onChange={(e) => setForm({ ...form, price_monthly: e.target.value })}
            />
            {!priceValid && form.price_monthly.length > 0 && (
              <p className="text-xs text-red-600 mt-1">Informe um valor válido.</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Motor OCR</label>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={form.ocr_engine}
              onChange={(e) =>
                setForm({ ...form, ocr_engine: e.target.value as PlanForm["ocr_engine"] })
              }
            >
              <option value="system_default">Padrão do sistema</option>
              <option value="fast_alpr">Fast-ALPR (local, gratuito)</option>
              <option value="plate_recognizer">Plate Recognizer</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Motor de reconhecimento facial</label>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={form.face_engine}
              onChange={(e) =>
                setForm({ ...form, face_engine: e.target.value as PlanForm["face_engine"] })
              }
              disabled={!form.face_recognition_enabled}
            >
              <option value="system_default">Padrão do sistema</option>
              <option value="insightface">InsightFace / ArcFace (local, gratuito)</option>
              <option value="deepface">DeepFace / ArcFace (local, gratuito)</option>
              <option value="opencv">OpenCV / SFace (local, básico)</option>
              <option value="rekognition">AWS Rekognition (pago)</option>
              <option value="luxand">Luxand Cloud (pago)</option>
              <option value="facepp">Face++ (pago)</option>
            </select>
          </div>

          <div className="flex flex-col gap-2 pt-1">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.ocr_enabled}
                onChange={(e) => setForm({ ...form, ocr_enabled: e.target.checked })}
              />
              Reconhecimento de placas (OCR)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.face_recognition_enabled}
                onChange={(e) => setForm({ ...form, face_recognition_enabled: e.target.checked })}
              />
              Reconhecimento facial
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.email_alerts}
                onChange={(e) => setForm({ ...form, email_alerts: e.target.checked })}
              />
              Alertas por e-mail
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.realtime_alerts}
                onChange={(e) => setForm({ ...form, realtime_alerts: e.target.checked })}
              />
              Alertas em tempo real
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Plano disponível
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3 py-2 border rounded text-sm"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting || !formValid}
              className="px-3 py-2 bg-black text-white rounded text-sm disabled:opacity-50"
            >
              {submitting ? "Salvando..." : editingId ? "Salvar" : "Criar"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
