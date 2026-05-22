"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import FilesSidebar from "@/components/FilesSidebar";
import ChatPanel from "@/components/ChatPanel";
import DocumentEditor from "@/components/DocumentEditor";
import { Matter, FileItem, ChatMessage, Template, KBStats, RetrievedLaw, CitationCheck, StructuredViolation, QualityReview } from "@/types";
import {
  Loader2,
  MessageSquare,
  FileEdit,
  Settings2,
  Save,
  Sparkles,
  FileText,
  ListChecks,
  Clock,
  Database,
  FilePlus,
  AlertTriangle,
  CheckCircle2,
  BrainCircuit,
  Scale,
  ArrowRight,
  ArrowLeft,
  Check,
} from "lucide-react";

type Tab = "chat" | "editor" | "instructions";

export default function MatterDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const matterId = params.id as string;
  const repIdFromUrl = searchParams.get("rep_id");

  const [matter, setMatter] = useState<Matter | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [kbStats, setKbStats] = useState<KBStats | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [editorContent, setEditorContent] = useState("");
  const [instructions, setInstructions] = useState("");
  const [savingInstructions, setSavingInstructions] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [additionalInstructions, setAdditionalInstructions] = useState("");
  const [showGenDialog, setShowGenDialog] = useState(false);
  const [loading, setLoading] = useState(true);
  const [autoSaving, setAutoSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState("");
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    ok: boolean;
    missing: string[];
    present: string[];
  } | null>(null);
  const [genError, setGenError] = useState("");
  const [wizardStep, setWizardStep] = useState(1);
  const [retrievedLaws, setRetrievedLaws] = useState<RetrievedLaw[]>([]);
  const [selectedLaws, setSelectedLaws] = useState<Set<number>>(new Set());
  const [searchingLaws, setSearchingLaws] = useState(false);
  const [citationCheck, setCitationCheck] = useState<CitationCheck | null>(null);
  const [normUsage, setNormUsage] = useState<{ all_used: boolean; used: { law: string; article: string }[]; unused: { law: string; article: string }[] } | null>(null);
  const [addresseeCheck, setAddresseeCheck] = useState<{ ok: boolean; reason: string } | null>(null);
  const [qualityReview, setQualityReview] = useState<QualityReview | null>(null);
  const [currentRepId, setCurrentRepId] = useState<string | null>(null);
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorLastSaved, setEditorLastSaved] = useState("");
  // Phase 3: Causes & Conditions wizard state
  const [violations, setViolations] = useState<StructuredViolation[]>([{ description: "", responsible: "", link_to_crime: "" }]);
  const [addresseeOverride, setAddresseeOverride] = useState("");
  const [normBindings, setNormBindings] = useState<Record<number, number>>({}); // lawIndex → violationIndex
  const autoSaveTimer = useRef<NodeJS.Timeout | null>(null);
  const editorSaveTimer = useRef<NodeJS.Timeout | null>(null);



  const loadMatter = useCallback(async () => {
    try {
      const [m, f, c, t] = await Promise.all([
        api.getMatter(matterId),
        api.listFiles(matterId),
        api.getChatHistory(matterId),
        api.listTemplates(),
      ]);
      setMatter(m as Matter);
      setFiles(f as FileItem[]);
      setMessages(c as ChatMessage[]);
      setTemplates(t as Template[]);
      setInstructions((m as Matter).custom_instructions || "");

      api.getKBStats().then((s) => setKbStats(s as KBStats)).catch(() => { });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [matterId]);

  useEffect(() => {
    if (matterId) loadMatter();
  }, [matterId, loadMatter]);

  useEffect(() => {
    if (!repIdFromUrl || loading) return;
    (async () => {
      try {
        const rep = (await api.getRepresentation(repIdFromUrl)) as any;
        if (rep && rep.content) {
          setEditorContent(rep.content);
          setCurrentRepId(rep.id);
          setActiveTab("editor");
        }
      } catch {
        // representation not found or no access — ignore
      }
    })();
  }, [repIdFromUrl, loading]);

  const handleEditorChange = useCallback(
    (html: string) => {
      setEditorContent(html);
      if (editorSaveTimer.current) clearTimeout(editorSaveTimer.current);
      editorSaveTimer.current = setTimeout(async () => {
        if (!currentRepId) return;
        setEditorSaving(true);
        try {
          await api.updateRepresentation(currentRepId, { content: html });
          setEditorLastSaved(
            new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
          );
        } catch {
          // silent — will retry on next change
        } finally {
          setEditorSaving(false);
        }
      }, 2000);
    },
    [currentRepId]
  );

  const refreshFiles = useCallback(async () => {
    const f = (await api.listFiles(matterId)) as FileItem[];
    setFiles(f);
  }, [matterId]);

  const refreshMessages = useCallback(async () => {
    const c = (await api.getChatHistory(matterId)) as ChatMessage[];
    setMessages(c);
  }, [matterId]);

  const handleInstructionsChange = (val: string) => {
    setInstructions(val);
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(async () => {
      setAutoSaving(true);
      try {
        await api.updateMatter(matterId, { custom_instructions: val });
        setLastSaved(
          new Date().toLocaleTimeString("ru-RU", {
            hour: "2-digit",
            minute: "2-digit",
          })
        );
      } catch {
      } finally {
        setAutoSaving(false);
      }
    }, 1500);
  };

  const handleSaveInstructions = async () => {
    setSavingInstructions(true);
    try {
      await api.updateMatter(matterId, { custom_instructions: instructions });
      setLastSaved(
        new Date().toLocaleTimeString("ru-RU", {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSavingInstructions(false);
    }
  };

  const handleSearchLaws = async () => {
    setSearchingLaws(true);
    try {
      const laws = (await api.searchLaws(matterId)) as RetrievedLaw[];
      setRetrievedLaws(laws);
      setSelectedLaws(new Set(laws.map((_, i) => i)));
      setWizardStep(3);
    } catch (e: any) {
      alert("Ошибка поиска законов: " + e.message);
    } finally {
      setSearchingLaws(false);
    }
  };

  const handleGenerate = async () => {
    setShowGenDialog(false);
    setGenerating(true);
    setGenError("");
    setValidationResult(null);
    setCitationCheck(null);
    setQualityReview(null);
    setActiveTab("editor");
    try {
      // Filter laws by user selection and pass to backend
      const lawsToSend = retrievedLaws.filter((_, i) => selectedLaws.has(i));

      // Build structured violations (only non-empty)
      const violsToSend = violations.filter(v => v.description.trim());

      // Build norm-violation bindings as string keys for API
      const bindingsToSend: Record<string, number> = {};
      for (const [lawIdx, violIdx] of Object.entries(normBindings)) {
        if (selectedLaws.has(Number(lawIdx)) && violIdx < violsToSend.length) {
          bindingsToSend[String(lawIdx)] = violIdx;
        }
      }

      const res = (await api.generateDocument(
        matterId,
        "",  // template_name не передаётся — ИИ сам определяет структуру по правилам
        additionalInstructions,
        lawsToSend.length > 0 ? lawsToSend : undefined,
        violsToSend.length > 0 ? violsToSend : undefined,
        addresseeOverride.trim() || undefined,
        Object.keys(bindingsToSend).length > 0 ? bindingsToSend : undefined,
      )) as {
        content: string;
        representation_id?: string;
        validation?: { ok: boolean; missing: string[]; present: string[] };
        citation_check?: CitationCheck;
        norm_usage?: { all_used: boolean; used: { law: string; article: string }[]; unused: { law: string; article: string }[] };
        addressee_check?: { ok: boolean; reason: string };
        quality_review?: QualityReview;
      };
      setEditorContent(res.content);
      if (res.representation_id) setCurrentRepId(res.representation_id);
      if (res.validation) setValidationResult(res.validation);
      if (res.citation_check) setCitationCheck(res.citation_check);
      if (res.norm_usage) setNormUsage(res.norm_usage);
      if (res.addressee_check) setAddresseeCheck(res.addressee_check);
      if (res.quality_review) setQualityReview(res.quality_review);
      await refreshMessages();
    } catch (e: any) {
      setGenError(e.message);
    } finally {
      setGenerating(false);
      setWizardStep(1);
    }
  };

  const handleLoadTemplate = async (templateId: string) => {
    setLoadingTemplate(true);
    setActiveTab("editor");
    try {
      const res = await api.getTemplateHtml(templateId);
      setEditorContent(res.html);
    } catch (e: any) {
      alert("Ошибка загрузки шаблона: " + e.message);
    } finally {
      setLoadingTemplate(false);
    }
  };

  const handleLoadBlankRepresentation = async () => {
    setLoadingTemplate(true);
    setActiveTab("editor");
    try {
      const res = await api.getBlankRepresentation();
      setEditorContent(res.html);
    } catch (e: any) {
      alert("Ошибка: " + e.message);
    } finally {
      setLoadingTemplate(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-white relative overflow-hidden font-sans">
        {/* Neon light glows */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />

        <div className="relative flex flex-col items-center max-w-sm px-6 text-center animate-pulse">
          <div className="relative w-20 h-20 mb-6 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border border-brand-500/30 animate-spin-slow" />
            <div className="absolute inset-2 rounded-full border border-dashed border-emerald-500/20 animate-spin" />
            <div className="relative w-12 h-12 rounded-full bg-brand-950 border border-brand-500/30 flex items-center justify-center shadow-[0_0_20px_rgba(0,51,170,0.4)]">
              <BrainCircuit className="w-6 h-6 text-brand-400 animate-pulse" />
            </div>
          </div>
          <h3 className="text-lg font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
            Синхронизация кабинета
          </h3>
          <p className="text-xs text-slate-400 mt-2 leading-relaxed">
            Загрузка материалов уголовного дела и подключение ИИ-анализатора...
          </p>
        </div>
      </div>
    );
  }

  if (!matter) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <div className="flex items-center justify-center py-20">
          <p className="text-gray-500">Дело не найдено</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <Navbar />

      {/* Matter header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-full flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-brand-600 bg-brand-50 px-2 py-0.5 rounded">
                ЕРДР
              </span>
              <h1 className="text-lg font-bold text-gray-900 truncate">
                {matter.name}
              </h1>
            </div>
            {matter.description && (
              <p className="text-sm text-gray-500 truncate mt-0.5">
                {matter.description}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 ml-4">
            {kbStats && kbStats.total_chunks > 0 && (
              <span className="flex items-center gap-1 text-xs text-brand-600 bg-brand-50 px-2 py-1 rounded-lg">
                <Database className="w-3 h-3" />
                RAG: {kbStats.total_chunks} фрагм.
              </span>
            )}
            <button
              onClick={() => setShowGenDialog(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 transition-all shadow-sm"
            >
              <Sparkles className="w-4 h-4" />
              Генерация документа
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 mt-3 -mb-px">
          {[
            { id: "chat" as Tab, label: "Чат с ИИ", icon: MessageSquare },
            {
              id: "editor" as Tab,
              label: "Редактор документа",
              icon: FileEdit,
            },
            {
              id: "instructions" as Tab,
              label: "Инструкции для ИИ",
              icon: Settings2,
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${activeTab === tab.id
                  ? "border-brand-600 text-brand-600 bg-brand-50/50"
                  : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Generate document wizard */}
      {showGenDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl p-6 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-brand-600" />
                Генерация представления
              </h3>
              <div className="flex items-center gap-1 text-xs text-gray-400">
                {[1, 2, 3, 4].map((s, i) => (
                  <span key={s} className="flex items-center gap-1">
                    {i > 0 && <span className="w-3 h-px bg-gray-300" />}
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${wizardStep >= s ? "bg-brand-600 text-white" : "bg-gray-200 text-gray-500"}`}>{s}</span>
                  </span>
                ))}
              </div>
            </div>

            {/* Step 1: Additional instructions */}
            {wizardStep === 1 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="flex items-center gap-1 text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                    <BrainCircuit className="w-3 h-3" />Gemini AI
                  </span>
                  {kbStats && kbStats.total_chunks > 0 && (
                    <span className="flex items-center gap-1 text-xs text-brand-600 bg-brand-50 px-2 py-1 rounded">
                      <Database className="w-3 h-3" />RAG: {kbStats.total_chunks} фрагм.
                    </span>
                  )}
                </div>
                <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3 text-xs text-brand-700 flex items-start gap-2">
                  <Scale className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>На следующем шаге укажите конкретные нарушения и адресата. ИИ использует эти данные для точного документа.</span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Дополнительные указания</label>
                  <textarea value={additionalInstructions} onChange={(e) => setAdditionalInstructions(e.target.value)} rows={3} className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500" placeholder="Укажите конкретные факты, статью УК Республики Казахстан, наименование органа…" />
                </div>
                <div className="flex items-center gap-3 pt-2">
                  <button onClick={() => { setShowGenDialog(false); setWizardStep(1); }} className="flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">Отмена</button>
                  <button onClick={() => setWizardStep(2)} className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 flex items-center justify-center gap-2">
                    <ArrowRight className="w-4 h-4" />
                    Далее — причины и условия
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Causes & Conditions */}
            {wizardStep === 2 && (
              <div className="space-y-4 flex-1 flex flex-col min-h-0">
                <div className="flex items-center gap-2 text-sm text-gray-700">
                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                  <span className="font-medium">Причины и условия преступления</span>
                </div>
                <p className="text-xs text-gray-500">Укажите конкретные нарушения, которые привели к преступлению. ИИ будет использовать только эти нарушения.</p>

                <div className="flex-1 min-h-0 overflow-y-auto space-y-3">
                  {violations.map((v, i) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-3 space-y-2 bg-gray-50/50">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-gray-500">Нарушение {i + 1}</span>
                        {violations.length > 1 && (
                          <button onClick={() => setViolations(prev => prev.filter((_, j) => j !== i))} className="text-xs text-red-500 hover:text-red-700">Удалить</button>
                        )}
                      </div>
                      <input value={v.description} onChange={(e) => { const next = [...violations]; next[i] = { ...next[i], description: e.target.value }; setViolations(next); }} className="w-full px-3 py-2 rounded border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" placeholder="Что нарушено? (напр. Отсутствие освещения дворовой территории)" />
                      <div className="grid grid-cols-2 gap-2">
                        <input value={v.responsible} onChange={(e) => { const next = [...violations]; next[i] = { ...next[i], responsible: e.target.value }; setViolations(next); }} className="px-3 py-2 rounded border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" placeholder="Ответственный (КСК, ТОО...)" />
                        <input value={v.link_to_crime} onChange={(e) => { const next = [...violations]; next[i] = { ...next[i], link_to_crime: e.target.value }; setViolations(next); }} className="px-3 py-2 rounded border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" placeholder="Связь с преступлением" />
                      </div>
                    </div>
                  ))}
                  <button onClick={() => setViolations(prev => [...prev, { description: "", responsible: "", link_to_crime: "" }])} className="w-full py-2 border border-dashed border-gray-300 rounded-lg text-xs text-gray-500 hover:bg-gray-50 flex items-center justify-center gap-1">
                    + Добавить нарушение
                  </button>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Адресат представления (необязательно)</label>
                  <input value={addresseeOverride} onChange={(e) => setAddresseeOverride(e.target.value)} className="w-full px-3 py-2 rounded border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" placeholder="напр. Председателю КСК «Качар» (если пусто — ИИ определит сам)" />
                </div>

                <div className="flex items-center gap-3 pt-2 flex-shrink-0">
                  <button onClick={() => setWizardStep(1)} className="flex items-center justify-center gap-1 flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
                    <ArrowLeft className="w-4 h-4" />Назад
                  </button>
                  <button onClick={handleSearchLaws} disabled={searchingLaws} className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 flex items-center justify-center gap-2">
                    {searchingLaws ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                    Далее — поиск законов
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Retrieved laws selection + norm-violation binding */}
            {wizardStep === 3 && (
              <div className="space-y-4 flex-1 flex flex-col min-h-0">
                <div className="flex items-center gap-2 text-sm text-gray-700">
                  <Scale className="w-4 h-4 text-brand-600" />
                  <span className="font-medium">Найденные нормы закона ({retrievedLaws.length})</span>
                </div>
                <p className="text-xs text-gray-500">Снимите отметку с нерелевантных норм. Привяжите каждую норму к нарушению из шага 2.</p>
                <div className="flex-1 min-h-0 overflow-y-auto border border-gray-200 rounded-lg divide-y divide-gray-100">
                  {retrievedLaws.length === 0 ? (
                    <p className="p-4 text-xs text-gray-400 text-center">Нормативные акты не найдены в базе законодательства.</p>
                  ) : retrievedLaws.map((law, i) => {
                    const rawScore = typeof law.score === 'number' ? law.score : 0;
                    const pct = Math.round(Math.max(1, Math.min(99, rawScore * 100)));
                    const pctColor = pct >= 70 ? "text-green-600 bg-green-50" : pct >= 50 ? "text-blue-600 bg-blue-50" : pct >= 35 ? "text-amber-600 bg-amber-50" : "text-gray-500 bg-gray-100";
                    const cleanText = law.text.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\*([^*]+)\*/g, '$1').replace(/#{1,6}\s*/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/^[-*+]\s+/gm, '• ').replace(/`([^`]+)`/g, '$1').replace(/\n{2,}/g, '\n').trim();
                    const filledViols = violations.filter(v => v.description.trim());
                    return (
                      <div key={i} className="p-4 hover:bg-gray-50">
                        <label className="flex items-start gap-3 cursor-pointer group">
                          <input type="checkbox" checked={selectedLaws.has(i)} onChange={() => {
                            setSelectedLaws((prev) => { const next = new Set(prev); if (next.has(i)) next.delete(i); else next.add(i); return next; });
                          }} className="mt-1 rounded text-brand-600 focus:ring-brand-500 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start gap-2 flex-wrap">
                              <span className="text-sm font-medium text-gray-900">{law.law_title}</span>
                              {law.article_number && <span className="text-[11px] bg-brand-50 text-brand-700 px-2 py-0.5 rounded font-medium whitespace-nowrap">ст.{law.article_number}</span>}
                              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ml-auto whitespace-nowrap ${pctColor}`}>{pct}%</span>
                            </div>
                            <p className="text-xs text-gray-600 mt-1.5 leading-relaxed whitespace-pre-line line-clamp-3 group-hover:line-clamp-none">{cleanText.substring(0, 400)}</p>
                          </div>
                        </label>
                        {selectedLaws.has(i) && filledViols.length > 0 && (
                          <div className="mt-2 ml-8">
                            <select value={normBindings[i] ?? ""} onChange={(e) => { setNormBindings(prev => ({ ...prev, [i]: e.target.value === "" ? undefined! : Number(e.target.value) })); }} className="text-xs px-2 py-1.5 rounded border border-gray-300 bg-white focus:ring-2 focus:ring-brand-500 w-full">
                              <option value="">— Привязать к нарушению —</option>
                              {filledViols.map((v, vi) => (
                                <option key={vi} value={vi}>Нарушение {vi + 1}: {v.description.substring(0, 60)}</option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center gap-3 pt-2 flex-shrink-0">
                  <button onClick={() => setWizardStep(2)} className="flex items-center justify-center gap-1 flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
                    <ArrowLeft className="w-4 h-4" />Назад
                  </button>
                  <button onClick={() => setWizardStep(4)} className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 flex items-center justify-center gap-2">
                    <ArrowRight className="w-4 h-4" />Превью ({selectedLaws.size} норм)
                  </button>
                </div>
              </div>
            )}

            {/* Step 4: Preview skeleton before generation */}
            {wizardStep === 4 && (() => {
              const filledViols = violations.filter(v => v.description.trim());
              const selLaws = retrievedLaws.filter((_, i) => selectedLaws.has(i));
              return (
                <div className="space-y-4 flex-1 flex flex-col min-h-0">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <FileText className="w-4 h-4 text-brand-600" />
                    <span className="font-medium">Превью структуры документа</span>
                  </div>
                  <div className="flex-1 min-h-0 overflow-y-auto border border-gray-200 rounded-lg p-4 bg-gray-50/50 space-y-3 text-sm">
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase">Адресат</span>
                      <p className="text-gray-800 mt-0.5">{addresseeOverride.trim() || "ИИ определит автоматически по фабуле дела"}</p>
                    </div>
                    <hr className="border-gray-200" />
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase">Выявленные нарушения ({filledViols.length})</span>
                      {filledViols.length === 0 ? (
                        <p className="text-xs text-gray-400 mt-1">Не указаны — ИИ определит из фабулы</p>
                      ) : filledViols.map((v, i) => {
                        const boundLaw = Object.entries(normBindings).find(([, vi]) => vi === i);
                        const lawInfo = boundLaw ? retrievedLaws[Number(boundLaw[0])] : null;
                        return (
                          <div key={i} className="mt-1.5 flex items-start gap-2">
                            <span className="text-brand-600 font-bold text-xs mt-0.5">{i + 1}.</span>
                            <div>
                              <p className="text-gray-800">{v.description}</p>
                              {v.responsible && <p className="text-xs text-gray-500">Ответственный: {v.responsible}</p>}
                              {lawInfo ? (
                                <p className="text-xs text-brand-600 mt-0.5">→ Норма: {lawInfo.law_title} ст.{lawInfo.article_number}</p>
                              ) : (
                                <p className="text-xs text-amber-500 mt-0.5">⚠ Норма не привязана</p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <hr className="border-gray-200" />
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase">Нормы закона ({selLaws.length})</span>
                      {selLaws.map((law, i) => (
                        <p key={i} className="text-xs text-gray-700 mt-1">• {law.law_title} ст.{law.article_number}</p>
                      ))}
                    </div>
                    {additionalInstructions.trim() && (
                      <>
                        <hr className="border-gray-200" />
                        <div>
                          <span className="text-xs font-semibold text-gray-500 uppercase">Доп. указания</span>
                          <p className="text-xs text-gray-600 mt-0.5">{additionalInstructions}</p>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-3 pt-2 flex-shrink-0">
                    <button onClick={() => setWizardStep(3)} className="flex items-center justify-center gap-1 flex-1 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
                      <ArrowLeft className="w-4 h-4" />Назад
                    </button>
                    <button onClick={handleGenerate} className="flex-1 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 flex items-center justify-center gap-2">
                      <Sparkles className="w-4 h-4" />Сгенерировать документ
                    </button>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        <FilesSidebar
          matterId={matterId}
          files={files}
          onFileUploaded={refreshFiles}
        />

        <div className="flex-1 flex overflow-hidden">
          {activeTab === "chat" && (
            <div className="flex-1">
              <ChatPanel
                matterId={matterId}
                messages={messages}
                onMessagesUpdated={refreshMessages}
              />
            </div>
          )}

          {activeTab === "editor" && (
            <div className="flex-1 flex overflow-hidden">
              {/* Left panel — template list */}
              <div className="w-64 bg-white border-r border-gray-200 flex flex-col overflow-y-auto">
                <div className="p-4 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
                    <ListChecks className="w-4 h-4 text-brand-600" />
                    Шаблоны
                  </h3>
                </div>
                <div className="p-3 space-y-1 flex-1">
                  {/* Blank representation button */}
                  <button
                    onClick={handleLoadBlankRepresentation}
                    disabled={loadingTemplate}
                    className="w-full text-left px-3 py-2.5 rounded-lg text-sm hover:bg-green-50 text-green-700 transition-colors flex items-center gap-2 border border-dashed border-green-300"
                  >
                    <FilePlus className="w-4 h-4 text-green-500 flex-shrink-0" />
                    <span className="truncate">Пустой бланк ст.200</span>
                  </button>

                  {templates.length === 0 ? (
                    <p className="text-xs text-gray-400 text-center mt-4">
                      Бланки не загружены
                    </p>
                  ) : (
                    templates.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => handleLoadTemplate(t.id)}
                        disabled={loadingTemplate}
                        className="w-full text-left px-3 py-2.5 rounded-lg text-sm hover:bg-brand-50 text-gray-600 hover:text-brand-700 transition-colors flex items-center gap-2"
                      >
                        <FileText className="w-4 h-4 text-brand-400 flex-shrink-0" />
                        <span className="truncate">{t.name}</span>
                      </button>
                    ))
                  )}
                </div>
                <div className="p-4 border-t border-gray-100">
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <Clock className="w-3.5 h-3.5" />
                    <span>
                      {generating
                        ? "Генерация документа…"
                        : loadingTemplate
                          ? "Загрузка шаблона…"
                          : editorContent
                            ? "Документ готов к редактированию"
                            : "Выберите шаблон или сгенерируйте"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Right panel — editor */}
              <div className="flex-1 p-4 overflow-hidden flex flex-col gap-2">
                {/* Validation banner */}
                {validationResult && !generating && (
                  <div
                    className={`flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs ${validationResult.ok
                        ? "bg-green-50 border border-green-200 text-green-800"
                        : "bg-amber-50 border border-amber-200 text-amber-800"
                      }`}
                  >
                    {validationResult.ok ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                    )}
                    <div>
                      <p className="font-medium">
                        {validationResult.ok
                          ? "Документ прошёл проверку: все обязательные разделы присутствуют"
                          : `Внимание: отсутствуют разделы (${validationResult.missing.length})`}
                      </p>
                      {!validationResult.ok && (
                        <p className="mt-0.5">
                          Не найдены:{" "}
                          {validationResult.missing
                            .map((s) =>
                            ({
                              дата_место: "дата/место",
                              ердр: "номер ЕРДР",
                              статья_ук: "статья УК Республики Казахстан",
                              обстоятельства: "обстоятельства",
                              нормативные_акты: "ст.200 УПК Республики Казахстан",
                              предлагаю: "«ПРЕДЛАГАЮ»",
                              срок: "месячный срок",
                            }[s] || s)
                            )
                            .join(", ")}
                          . Отредактируйте документ вручную или перегенерируйте
                          с уточнёнными указаниями.
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Citation check */}
                {citationCheck && !citationCheck.unverified.length && citationCheck.cited.length > 0 && !generating && (
                  <div className="flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs bg-blue-50 border border-blue-200 text-blue-800">
                    <Scale className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                    <p>Процитировано статей: {citationCheck.cited.join(", ")}. Все ссылки подтверждены базой законодательства.</p>
                  </div>
                )}
                {citationCheck && citationCheck.unverified.length > 0 && !generating && (
                  <div className="flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs bg-amber-50 border border-amber-200 text-amber-800">
                    <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                    <p>Непроверенные ссылки (отсутствуют в базе): ст. {citationCheck.unverified.join(", ")}. Проверьте вручную или загрузите соответствующий закон.</p>
                  </div>
                )}

                {/* Norm usage check */}
                {normUsage && !generating && (
                  <div className={`flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs ${normUsage.all_used ? "bg-green-50 border border-green-200 text-green-800" : "bg-red-50 border border-red-200 text-red-800"}`}>
                    {normUsage.all_used ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                    )}
                    <div>
                      <p className="font-medium">
                        {normUsage.all_used
                          ? `Все ${normUsage.used.length} выбранных норм использованы в документе`
                          : `${normUsage.unused.length} из ${normUsage.used.length + normUsage.unused.length} норм НЕ использованы в документе!`}
                      </p>
                      {!normUsage.all_used && normUsage.unused.length > 0 && (
                        <ul className="mt-1 space-y-0.5">
                          {normUsage.unused.map((n, i) => (
                            <li key={i}>❌ {n.law} — {n.article}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}

                {/* Addressee check */}
                {addresseeCheck && !addresseeCheck.ok && !generating && (
                  <div className="flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs bg-red-50 border border-red-200 text-red-800">
                    <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">⚠️ Неправильный адресат</p>
                      <p className="mt-0.5">{addresseeCheck.reason}</p>
                    </div>
                  </div>
                )}

                {/* Deep legal-soundness review */}
                {qualityReview && qualityReview.available && !generating && (
                  <div
                    className={`flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs ${qualityReview.overall === "good"
                        ? "bg-green-50 border border-green-200 text-green-800"
                        : qualityReview.overall === "warnings"
                          ? "bg-amber-50 border border-amber-200 text-amber-800"
                          : "bg-red-50 border border-red-200 text-red-800"
                      }`}
                  >
                    {qualityReview.overall === "good" ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                    ) : (
                      <BrainCircuit className={`w-4 h-4 flex-shrink-0 mt-0.5 ${qualityReview.overall === "poor" ? "text-red-500" : "text-amber-500"}`} />
                    )}
                    <div className="flex-1">
                      <p className="font-medium">
                        {qualityReview.overall === "good"
                          ? "Юридическая проверка пройдена: причинно-следственная связь, меры и адресат согласованы"
                          : qualityReview.overall === "poor"
                            ? "Юридическая проверка: выявлены серьёзные замечания"
                            : "Юридическая проверка: есть замечания к содержанию"}
                      </p>
                      {!qualityReview.causal_chain_ok && (
                        <p className="mt-0.5">• Причинно-следственная связь изложена недостаточно явно</p>
                      )}
                      {!qualityReview.measures_mapped_ok && (
                        <p className="mt-0.5">• Не каждому нарушению соответствует мера в разделе ПРЕДЛАГАЮ</p>
                      )}
                      {!qualityReview.addressee_reasoning_ok && (
                        <p className="mt-0.5">• Выбор адресата слабо обоснован фабулой</p>
                      )}
                      {!qualityReview.grounding_ok && (
                        <p className="mt-0.5">• Возможны реквизиты, не подтверждённые материалами дела</p>
                      )}
                      {qualityReview.issues.length > 0 && (
                        <ul className="mt-1 space-y-0.5">
                          {qualityReview.issues.map((it, i) => (
                            <li key={i}>
                              <span className="font-semibold">
                                {it.severity === "high" ? "⛔" : it.severity === "medium" ? "⚠️" : "ℹ️"}
                              </span>{" "}
                              {it.text}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}

                {/* Generation error */}
                {genError && !generating && (
                  <div className="flex items-start gap-2 px-4 py-2.5 rounded-lg text-xs bg-red-50 border border-red-200 text-red-800">
                    <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">Ошибка генерации</p>
                      <p className="mt-0.5">{genError}</p>
                      <p className="mt-1 text-red-600">
                        Попробуйте: уточнить дополнительные указания, проверить
                        загруженные файлы дела, или изменить настройки модели в
                        разделе «Настройки».
                      </p>
                    </div>
                  </div>
                )}

                <div className="flex-1 overflow-hidden">
                  {generating || loadingTemplate ? (
                    <div className="h-full flex flex-col items-center justify-center bg-white rounded-xl border border-gray-200">
                      <Loader2 className="w-8 h-8 animate-spin text-brand-600 mb-4" />
                      <p className="text-sm font-medium text-gray-700">
                        {generating
                          ? "Gemini генерирует представление…"
                          : "Загрузка шаблона…"}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {generating
                          ? "Анализ фактов дела, базы знаний и нормативных требований"
                          : "Извлечение структуры документа"}
                      </p>
                    </div>
                  ) : (
                    <DocumentEditor
                      content={editorContent}
                      onContentChange={handleEditorChange}
                      saving={editorSaving}
                      lastSaved={editorLastSaved}
                    />
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === "instructions" && (
            <div className="flex-1 p-6 overflow-y-auto">
              <div className="max-w-2xl">
                <h3 className="text-lg font-semibold text-gray-900 mb-1">
                  Инструкции для ИИ
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Укажите конкретные указания для ИИ при работе с данным делом.
                  Эти инструкции передаются модели при каждом запросе.
                </p>
                <textarea
                  value={instructions}
                  onChange={(e) => handleInstructionsChange(e.target.value)}
                  rows={14}
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent leading-relaxed"
                  placeholder={`Пример:\n\n- Юрисдикция: Республика Казахстан\n- Тон: Формальный\n- Область права: уголовное право\n- Статья: ст. 188 УК Республики Казахстан\n- Представление: по ст.200 УПК Республики Казахстан\n- Ключевые даты и обстоятельства`}
                />
                <div className="flex items-center justify-between mt-4">
                  <div className="text-xs text-gray-400">
                    {autoSaving && (
                      <span className="flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />{" "}
                        Автосохранение…
                      </span>
                    )}
                    {lastSaved && !autoSaving && (
                      <span>Сохранено в {lastSaved}</span>
                    )}
                  </div>
                  <button
                    onClick={handleSaveInstructions}
                    disabled={savingInstructions}
                    className="flex items-center gap-2 px-4 py-2.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
                  >
                    {savingInstructions ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    Сохранить
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
