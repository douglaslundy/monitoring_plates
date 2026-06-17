"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import { Modal } from "@/components/ui/Modal";
import type { MonitoredPlate } from "@/types";
import { Bell, Plus, Trash2, Shield, Mail, ToggleLeft, ToggleRight } from "lucide-react";

interface PlateForm {
  plate: string;
  description: string;
  alert_email: string;
}

const EMPTY_FORM: PlateForm = { plate: "", description: "", alert_email: "" };
const PLATE_RE = /^[A-Z]{3}\d{4}$|^[A-Z]{3}\d[A-Z]\d{2}$/;

function validate(form: PlateForm): string {
  if (!PLATE_RE.test(form.plate.toUpperCase().trim())) {
    return "Placa inválida. Use o formato AAA1234 ou AAA1A23 (Mercosul).";
  }
  if (form.alert_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.alert_email)) {
    return "E-mail para alertas inválido.";
  }
  return "";
}

export default function ClientAlertsPage() {
  const [plates, setPlates] = useState<MonitoredPlate[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<PlateForm>(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<MonitoredPlate[]>("/api/monitored-plates");
      setPlates(res.data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleChange(field: keyof PlateForm, value: string) {
    setForm((prev) => ({ ...prev, [field]: field === "plate" ? value.toUpperCase() : value }));
    if (formError) setFormError("");
  }

  async function handleCreate() {
    const err = validate(form);
    if (err) {
      setFormError(err);
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      await api.post("/api/monitored-plates", {
        plate: form.plate.trim(),
        description: form.description.trim() || null,
        alert_email: form.alert_email.trim() || null,
      });
      setModalOpen(false);
      setForm(EMPTY_FORM);
      await load();
    } catch (e: unknown) {
      setFormError(extractErrorMessage(e, "Erro ao salvar. Tente novamente."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(p: MonitoredPlate) {
    try {
      await api.patch(`/api/monitored-plates/${p.id}`, { is_active: !p.is_active });
      setPlates((prev) =>
        prev.map((pl) => (pl.id === p.id ? { ...pl, is_active: !pl.is_active } : pl))
      );
    } catch {
      /* ignore */
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/api/monitored-plates/${id}`);
      setPlates((prev) => prev.filter((p) => p.id !== id));
    } catch {
      /* ignore */
    } finally {
      setDeleteConfirm(null);
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <PageHeader
          title="Placas Monitoradas"
          description="Receba alertas quando estas placas forem detectadas"
        />
        <button
          onClick={() => {
            setForm(EMPTY_FORM);
            setFormError("");
            setModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Monitorar placa
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : plates.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Bell className="h-14 w-14 mx-auto mb-4 opacity-15" />
          <p className="text-base font-medium">Nenhuma placa monitorada</p>
          <p className="text-sm mt-1">Adicione uma placa para receber alertas em tempo real.</p>
          <button
            onClick={() => setModalOpen(true)}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Monitorar primeira placa
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {plates.map((p) => (
            <div
              key={p.id}
              className={`bg-white rounded-xl border shadow-sm p-4 flex items-center gap-4 transition-opacity ${
                p.is_active ? "" : "opacity-60"
              }`}
            >
              {/* Icon */}
              <div
                className={`h-10 w-10 rounded-full flex items-center justify-center shrink-0 ${
                  p.is_active ? "bg-primary/10" : "bg-gray-100"
                }`}
              >
                <Shield
                  className={`h-5 w-5 ${p.is_active ? "text-primary" : "text-gray-400"}`}
                />
              </div>

              {/* Main info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono font-bold text-base tracking-wider">{p.plate}</span>
                  {!p.is_active && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                      inativo
                    </span>
                  )}
                </div>
                {p.description && (
                  <p className="text-sm text-muted-foreground truncate mt-0.5">{p.description}</p>
                )}
                {p.alert_email && (
                  <p className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                    <Mail className="h-3 w-3 shrink-0" />
                    <span className="truncate">{p.alert_email}</span>
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => toggleActive(p)}
                  title={p.is_active ? "Desativar" : "Ativar"}
                  className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {p.is_active ? (
                    <ToggleRight className="h-6 w-6 text-primary" />
                  ) : (
                    <ToggleLeft className="h-6 w-6 text-gray-400" />
                  )}
                </button>
                <button
                  onClick={() => setDeleteConfirm(p.id)}
                  title="Remover"
                  className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-500 transition-colors text-muted-foreground"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create modal */}
      <Modal
        open={modalOpen}
        onOpenChange={(open) => {
          setModalOpen(open);
          if (!open) setFormError("");
        }}
        title="Monitorar nova placa"
        description="Receba um alerta sempre que esta placa for detectada."
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">
              Placa <span className="text-red-500">*</span>
            </label>
            <input
              value={form.plate}
              onChange={(e) => handleChange("plate", e.target.value)}
              placeholder="ABC1234"
              maxLength={7}
              className="w-full px-3 py-2 border rounded-lg text-sm font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-primary/50"
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Padrão antigo (AAA1234) ou Mercosul (AAA1A23)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Descrição</label>
            <input
              value={form.description}
              onChange={(e) => handleChange("description", e.target.value)}
              placeholder="Ex: Veículo suspeito, entrega programada…"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">E-mail para alertas</label>
            <input
              type="email"
              value={form.alert_email}
              onChange={(e) => handleChange("alert_email", e.target.value)}
              placeholder="email@exemplo.com (opcional)"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Deixe em branco para usar apenas alertas na tela
            </p>
          </div>

          {formError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {formError}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => {
                setModalOpen(false);
                setFormError("");
              }}
              className="flex-1 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={handleCreate}
              disabled={saving || !form.plate}
              className="flex-1 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {saving ? "Salvando…" : "Monitorar"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirm modal */}
      <Modal
        open={!!deleteConfirm}
        onOpenChange={(open) => !open && setDeleteConfirm(null)}
        title="Remover placa monitorada"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Tem certeza que deseja parar de monitorar esta placa? Esta ação não pode ser desfeita.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setDeleteConfirm(null)}
              className="flex-1 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
              className="flex-1 py-2 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors"
            >
              Remover
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
