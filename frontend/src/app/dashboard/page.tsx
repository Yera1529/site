"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { MatterListItem } from "@/types";
import {
  Plus,
  FolderOpen,
  FileText,
  Calendar,
  ChevronRight,
  Loader2,
  Search,
  Trash2,
  BrainCircuit,
  Check,
  Scale,
  Sparkles,
  Database,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [matters, setMatters] = useState<MatterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [creationStep, setCreationStep] = useState(0);
  const [creationProgress, setCreationProgress] = useState(0);

  const loadMatters = () => {
    api
      .listMatters()
      .then((data) => setMatters(data as MatterListItem[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadMatters();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setCreationStep(1);
    setCreationProgress(5);

    let createdMatterId: string | null = null;
    let apiError: string | null = null;

    // Start API call in background
    api.createMatter({ name: newName, description: newDesc })
      .then((matter: any) => {
        createdMatterId = matter.id;
      })
      .catch((err: any) => {
        apiError = err.message || "Неизвестная ошибка при создании дела";
      });

    // Run beautiful visual steps for Wow Effect
    const runProgress = async () => {
      // Step 1: Initialize AI Space
      await new Promise((r) => setTimeout(r, 600));
      if (apiError) return handleCreationFailure(apiError);
      setCreationStep(2);
      setCreationProgress(25);

      // Step 2: Database Sync
      await new Promise((r) => setTimeout(r, 700));
      if (apiError) return handleCreationFailure(apiError);
      setCreationStep(3);
      setCreationProgress(50);

      // Step 3: Legislation Match
      await new Promise((r) => setTimeout(r, 700));
      if (apiError) return handleCreationFailure(apiError);
      setCreationStep(4);
      setCreationProgress(75);

      // Step 4: Semantic RAG Search Activation
      await new Promise((r) => setTimeout(r, 700));
      if (apiError) return handleCreationFailure(apiError);
      setCreationProgress(95);

      // Wait until API finishes
      let attempts = 0;
      while (!createdMatterId && !apiError && attempts < 20) {
        await new Promise((r) => setTimeout(r, 150));
        attempts++;
      }

      if (apiError) {
        return handleCreationFailure(apiError);
      }

      if (!createdMatterId) {
        return handleCreationFailure("Превышено время ожидания сервера");
      }

      // Step 5: Preparing Workspace
      setCreationStep(5);
      setCreationProgress(100);
      await new Promise((r) => setTimeout(r, 600));

      // Visual transitioning phase to keep the modal open during router dynamic compile & fetch
      setCreationStep(6);
      
      // Perform route push!
      router.push(`/matters/${createdMatterId}`);

      // Async clean up of form inputs and states after transition has likely started/finished
      setTimeout(() => {
        setNewName("");
        setNewDesc("");
        setShowCreate(false);
        setCreating(false);
        setCreationStep(0);
        setCreationProgress(0);
      }, 5000);
    };

    const handleCreationFailure = (errMsg: string) => {
      alert(errMsg);
      setCreating(false);
      setCreationStep(0);
      setCreationProgress(0);
    };

    runProgress();
  };

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Удалить дело «${name}»?`)) return;
    try {
      await api.deleteMatter(id);
      loadMatters();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const filtered = matters.filter(
    (m) =>
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.description?.toLowerCase().includes(search.toLowerCase())
  );



  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center">
              <FolderOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Уголовные дела</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Управление уголовными делами и документами
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-brand-600 text-white text-sm
              font-medium rounded-xl hover:bg-brand-700 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Новое уголовное дело
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск уголовных дел…"
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm bg-white
              focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
        </div>

        {/* Create modal */}
        {showCreate && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md flex items-center justify-center z-50 px-4 transition-all duration-300">
            {creating ? (
              <div className="bg-gradient-to-br from-slate-900 via-brand-950 to-slate-900 text-white rounded-2xl shadow-2xl w-full max-w-lg p-8 border border-brand-500/30 overflow-hidden relative animate-fade-in-up">
                
                {/* Decorative neon light glows in background */}
                <div className="absolute -top-40 -right-40 w-80 h-80 bg-brand-500/20 rounded-full blur-3xl" />
                <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl" />
                
                {/* Glowing neural ring */}
                <div className="flex flex-col items-center justify-center mb-8 relative">
                  <div className="relative w-24 h-24 flex items-center justify-center">
                    {/* Ring 1 - Outer spin */}
                    <div className="absolute inset-0 rounded-full border-2 border-dashed border-brand-500/40 animate-spin-slow" />
                    {/* Ring 2 - Inner pulse */}
                    <div className="absolute inset-2 rounded-full border border-emerald-500/30 animate-pulse" />
                    {/* Core Brain Icon */}
                    <div className="relative w-16 h-16 rounded-full bg-brand-900/50 border border-brand-500/30 flex items-center justify-center shadow-[0_0_20px_rgba(0,51,170,0.5)]">
                      <BrainCircuit className="w-8 h-8 text-brand-400 animate-pulse" />
                    </div>
                  </div>
                  <h3 className="text-xl font-bold mt-4 bg-gradient-to-r from-blue-400 via-indigo-200 to-emerald-400 bg-clip-text text-transparent transition-all duration-300">
                    {creationStep === 6 ? "Вход в ИИ-кабинет..." : "Инициализация ПредставлениеAi"}
                  </h3>
                  <p className="text-xs text-brand-300 mt-1 uppercase tracking-widest font-semibold animate-pulse">
                    {creationStep === 6 ? "Запуск рабочего пространства" : "ИИ-анализатор уголовных дел"}
                  </p>
                </div>

                {/* Progress Bar */}
                <div className="mb-8">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-slate-400 font-medium">Прогресс создания</span>
                    <span className="text-sm font-bold text-emerald-400">{creationProgress}%</span>
                  </div>
                  <div className="w-full bg-slate-800/80 rounded-full h-2.5 p-0.5 border border-slate-700/50">
                    <div 
                      className="bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 h-1.5 rounded-full transition-all duration-300 shadow-[0_0_10px_rgba(16,185,129,0.5)]"
                      style={{ width: `${creationProgress}%` }}
                    />
                  </div>
                </div>

                {/* Simulated Steps */}
                <div className="space-y-4">
                  {[
                    { id: 1, label: "Инициализация ИИ-пространства уголовного дела", icon: Sparkles },
                    { id: 2, label: "Связывание ЕРДР и сохранение в базу данных", icon: Database },
                    { id: 3, label: "Синхронизация с базой законодательства РК", icon: Scale },
                    { id: 4, label: "Активация семантического RAG-поиска норм", icon: BrainCircuit },
                    { id: 5, label: "Подготовка кабинета следователя", icon: FolderOpen }
                  ].map((step) => {
                    const isActive = creationStep === step.id;
                    const isDone = creationStep > step.id;
                    
                    return (
                      <div 
                        key={step.id} 
                        className={`flex items-center gap-3 transition-all duration-300 ${
                          isActive ? "opacity-100 translate-x-1" : isDone ? "opacity-60" : "opacity-30"
                        }`}
                      >
                        <div className="flex-shrink-0">
                          {isDone ? (
                            <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500 flex items-center justify-center shadow-[0_0_8px_rgba(16,185,129,0.4)]">
                              <Check className="w-3.5 h-3.5 text-emerald-400 stroke-[3]" />
                            </div>
                          ) : isActive ? (
                            <div className="w-6 h-6 rounded-full bg-brand-500/20 border border-brand-400 flex items-center justify-center animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.5)]">
                              <step.icon className="w-3 h-3 text-brand-300 animate-spin-slow" />
                            </div>
                          ) : (
                            <div className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-600" />
                            </div>
                          )}
                        </div>
                        <span className={`text-sm ${
                          isActive ? "text-white font-semibold" : isDone ? "text-slate-300" : "text-slate-500"
                        }`}>
                          {step.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 animate-fade-in-up">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Регистрация уголовного дела</h3>
                <form onSubmit={handleCreate} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Номер ЕРДР
                    </label>
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      required
                      className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm
                        focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                      placeholder="Введите номер ЕРДР (например, 276940031000265)"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Фабула уголовного дела
                    </label>
                    <textarea
                      value={newDesc}
                      onChange={(e) => setNewDesc(e.target.value)}
                      rows={3}
                      className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm resize-none
                        focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                      placeholder="Краткое описание фабулы уголовного дела…"
                    />
                  </div>
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowCreate(false)}
                      className="flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium
                        rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Отмена
                    </button>
                    <button
                      type="submit"
                      disabled={creating}
                      className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg
                        hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      Создать
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        )}

        {/* Matters grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 animate-fade-in-up">
              <div className="relative inline-flex items-center justify-center w-24 h-24 mb-6">
                <div className="absolute inset-0 bg-brand-100 rounded-3xl rotate-6" />
                <div className="absolute inset-0 bg-brand-50 rounded-3xl -rotate-3" />
                <div className="relative w-full h-full bg-white rounded-3xl border border-brand-100 flex items-center justify-center shadow-lg">
                  <FolderOpen className="w-10 h-10 text-brand-400" />
                </div>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                {search ? "Ничего не найдено" : "Нет уголовных дел"}
              </h3>
              <p className="text-gray-500 text-sm max-w-sm mx-auto mb-6">
                {search
                  ? "Попробуйте изменить поисковый запрос"
                  : "Зарегистрируйте первое уголовное дело, чтобы начать работу с системой"}
              </p>
              {!search && (
                <button
                  onClick={() => setShowCreate(true)}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-brand-600 text-white text-sm
                    font-semibold rounded-xl hover:bg-brand-700 transition-all hover:shadow-lg hover:-translate-y-0.5"
                >
                  <Plus className="w-4 h-4" />
                  Создать первое дело
                </button>
              )}
            </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((matter) => (
              <div
                key={matter.id}
                onClick={() => router.push(`/matters/${matter.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') router.push(`/matters/${matter.id}`); }}
                className="bg-white rounded-xl border border-gray-200 p-5 text-left cursor-pointer
                  hover:border-brand-300 hover:shadow-md transition-all group relative"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center">
                    <FolderOpen className="w-5 h-5 text-brand-600" />
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => handleDelete(matter.id, matter.name, e)}
                      className="p-1 text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                      title="Удалить"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-brand-500 transition-colors" />
                  </div>
                </div>
                <h3 className="font-semibold text-gray-900 mb-1 line-clamp-1">{matter.name}</h3>
                {matter.description && (
                  <p className="text-sm text-gray-500 line-clamp-2 mb-3">{matter.description}</p>
                )}
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" />
                    {matter.file_count} файл(ов)
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    {new Date(matter.created_at).toLocaleDateString("ru-RU")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
