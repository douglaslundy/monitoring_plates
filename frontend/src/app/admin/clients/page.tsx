"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Client, Plan } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable, Column } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { MetricCard } from "@/components/ui/MetricCard";
import { Building2, Plus, Power, Pencil, Trash2 } from "lucide-react";
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

interface EditForm {
  id: string;
  name: string;
  email: string;
  plan_id: string;
  plan_expires_at: string;
  is_active: boolean;
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
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState<CreateForm>(emptyForm);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
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
      setError("Erro ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError("");
    try {
      await api.post("/api/clients", {
        ...form,
        plan_expires_at: form.plan_expires_at || null,
        is_active: true,
      });
      toast("Cliente criado");
      setModalOpen(false);
      setForm(emptyForm);
      fetchData();
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail || "Erro ao criar cliente");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(c: Client) {
    try {
      await api.patch(`/api/clients/${c.id}`, { is_active: !c.is_active });
      fetchData();
    } catch {
      toast("Falha ao atualizar status");
    }
  }

  function openEdit(c: Client) {
    setEditForm({
      id: c.id,
      name: c.name,
      email: c.email,
      plan_id: c.plan_id,
      plan_expires_at: c.plan_expires_at ? c.plan_expires_at.slice(0, 10) : "",
      is_active: c.is_active,
    });
    setEditOpen(true);
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editForm) return;
    setSubmitting(true);
    try {
      await api.patch(`/api/clients/${editForm.id}`, {
        name: editForm.name,
        email: editForm.email,
        plan_id: editForm.plan_id,
        plan_expires_at: editForm.plan_expires_at || null,
        is_active: editForm.is_active,
      });
      toast("Cliente atualizado");
      setEditOpen(false);
      setEditForm(null);
      fetchData();
    } catch (err: any) {
      toast(err?.response?.data?.detail || "Falha ao atualizar cliente");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(c: Client) {
    if (!confirm(`Excluir cliente ${c.name}? Esta acao remove dados relacionados.`)) return;
    try {
      await api.delete(`/api/clients/${c.id}`);
      toast("Cliente excluido");
      fetchData();
    } catch (err: any) {
      toast(err?.response?.data?.detail || "Falha ao excluir cliente");
    }
  }

  const columns: Column<Client>[] = [
    {
      key: "name",
      header: "Cliente",
      render: (_, row) => (
        <div>
          <p className="font-medium">{row.name}</p>
          <p className="text-xs text-muted-foreground">{row.email}</p>
        </div>
      ),
    },
    { key: "plan", header: "Plano", render: (_, row) => <span>{row.plan?.name ?? "-"}</span> },
    { key: "camera_count", header: "Cameras", render: (_, row) => <span>{row.camera_count}</span> },
    {
      key: "is_active",
      header: "Status",
      render: (_, row) => <Badge variant={row.is_active ? "success" : "danger"}>{row.is_active ? "Ativo" : "Inativo"}</Badge>,
    },
    {
      key: "id",
      header: "Acoes",
      render: (_, row) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(row)} className="p-1.5 rounded hover:bg-gray-100" title="Editar">
            <Pencil className="h-4 w-4 text-blue-600" />
          </button>
          <button onClick={() => handleToggleActive(row)} className="p-1.5 rounded hover:bg-gray-100" title="Ativar/Desativar">
            <Power className={`h-4 w-4 ${row.is_active ? "text-orange-600" : "text-green-600"}`} />
          </button>
          <button onClick={() => handleDelete(row)} className="p-1.5 rounded hover:bg-gray-100" title="Excluir">
            <Trash2 className="h-4 w-4 text-red-600" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-6">
      <PageHeader title="Clientes" description="Gerencie os clientes" action={{ label: "Novo Cliente", icon: Plus, onClick: () => setModalOpen(true) }} />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <MetricCard title="Total" value={clients.length} icon={Building2} />
        <MetricCard title="Ativos" value={clients.filter((c) => c.is_active).length} />
        <MetricCard title="Inativos" value={clients.filter((c) => !c.is_active).length} />
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>}

      <DataTable data={clients} columns={columns} loading={loading} emptyMessage="Nenhum cliente" />

      <Modal open={modalOpen} onOpenChange={setModalOpen} title="Novo Cliente" description="Cadastro de cliente e admin">
        <form onSubmit={handleSubmit} className="space-y-3">
          {submitError && <div className="p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{submitError}</div>}
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <select className="w-full border rounded px-3 py-2 text-sm" value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}>
            <option value="">Selecione o plano</option>
            {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input type="date" className="w-full border rounded px-3 py-2 text-sm" value={form.plan_expires_at} onChange={(e) => setForm({ ...form, plan_expires_at: e.target.value })} />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Nome admin" value={form.admin_name} onChange={(e) => setForm({ ...form, admin_name: e.target.value })} />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="Email admin" value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} />
          <input type="password" className="w-full border rounded px-3 py-2 text-sm" placeholder="Senha admin" value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setModalOpen(false)} className="px-3 py-2 border rounded text-sm">Cancelar</button>
            <button type="submit" disabled={submitting} className="px-3 py-2 bg-black text-white rounded text-sm">{submitting ? "Salvando..." : "Criar"}</button>
          </div>
        </form>
      </Modal>

      <Modal open={editOpen} onOpenChange={setEditOpen} title="Editar Cliente" description="Altere plano e dados">
        {editForm && (
          <form onSubmit={saveEdit} className="space-y-3">
            <input className="w-full border rounded px-3 py-2 text-sm" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
            <input className="w-full border rounded px-3 py-2 text-sm" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
            <select className="w-full border rounded px-3 py-2 text-sm" value={editForm.plan_id} onChange={(e) => setEditForm({ ...editForm, plan_id: e.target.value })}>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <input type="date" className="w-full border rounded px-3 py-2 text-sm" value={editForm.plan_expires_at} onChange={(e) => setEditForm({ ...editForm, plan_expires_at: e.target.value })} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })} /> Cliente ativo</label>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setEditOpen(false)} className="px-3 py-2 border rounded text-sm">Cancelar</button>
              <button type="submit" disabled={submitting} className="px-3 py-2 bg-black text-white rounded text-sm">{submitting ? "Salvando..." : "Salvar"}</button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
