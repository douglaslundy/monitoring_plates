import { AlertSentLogsPage } from "@/components/alerts/AlertSentLogsPage";

export default function ClientAlertSentLogsPage() {
  return (
    <AlertSentLogsPage
      title="Alertas disparados"
      description="Histórico de alertas enviados das suas placas monitoradas"
      displayMode="cards"
    />
  );
}
