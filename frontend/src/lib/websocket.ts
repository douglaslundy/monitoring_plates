import type { RealtimeAlert } from "@/types";

export type RealtimeConnectionStatus =
  | "idle"
  | "auth_pending"
  | "connecting"
  | "connected"
  | "retrying"
  | "disconnected"
  | "error";

export interface RealtimeConnectionState {
  connected: boolean;
  status: RealtimeConnectionStatus;
  message: string;
  retryAfterMs: number | null;
  attempts: number;
}

export class PlateAlertWebSocket {
  private ws: WebSocket | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private closedByUser = false;
  private retryAttempt = 0;

  constructor(
    private readonly clientId: string,
    private readonly token: string,
  ) {}

  connect(
    onAlert: (data: RealtimeAlert) => void,
    onStatusChange: (state: RealtimeConnectionState) => void,
  ): void {
    if (this.closedByUser) return;

    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }

    if (this.ws && this.ws.readyState !== WebSocket.CLOSED) {
      this.ws.close();
    }

    const url = new URL(window.location.origin);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `/api/ws/${this.clientId}`;
    url.searchParams.set("token", this.token);

    try {
      onStatusChange({
        connected: false,
        status: "connecting",
        message: "Conectando ao tempo real...",
        retryAfterMs: null,
        attempts: this.retryAttempt,
      });
      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => {
        this.retryAttempt = 0;
        onStatusChange({
          connected: true,
          status: "connected",
          message: "Tempo real conectado.",
          retryAfterMs: null,
          attempts: this.retryAttempt,
        });
        if (this.timer) {
          clearTimeout(this.timer);
          this.timer = null;
        }
      };

      this.ws.onclose = (event) => {
        const closedReason = event.code === 1008
          ? "Autenticacao invalida para o websocket."
          : event.code === 1006
            ? "Conexao com o websocket foi interrompida."
            : "Tempo real indisponivel no momento.";

        onStatusChange({
          connected: false,
          status: this.closedByUser ? "disconnected" : event.code === 1008 ? "error" : "retrying",
          message: closedReason,
          retryAfterMs: this.closedByUser || event.code === 1008 ? null : 1000 * Math.min(8, this.retryAttempt + 1),
          attempts: this.retryAttempt,
        });

        if (!this.closedByUser && event.code !== 1008) {
          this.retryAttempt += 1;
          const delayMs = Math.min(15_000, 1_000 * 2 ** Math.min(this.retryAttempt, 4));
          this.timer = setTimeout(
            () => this.connect(onAlert, onStatusChange),
            delayMs,
          );
        }
      };

      this.ws.onerror = () => {
        onStatusChange({
          connected: false,
          status: this.closedByUser ? "disconnected" : "retrying",
          message: "Falha na conexao em tempo real. Tentando novamente...",
          retryAfterMs: this.closedByUser ? null : 1_000,
          attempts: this.retryAttempt,
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          if (
            data.type === "plate_alert" ||
            data.type === "face_alert" ||
            data.type === "camera_health_alert" ||
            data.type === "worker_delay_alert" ||
            data.type === "ocr_pipeline_alert"
          ) {
            onAlert(data as RealtimeAlert);
          }
        } catch {
          /* ignore malformed messages */
        }
      };
    } catch {
      if (!this.closedByUser) {
        this.retryAttempt += 1;
        const delayMs = Math.min(15_000, 1_000 * 2 ** Math.min(this.retryAttempt, 4));
        onStatusChange({
          connected: false,
          status: "retrying",
          message: "Falha ao iniciar o tempo real. Reconectando...",
          retryAfterMs: delayMs,
          attempts: this.retryAttempt,
        });
        this.timer = setTimeout(() => this.connect(onAlert, onStatusChange), delayMs);
      }
    }
  }

  disconnect(): void {
    this.closedByUser = true;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
