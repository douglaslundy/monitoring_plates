import { MonitoredPlatesManager } from "@/components/alerts/MonitoredPlatesManager";

export default function AdminAlertsPage() {
  return (
    <MonitoredPlatesManager
      title="Alertas"
      description="Cadastre placas monitoradas para receber alertas em tempo real"
    />
  );
}
