"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { API_URL } from "@/lib/api";
import { Shield, Loader2, Lock, ArrowRight } from "lucide-react";

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
    <div className="min-h-screen flex">
      {/* Left panel — branded */}
      <div className="hidden lg:flex lg:w-[480px] xl:w-[540px] flex-col justify-between relative overflow-hidden bg-[#020817]">
        {/* Background decorations */}
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-[400px] h-[400px] bg-brand-600/25 blur-[100px] rounded-full" />
          <div className="absolute bottom-1/4 right-1/4 w-[300px] h-[300px] bg-accent-600/15 blur-[80px] rounded-full" />
          <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-60" />
        </div>

        {/* Content */}
        <div className="relative z-10 p-10">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/mvd-logo.png" alt="МВД РК" width={36} height={36} className="rounded-full object-contain" />
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-white tracking-tight">Представление</span>
              <span className="text-lg font-bold text-accent-300">Ai</span>
            </div>
          </Link>
        </div>

        <div className="relative z-10 p-10">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center mb-8 border border-white/20">
            <Shield className="w-7 h-7 text-accent-300" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-4 leading-tight">
            Интеллектуальная<br />
            система для<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-200 to-accent-300">
              следственных органов
            </span>
          </h2>
          <p className="text-white/50 text-sm leading-relaxed max-w-sm">
            Автоматизация составления представлений по ст.&nbsp;200&nbsp;УПК&nbsp;РК
            с применением искусственного интеллекта
          </p>
        </div>

        <div className="relative z-10 p-10 text-xs text-white/30">
          © {new Date().getFullYear()} МВД Республики Казахстан
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex flex-col">
        {/* Mobile header */}
        <div className="lg:hidden govt-bar text-white py-3 px-6">
          <div className="max-w-6xl mx-auto flex items-center gap-2.5">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/mvd-logo.png" alt="МВД РК" width={28} height={28} className="rounded-full object-contain" />
              <span className="text-base font-bold">
                Представление<span className="text-accent-300">Ai</span>
              </span>
            </Link>
          </div>
        </div>

        <div className="flex-1 flex items-center justify-center px-6 py-12 bg-gray-50">
          <div className="w-full max-w-[420px]">
            {/* Header */}
            <div className="mb-8">
              <div className="w-12 h-12 bg-brand-50 rounded-2xl flex items-center justify-center mb-5 border border-brand-100">
                <Lock className="w-5 h-5 text-brand-600" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-1">
                Вход в систему
              </h2>
              <p className="text-sm text-gray-500">
                Введите данные учётной записи для доступа к платформе
              </p>
            </div>

            {error && (
              <div className="mb-5 space-y-2">
                <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
                  {error}
                </div>
                {error.includes("подключиться к серверу") && (
                  <div className="p-3.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl text-sm">
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

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Электронная почта
                </label>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm bg-white
                    focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                    shadow-sm placeholder:text-gray-400 transition-shadow"
                  placeholder="example@company.ru"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Пароль
                </label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm bg-white
                    focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
                    shadow-sm placeholder:text-gray-400 transition-shadow"
                  placeholder="Введите пароль"
                />
              </div>

              <div className="flex items-center justify-end">
                <Link
                  href="/reset-password"
                  className="text-sm text-gray-500 hover:text-brand-600 transition-colors"
                >
                  Забыли пароль?
                </Link>
              </div>

              <button
                id="login-submit"
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-brand-600 text-white font-semibold rounded-xl
                  hover:bg-brand-700 transition-all disabled:opacity-50
                  flex items-center justify-center gap-2 shadow-md hover:shadow-lg
                  hover:-translate-y-0.5 active:translate-y-0"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4" />
                )}
                Войти
              </button>
            </form>

            <p className="text-center text-sm text-gray-500 mt-8">
              Нет учётной записи?{" "}
              <Link
                href="/register"
                className="text-brand-600 hover:text-brand-700 font-semibold"
              >
                Зарегистрироваться
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
