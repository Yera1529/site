"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Scale, Loader2, CheckCircle } from "lucide-react";

export default function ResetPasswordPage() {
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);

    if (!email.trim() || !email.includes("@")) {
      setError("Введите корректный адрес электронной почты");
      return;
    }
    if (newPassword.length < 6) {
      setError("Новый пароль должен содержать не менее 6 символов");
      return;
    }
    if (!adminKey.trim()) {
      setError("Введите ключ администратора (SECRET_KEY из конфигурации сервера)");
      return;
    }

    setLoading(true);
    try {
      await api.resetPassword({ email, new_password: newPassword, admin_key: adminKey });
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Ошибка сброса пароля");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="govt-bar text-white py-3 px-6">
        <div className="max-w-6xl mx-auto flex items-center gap-2.5">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-white/15 rounded-md flex items-center justify-center">
              <Scale className="w-4 h-4 text-white" />
            </div>
            <span className="text-base font-bold">Представление<span className="text-accent-300">Ai</span></span>
          </Link>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">Сброс пароля</h2>
            <p className="text-sm text-gray-500 mb-6">
              Для сброса пароля требуется ключ администратора (SECRET_KEY)
            </p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            {success ? (
              <div className="text-center py-6">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                <p className="text-green-700 font-medium mb-1">Пароль успешно изменён</p>
                <p className="text-sm text-gray-500 mb-4">
                  Теперь вы можете войти с новым паролем
                </p>
                <Link
                  href="/login"
                  className="inline-block px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition-colors"
                >
                  Перейти ко входу
                </Link>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Электронная почта
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm
                      focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                    placeholder="example@company.ru"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Новый пароль
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm
                      focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                    placeholder="Не менее 6 символов"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Ключ администратора
                  </label>
                  <input
                    type="password"
                    value={adminKey}
                    onChange={(e) => setAdminKey(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm
                      focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                    placeholder="SECRET_KEY из .env"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 bg-brand-600 text-white font-medium rounded-lg
                    hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                  Сбросить пароль
                </button>
              </form>
            )}
          </div>

          <p className="text-center text-sm text-gray-500 mt-6">
            <Link href="/login" className="text-brand-600 hover:text-brand-700 font-medium">
              Вернуться ко входу
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
