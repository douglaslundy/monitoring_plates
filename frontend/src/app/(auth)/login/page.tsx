"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Shield, Camera } from "lucide-react";
import { login } from "@/lib/auth";

function validateEmail(email: string): string {
  if (!email) return "Email é obrigatório";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Email inválido";
  return "";
}

function validatePassword(password: string): string {
  if (!password) return "Senha é obrigatória";
  if (password.length < 8) return "Mínimo 8 caracteres";
  if (!/[A-Z]/.test(password)) return "Deve ter ao menos 1 letra maiúscula";
  if (!/[0-9]/.test(password)) return "Deve ter ao menos 1 número";
  return "";
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function handleEmailChange(value: string) {
    setEmail(value);
    if (emailError) setEmailError(validateEmail(value));
    setServerError("");
  }

  function handlePasswordChange(value: string) {
    setPassword(value);
    if (passwordError) setPasswordError(validatePassword(value));
    setServerError("");
  }

  function handleEmailBlur() {
    setEmailError(validateEmail(email));
  }

  function handlePasswordBlur() {
    setPasswordError(validatePassword(password));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const emailErr = validateEmail(email);
    const passErr = validatePassword(password);
    setEmailError(emailErr);
    setPasswordError(passErr);
    if (emailErr || passErr) return;

    setLoading(true);
    setServerError("");

    try {
      const data = await login(email, password);
      const role: string = data.user?.role ?? "";
      router.push(role === "super_admin" ? "/admin" : "/client");
    } catch {
      setServerError("Email ou senha incorretos");
    } finally {
      setLoading(false);
    }
  }

  const isFormValid = !emailError && !passwordError && email && password;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-100 to-blue-50 p-4">
      <div className="w-full max-w-md animate-login">
        {/* Logo + title */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative h-14 w-14 mb-3">
            <Shield className="absolute inset-0 h-14 w-14 text-primary opacity-20" />
            <Shield className="absolute inset-0 h-14 w-14 text-primary" style={{ clipPath: "inset(0 0 50% 0)" }} />
            <Camera className="absolute inset-0 m-auto h-7 w-7 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-primary">Monitoramento</h1>
          <p className="text-sm text-muted-foreground mt-1">Sistema de Reconhecimento de Placas</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-lg font-semibold mb-1">Entrar na conta</h2>
          <p className="text-sm text-muted-foreground mb-6">Acesse seu painel de monitoramento</p>

          {serverError && (
            <div
              role="alert"
              className="mb-5 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
            >
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => handleEmailChange(e.target.value)}
                onBlur={handleEmailBlur}
                aria-describedby={emailError ? "email-error" : undefined}
                aria-invalid={!!emailError}
                className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                  emailError
                    ? "border-red-400 focus:ring-red-400/50"
                    : "border-gray-300"
                }`}
                placeholder="seu@email.com"
              />
              {emailError && (
                <p id="email-error" className="mt-1 text-xs text-red-600">
                  {emailError}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1.5">
                Senha
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  onBlur={handlePasswordBlur}
                  aria-describedby={passwordError ? "password-error" : undefined}
                  aria-invalid={!!passwordError}
                  className={`w-full border rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-colors ${
                    passwordError
                      ? "border-red-400 focus:ring-red-400/50"
                      : "border-gray-300"
                  }`}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {passwordError && (
                <p id="password-error" className="mt-1 text-xs text-red-600">
                  {passwordError}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || !isFormValid}
              className="w-full bg-primary text-primary-foreground py-2.5 rounded-lg font-medium hover:opacity-90 disabled:opacity-50 transition-opacity focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            >
              {loading ? "Entrando…" : "Entrar"}
            </button>
          </form>

          <div className="mt-5 text-center">
            <a
              href="/forgot-password"
              className="text-sm text-primary hover:underline focus:outline-none focus:underline"
            >
              Esqueci minha senha
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
