"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { RepresentationItem } from "@/types";
import {
  Loader2, FileCheck, Trash2, ExternalLink, ChevronDown, Filter,
  FileText, Clock, CheckCircle2, Send, PenLine,
} from "lucide-react";

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: "Черновик", color: "bg-gray-100 text-gray-700" },
  finalized: { label: "Завершён", color: "bg-green-100 text-green-700" },
  sent: { label: "Отправлен", color: "bg-blue-100 text-blue-700" },
};

const STATUS_ICONS: Record<string, React.ElementType> = {
  draft: PenLine,
  finalized: CheckCircle2,
  sent: Send,
};

export default function RepresentationsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [reps, setReps] = useState<RepresentationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [user, authLoading, router]);

  const loadData = async () => {
    try {
      const data = (await api.listRepresentations(undefined, filterStatus || undefined)) as RepresentationItem[];
      setReps(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (user) loadData(); }, [user, filterStatus]);

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Удалить представление «${title}»?`)) return;
    try { await api.deleteRepresentation(id); loadData(); }
    catch (e: any) { alert(e.message); }
  };

  const handleOpen = (rep: RepresentationItem) => {
    router.push(`/matters/${rep.matter_id}?rep_id=${rep.id}`);
  };

  const fmtDate = (iso: string) =>
    new Date(iso).toLocaleDateString("ru-RU", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });

  if (authLoading || !user) {
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
              <FileCheck className="w-6 h-6 text-brand-600" />
              Представления
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Все сгенерированные представления по ст.200 УПК РК
            </p>
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="pl-10 pr-8 py-2.5 rounded-lg border border-gray-300 text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[170px]"
            >
              <option value="">Все статусы</option>
              <option value="draft">Черновики</option>
              <option value="finalized">Завершённые</option>
              <option value="sent">Отправленные</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200">
          {loading ? (
            <div className="py-16 flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
            </div>
          ) : reps.length === 0 ? (
            <div className="py-16 text-center text-gray-400">
              <FileText className="w-10 h-10 mx-auto mb-2 text-gray-300" />
              <p className="text-sm">Представления ещё не создавались</p>
              <p className="text-xs mt-1">Перейдите в уголовное дело и нажмите «Генерация документа»</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {reps.map((r) => {
                const st = STATUS_LABELS[r.status] || STATUS_LABELS.draft;
                const Icon = STATUS_ICONS[r.status] || PenLine;
                return (
                  <li
                    key={r.id}
                    className="px-5 py-4 flex items-center gap-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => handleOpen(r)}
                  >
                    <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                      <Icon className="w-5 h-5 text-brand-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {r.title || "Без названия"}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${st.color}`}>
                          {st.label}
                        </span>
                        <span className="flex items-center gap-1 text-xs text-gray-400">
                          <Clock className="w-3 h-3" />
                          {fmtDate(r.updated_at)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleOpen(r); }}
                        className="p-1.5 text-gray-400 hover:text-brand-600 rounded-lg hover:bg-brand-50"
                        title="Открыть"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(r.id, r.title); }}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50"
                        title="Удалить"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
