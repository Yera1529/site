"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { API_URL } from "@/lib/api";
import { Scale, Loader2 } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!email.trim() || !email.includes("@")) {
      setError("Введите корректный адрес электронной почты");
      return;
    }
    if (password.length < 6) {
      setError("Пароль должен содержать не менее 6 символов");
      return;
    }

    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Ошибка входа");
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
            <span className="text-base font-bold">
              Представление<span className="text-accent-300">Ai</span>
            </span>
          </Link>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">
              Вход в систему
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              ПредставлениеAi — юридический помощник МВД РК
            </p>

            {error && (
              <div className="mb-4 space-y-2">
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                  {error}
                </div>
                {error.includes("подключиться к серверу") && (
                  <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg text-sm">
                    <p className="font-medium mb-1">Что проверить:</p>
                    <ul className="list-disc list-inside space-y-0.5 text-xs">
                      <li>
                        Запустите бэкенд:{" "}
                        <code className="bg-amber-100 px-1 rounded">
                          docker compose up
                        </code>
                      </li>
                      <li>
                        Проверьте{" "}
                        <code className="bg-amber-100 px-1 rounded">
                          NEXT_PUBLIC_API_URL
                        </code>{" "}
                        в{" "}
                        <code className="bg-amber-100 px-1 rounded">
                          frontend/.env.local
                        </code>
                      </li>
                    </ul>
                    <a
                      href={`${API_URL}/api/health`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block mt-2 text-xs text-brand-600 hover:underline"
                    >
                      Проверить ответ сервера →
                    </a>
                  </div>
                )}
              </div>
            )}

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
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  placeholder="example@company.ru"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Пароль
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  placeholder="Введите пароль"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-brand-600 text-white font-medium rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                Войти
              </button>
            </form>

            <div className="flex items-center justify-between mt-4 text-sm">
              <Link
                href="/reset-password"
                className="text-gray-500 hover:text-gray-700"
              >
                Забыли пароль?
              </Link>
            </div>
          </div>

          <p className="text-center text-sm text-gray-500 mt-6">
            Нет учётной записи?{" "}
            <Link
              href="/register"
              className="text-brand-600 hover:text-brand-700 font-medium"
            >
              Зарегистрироваться
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
