"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { User, Client } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable, Column } from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";

const roleLabel: Record<string, string> = {
  super_admin: "Super Admin",
  client_admin: "Admin Cliente",
  client_user: "Usuário",
};

const roleBadge: Record<
  string,
  "default" | "success" | "warning" | "secondary" | "danger"
> = {
  super_admin: "default",
  client_admin: "warning",
  client_user: "secondary",
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterClient, setFilterClient] = useState("");
  const [filterRole, setFilterRole] = useState("");

  useEffect(() => {
    fetchData();
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
        <Badge variant={roleBadge[row.role] ?? "secondary"}>
          {roleLabel[row.role] ?? row.role}
        </Badge>
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
        <Badge variant={row.is_active ? "success" : "danger"}>
          {row.is_active ? "Ativo" : "Inativo"}
        </Badge>
      ),
    },
    {
      key: "created_at",
      header: "Criado em",
      render: (_, row) => new Date(row.created_at).toLocaleDateString("pt-BR"),
    },
  ];

  return (
    <div className="p-6">
      <PageHeader title="Usuários" description="Gerencie os usuários do sistema" />

      <div className="flex flex-wrap gap-3 mb-4">
        {clients.length > 0 && (
          <select
            value={filterClient}
            onChange={(e) => setFilterClient(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">Todos os clientes</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
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
            onClick={() => {
              setFilterClient("");
              setFilterRole("");
            }}
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
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        emptyMessage="Nenhum usuário encontrado"
      />
    </div>
  );
}
