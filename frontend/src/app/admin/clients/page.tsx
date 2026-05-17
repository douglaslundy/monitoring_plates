"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Client, Plan } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable, Column } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { MetricCard } from "@/components/ui/MetricCard";
import { Building2, Plus, Power } from "lucide-react";
import { useToast } from "@/components/ui/Toast";

interface CreateForm {
  name: string;
  email: string;
  plan_id: string;
  plan_expires_at: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

const emptyForm: CreateForm = {
  name: "",
  email: "",
  plan_id: "",
  plan_expires_at: "",
  admin_name: "",
  admin_email: "",
  admin_password: "",
};

export default function ClientsPage() {
  const { toast } = useToast();
  const [clients, setClients] = useState<Client[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [formErrors, setFormErrors] = useState<Partial<CreateForm>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    setError("");
    try {
      const [cr, pr] = await Promise.all([
        api.get<Client[]>("/api/clients"),
        api.get<Plan[]>("/api/plans"),
      ]);
      setClients(cr.data);
      setPlans(pr.data);
    } catch {
      setError("Erro ao carregar dados. Verifique sua conexão.");
    } finally {
      setLoading(false);
    }
  }

  function validate(): boolean {
    const errs: Partial<CreateForm> = {};
    if (!form.name.trim()) errs.name = "Campo obrigatório";
    if (!form.email.trim()) errs.email = "Campo obrigatório";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = "Email inválido";
    if (!form.plan_id) errs.plan_id = "Campo obrigatório";
    if (!form.admin_name.trim()) errs.admin_name = "Campo obrigatório";
    if (!form.admin_email.trim()) errs.admin_email = "Campo obrigatório";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.admin_email)) errs.admin_email = "Email inválido";
    if (!form.admin_password) errs.admin_password = "Campo obrigatório";
    else if (form.admin_password.length < 8) errs.admin_password = "Mínimo 8 caracteres";
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      await api.post("/api/clients", {
        name: form.name,
        email: form.email,
        plan_id: form.plan_id,
        plan_expires_at: form.plan_expires_at || null,
        is_active: true,
        admin_name: form.admin_name,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
      });
      toast("Cliente criado com sucesso");
      closeModal();
      fetchData();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSubmitError(detail ?? "Erro ao criar cliente");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(c: Client) {
    try {
      if (c.is_active) {
        await api.delete(`/api/clients/${c.id}`);
      } else {
        await api.patch(`/api/clients/${c.id}`, { is_active: true });
      }
      fetchData();
    } catch {
      // silent error — table will reflect real state on next fetch
    }
  }

  function closeModal() {
    setModalOpen(false);
    setForm(emptyForm);
    setFormErrors({});
    setSubmitError("");
  }

  const inputCls = (err?: string) =>
    `w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary ${err ? "border-red-400 focus:ring-red-400" : "border-gray-300"}`;

  const columns: Column<Client>[] = [
    {
      key: "name",
      header: "Cliente",
      sortable: true,
      render: (_, row) => (
        <div>
          <p className="font-medium">{row.name}</p>
          <p className="text-xs text-muted-foreground">{row.email}</p>
        </div>
      ),
    },
    {
      key: "plan",
      header: "Plano",
      render: (_, row) => (
        <span className="font-medium text-primary">{row.plan?.name ?? "—"}</span>
      ),
    },
    {
      key: "camera_count",
      header: "Câmeras",
      sortable: true,
      render: (_, row) => <span>{row.camera_count}</span>,
    },
    {
      key: "plan_expires_at",
      header: "Expira em",
      render: (_, row) => {
        if (!row.plan_expires_at)
          return <span className="text-muted-foreground text-xs">Sem expiração</span>;
        const d = new Date(row.plan_expires_at);
        const days = Math.ceil((d.getTime() - Date.now()) / 86400000);
        return (
          <span className={days <= 30 && days > 0 ? "text-orange-600 font-medium" : ""}>
            {d.toLocaleDateString("pt-BR")}
            {days <= 30 && days > 0 && (
              <span className="ml-1 text-xs">({days}d)</span>
            )}
          </span>
        );
      },
    },
    {
      key: "is_active",
      header: "Status",
      render: (_, row) => (
        <Badge variant={row.is_active ? "success" : "danger"}>
          {row.is_active ? "Ativo" : "Inativo"}
        </Badge>
      ),
    },
    {
      key: "id",
      header: "Ações",
      render: (_, row) => (
        <button
          onClick={() => handleToggleActive(row)}
          title={row.is_active ? "Desativar cliente" : "Reativar cliente"}
          className="p-1.5 rounded hover:bg-gray-100 transition-colors"
        >
          <Power
            className={`h-4 w-4 ${row.is_active ? "text-red-500" : "text-green-500"}`}
          />
        </button>
      ),
    },
  ];

