"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { LegislationDoc, ArticleNode } from "@/types";
import {
  Upload, Trash2, Loader2, Scale, Search, RefreshCw, ChevronDown,
  ChevronRight, FileText, Filter, X, BookOpen, Layers,
} from "lucide-react";

export default function LegislationPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [docs, setDocs] = useState<LegislationDoc[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQ, setSearchQ] = useState("");
  const [filterCat, setFilterCat] = useState("");

  const [showUpload, setShowUpload] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("уголовное право");
  const [uploadYear, setUploadYear] = useState("");
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const [selectedDoc, setSelectedDoc] = useState<LegislationDoc | null>(null);
  const [articles, setArticles] = useState<ArticleNode[]>([]);
  const [loadingArticles, setLoadingArticles] = useState(false);
  const [expandedArt, setExpandedArt] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && (!user || user.role !== "admin")) router.replace("/dashboard");
  }, [user, authLoading, router]);

  const loadData = async () => {
    try {
      const [d, c] = await Promise.all([
        api.listLegislation(searchQ || undefined, filterCat || undefined),
        api.getLegislationCategories(),
      ]);
      setDocs(d as LegislationDoc[]);
      setCategories(c as string[]);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (user?.role === "admin") loadData(); }, [user]);

  useEffect(() => {
    if (!user) return;
    const t = setTimeout(() => {
      setLoading(true);
      api.listLegislation(searchQ || undefined, filterCat || undefined)
        .then((d) => setDocs(d as LegislationDoc[]))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [searchQ, filterCat]);

  const handleUpload = async () => {
    const file = inputRef.current?.files?.[0];
    if (!file || !uploadTitle.trim()) return;
    setUploading(true);
    try {
      await api.uploadLegislation(uploadTitle.trim(), uploadCategory, uploadYear ? parseInt(uploadYear) : null, file);
      setShowUpload(false);
      setUploadTitle(""); setUploadYear("");
      if (inputRef.current) inputRef.current.value = "";
      loadData();
    } catch (e: any) { alert(e.message); }
    finally { setUploading(false); }
  };

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Удалить закон «${title}»?`)) return;
    try { await api.deleteLegislation(id); loadData(); if (selectedDoc?.id === id) setSelectedDoc(null); }
    catch (e: any) { alert(e.message); }
  };

  const handleReindex = async (id: string) => {
    setReindexing(id);
    try { await api.reindexLegislation(id); loadData(); }
    catch (e: any) { alert(e.message); }
    finally { setReindexing(null); }
  };

  const handleSelectDoc = async (doc: LegislationDoc) => {
    setSelectedDoc(doc);
    setLoadingArticles(true);
    setExpandedArt(null);
    try {
      const arts = (await api.getLegislationArticles(doc.id)) as ArticleNode[];
      setArticles(arts);
    } catch { setArticles([]); }
    finally { setLoadingArticles(false); }
  };

  const fmt = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  };

  const fmtDate = (iso: string) => new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });

  if (authLoading) return <div className="min-h-screen flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-brand-600" /></div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Scale className="w-6 h-6 text-brand-600" />Законодательство</h1>
            <p className="text-sm text-gray-500 mt-1">Управление правовой базой для RAG-генерации представлений</p>
          </div>
          <button onClick={() => setShowUpload(true)} className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700">
            <Upload className="w-4 h-4" />Загрузить закон
          </button>
        </div>

        {/* Search & filter */}
        <div className="flex items-center gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input value={searchQ} onChange={(e) => setSearchQ(e.target.value)} placeholder="Поиск по названию…" className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <select value={filterCat} onChange={(e) => setFilterCat(e.target.value)} className="pl-10 pr-8 py-2.5 rounded-lg border border-gray-300 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[200px]">
              <option value="">Все категории</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div className="flex gap-6">
          {/* List */}
          <div className={`${selectedDoc ? "w-1/2" : "w-full"} transition-all`}>
            <div className="bg-white rounded-xl border border-gray-200">
              <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">Документы ({docs.length})</span>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <Layers className="w-3.5 h-3.5" />
                  <span>{docs.reduce((s, d) => s + d.chunk_count, 0)} фрагментов</span>
                </div>
              </div>
              {loading ? (
                <div className="py-12 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-brand-600" /></div>
              ) : docs.length === 0 ? (
                <div className="py-12 text-center text-gray-400"><Scale className="w-10 h-10 mx-auto mb-2 text-gray-300" /><p className="text-sm">Законы не загружены</p></div>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {docs.map((d) => (
                    <li key={d.id} className={`px-5 py-3 flex items-center gap-3 hover:bg-gray-50 cursor-pointer transition-colors ${selectedDoc?.id === d.id ? "bg-brand-50/50" : ""}`} onClick={() => handleSelectDoc(d)}>
                      <div className="w-9 h-9 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0"><BookOpen className="w-4 h-4 text-brand-600" /></div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{d.title}</p>
                        <p className="text-xs text-gray-400">{d.category}{d.year ? ` · ${d.year} г.` : ""} · {d.article_count} статей · {d.chunk_count} фрагм. · {fmt(d.file_size)}</p>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {d.indexed_at && <span className="text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded">индексирован</span>}
                        <button onClick={(e) => { e.stopPropagation(); handleReindex(d.id); }} disabled={reindexing === d.id} className="p-1.5 text-gray-400 hover:text-brand-600 rounded-lg hover:bg-brand-50 disabled:opacity-50" title="Переиндексировать">
                          <RefreshCw className={`w-3.5 h-3.5 ${reindexing === d.id ? "animate-spin" : ""}`} />
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); handleDelete(d.id, d.title); }} className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50" title="Удалить">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Detail panel */}
          {selectedDoc && (
            <div className="w-1/2 bg-white rounded-xl border border-gray-200 flex flex-col max-h-[calc(100vh-220px)]">
              <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-gray-900 truncate">{selectedDoc.title}</h3>
                  <p className="text-xs text-gray-400">{selectedDoc.category} · {selectedDoc.article_count} статей · {fmtDate(selectedDoc.created_at)}</p>
                </div>
                <button onClick={() => setSelectedDoc(null)} className="p-1 text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {loadingArticles ? (
                  <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-brand-600" /></div>
                ) : articles.length === 0 ? (
                  <p className="text-xs text-gray-400 text-center py-8">Статьи не распознаны. Документ индексирован как единый блок.</p>
                ) : (
                  <div className="space-y-1">
                    {articles.map((a) => (
                      <div key={a.number} className="border border-gray-100 rounded-lg">
                        <button onClick={() => setExpandedArt(expandedArt === a.number ? null : a.number)} className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50">
                          {expandedArt === a.number ? <ChevronDown className="w-3.5 h-3.5 text-gray-400" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-400" />}
                          <span className="text-xs font-medium text-brand-700">Ст. {a.number}</span>
                          <span className="text-xs text-gray-600 truncate">{a.title}</span>
                        </button>
                        {expandedArt === a.number && (
                          <div className="px-3 pb-3 pl-8 text-xs text-gray-600 leading-relaxed whitespace-pre-wrap">{a.text.substring(0, 1000)}{a.text.length > 1000 ? "…" : ""}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Upload modal */}
        {showUpload && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Загрузить закон</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Название</label>
                  <input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} placeholder="Уголовный кодекс РК" className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="flex gap-3">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Категория</label>
                    <select value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)} className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500">
                      <option value="уголовное право">Уголовное право</option>
                      <option value="административное право">Административное право</option>
                      <option value="трудовое право">Трудовое право</option>
                      <option value="гражданское право">Гражданское право</option>
                      <option value="техника безопасности">Техника безопасности</option>
                      <option value="иное">Иное</option>
                    </select>
                  </div>
                  <div className="w-24">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Год</label>
                    <input type="number" value={uploadYear} onChange={(e) => setUploadYear(e.target.value)} placeholder="2024" className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Файл</label>
                  <input ref={inputRef} type="file" accept=".docx,.doc,.md,.txt,.rtf,.odt" className="w-full text-sm text-gray-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100" />
                </div>
                <div className="flex gap-3 pt-2">
                  <button onClick={() => setShowUpload(false)} className="flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">Отмена</button>
                  <button onClick={handleUpload} disabled={uploading || !uploadTitle.trim()} className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center justify-center gap-2">
                    {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}Загрузить
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
