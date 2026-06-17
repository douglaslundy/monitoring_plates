"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { Client } from "@/types";
import { MetricCard } from "@/components/ui/MetricCard";
import { SystemResources } from "@/components/live/SystemResources";
import { Building2, Users, CreditCard, AlertTriangle } from "lucide-react";

export default function AdminDashboard() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Client[]>("/api/clients")
      .then((r) => setClients(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const activeClients = clients.filter((c) => c.is_active);
  const totalCameras = clients.reduce((sum, c) => sum + (c.camera_count ?? 0), 0);
  const expiringClients = clients.filter((c) => {
    if (!c.plan_expires_at) return false;
    const days = Math.ceil(
      (new Date(c.plan_expires_at).getTime() - Date.now()) / 86400000
    );
    return days <= 30 && days > 0;
  });

  const quickLinks = [
    { label: "Gerenciar Clientes", href: "/admin/clients", icon: Building2, description: "Criar e administrar clientes" },
    { label: "Ver Planos", href: "/admin/plans", icon: CreditCard, description: "Planos e assinaturas" },
    { label: "Usuários", href: "/admin/users", icon: Users, description: "Gerenciar usuários do sistema" },
  ];

  if (loading) {
    return (
      <div className="p-6">
        <div className="mb-6">
          <div className="h-8 w-40 bg-gray-100 rounded animate-pulse mb-2" />
          <div className="h-4 w-56 bg-gray-100 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white border rounded-xl p-6 animate-pulse">
              <div className="h-4 w-24 bg-gray-100 rounded mb-3" />
              <div className="h-9 w-16 bg-gray-100 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Visão geral do sistema</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          title="Total de Clientes"
          value={clients.length}
          icon={Building2}
        />
        <MetricCard
          title="Clientes Ativos"
          value={activeClients.length}
          icon={Users}
          description={`${clients.length - activeClients.length} inativo(s)`}
        />
        <MetricCard
          title="Total de Câmeras"
          value={totalCameras}
          description="Em todos os clientes"
        />
        <MetricCard
          title="Planos Expirando"
          value={expiringClients.length}
          icon={AlertTriangle}
          description="Próximos 30 dias"
        />
      </div>

      <SystemResources />

      {expiringClients.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-6">
          <h3 className="font-semibold text-orange-800 mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Planos expirando em breve
          </h3>
          <div className="space-y-2">
            {expiringClients.map((c) => {
              const days = Math.ceil(
                (new Date(c.plan_expires_at!).getTime() - Date.now()) / 86400000
              );
              return (
                <div key={c.id} className="flex items-center justify-between text-sm">
                  <span className="font-medium">{c.name}</span>
                  <span className="text-orange-700">
                    {days} dia{days !== 1 ? "s" : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {quickLinks.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-4 p-5 bg-white rounded-xl border shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="p-2 bg-primary/10 rounded-lg shrink-0">
                <Icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold">{item.label}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