  const activeClients = clients.filter((c) => c.is_active);
  const expiringCount = clients.filter((c) => {
    if (!c.plan_expires_at) return false;
    const d = Math.ceil((new Date(c.plan_expires_at).getTime() - Date.now()) / 86400000);
    return d <= 30 && d > 0;
  }).length;

  return (
    <div className="p-6">
      <PageHeader
        title="Clientes"
        description="Gerencie os clientes do sistema"
        action={{ label: "Novo Cliente", icon: Plus, onClick: () => setModalOpen(true) }}
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <MetricCard title="Total" value={clients.length} icon={Building2} />
        <MetricCard title="Ativos" value={activeClients.length} description="Clientes ativos" />
        <MetricCard title="Expirando" value={expiringCount} description="Próximos 30 dias" />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={fetchData} className="underline text-xs ml-4">
            Tentar novamente
          </button>
        </div>
      )}

      <DataTable
        data={clients}
        columns={columns}
        loading={loading}
        emptyMessage="Nenhum cliente cadastrado. Crie o primeiro!"
      />

      <Modal
        open={modalOpen}
        onOpenChange={(o) => { if (!o) closeModal(); else setModalOpen(true); }}
        title="Novo Cliente"
        description="Cadastre uma empresa e seu administrador"
      >
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {submitError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {submitError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Nome da Empresa *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={inputCls(formErrors.name)}
                placeholder="Empresa ABC"
              />
              {formErrors.name && (
                <p className="mt-1 text-xs text-red-600">{formErrors.name}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Email da Empresa *</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className={inputCls(formErrors.email)}
                placeholder="contato@empresa.com"
              />
              {formErrors.email && (
                <p className="mt-1 text-xs text-red-600">{formErrors.email}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Plano *</label>
              <select
                value={form.plan_id}
                onChange={(e) => setForm({ ...form, plan_id: e.target.value })}
                className={inputCls(formErrors.plan_id)}
              >
                <option value="">Selecione</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — R$ {Number(p.price_monthly).toFixed(2)}
                  </option>
                ))}
              </select>
              {formErrors.plan_id && (
                <p className="mt-1 text-xs text-red-600">{formErrors.plan_id}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Expira em</label>
              <input
                type="date"
                value={form.plan_expires_at}
                onChange={(e) => setForm({ ...form, plan_expires_at: e.target.value })}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>

          <hr className="my-2" />
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Administrador do Cliente
          </p>

          <div>
            <label className="block text-sm font-medium mb-1">Nome do Administrador *</label>
            <input
              type="text"
              value={form.admin_name}
              onChange={(e) => setForm({ ...form, admin_name: e.target.value })}
              className={inputCls(formErrors.admin_name)}
              placeholder="João Silva"
            />
            {formErrors.admin_name && (
              <p className="mt-1 text-xs text-red-600">{formErrors.admin_name}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Email do Admin *</label>
              <input
                type="email"
                value={form.admin_email}
                onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
                className={inputCls(formErrors.admin_email)}
                placeholder="admin@empresa.com"
              />
              {formErrors.admin_email && (
                <p className="mt-1 text-xs text-red-600">{formErrors.admin_email}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Senha do Admin *</label>
              <input
                type="password"
                value={form.admin_password}
                onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
                className={inputCls(formErrors.admin_password)}
                placeholder="Mínimo 8 caracteres"
              />
              {formErrors.admin_password && (
                <p className="mt-1 text-xs text-red-600">{formErrors.admin_password}</p>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={closeModal}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition"
            >
              {submitting ? "Criando..." : "Criar Cliente"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
