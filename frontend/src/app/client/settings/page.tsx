"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { getMe, UserMe } from "@/lib/auth";
import { PageHeader } from "@/components/ui/PageHeader";
import { useToast } from "@/components/ui/Toast";
import {
  User,
  Shield,
  CreditCard,
  Eye,
  EyeOff,
  Check,
  X,
  Camera,
  Clock,
  Mail,
} from "lucide-react";

function validateName(v: string): string {
  if (!v.trim()) return "Nome é obrigatório";
  if (v.trim().length < 2) return "Nome muito curto";
  return "";
}

function pwdRules(p: string) {
  return [
    { label: "Mínimo 8 caracteres", ok: p.length >= 8 },
    { label: "1 letra maiúscula", ok: /[A-Z]/.test(p) },
    { label: "1 número", ok: /[0-9]/.test(p) },
  ];
}

function PwdInput({
  id,
  value,
  onChange,
  placeholder,
  label,
  describedBy,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label: string;
  describedBy?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium mb-1.5">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder ?? "••••••••"}
          aria-describedby={describedBy}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          aria-label={show ? "Ocultar senha" : "Mostrar senha"}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

export default function ClientSettingsPage() {
  const { toast } = useToast();
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(true);

  // Profile
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState("");
  const [savingName, setSavingName] = useState(false);

  // Password
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdError, setPwdError] = useState("");
  const [savingPwd, setSavingPwd] = useState(false);

  const load = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
      setName(me.name);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault();
    const err = validateName(name);
    setNameError(err);
    if (err) return;
    setSavingName(true);
    try {
      await api.patch(`/api/users/${user!.id}`, { name: name.trim() });
      toast("Nome atualizado com sucesso");
      await load();
    } catch {
      toast("Erro ao atualizar nome", "error");
    } finally {
      setSavingName(false);
    }
  }

  async function handleSavePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwdError("");
    const rules = pwdRules(newPwd);
    if (rules.some((r) => !r.ok)) {
      setPwdError("A nova senha não atende aos requisitos");
      return;
    }
    if (newPwd !== confirmPwd) {
      setPwdError("Senhas não coincidem");
      return;
    }
    setSavingPwd(true);
    try {
      await api.post("/api/auth/change-password", {
        current_password: currentPwd,
        new_password: newPwd,
      });
      toast("Senha alterada com sucesso");
      setCurrentPwd("");
      setNewPwd("");
      setConfirmPwd("");
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Senha atual incorreta ou erro ao alterar";
      setPwdError(detail);
    } finally {
      setSavingPwd(false);
    }
  }

  const plan = user?.client?.plan;

  if (loading) {
    return (
      <div className="p-6 max-w-3xl space-y-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl">
      <PageHeader
        title="Configurações"
        description="Gerencie seu perfil e preferências de conta"
      />

      <div className="space-y-6">
        {/* ── Perfil ── */}
        <section className="bg-white rounded-xl border shadow-sm p-6">
          <div className="flex items-center gap-2 mb-5">
            <User className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="font-semibold">Perfil</h2>
          </div>

          <form onSubmit={handleSaveName} className="space-y-4" noValidate>
            <div>
              <label htmlFor="profile-name" className="block text-sm font-medium mb-1.5">
                Nome
              </label>
              <input
                id="profile-name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setNameError(validateName(e.target.value));
                }}
                aria-describedby={nameError ? "name-error" : undefined}
                aria-invalid={!!nameError}
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 ${
                  nameError ? "border-red-400" : "border-gray-300"
                }`}
              />
              {nameError && (
                <p id="name-error" className="mt-1 text-xs text-red-600">
                  {nameError}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="profile-email" className="block text-sm font-medium mb-1.5">
                Email
              </label>
              <input
                id="profile-email"
                value={user?.email ?? ""}
                disabled
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-muted-foreground"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                O email não pode ser alterado.
              </p>
            </div>

            <button
              type="submit"
              disabled={savingName || name.trim() === user?.name}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            >
              {savingName ? "Salvando…" : "Salvar nome"}
            </button>
          </form>
        </section>

        {/* ── Alterar Senha ── */}
        <section className="bg-white rounded-xl border shadow-sm p-6">
          <div className="flex items-center gap-2 mb-5">
            <Shield className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="font-semibold">Alterar Senha</h2>
          </div>

          <form onSubmit={handleSavePassword} className="space-y-4" noValidate>
            <PwdInput
              id="current-pwd"
              label="Senha atual"
              value={currentPwd}
              onChange={setCurrentPwd}
            />

            <div>
              <PwdInput
                id="new-pwd"
                label="Nova senha"
                value={newPwd}
                onChange={(v) => {
                  setNewPwd(v);
                  setPwdError("");
                }}
                describedBy="pwd-rules"
              />
              {newPwd && (
                <ul id="pwd-rules" className="mt-2 space-y-1" aria-live="polite">
                  {pwdRules(newPwd).map((r) => (
                    <li
                      key={r.label}
                      className={`flex items-center gap-1.5 text-xs ${
                        r.ok ? "text-green-600" : "text-muted-foreground"
                      }`}
                    >
                      {r.ok ? (
                        <Check className="h-3 w-3" aria-hidden="true" />
                      ) : (
                        <X className="h-3 w-3" aria-hidden="true" />
                      )}
                      {r.label}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <label htmlFor="confirm-pwd" className="block text-sm font-medium mb-1.5">
                Confirmar nova senha
              </label>
              <input
                id="confirm-pwd"
                type="password"
                value={confirmPwd}
                onChange={(e) => {
                  setConfirmPwd(e.target.value);
                  setPwdError("");
                }}
                aria-invalid={!!(confirmPwd && confirmPwd !== newPwd)}
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 ${
                  confirmPwd && confirmPwd !== newPwd
                    ? "border-red-400"
                    : "border-gray-300"
                }`}
                placeholder="••••••••"
              />
              {confirmPwd && confirmPwd !== newPwd && (
                <p className="mt-1 text-xs text-red-600">Senhas não coincidem</p>
              )}
            </div>

            {pwdError && (
              <p
                role="alert"
                className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2"
              >
                {pwdError}
              </p>
            )}

            <button
              type="submit"
              disabled={savingPwd || !currentPwd || !newPwd || !confirmPwd}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            >
              {savingPwd ? "Alterando…" : "Alterar senha"}
            </button>
          </form>
        </section>

        {/* ── Plano Atual ── */}
        {plan ? (
          <section className="bg-white rounded-xl border shadow-sm p-6">
            <div className="flex items-center gap-2 mb-5">
              <CreditCard className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="font-semibold">Plano Atual</h2>
            </div>

            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-lg font-bold">{plan.name}</p>
                {user?.client?.name && (
                  <p className="text-sm text-muted-foreground">{user.client.name}</p>
                )}
              </div>
              {user?.client?.plan && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-primary/10 text-primary">
                  Ativo
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Camera className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                  <p className="text-xs text-muted-foreground">Câmeras</p>
                </div>
                <p className="font-semibold">
                  {plan.max_cameras === null ? "Ilimitado" : plan.max_cameras}
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                  <p className="text-xs text-muted-foreground">Retenção</p>
                </div>
                <p className="font-semibold">
                  {plan.retention_days === null
                    ? "Ilimitado"
                    : `${plan.retention_days} dias`}
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Mail className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                  <p className="text-xs text-muted-foreground">Alertas e-mail</p>
                </div>
                <p className="font-semibold">
                  {plan.email_alerts ? "Incluído" : "Não incluído"}
                </p>
              </div>
            </div>

            {user?.client?.plan_expires_at && (
              <p className="mt-4 text-xs text-muted-foreground">
                Plano válido até{" "}
                <strong>
                  {new Date(user.client.plan_expires_at).toLocaleDateString("pt-BR")}
                </strong>
              </p>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
