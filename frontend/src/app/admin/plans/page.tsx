"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { Plan } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { CreditCard, Users, Camera, Clock, Mail, Wifi } from "lucide-react";

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<Plan[]>("/api/plans")
      .then((r) => setPlans(r.data))
      .catch(() => setError("Erro ao carregar planos"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-6">
        <div className="h-8 w-32 bg-gray-100 rounded animate-pulse mb-8" />
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
      </div>
    );
  }

  return (
    <div className="p-6">
      <PageHeader title="Planos" description="Planos disponíveis no sistema" />

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

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
              <div className="p-2 bg-primary/10 rounded-lg shrink-0">
                <CreditCard className="h-5 w-5 text-primary" />
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
            Nenhum plano disponível
          </div>
        )}
      </div>
    </div>
  );
}
