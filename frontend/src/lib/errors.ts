/**
 * Extrai uma mensagem de erro LEGÍVEL (string) de uma resposta da API.
 *
 * Trata os formatos comuns do FastAPI:
 *  - HTTPException → `detail` é string;
 *  - validação 422 → `detail` é array de `{ type, loc, msg, input }`.
 *
 * Nunca devolve objeto/array — evita o React error #31 ("objects are not valid
 * as a React child") ao exibir `detail` direto na tela.
 */
export function extractErrorMessage(e: unknown, fallback = "Ocorreu um erro. Tente novamente."): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;

  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    if (msgs.length) return msgs.join("; ");
  }

  return fallback;
}
