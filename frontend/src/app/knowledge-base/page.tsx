"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { KBDocument, KBStats } from "@/types";
import {
  Upload,
  Trash2,
  Loader2,
  FileText,
  Database,
  AlertCircle,
  CheckCircle,
  BookOpen,
  Layers,
  Info,
} from "lucide-react";

interface UploadStatus {
  name: string;
  status: "uploading" | "done" | "error" | "skipped";
  error?: string;
}

export default function KnowledgeBasePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [stats, setStats] = useState<KBStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploads, setUploads] = useState<UploadStatus[]>([]);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!authLoading && (!user || user.role !== "admin")) {
      router.replace("/dashboard");
    }
  }, [user, authLoading, router]);

  const loadData = async () => {
    try {
      const [docs, st] = await Promise.all([
        api.listKBDocuments(),
        api.getKBStats(),
      ]);
      setDocuments(docs as KBDocument[]);
      setStats(st as KBStats);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === "admin") loadData();
  }, [user]);

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setUploading(true);

    const files = Array.from(fileList);
    const statuses: UploadStatus[] = files.map((f) => ({
      name: f.name,
      status: "uploading" as const,
    }));
    setUploads(statuses);

    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const ext = f.name.split(".").pop()?.toLowerCase();
      if (!ext || !["md", "txt", "markdown"].includes(ext)) {
        setUploads((prev) =>
          prev.map((u, idx) =>
            idx === i
              ? { ...u, status: "skipped", error: "Неподдерживаемый формат" }
              : u
          )
        );
        continue;
      }
      try {
        await api.uploadKBDocument(f);
        setUploads((prev) =>
          prev.map((u, idx) => (idx === i ? { ...u, status: "done" } : u))
        );
      } catch (e: any) {
        setUploads((prev) =>
          prev.map((u, idx) =>
            idx === i ? { ...u, status: "error", error: e.message } : u
          )
        );
      }
    }

    setUploading(false);
    loadData();
    setTimeout(() => setUploads([]), 6000);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Удалить документ «${name}» из базы знаний?`)) return;
    try {
      await api.deleteKBDocument(id);
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Database className="w-6 h-6 text-brand-600" />
              База знаний — ст.200 УПК РК
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Загрузите документы-представления для обучения RAG-системы
            </p>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center">
                <BookOpen className="w-5 h-5 text-brand-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.total_documents}
                </p>
                <p className="text-xs text-gray-500">Документов</p>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-accent-50 flex items-center justify-center">
                <Layers className="w-5 h-5 text-accent-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.total_chunks}
                </p>
                <p className="text-xs text-gray-500">Векторных фрагментов</p>
              </div>
            </div>
          </div>
        )}

        {/* Info box */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 flex gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">Как работает RAG</p>
            <p>
              Загруженные документы разбиваются на фрагменты, векторизуются и
              индексируются. При генерации представления система находит наиболее
              релевантные фрагменты и передаёт их модели как контекст, повышая
              точность и соответствие стилю ст.200 УПК РК.
            </p>
          </div>
        </div>

        {/* Upload area */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">
            Загрузить документы
          </h2>
          <div className="relative border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-brand-400 transition-colors">
            {uploading ? (
              <Loader2 className="w-8 h-8 mx-auto text-brand-600 animate-spin" />
            ) : (
              <Upload className="w-8 h-8 mx-auto text-gray-400" />
            )}
            <p className="text-sm text-gray-600 mt-2 font-medium">
              Перетащите файлы .md / .txt или нажмите для выбора
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Поддерживается пакетная загрузка (50+ файлов). Документы должны
              содержать представления по ст.200 УПК РК.
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".md,.txt,.markdown"
              className="absolute inset-0 opacity-0 cursor-pointer"
              onChange={(e) => handleUpload(e.target.files)}
            />
          </div>

          {uploads.length > 0 && (
            <div className="mt-4 max-h-48 overflow-y-auto space-y-1">
              {uploads.map((u, i) => (
                <div key={i} className="flex items-center gap-2 text-xs py-1">
                  {u.status === "uploading" && (
                    <Loader2 className="w-3 h-3 animate-spin text-brand-600 flex-shrink-0" />
                  )}
                  {u.status === "done" && (
                    <CheckCircle className="w-3 h-3 text-green-500 flex-shrink-0" />
                  )}
                  {u.status === "error" && (
                    <AlertCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
                  )}
                  {u.status === "skipped" && (
                    <AlertCircle className="w-3 h-3 text-amber-500 flex-shrink-0" />
                  )}
                  <span
                    className={`truncate ${
                      u.status === "error"
                        ? "text-red-600"
                        : u.status === "skipped"
                        ? "text-amber-600"
                        : "text-gray-600"
                    }`}
                  >
                    {u.name}
                  </span>
                  {u.error && (
                    <span className="text-red-500 truncate" title={u.error}>
                      — {u.error}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Document list */}
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-sm font-semibold text-gray-900">
              Загруженные документы ({documents.length})
            </h2>
          </div>

          {documents.length === 0 ? (
            <div className="py-12 text-center text-gray-400">
              <FileText className="w-10 h-10 mx-auto mb-2 text-gray-300" />
              <p className="text-sm">
                База знаний пуста. Загрузите документы-представления.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="px-6 py-3 flex items-center gap-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="w-9 h-9 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                    <FileText className="w-4 h-4 text-brand-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {doc.title}
                    </p>
                    <p className="text-xs text-gray-400">
                      {doc.filename} · {formatSize(doc.file_size)} ·{" "}
                      {doc.chunk_count} фрагм. · {formatDate(doc.created_at)}
                    </p>
                  </div>
                  <span className="text-xs bg-brand-50 text-brand-700 px-2 py-0.5 rounded font-medium">
                    ст.{doc.article}
                  </span>
                  <button
                    onClick={() => handleDelete(doc.id, doc.title)}
                    className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded-lg hover:bg-red-50"
                    title="Удалить"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
