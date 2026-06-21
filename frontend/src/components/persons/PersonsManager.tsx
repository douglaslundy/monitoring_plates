"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { getMe } from "@/lib/auth";
import { extractErrorMessage } from "@/lib/errors";
import { PageHeader } from "@/components/ui/PageHeader";
import { Modal } from "@/components/ui/Modal";
import type { Client, Person } from "@/types";
import {
  UserPlus,
  Trash2,
  Mail,
  MessageCircle,
  PencilLine,
  ToggleLeft,
  ToggleRight,
  UserRound,
  Upload,
} from "lucide-react";

interface PersonForm {
  name: string;
  cpf: string;
  birth_date: string;
  phone: string;
  address: string;
  notes: string;
  alert_active: boolean;
  alert_email: string;
  alert_whatsapp: string;
  client_id: string;
}

const EMPTY_FORM: PersonForm = {
  name: "",
  cpf: "",
  birth_date: "",
  phone: "",
  address: "",
  notes: "",
  alert_active: false,
  alert_email: "",
  alert_whatsapp: "",
  client_id: "",
};

function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}

function validate(form: PersonForm, isSuperAdmin: boolean): string {
  if (!form.name.trim()) return "Nome é obrigatório.";
  if (isSuperAdmin && !form.client_id) return "Selecione um cliente para associar a pessoa.";
  if (form.cpf && onlyDigits(form.cpf).length !== 11) return "CPF deve ter 11 dígitos.";
  if (form.alert_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.alert_email)) return "E-mail inválido.";
  if (form.alert_whatsapp) {
    const digits = form.alert_whatsapp.replace(/[\s\-()]/g, "");
    if (!/^\+?\d{10,15}$/.test(digits)) return "Número WhatsApp inválido. Use +5511999998888.";
  }
  return "";
}

