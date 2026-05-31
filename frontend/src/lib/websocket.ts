import type { PlateAlert } from "@/types";

export class PlateAlertWebSocket {
  private ws: WebSocket | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  constructor(
    private readonly clientId: string,
    private readonly token: string,
  ) {}

  connect(
    onAlert: (data: PlateAlert) => void,
    onStatusChange: (connected: boolean) => void,
  ): void {
    if (this.closed) return;

    const apiBase =
      process.env.NEXT_PUBLIC_API_URL || `http://${window.location.hostname}:8000`;
    const wsBase = apiBase.replace(/^http/, "ws");
    const url = `${wsBase}/api/ws/${this.clientId}?token=${encodeURIComponent(this.token)}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        onStatusChange(true);
        if (this.timer) {
          clearTimeout(this.timer);
          this.timer = null;
        }
      };

      this.ws.onclose = () => {
        onStatusChange(false);
        if (!this.closed) {
          this.timer = setTimeout(
            () => this.connect(onAlert, onStatusChange),
            5_000,
          );
        }
      };

      this.ws.onerror = () => {
        /* onclose fires next */
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string);
          if (data.type === "plate_alert") {
            onAlert(data as PlateAlert);
          }
        } catch {
          /* ignore malformed messages */
        }
      };
    } catch {
      if (!this.closed) {
        this.timer = setTimeout(
          () => this.connect(onAlert, onStatusChange),
          5_000,
        );
      }
    }
  }

  disconnect(): void {
    this.closed = true;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
