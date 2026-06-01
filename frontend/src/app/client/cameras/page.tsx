"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { Camera } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Camera as CameraIcon, Video, Cpu, Trash2, Pencil } from "lucide-react";

interface EditForm {
  name: string;
  location: string;
  connection_type: "rtsp" | "agent";
  rtsp_url: string;
  dual_lens: boolean;
  lens_side: "upper" | "lower";
  is_active: boolean;
}

export default function ClientCamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [connectionType, setConnectionType] = useState<"rtsp" | "agent">("rtsp");
  const [rtspUrl, setRtspUrl] = useState("");
  const [dualLens, setDualLens] = useState(false);
  const [lensSide, setLensSide] = useState<"upper" | "lower">("upper");
  const [saving, setSaving] = useState(false);
  const [editTarget, setEditTarget] = useState<Camera | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const fetchCameras = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<Camera[]>("/api/cameras");
      setCameras(res.data);
    } catch {
      setError("Erro ao carregar cameras. Verifique sua conexao.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCameras();
  }, [fetchCameras]);

  async function handleCreateCamera(e: React.FormEvent) {
    e.preventDefault();

    if (!name.trim()) {
      setError("Informe o nome da camera.");
      return;
    }
    if (connectionType === "rtsp" && !rtspUrl.trim()) {
      setError("Informe a URL RTSP para camera RTSP.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await api.post("/api/cameras", {
        name: name.trim(),
        location: location.trim() || null,
        connection_type: connectionType,
        rtsp_url: connectionType === "rtsp" ? rtspUrl.trim() : null,
        dual_lens: dualLens,
        lens_side: dualLens ? lensSide : null,
        is_active: true,
      });

      setName("");
      setLocation("");
      setConnectionType("rtsp");
      setRtspUrl("");
      setDualLens(false);
      setLensSide("upper");
      await fetchCameras();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Erro ao cadastrar camera.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(cam: Camera) {
    if (!confirm(`Remover câmera ${cam.name}?`)) return;
    try {
      await api.delete(`/api/cameras/${cam.id}`);
      await fetchCameras();
    } catch {
      setError("Erro ao remover camera.");
    }
  }

  function openEdit(cam: Camera) {
    setEditTarget(cam);
    setEditForm({
      name: cam.name,
      location: cam.location ?? "",
      connection_type: cam.connection_type,
      rtsp_url: cam.rtsp_url ?? "",
      dual_lens: cam.dual_lens ?? false,
      lens_side: cam.lens_side ?? "upper",
      is_active: cam.is_active,
    });
    setEditError("");
  }

  function closeEdit() {
    setEditTarget(null);
    setEditForm(null);
    setEditError("");
  }

  async function handleEditSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editTarget || !editForm) return;
    if (!editForm.name.trim()) {
      setEditError("Informe o nome da camera.");
      return;
    }
    if (editForm.connection_type === "rtsp" && !editForm.rtsp_url.trim()) {
      setEditError("Informe a URL RTSP para camera RTSP.");
      return;
    }
    setEditSaving(true);
    setEditError("");
    try {
      await api.patch(`/api/cameras/${editTarget.id}`, {
        name: editForm.name.trim(),
        location: editForm.location.trim() || null,
        connection_type: editForm.connection_type,
        rtsp_url: editForm.connection_type === "rtsp" ? editForm.rtsp_url.trim() : null,
        dual_lens: editForm.dual_lens,
        lens_side: editForm.dual_lens ? editForm.lens_side : null,
        is_active: editForm.is_active,
      });
      closeEdit();
      await fetchCameras();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setEditError(typeof detail === "string" ? detail : "Erro ao editar camera.");
    } finally {
      setEditSaving(false);
    }
  }

  function formatLastSeen(dateStr: string | null) {
    if (!dateStr) return "Nunca conectou";
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000);
    if (diff < 1) return "Agora mesmo";
    if (diff < 60) return `${diff}m atras`;
    const h = Math.floor(diff / 60);
    if (h < 24) return `${h}h atras`;
    return new Date(dateStr).toLocaleDateString("pt-BR");
  }

  const online = cameras.filter((c) => c.is_online).length;

  return (
    <div className="p-6">
      <PageHeader title="Minhas Cameras" description="Cameras de monitoramento do seu sistema" />

      <form onSubmit={handleCreateCamera} className="mb-6 border rounded-lg p-4 bg-white shadow-sm space-y-3">
        <p className="font-medium">Cadastrar camera</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nome da camera"
            className="w-full border rounded-md px-3 py-2 text-sm"
          />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Local (opcional)"
            className="w-full border rounded-md px-3 py-2 text-sm"
          />
          <select
            value={connectionType}
            onChange={(e) => setConnectionType(e.target.value as "rtsp" | "agent")}
            className="w-full border rounded-md px-3 py-2 text-sm"
          >
            <option value="rtsp">RTSP</option>
            <option value="agent">Agente</option>
          </select>
          {connectionType === "rtsp" && (
            <input
              value={rtspUrl}
              onChange={(e) => setRtspUrl(e.target.value)}
              placeholder="rtsp://usuario:senha@ip:porta/stream"
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
          )}
          <div className="col-span-1 md:col-span-2 border rounded-md p-3 bg-gray-50">
            <label className="flex items-center gap-2 text-sm mb-2">
              <input type="checkbox" checked={dualLens} onChange={(e) => setDualLens(e.target.checked)} />
              Camera de 2 lentes
            </label>
            {dualLens && (
              <select
                value={lensSide}
                onChange={(e) => setLensSide(e.target.value as "upper" | "lower")}
                className="w-full border rounded-md px-3 py-2 text-sm"
              >
                <option value="upper">Lente 1 (superior)</option>
                <option value="lower">Lente 2 (inferior)</option>
              </select>
            )}
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-md bg-black text-white text-sm disabled:opacity-60"
        >
          {saving ? "Salvando..." : "Cadastrar camera"}
        </button>
      </form>

      {cameras.length > 0 && (
        <div className="flex gap-4 mb-6 text-sm">
          <span className="text-muted-foreground">
            {cameras.length} camera{cameras.length !== 1 ? "s" : ""}
          </span>
          <span className="text-green-600 font-medium">{online} online</span>
          <span className="text-gray-400">{cameras.length - online} offline</span>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={fetchCameras} className="underline text-xs ml-4">
            Tentar novamente
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="border rounded-lg p-4 animate-pulse bg-gray-50 h-36" />
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CameraIcon className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>Nenhuma camera configurada ainda.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras.map((cam) => (
            <div key={cam.id} className="border rounded-lg p-4 bg-white shadow-sm">
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate">{cam.name}</p>
                  {cam.location && (
                    <p className="text-xs text-muted-foreground truncate">{cam.location}</p>
                  )}
                </div>
                <div className="ml-2 shrink-0">
                  {cam.is_online ? (
                    <span className="flex items-center gap-1 text-xs text-green-600">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                      </span>
                      Online
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <span className="h-2 w-2 rounded-full bg-gray-300" />
                      Offline
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 mb-3">
                <Badge variant={cam.connection_type === "rtsp" ? "default" : "secondary"}>
                  <span className="flex items-center gap-1">
                    {cam.connection_type === "rtsp" ? (
                      <>
                        <Video className="h-3 w-3" /> RTSP
                      </>
                    ) : (
                      <>
                        <Cpu className="h-3 w-3" /> Agente
                      </>
                    )}
                  </span>
                </Badge>
              </div>

              <p className="text-xs text-muted-foreground">Ultima atividade: {formatLastSeen(cam.last_seen_at)}</p>
              <div className="mt-2 flex gap-3">
                <button onClick={() => openEdit(cam)} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                  <Pencil className="h-3 w-3" /> Editar
                </button>
                <button onClick={() => handleDelete(cam)} className="text-xs text-red-600 hover:underline flex items-center gap-1">
                  <Trash2 className="h-3 w-3" /> Excluir
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={!!editTarget && !!editForm}
        onOpenChange={(o) => {
          if (!o) closeEdit();
        }}
        title="Editar camera"
      >
        {editForm && (
          <form onSubmit={handleEditSave} className="space-y-4">
            {editError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {editError}
              </div>
            )}
            <input value={editForm.name} onChange={(e) => setEditForm((p) => (p ? { ...p, name: e.target.value } : p))} placeholder="Nome da camera" className="w-full border rounded-md px-3 py-2 text-sm" />
            <input value={editForm.location} onChange={(e) => setEditForm((p) => (p ? { ...p, location: e.target.value } : p))} placeholder="Local (opcional)" className="w-full border rounded-md px-3 py-2 text-sm" />
            <select value={editForm.connection_type} onChange={(e) => setEditForm((p) => (p ? { ...p, connection_type: e.target.value as "rtsp" | "agent" } : p))} className="w-full border rounded-md px-3 py-2 text-sm">
              <option value="rtsp">RTSP</option>
              <option value="agent">Agente</option>
            </select>
            {editForm.connection_type === "rtsp" && (
              <input value={editForm.rtsp_url} onChange={(e) => setEditForm((p) => (p ? { ...p, rtsp_url: e.target.value } : p))} placeholder="rtsp://usuario:senha@ip:porta/stream" className="w-full border rounded-md px-3 py-2 text-sm" />
            )}
            <div className="border rounded-md p-3 bg-gray-50">
              <label className="flex items-center gap-2 text-sm mb-2">
                <input type="checkbox" checked={editForm.dual_lens} onChange={(e) => setEditForm((p) => (p ? { ...p, dual_lens: e.target.checked } : p))} />
                Camera de 2 lentes
              </label>
              {editForm.dual_lens && (
                <select value={editForm.lens_side} onChange={(e) => setEditForm((p) => (p ? { ...p, lens_side: e.target.value as "upper" | "lower" } : p))} className="w-full border rounded-md px-3 py-2 text-sm">
                  <option value="upper">Lente 1 (superior)</option>
                  <option value="lower">Lente 2 (inferior)</option>
                </select>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm((p) => (p ? { ...p, is_active: e.target.checked } : p))} />
              Camera ativa
            </label>
            <div className="flex gap-3">
              <button type="button" onClick={closeEdit} className="flex-1 py-2 border rounded-lg text-sm hover:bg-gray-50">
                Cancelar
              </button>
              <button type="submit" disabled={editSaving} className="flex-1 py-2 rounded-lg bg-black text-white text-sm disabled:opacity-60">
                {editSaving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
