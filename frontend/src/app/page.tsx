"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { FileText, MessageSquare, FileCheck, Shield, ArrowRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="govt-bar text-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Image src="/mvd-logo.png" alt="МВД РК" width={36} height={36} className="rounded-full object-contain" />
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-bold tracking-tight">Представление</span>
              <span className="text-xl font-bold text-accent-300">Ai</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-medium text-white/80 hover:text-white transition-colors"
            >
              Войти
            </Link>
            <Link
              href="/register"
              className="px-4 py-2 text-sm font-medium bg-white text-brand-700 rounded-lg hover:bg-gray-100 transition-colors"
            >
              Регистрация
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main>
        <section className="bg-gradient-to-b from-brand-950 via-brand-900 to-brand-800 text-white py-24 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 text-accent-200 text-sm font-medium mb-8 backdrop-blur-sm">
              <Shield className="w-4 h-4" />
              Юридический помощник на базе искусственного интеллекта
            </div>
            <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-6">
              Интеллектуальная система
              <br />
              <span className="text-accent-300">правовой поддержки</span>
            </h1>
            <p className="text-lg text-white/70 mb-10 max-w-2xl mx-auto leading-relaxed">
            Загружайте материалы уголовных дел, задавайте вопросы ИИ по документам и генерируйте
            процессуальные документы — с использованием модели Saiga NeMo 12B,
            оптимизированной для русского языка.
            </p>
            <div className="flex items-center justify-center gap-4">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-6 py-3 bg-white text-brand-800 font-semibold rounded-xl hover:bg-gray-100 transition-colors shadow-lg"
              >
                Начать работу
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/login"
                className="px-6 py-3 bg-white/10 text-white font-medium rounded-xl hover:bg-white/20 transition-colors backdrop-blur-sm border border-white/20"
              >
                Войти в систему
              </Link>
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="max-w-6xl mx-auto px-6 py-20">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-gray-900 mb-3">Возможности платформы</h2>
            <p className="text-gray-500">Полный набор инструментов для работы с юридическими документами</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="rounded-2xl p-8 border border-gray-200 hover:border-brand-300 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-brand-50 rounded-xl flex items-center justify-center mb-5">
                <FileText className="w-6 h-6 text-brand-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Анализ документов</h3>
              <p className="text-gray-500 text-sm leading-relaxed">
                Загружайте PDF, DOCX и TXT файлы. ИИ извлекает и анализирует содержание
                для интеллектуального поиска по документам.
              </p>
            </div>
            <div className="rounded-2xl p-8 border border-gray-200 hover:border-brand-300 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-accent-50 rounded-xl flex items-center justify-center mb-5">
                <MessageSquare className="w-6 h-6 text-accent-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">ИИ-ассистент</h3>
              <p className="text-gray-500 text-sm leading-relaxed">
                Задавайте вопросы по материалам дела и получайте контекстные ответы
                с использованием технологии RAG (поиск по документам).
              </p>
            </div>
            <div className="rounded-2xl p-8 border border-gray-200 hover:border-brand-300 hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center mb-5">
                <FileCheck className="w-6 h-6 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Генерация документов</h3>
              <p className="text-gray-500 text-sm leading-relaxed">
                Создавайте иски, договоры, ходатайства и заключения по шаблонам.
                Редактируйте и экспортируйте в DOCX.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-8 text-center text-sm text-gray-400">
        &copy; {new Date().getFullYear()} ПредставлениеAi. Все права защищены.
      </footer>
    </div>
  );
}
