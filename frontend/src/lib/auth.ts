import api from "./api";

export interface UserMe {
  id: string;
  name: string;
  email: string;
  role: string;
  client_id: string | null;
  is_active: boolean;
  created_at: string;
  client?: {
    id: string;
    name: string;
    email: string;
    plan_expires_at?: string | null;
    plan?: {
      id: string;
      name: string;
      max_cameras: number | null;
      retention_days: number | null;
      email_alerts: boolean;
      realtime_alerts: boolean;
    };
  } | null;
}

function setTokenCookie(token: string): void {
  // Mesma validade do token de acesso (7 dias) — evita o cookie sobreviver ao
  // token e dar a falsa sensação de "logado" (com 401 nas páginas).
  const expires = new Date();
  expires.setDate(expires.getDate() + 7);
  document.cookie = `auth-token=${encodeURIComponent(token)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
}

function clearTokenCookie(): void {
  document.cookie = "auth-token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
}

export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(^| )auth-token=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : null;
}

export async function login(email: string, password: string) {
  const { data } = await api.post("/api/auth/login", { email, password });
  setTokenCookie(data.access_token);
  return data;
}

export async function logout(): Promise<void> {
  clearTokenCookie();
  window.location.href = "/login";
}

export async function getMe(): Promise<UserMe> {
  const { data } = await api.get<UserMe>("/api/auth/me");
  return data;
}
