"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { getMe } from "@/lib/auth";
import { User, Client } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable, Column } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { Plus, Pencil, Trash2 } from "lucide-react";

const roleLabel: Record<string, string> = {
  super_admin: "Super Admin",
  client_admin: "Admin Cliente",
  client_user: "Usuário",
};

const roleBadge: Record<string, "default" | "success" | "warning" | "secondary" | "danger"> = {
  super_admin: "default",
  client_admin: "warning",
  client_user: "secondary",
};

interface UserForm {
  name: string;
  email: string;
  password: string;
  role: string;
  client_id: string;
  is_active: boolean;
}

const EMPTY_FORM: UserForm = {
  name: "",
  email: "",
  password: "",
  role: "client_user",
  client_id: "",
  is_active: true,
};

export default function UsersPage() {
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterClient, setFilterClient] = useState("");
  const [filterRole, setFilterRole] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<UserForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    getMe()
      .then((m) => setCurrentUserId(m.id))
      .catch(() => {});
  }, []);

  async function fetchData() {
    setLoading(true);
    setError("");
    try {
      const [ur, cr] = await Promise.all([
        api.get<User[]>("/api/users"),
        api.get<Client[]>("/api/clients").catch(() => ({ data: [] as Client[] })),
      ]);
      setUsers(ur.data);
      setClients(cr.data);
    } catch {
      setError("Erro ao carregar usuários");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormError("");
    setModalOpen(true);
  }

  function openEdit(u: User) {
    setEditingId(u.id);
    setForm({
      name: u.name,
      email: u.email,
      password: "",
      role: u.role,
      client_id: u.client_id ?? "",
      is_active: u.is_active,
    });
    setFormError("");
    setModalOpen(true);
  }

  const nameValid = form.name.trim().length > 0;
  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim());
  // Na criação a senha é obrigatória (>= 8); na edição é opcional (vazia = manter).
  const passwordValid = editingId
    ? form.password.length === 0 || form.password.length >= 8
    : form.password.length >= 8;
  const formValid = nameValid && emailValid && passwordValid;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formValid) {
      setFormError("Verifique os campos obrigatórios");
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      if (editingId) {
        const payload: Record<string, unknown> = {
          name: form.name.trim(),
          email: form.email.trim(),
          role: form.role,
          client_id: form.client_id || null,
          is_active: form.is_active,
        };
        if (form.password) payload.password = form.password;
        await api.patch(`/api/users/${editingId}`, payload);
        toast("Usuário atualizado");
      } else {
        await api.post("/api/users", {
          name: form.name.trim(),
          email: form.email.trim(),
          password: form.password,
          role: form.role,
          client_id: form.client_id || null,
          is_active: form.is_active,
        });
        toast("Usuário criado");
      }
      setModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(msg ?? "Erro ao salvar usuário");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(u: User) {
    if (!confirm(`Excluir o usuário "${u.name}"?`)) return;
    try {
      await api.delete(`/api/users/${u.id}`);
      toast("Usuário excluido");
      fetchData();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(msg ?? "Falha ao excluir usuário");
    }
  }

  const clientMap = Object.fromEntries(clients.map((c) => [c.id, c.name]));
  const filtered = users.filter((u) => {
    if (filterClient && u.client_id !== filterClient) return false;
    if (filterRole && u.role !== filterRole) return false;
    return true;
  });

  const columns: Column<User>[] = [
    {
      key: "name",
      header: "Usuário",
      sortable: true,
      render: (_, row) => (
        <div>
          <p className="font-medium">{row.name}</p>
          <p className="text-xs text-muted-foreground">{row.email}</p>
        </div>
      ),
    },
    {
      key: "role",
      header: "Perfil",
      render: (_, row) => (
        <Badge variant={roleBadge[row.role] ?? "secondary"}>{roleLabel[row.role] ?? row.role}</Badge>
      ),
    },
    {
      key: "client_id",
      header: "Cliente",
      render: (_, row) =>
        row.client_id ? (
          <span>{clientMap[row.client_id] ?? "—"}</span>
        ) : (
          <span className="italic text-muted-foreground text-xs">Sistema</span>
        ),
    },
    {
      key: "is_active",
      header: "Status",
      render: (_, row) => (
        <Badge variant={row.is_active ? "success" : "danger"}>{row.is_active ? "Ativo" : "Inativo"}</Badge>
      ),
    },
    {
      key: "created_at",
      header: "Criado em",
      render: (_, row) => new Date(row.created_at).toLocaleDateString("pt-BR"),
    },
    {
      key: "id",
      header: "Ações",
      render: (_, row) => (
        <div className="flex gap-2">
          <button onClick={() => openEdit(row)} className="p-1.5 rounded hover:bg-gray-100" title="Editar">
            <Pencil className="h-4 w-4 text-blue-600" />
          </button>
          {row.id !== currentUserId && (
            <button onClick={() => handleDelete(row)} className="p-1.5 rounded hover:bg-gray-100" title="Excluir">
              <Trash2 className="h-4 w-4 text-red-600" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="p-6">
      <PageHeader
        title="Usuários"
        description="Gerencie os usuários do sistema"
        action={{ label: "Novo Usuário", icon: Plus, onClick: openCreate }}
      />

      <div className="flex flex-wrap gap-3 mb-4">
        {clients.length > 0 && (
          <select
            value={filterClient}
            onChange={(e) => setFilterClient(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">Todos os clientes</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        )}
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">Todos os perfis</option>
          <option value="super_admin">Super Admin</option>
          <option value="client_admin">Admin Cliente</option>
          <option value="client_user">Usuário</option>
        </select>
        {(filterClient || filterRole) && (
          <button
            onClick={() => { setFilterClient(""); setFilterRole(""); }}
            className="text-sm text-muted-foreground hover:text-foreground underline"
          >
            Limpar filtros
          </button>
        )}
        <span className="text-sm text-muted-foreground self-center ml-auto">
          {filtered.length} usuário{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">{error}</div>
      )}

      <DataTable data={filtered} columns={columns} loading={loading} emptyMessage="Nenhum usuário encontrado" />

      <Modal open={modalOpen} onOpenChange={setModalOpen} title={editingId ? "Editar Usuário" : "Novo Usuário"}>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Nome *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Nome completo"
            />
            {!nameValid && form.name.length > 0 && <p className="text-xs text-red-600 mt-1">Informe o nome.</p>}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">E-mail *</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="email@exemplo.com"
            />
            {!emailValid && form.email.length > 0 && <p className="text-xs text-red-600 mt-1">E-mail inválido.</p>}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              {editingId ? "Senha (deixe vazio para manter)" : "Senha *"}
            </label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder={editingId ? "••••••••" : "Mínimo 8 caracteres"}
            />
            {!passwordValid && form.password.length > 0 && (
              <p className="text-xs text-red-600 mt-1">Mínimo 8 caracteres.</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Perfil *</label>
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="client_user">Usuário</option>
              <option value="client_admin">Admin Cliente</option>
              <option value="super_admin">Super Admin</option>
            </select>
          </div>
          {clients.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-1">Cliente</label>
              <select
                value={form.client_id}
                onChange={(e) => setForm((f) => ({ ...f, client_id: e.target.value }))}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Nenhum (sistema)</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="rounded"
            />
            <label htmlFor="is_active" className="text-sm">Usuário ativo</label>
          </div>

          {formError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">{formError}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving || !formValid}
              className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
            >
              {saving ? "Salvando..." : editingId ? "Salvar" : "Criar Usuário"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
