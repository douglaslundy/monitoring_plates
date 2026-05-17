"use client";

import { useState } from "react";
import Link from "next/link";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSent(true);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md bg-white rounded-xl shadow-md p-8">
        <h1 className="text-2xl font-bold text-center mb-6">
          Recuperar senha
        </h1>

        {sent ? (
          <div className="text-center">
            <p className="text-green-700 mb-4">
              Se o email estiver cadastrado, você receberá as instruções em
              breve.
            </p>
            <Link href="/login" className="text-primary hover:underline text-sm">
              Voltar ao login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="seu@email.com"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 transition"
            >
              Enviar link de recuperação
            </button>
            <div className="text-center">
              <Link href="/login" className="text-sm text-primary hover:underline">
                Voltar ao login
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
