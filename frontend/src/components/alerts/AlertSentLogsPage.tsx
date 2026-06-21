"use client";

import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import { Modal } from "@/components/ui/Modal";
import type { AlertLog } from "@/types";
import { BellRing, Filter, ImageOff, Search, Trash2 } from "lucide-react";

const MESSAGE_PREVIEW_LIMIT = 50;

function truncate(value: string, limit = MESSAGE_PREVIEW_LIMIT): string {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit).trimEnd()}…`;
}

const CHANNEL_OPTIONS = [
  { label: "Todos os tipos", value: "" },
  { label: "E-mail", value: "email" },
  { label: "WhatsApp", value: "whatsapp" },
  { label: "WebSocket", value: "websocket" },
] as const;

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function localDateTimeToIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

export function AlertSentLogsPage({ title, description }: { title: string; description: string }) {
  const [items, setItems] = useState<AlertLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    channel: "",
    message: "",
    sentFrom: "",
    sentTo: "",
  });
  const [appliedFilters, setAppliedFilters] = useState(filters);
  const [selected, setSelected] = useState<AlertLog | null>(null);

  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    if (appliedFilters.channel) params.set("channel", appliedFilters.channel);
    if (appliedFilters.message.trim()) params.set("message", appliedFilters.message.trim());
    const sentFrom = localDateTimeToIso(appliedFilters.sentFrom);
    const sentTo = localDateTimeToIso(appliedFilters.sentTo);
    if (sentFrom) params.set("sent_from", sentFrom);
    if (sentTo) params.set("sent_to", sentTo);
    params.set("limit", "200");
    return params.toString();
  }, [appliedFilters]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<AlertLog[]>(`/api/alerts/sent?${queryParams}`);
      setItems(res.data);
    } catch (e: unknown) {
      setError(extractErrorMessage(e, "Não foi possível carregar os alertas enviados."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [queryParams]);

  function applyFilters() {
    setAppliedFilters(filters);
  }

  function clearFilters() {
    const empty = { channel: "", message: "", sentFrom: "", sentTo: "" };
    setFilters(empty);
    setAppliedFilters(empty);
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader title={title} description={description} />

      <section className="bg-white rounded-xl border shadow-sm p-4 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Filter className="h-4 w-4" />
          Filtros
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1.5">Tipo de evento</label>
            <select
              value={filters.channel}
              onChange={(e) => setFilters((prev) => ({ ...prev, channel: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 bg-white"
            >
              {CHANNEL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5">Mensagem contém</label>
            <input
              value={filters.message}
              onChange={(e) => setFilters((prev) => ({ ...prev, message: e.target.value }))}
              placeholder="placa, câmera, local..."
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5">Data e hora inicial</label>
            <input
              type="datetime-local"
              value={filters.sentFrom}
              onChange={(e) => setFilters((prev) => ({ ...prev, sentFrom: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5">Data e hora final</label>
            <input
              type="datetime-local"
              value={filters.sentTo}
              onChange={(e) => setFilters((prev) => ({ ...prev, sentTo: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={applyFilters}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition"
          >
            <Search className="h-4 w-4" />
            Aplicar filtros
          </button>
          <button
            type="button"
            onClick={clearFilters}
            className="inline-flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            <Trash2 className="h-4 w-4" />
            Limpar
          </button>
        </div>
      </section>

      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border shadow-sm p-10 text-center text-muted-foreground">
          <BellRing className="h-14 w-14 mx-auto mb-4 opacity-15" />
          <p className="text-base font-medium">Nenhum alerta encontrado</p>
          <p className="text-sm mt-1">Ajuste os filtros para localizar alertas já disparados.</p>
        </div>
      ) : (
        <div className="overflow-hidden bg-white rounded-xl border shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr className="text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Imagem</th>
                  <th className="px-4 py-3 font-medium">Data/hora</th>
                  <th className="px-4 py-3 font-medium">Tipo</th>
                  <th className="px-4 py-3 font-medium">Placa</th>
                  <th className="px-4 py-3 font-medium">Câmera</th>
                  <th className="px-4 py-3 font-medium">Mensagem</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelected(item)}
                    className="border-b last:border-b-0 align-middle cursor-pointer hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      {item.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={item.image_url}
                          alt={`Frame ${item.plate}`}
                          className="h-10 w-14 rounded object-cover border bg-gray-100"
                        />
                      ) : (
                        <div className="h-10 w-14 rounded border bg-gray-50 flex items-center justify-center text-gray-300">
                          <ImageOff className="h-4 w-4" />
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">{formatDateTime(item.sent_at)}</td>
                    <td className="px-4 py-3 whitespace-nowrap capitalize">{item.channel}</td>
                    <td className="px-4 py-3 font-mono font-semibold">{item.plate}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{item.camera_name}</div>
                      {item.location && (
                        <div className="text-xs text-muted-foreground">{item.location}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <p className="text-muted-foreground">
                        {item.message ? truncate(item.message) : "—"}
                      </p>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          item.status === "sent"
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title="Detalhes do alerta"
        description={selected ? `Placa ${selected.plate}` : undefined}
      >
        {selected && (
          <div className="space-y-4">
            {selected.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={selected.image_url}
                alt={`Frame ${selected.plate}`}
                className="w-full max-h-72 object-contain rounded-lg border bg-gray-50"
              />
            ) : (
              <div className="w-full h-40 rounded-lg border bg-gray-50 flex items-center justify-center text-gray-300">
                <ImageOff className="h-8 w-8" />
              </div>
            )}

            <dl className="grid grid-cols-3 gap-x-3 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Placa</dt>
              <dd className="col-span-2 font-mono font-semibold">{selected.plate}</dd>

              <dt className="text-muted-foreground">Data/hora</dt>
              <dd className="col-span-2">{formatDateTime(selected.sent_at)}</dd>

              <dt className="text-muted-foreground">Tipo</dt>
              <dd className="col-span-2 capitalize">{selected.channel}</dd>

              <dt className="text-muted-foreground">Câmera</dt>
              <dd className="col-span-2">
                {selected.camera_name}
                {selected.location ? ` — ${selected.location}` : ""}
              </dd>

              <dt className="text-muted-foreground">Status</dt>
              <dd className="col-span-2">
                <span
                  className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                    selected.status === "sent"
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {selected.status}
                </span>
              </dd>
            </dl>

            {selected.message && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Mensagem</p>
                <p className="text-sm whitespace-pre-wrap rounded-lg border bg-gray-50 p-3">
                  {selected.message}
                </p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
