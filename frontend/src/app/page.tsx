"use client";

import { useRouter } from "next/navigation";
import { FolderSearch, BotMessageSquare, FileOutput, Gavel, ArrowRight, Upload, Search, Download } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

export default function Home() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-brand-200 selection:text-brand-900">
      {/* Premium Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-brand-950/80 backdrop-blur-xl border-b border-white/10 transition-all duration-300">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="relative w-10 h-10 overflow-hidden rounded-full border-2 border-white/10 group-hover:border-white/30 transition-colors">
              <Image src="/mvd-logo.png" alt="МВД Республики Казахстан" fill className="object-cover" />
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-bold tracking-tight text-white">Представление</span>
              <span className="text-xl font-bold text-accent-400">Ai</span>
            </div>
          </Link>
          <Link
            href="/dashboard"
            className="px-6 py-2.5 text-sm font-bold bg-white text-brand-900 rounded-xl hover:bg-gray-100 hover:shadow-[0_0_20px_rgba(255,255,255,0.2)] transition-all"
          >
            Панель управления
          </Link>
        </div>
      </header>

      <main>
        {/* Hero Section */}
        <section className="relative overflow-hidden bg-[#020817] text-white min-h-screen flex items-center pt-20">
          {/* Abstract Ambient Background */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1200px] h-[800px] opacity-60 pointer-events-none">
            <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-brand-600/30 blur-[120px] rounded-full mix-blend-screen animate-pulse-slow" />
            <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-accent-600/20 blur-[100px] rounded-full mix-blend-screen" />
            {/* Grid Pattern overlay */}
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-50" />
          </div>

          <div className="relative z-10 max-w-7xl mx-auto px-6 w-full grid lg:grid-cols-12 gap-16 items-center">
            
            {/* Hero Text */}
            <div className="lg:col-span-7 text-left animate-fade-in-up">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-brand-200 text-xs font-semibold uppercase tracking-wider mb-8 backdrop-blur-md shadow-lg">
                <span className="w-2 h-2 rounded-full bg-accent-400 animate-pulse" />
                МВД Республики Казахстан
              </div>
              
              <h1 className="text-5xl md:text-6xl lg:text-[4.5rem] font-extrabold leading-[1.05] mb-8 tracking-tight">
                Автоматизация
                <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-brand-200 to-accent-300">
                  представлений
                </span>
                <br />
                <span className="text-3xl md:text-4xl text-white/90">по ст. 200 УПК Республики Казахстан</span>
              </h1>
              
              <p className="text-xl text-brand-100/70 mb-12 max-w-2xl leading-relaxed font-light">
                Интеллектуальная система для следователей. Загрузите материалы уголовного дела, проведите анализ через ИИ-ассистент, получите готовый документ — строго соответствующий требованиям законодательства Республики Казахстан.
              </p>
              
              <div className="flex flex-wrap items-center gap-5">
                <Link
                  href="/dashboard"
                  className="relative group px-8 py-4 bg-white text-brand-950 font-bold rounded-2xl hover:bg-brand-50 transition-all shadow-[0_0_40px_rgba(255,255,255,0.15)] hover:shadow-[0_0_60px_rgba(255,255,255,0.3)] hover:-translate-y-1 overflow-hidden"
                >
                  <span className="relative z-10 flex items-center gap-2 text-lg">
                    Открыть панель <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </span>
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-brand-100/40 to-transparent -translate-x-[150%] group-hover:translate-x-[150%] transition-transform duration-700 ease-in-out" />
                </Link>
                <Link
                  href="/templates"
                  className="px-8 py-4 bg-white/5 text-white font-medium text-lg rounded-2xl hover:bg-white/10 transition-colors backdrop-blur-md border border-white/10"
                >
                  Шаблоны документов
                </Link>
              </div>
            </div>
            
            {/* Hero Visual (Glassmorphism UI mockup) */}
            <div className="hidden lg:block lg:col-span-5 relative animate-float">
              <div className="absolute inset-0 bg-gradient-to-tr from-brand-600/30 to-accent-500/20 blur-3xl rounded-full" />
              <div className="relative rounded-3xl border border-white/10 bg-white/5 backdrop-blur-2xl shadow-2xl p-8 overflow-hidden transform rotate-2 hover:rotate-0 transition-transform duration-500">
                {/* Window Controls */}
                <div className="flex gap-2 mb-8">
                  <div className="w-3 h-3 rounded-full bg-red-400/80" />
                  <div className="w-3 h-3 rounded-full bg-amber-400/80" />
                  <div className="w-3 h-3 rounded-full bg-emerald-400/80" />
                </div>
                
                {/* Fake UI Content */}
                <div className="flex items-center gap-4 mb-8 border-b border-white/10 pb-6">
                  <div className="w-12 h-12 rounded-xl bg-brand-500/20 flex items-center justify-center border border-white/10">
                    <FileOutput className="w-6 h-6 text-brand-300" />
                  </div>
                  <div>
                    <div className="text-white font-semibold tracking-wide">Генерация документа</div>
                    <div className="text-brand-200/60 text-sm font-mono mt-1">Status: Processing...</div>
                  </div>
                </div>
                
                <div className="space-y-5">
                  <div className="h-2.5 w-3/4 bg-white/10 rounded-full overflow-hidden">
                     <div className="h-full bg-gradient-to-r from-brand-400 to-accent-400 w-2/3 shadow-[0_0_10px_rgba(100,200,255,0.5)] animate-pulse" />
                  </div>
                  <div className="h-2 w-full bg-white/5 rounded-full" />
                  <div className="h-2 w-5/6 bg-white/5 rounded-full" />
                  <div className="h-2 w-4/6 bg-white/5 rounded-full" />
                </div>
                
                <div className="mt-8 p-5 rounded-2xl bg-[#030b20] border border-white/5 text-sm text-brand-100/70 font-mono shadow-inner">
                  <div className="flex items-center gap-2 mb-2">
                    <Gavel className="w-4 h-4 text-accent-400" />
                    <span className="text-white/90">ст. 200 УПК Республики Казахстан</span>
                  </div>
                  <span className="text-emerald-400">✓</span> Анализ завершён.<br/>
                  <span className="text-accent-400 animate-pulse">⟳</span> Формирование мотивировочной части...
                </div>
              </div>
            </div>
            
          </div>
        </section>

        {/* Stats Strip */}
        <section className="relative z-20 bg-brand-950 border-b border-white/5 py-8 -mt-6">
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { value: "200", label: "Статья УПК", sub: "Республики Казахстан" },
              { value: "26", label: "Шаблонов", sub: "Следственного департамента" },
              { value: "AI", label: "Gemini", sub: "Генерация и анализ" },
              { value: "RAG", label: "Система", sub: "Поиск по нормам закона" },
            ].map((s, i) => (
              <div key={i} className="text-center">
                <div className="text-3xl font-extrabold text-white mb-1">{s.value}</div>
                <div className="text-sm font-medium text-brand-200/80">{s.label}</div>
                <div className="text-xs text-brand-200/40 mt-0.5">{s.sub}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Features — Bento Grid */}
        <section className="bg-slate-50 py-32 px-6 relative z-20">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-24">
              <h2 className="text-sm font-bold tracking-widest text-brand-600 uppercase mb-4">Возможности платформы</h2>
              <h3 className="text-4xl md:text-5xl font-extrabold text-gray-900 tracking-tight">
                Инструментарий следователя
              </h3>
              <p className="mt-4 text-lg text-gray-500 max-w-2xl mx-auto">
                Полный цикл работы с представлениями — от загрузки материалов до генерации готового документа
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6 auto-rows-[340px]">
              {/* Bento Item 1 - Large Left */}
              <div className="md:col-span-2 group relative overflow-hidden rounded-3xl bg-white border border-gray-200 shadow-sm hover:shadow-xl transition-all duration-500 p-10 flex flex-col justify-between">
                <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-brand-50/60 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 group-hover:bg-brand-100/60 transition-colors duration-700" />
                
                <div className="relative z-10 w-16 h-16 bg-brand-50 rounded-2xl flex items-center justify-center mb-6 border border-brand-100 text-brand-600 group-hover:scale-110 group-hover:rotate-3 transition-transform duration-500 shadow-sm">
                  <FolderSearch className="w-8 h-8" />
                </div>
                
                <div className="relative z-10 mt-auto">
                  <h4 className="text-3xl font-bold text-gray-900 mb-4 tracking-tight">Анализ фактов дела</h4>
                  <p className="text-gray-500 leading-relaxed text-lg max-w-lg">
                    Загрузите материалы уголовного дела. ИИ автоматически анализирует обстоятельства и выявленные нарушения для формирования мотивировочной части представления.
                  </p>
                </div>
              </div>

              {/* Bento Item 2 - Small Top Right */}
              <div className="group relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-900 to-brand-950 border border-brand-800 shadow-lg p-8 flex flex-col justify-between text-white hover:-translate-y-2 transition-transform duration-500">
                <div className="absolute inset-0 bg-white/5 mix-blend-overlay opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative z-10 w-14 h-14 bg-white/10 rounded-2xl backdrop-blur-md flex items-center justify-center mb-6 border border-white/20 text-accent-300 shadow-inner">
                  <BotMessageSquare className="w-7 h-7" />
                </div>
                <div className="relative z-10 mt-auto">
                  <h4 className="text-2xl font-bold mb-3">ИИ-консультация</h4>
                  <p className="text-white/70 text-sm leading-relaxed">
                    Чат-бот на базе Gemini помогает уточнить юридические формулировки, подобрать нормативные ссылки и определить превентивные меры.
                  </p>
                </div>
              </div>

              {/* Bento Item 3 - Small Bottom Left */}
              <div className="group relative overflow-hidden rounded-3xl bg-white border border-gray-200 shadow-sm p-8 flex flex-col justify-between hover:border-accent-200 hover:shadow-lg transition-all duration-500">
                <div className="relative z-10 w-14 h-14 bg-accent-50 rounded-2xl flex items-center justify-center mb-6 border border-accent-100 text-accent-600 group-hover:-translate-y-1 transition-transform duration-300 shadow-sm">
                  <Gavel className="w-7 h-7" />
                </div>
                <div className="relative z-10 mt-auto">
                  <h4 className="text-2xl font-bold text-gray-900 mb-3">Законодательство Республики Казахстан</h4>
                  <p className="text-gray-500 text-sm leading-relaxed">
                    Полное соответствие требованиям УПК Республики Казахстан. Автоматический подбор нормативных ссылок на основе FAISS-индекса.
                  </p>
                </div>
              </div>

              {/* Bento Item 4 - Medium Bottom Right */}
              <div className="md:col-span-2 group relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-50 to-brand-50/50 border border-gray-200 shadow-sm p-10 flex flex-col justify-between hover:bg-brand-50 transition-colors duration-500">
                <div className="relative z-10 w-16 h-16 bg-white rounded-2xl flex items-center justify-center mb-6 shadow-md border border-gray-100 text-brand-600 group-hover:scale-105 transition-transform duration-300">
                  <FileOutput className="w-8 h-8" />
                </div>
                <div className="relative z-10 mt-auto">
                  <h4 className="text-3xl font-bold text-gray-900 mb-4 tracking-tight">Генерация представления</h4>
                  <p className="text-gray-600 leading-relaxed text-lg max-w-xl">
                    Автоматическое создание готового проекта представления по ст. 200 УПК Республики Казахстан в формате DOCX с использованием утверждённых ведомственных шаблонов.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="bg-white py-28 px-6 border-t border-gray-100">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-20">
              <h2 className="text-sm font-bold tracking-widest text-brand-600 uppercase mb-4">Как это работает</h2>
              <h3 className="text-4xl font-extrabold text-gray-900 tracking-tight">Три шага до готового документа</h3>
            </div>

            <div className="grid md:grid-cols-3 gap-12">
              {[
                {
                  step: "01",
                  icon: Upload,
                  title: "Загрузите дело",
                  desc: "Создайте уголовное дело и загрузите материалы — протоколы, постановления, справки. Система извлечёт и структурирует ключевые факты.",
                },
                {
                  step: "02",
                  icon: Search,
                  title: "Анализ и нормы",
                  desc: "ИИ-ассистент анализирует обстоятельства, подбирает нормативные ссылки из базы законодательства и предлагает формулировки.",
                },
                {
                  step: "03",
                  icon: Download,
                  title: "Получите документ",
                  desc: "Система генерирует представление в соответствии со ст. 200 УПК Республики Казахстан. Отредактируйте и скачайте в формате DOCX.",
                },
              ].map((item) => (
                <div key={item.step} className="relative group">
                  <div className="text-7xl font-black text-brand-50 absolute -top-4 -left-2 select-none group-hover:text-brand-100 transition-colors">{item.step}</div>
                  <div className="relative pt-8">
                    <div className="w-14 h-14 rounded-2xl bg-brand-50 flex items-center justify-center mb-5 border border-brand-100 group-hover:scale-110 transition-transform">
                      <item.icon className="w-7 h-7 text-brand-600" />
                    </div>
                    <h4 className="text-xl font-bold text-gray-900 mb-3">{item.title}</h4>
                    <p className="text-gray-500 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="relative overflow-hidden bg-[#020817] py-24 px-6">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] opacity-40 pointer-events-none">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-brand-600/30 blur-[100px] rounded-full" />
          </div>
          <div className="relative z-10 max-w-3xl mx-auto text-center">
            <h2 className="text-4xl md:text-5xl font-extrabold text-white mb-6 tracking-tight">
              Начните работу
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-200 to-accent-300">прямо сейчас</span>
            </h2>
            <p className="text-lg text-brand-100/60 mb-10 max-w-xl mx-auto">
              Откройте панель управления, создайте уголовное дело и сгенерируйте первое представление.
            </p>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white text-brand-950 font-bold text-lg rounded-2xl hover:bg-brand-50 transition-all shadow-[0_0_40px_rgba(255,255,255,0.15)] hover:shadow-[0_0_60px_rgba(255,255,255,0.3)] hover:-translate-y-1"
            >
              Открыть панель управления <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-12">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 grayscale opacity-60">
            <Image src="/mvd-logo.png" alt="МВД Республики Казахстан" width={24} height={24} />
            <span className="font-semibold text-gray-900">ПредставлениеAi</span>
          </div>
          <div className="text-sm text-gray-400">
            &copy; {new Date().getFullYear()} Все права защищены. Интеллектуальная система МВД Республики Казахстан.
          </div>
        </div>
      </footer>
    </div>
  );
}
