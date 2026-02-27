"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Template } from "@/types";
import {
  Plus,
  FileStack,
  Trash2,
  Loader2,
  Upload,
  FileText,
  Calendar,
  ShieldAlert,
} from "lucide-react";

export default function TemplatesPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
    if (!authLoading && user && user.role !== "admin") router.replace("/dashboard");
  }, [user, authLoading, router]);

  const loadTemplates = () => {
    api
      .listTemplates()
      .then((data) => setTemplates(data as Template[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (user?.role === "admin") loadTemplates();
  }, [user]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !newName.trim()) return;
    setUploading(true);
    try {
      await api.uploadTemplate(newName.trim(), newDesc.trim(), file);
      setShowUpload(false);
      setNewName("");
      setNewDesc("");
      if (fileRef.current) fileRef.current.value = "";
      loadTemplates();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Удалить шаблон «${name}»?`)) return;
    try {
      await api.deleteTemplate(id);
      loadTemplates();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  };

  if (authLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
      </div>
    );
  }

  if (user.role !== "admin") {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex flex-col items-center justify-center py-20">
          <ShieldAlert className="w-12 h-12 text-red-400 mb-3" />
          <p className="text-lg font-medium text-gray-700">Доступ запрещён</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Шаблоны документов</h1>
            <p className="text-sm text-gray-500 mt-1">
              Загрузка и управление шаблонами для генерации документов
            </p>
          </div>
          <button
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-xl hover:bg-brand-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Загрузить шаблон
          </button>
        </div>

        {/* Upload dialog */}
        {showUpload && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-brand-600" />
                Загрузка шаблона
              </h3>
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Название</label>
                  <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="Например: Представление прокурора"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
                  <textarea
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    rows={2}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="Краткое описание шаблона…"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Файл шаблона</label>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".docx,.doc,.rtf,.odt,.txt"
                    required
                    className="w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
                  />
                  <p className="text-xs text-gray-400 mt-1">DOCX, RTF, ODT или TXT</p>
                </div>
                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowUpload(false)}
                    className="flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50"
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    disabled={uploading}
                    className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {uploading && <Loader2 className="w-4 h-4 animate-spin" />}
                    Загрузить
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Templates list */}
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-20">
            <FileStack className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 font-medium">Шаблоны ещё не загружены</p>
            <p className="text-sm text-gray-400 mt-1">Загрузите DOCX/RTF шаблон для начала работы</p>
          </div>
        ) : (
          <div className="space-y-3">
            {templates.map((t) => (
              <div
                key={t.id}
                className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4 hover:border-brand-300 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5 text-brand-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900">{t.name}</h3>
                  {t.description && (
                    <p className="text-sm text-gray-500 truncate">{t.description}</p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-gray-400 mt-1">
                    <span>{t.file_type.toUpperCase()}</span>
                    <span>{formatSize(t.file_size)}</span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {new Date(t.created_at).toLocaleDateString("ru-RU")}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(t.id, t.name)}
                  className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                  title="Удалить"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
