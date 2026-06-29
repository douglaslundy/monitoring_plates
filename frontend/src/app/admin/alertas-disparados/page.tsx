import { AlertSentLogsPage } from "@/components/alerts/AlertSentLogsPage";

export default function AdminAlertSentLogsPage() {
  return (
    <AlertSentLogsPage
      title="Alertas disparados"
      description="Veja todos os alertas enviados com filtro por tipo, data/hora e mensagem"
      viewStorageKey="admin-alert-sent-logs-view"
    />
  );
}