export function PersonsManager({ title, description }: { title: string; description: string }) {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<PersonForm>(EMPTY_FORM);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [personsRes, meRes] = await Promise.all([
        api.get<Person[]>("/api/persons"),
        getMe(),
      ]);
      setPersons(personsRes.data);
      const isAdmin = meRes.role === "super_admin";
      setIsSuperAdmin(isAdmin);
      if (isAdmin) {
        const clientsRes = await api.get<Client[]>("/api/clients");
        setClients(clientsRes.data);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleChange(field: keyof PersonForm, value: string | boolean) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (formError) setFormError("");
  }

  function openCreateModal() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setPhotoFile(null);
    setFormError("");
    setModalOpen(true);
  }

  function openEditModal(p: Person) {
    setEditingId(p.id);
    setForm({
      name: p.name,
      cpf: p.cpf ?? "",
      birth_date: p.birth_date ?? "",
      phone: p.phone ?? "",
      address: p.address ?? "",
      notes: p.notes ?? "",
      alert_active: p.alert_active,
      alert_email: p.alert_email ?? "",
      alert_whatsapp: p.alert_whatsapp ?? "",
      client_id: p.client_id ?? "",
    });
    setPhotoFile(null);
    setFormError("");
    setModalOpen(true);
  }

  async function handleSave() {
    const err = validate(form, isSuperAdmin);
    if (err) {
      setFormError(err);
      return;
    }
    setSaving(true);
    setFormError("");
    try {
      const payload: Record<string, string | boolean | null> = {
        name: form.name.trim(),
        cpf: form.cpf.trim() || null,
        birth_date: form.birth_date || null,
        phone: form.phone.trim() || null,
        address: form.address.trim() || null,
        notes: form.notes.trim() || null,
        alert_active: form.alert_active,
        alert_email: form.alert_email.trim() || null,
        alert_whatsapp: form.alert_whatsapp.trim() || null,
      };
      if (isSuperAdmin && form.client_id) payload.client_id = form.client_id;

      let personId = editingId;
      if (editingId) {
        await api.patch(`/api/persons/${editingId}`, payload);
      } else {
        const res = await api.post<Person>("/api/persons", payload);
        personId = res.data.id;
      }

      if (photoFile && personId) {
        const fd = new FormData();
        fd.append("file", photoFile);
        await api.post(`/api/persons/${personId}/face`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      }

      setModalOpen(false);
      setForm(EMPTY_FORM);
      setPhotoFile(null);
      setEditingId(null);
      await load();
    } catch (e: unknown) {
      setFormError(extractErrorMessage(e, "Erro ao salvar. Tente novamente."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(p: Person) {
    try {
      await api.patch(`/api/persons/${p.id}`, { is_active: !p.is_active });
      setPersons((prev) => prev.map((x) => (x.id === p.id ? { ...x, is_active: !x.is_active } : x)));
    } catch {
      /* ignore */
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/api/persons/${id}`);
      setPersons((prev) => prev.filter((p) => p.id !== id));
    } catch {
      /* ignore */
    } finally {
      setDeleteConfirm(null);
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <PageHeader title={title} description={description} />
        <button
          onClick={openCreateModal}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <UserPlus className="h-4 w-4" />
          Cadastrar pessoa
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : persons.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <UserRound className="h-14 w-14 mx-auto mb-4 opacity-15" />
          <p className="text-base font-medium">Nenhuma pessoa cadastrada</p>
          <p className="text-sm mt-1">Cadastre pessoas para reconhecimento facial e alertas.</p>
          <button
            onClick={openCreateModal}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <UserPlus className="h-4 w-4" />
            Cadastrar primeira pessoa
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {persons.map((p) => (
            <div
              key={p.id}
              className={`bg-white rounded-xl border shadow-sm p-4 flex items-center gap-4 transition-opacity ${
                p.is_active ? "" : "opacity-60"
              }`}
            >
              {p.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={p.photo_url}
                  alt={p.name}
                  className="h-12 w-12 rounded-full object-cover shrink-0 border"
                />
              ) : (
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <UserRound className="h-6 w-6 text-primary" />
                </div>
              )}

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-base">{p.name}</span>
                  {p.alert_active && (
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                      alerta ativo
                    </span>
                  )}
                  {!p.is_active && (
                    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">inativo</span>
                  )}
                  <span className="text-xs text-muted-foreground">{p.faces_count} face(s)</span>
                </div>
                {p.cpf && <p className="text-sm text-muted-foreground mt-0.5">CPF: {p.cpf}</p>}
                {p.alert_email && (
                  <p className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                    <Mail className="h-3 w-3 shrink-0" />
                    <span className="truncate">{p.alert_email}</span>
                  </p>
                )}
                {p.alert_whatsapp && (
                  <p className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                    <MessageCircle className="h-3 w-3 shrink-0" />
                    <span className="truncate">{p.alert_whatsapp}</span>
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => toggleActive(p)}
                  title={p.is_active ? "Desativar" : "Ativar"}
                  className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  {p.is_active ? (
                    <ToggleRight className="h-6 w-6 text-primary" />
                  ) : (
                    <ToggleLeft className="h-6 w-6 text-gray-400" />
                  )}
                </button>
                <button
                  onClick={() => openEditModal(p)}
                  title="Editar"
                  className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-muted-foreground"
                >
                  <PencilLine className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setDeleteConfirm(p.id)}
                  title="Remover"
                  className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-500 transition-colors text-muted-foreground"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen}
        onOpenChange={(open) => {
          setModalOpen(open);
          if (!open) {
            setFormError("");
            setEditingId(null);
          }
        }}
        title={editingId ? "Editar pessoa" : "Cadastrar nova pessoa"}
        description="Cadastre dados e foto para reconhecimento facial."
      >
        <div className="space-y-4">
          {isSuperAdmin && (
            <div>
              <label className="block text-sm font-medium mb-1.5">
                Cliente <span className="text-red-500">*</span>
              </label>
              <select
                value={form.client_id}
                onChange={(e) => handleChange("client_id", e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 bg-white"
              >
                <option value="">Selecione um cliente…</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5">
              Nome <span className="text-red-500">*</span>
            </label>
            <input
              value={form.name}
              onChange={(e) => handleChange("name", e.target.value)}
              placeholder="Nome completo"
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1.5">CPF</label>
              <input
                value={form.cpf}
                onChange={(e) => handleChange("cpf", e.target.value)}
                placeholder="00000000000"
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Nascimento</label>
              <input
                type="date"
                value={form.birth_date}
                onChange={(e) => handleChange("birth_date", e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1.5">Telefone</label>
              <input
                value={form.phone}
                onChange={(e) => handleChange("phone", e.target.value)}
                placeholder="(00) 00000-0000"
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Endereço</label>
              <input
                value={form.address}
                onChange={(e) => handleChange("address", e.target.value)}
                placeholder="Rua, número, cidade"
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Foto (reconhecimento facial)</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={(e) => setPhotoFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 px-3 py-2 border rounded-lg text-sm hover:bg-gray-50 transition"
            >
              <Upload className="h-4 w-4" />
              {photoFile ? photoFile.name : "Selecionar foto"}
            </button>
          </div>

          <div className="border-t pt-4 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={form.alert_active}
                onChange={(e) => handleChange("alert_active", e.target.checked)}
                className="h-4 w-4"
              />
              Disparar alerta quando esta pessoa for reconhecida
            </label>
            {form.alert_active && (
              <div className="grid grid-cols-1 gap-3">
                <input
                  type="email"
                  value={form.alert_email}
                  onChange={(e) => handleChange("alert_email", e.target.value)}
                  placeholder="E-mail para alertas (opcional)"
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
                <input
                  value={form.alert_whatsapp}
                  onChange={(e) => handleChange("alert_whatsapp", e.target.value)}
                  placeholder="WhatsApp +5511999998888 (opcional)"
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
            )}
          </div>

          {formError && (
            <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-700">
              {formError}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              onClick={() => setModalOpen(false)}
              className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50 transition"
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition disabled:opacity-50"
            >
              {saving ? "Salvando…" : editingId ? "Salvar" : "Cadastrar"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={deleteConfirm !== null}
        onOpenChange={(open) => !open && setDeleteConfirm(null)}
        title="Remover pessoa"
        description="Esta ação não pode ser desfeita."
      >
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => setDeleteConfirm(null)}
            className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50 transition"
          >
            Cancelar
          </button>
          <button
            onClick={() => deleteConfirm && handleDelete(deleteConfirm)}
            className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition"
          >
            Remover
          </button>
        </div>
      </Modal>
    </div>
  );
}
