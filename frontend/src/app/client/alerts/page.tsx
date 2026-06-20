import { MonitoredPlatesManager } from "@/components/alerts/MonitoredPlatesManager";

export default function ClientAlertsPage() {
  return (
    <MonitoredPlatesManager
      title="Placas Monitoradas"
      description="Receba alertas quando estas placas forem detectadas"
    />
  );
}
