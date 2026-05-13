"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { Template } from "@/types";
import {
  Plus,
  Trash2,
  Loader2,
  Upload,
  Calendar,
  ShieldAlert,
  Download,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Search,
  FolderOpen,
} from "lucide-react";

/* ─────────────────────── Static Templates from SD ─────────────────────── */

interface SDTemplate {
  id: number;
  filename: string;
  title: string;
  category: string;
  description: string;
}

const SD_TEMPLATES: SDTemplate[] = [
  { id: 1, filename: "1 ДУИС.DOCX", title: "ДУИС", category: "Пенитенциарная система", description: "Представление в Департамент уголовно-исполнительной системы" },
  { id: 2, filename: "2 ресторан-2.docx", title: "Ресторан", category: "Общественное питание", description: "Представление по фактам нарушений в ресторане" },
  { id: 3, filename: "3 адвокат-2.docx", title: "Адвокат", category: "Адвокатура", description: "Представление по нарушениям адвокатской деятельности" },
  { id: 4, filename: "4 акимат.docx", title: "Акимат", category: "Государственные органы", description: "Представление в акимат по выявленным нарушениям" },
  { id: 5, filename: "5 ТОО Торговый дом.docx", title: "ТОО Торговый дом", category: "Предпринимательство", description: "Представление в адрес ТОО Торговый дом" },
  { id: 6, filename: "6 Банки(1).docx", title: "Банки", category: "Финансовый сектор", description: "Представление в банковские организации" },
  { id: 7, filename: "7. образ предст 297 ТК, КНБ, МЗ.docx", title: "Ст. 297 ТК, КНБ, МЗ", category: "Трудовое/КНБ/МЗ", description: "Образец представления по ст. 297 ТК Республики Казахстан в КНБ и МЗ" },
  { id: 8, filename: "8. Образец МКИ и МЦРиАП.docx", title: "МКИ и МЦРиАП", category: "Информатизация", description: "Образец представления в МКИ и Министерство цифрового развития" },
  { id: 9, filename: "9. Образец МКИ по суицидам 2.docx", title: "МКИ по суицидам", category: "Информатизация", description: "Образец представления в МКИ по фактам суицида" },
  { id: 10, filename: "10. Образец охрана рус.docx", title: "Охрана", category: "Безопасность", description: "Образец представления по охранной деятельности" },
  { id: 11, filename: "11. Образец предст  казпочта 4.docx", title: "Казпочта", category: "Почтовая связь", description: "Образец представления в АО «Казпочта»" },
  { id: 12, filename: "12. в ПС и гос.служ.docx", title: "ПС и гос. служба", category: "Государственная служба", description: "Представление в правоохранительную и государственную службу" },
  { id: 13, filename: "13. выезд на встречную.docx", title: "Выезд на встречную", category: "ДТП", description: "Представление по фактам выезда на встречную полосу" },
  { id: 14, filename: "14. ДУИС, на отправку.DOCX", title: "ДУИС (на отправку)", category: "Пенитенциарная система", description: "Представление в ДУИС для отправки" },
  { id: 15, filename: "15. образ предст по иностр.docx", title: "По иностранцам", category: "Миграция", description: "Образец представления по иностранным гражданам" },
  { id: 16, filename: "16. Образец по выпадению.docx", title: "По выпадению", category: "Несчастные случаи", description: "Образец представления по фактам выпадения" },
  { id: 17, filename: "17. Образец пожарной без..docx", title: "Пожарная безопасность", category: "Безопасность", description: "Образец представления по пожарной безопасности" },
  { id: 18, filename: "18. опрокидывание.docx", title: "Опрокидывание", category: "ДТП", description: "Представление по ДТП — опрокидывание ТС" },
  { id: 19, filename: "19. по минивэнам.docx", title: "По минивэнам", category: "ДТП", description: "Представление по фактам ДТП с минивэнами" },
  { id: 20, filename: "20. по тех.осмотру.docx", title: "Тех. осмотр", category: "Транспорт", description: "Представление по нарушениям технического осмотра" },
  { id: 21, filename: "21. Представление по Вейпам (1).docx", title: "По вейпам", category: "Общественный порядок", description: "Представление по фактам распространения вейпов" },
  { id: 22, filename: "22. ресторан, на отправку.docx", title: "Ресторан (на отправку)", category: "Общественное питание", description: "Представление по ресторану для отправки" },
  { id: 23, filename: "23. по 156 оконч.docx", title: "По ст. 156", category: "Уголовное право", description: "Представление по ст. 156 УК Республики Казахстан (окончательная версия)" },
  { id: 24, filename: "24. Представ Акимат рус.docx", title: "Акимат (рус.)", category: "Государственные органы", description: "Представление в акимат на русском языке" },
  { id: 25, filename: "25. Представ. Мин транспорт рус.docx", title: "Мин. транспорт", category: "Транспорт", description: "Представление в Министерство транспорта Республики Казахстан" },
  { id: 26, filename: "26. в ДГД по аренде кварт.docx", title: "ДГД по аренде квартир", category: "Налоги", description: "Представление в ДГД по фактам незаконной аренды квартир" },
];

const INSTRUCTION_FILE = "00. инструкция 200 обн(1).docx";

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<"sd" | "custom">("sd");
  const [expandedInstr, setExpandedInstr] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const loadTemplates = () => {
    api
      .listTemplates()
      .then((data) => setTemplates(data as Template[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTemplates();
  }, []);

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

  /** Build download URL for a static SD template file in /public/templates-sd/ */
  const getSDDownloadUrl = (filename: string) =>
    `/templates-sd/${encodeURIComponent(filename)}`;

  /* Filter SD templates */
  const categories = Array.from(new Set(SD_TEMPLATES.map((t) => t.category))).sort();
  const filteredSD = SD_TEMPLATES.filter((t) => {
    const matchesSearch =
      !searchQuery ||
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === "all" || t.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });



  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-6 py-8">

        {/* Page header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center">
              <FolderOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Шаблоны документов</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Образцы представлений Следственного департамента
              </p>
            </div>
          </div>
        </div>

        {/* ─── Instruction Card ─── */}
        <div className="mb-6">
          <div
            className={`bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl overflow-hidden transition-all duration-300 ${expandedInstr ? "shadow-lg" : "shadow-sm"}`}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => setExpandedInstr(!expandedInstr)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setExpandedInstr(!expandedInstr); }}
              className="w-full flex items-center justify-between px-6 py-4 text-left cursor-pointer select-none"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Инструкция по ст. 200 УПК Республики Казахстан</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Методические указания по составлению представлений
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={getSDDownloadUrl(INSTRUCTION_FILE)}
                  download
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-100 hover:bg-amber-200 text-amber-800 text-xs font-medium rounded-lg transition-colors no-underline"
                >
                  <Download className="w-3.5 h-3.5" />
                  Скачать DOCX
                </a>
                {expandedInstr ? (
                  <ChevronUp className="w-5 h-5 text-gray-400" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-400" />
                )}
              </div>
            </div>
            {expandedInstr && (
              <div className="px-6 pb-5 border-t border-amber-200/50">
                <div className="mt-4 prose prose-sm max-w-none text-gray-700">
                  <p>
                    Данный файл содержит полную инструкцию по порядку вынесения представлений
                    об устранении причин и условий, способствовавших совершению уголовного
                    правонарушения, в соответствии со <strong>ст. 200 УПК Республики Казахстан</strong>.
                  </p>
                  <p className="mt-2">
                    Инструкция включает порядок составления, требования к оформлению,
                    структуру документа и рекомендации по формулировкам мотивировочной
                    и резолютивной частей представления.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ─── Tabs ─── */}
        <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-xl mb-6 w-fit">
          <button
            onClick={() => setActiveTab("sd")}
            className={`px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              activeTab === "sd"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Образцы СД ({SD_TEMPLATES.length})
          </button>
          <button
            onClick={() => setActiveTab("custom")}
            className={`px-5 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
              activeTab === "custom"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Пользовательские ({templates.length})
          </button>
        </div>

        {/* ─── SD Templates Tab ─── */}
        {activeTab === "sd" && (
          <div className="animate-fade-in">
            {/* Search & Filter */}
            <div className="flex flex-col sm:flex-row gap-3 mb-6">
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Поиск по шаблонам…"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm bg-white
                    focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-4 py-2.5 rounded-xl border border-gray-200 text-sm bg-white text-gray-700
                  focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent min-w-[200px]"
              >
                <option value="all">Все категории</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {/* Templates Grid */}
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredSD.map((t) => (
                <div
                  key={t.id}
                  className="group bg-white rounded-2xl border border-gray-200 p-5 hover:border-brand-300 hover:shadow-lg transition-all duration-300 flex flex-col"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center group-hover:bg-brand-100 transition-colors">
                      <FileText className="w-5 h-5 text-brand-600" />
                    </div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
                      {t.category}
                    </span>
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-1 line-clamp-1">{t.title}</h3>
                  <p className="text-sm text-gray-500 line-clamp-2 mb-4 flex-1">{t.description}</p>
                  <a
                    href={getSDDownloadUrl(t.filename)}
                    download
                    className="flex items-center justify-center gap-2 w-full py-2.5 bg-gray-50 hover:bg-brand-50 text-gray-700 hover:text-brand-700 text-sm font-medium rounded-xl border border-gray-200 hover:border-brand-200 transition-all duration-200 no-underline"
                  >
                    <Download className="w-4 h-4" />
                    Скачать шаблон
                  </a>
                </div>
              ))}
            </div>

            {filteredSD.length === 0 && (
              <div className="text-center py-16">
                <FileText className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500 font-medium">Ничего не найдено</p>
                <p className="text-sm text-gray-400 mt-1">Попробуйте изменить поисковый запрос или категорию</p>
              </div>
            )}
          </div>
        )}

        {/* ─── Custom Templates Tab ─── */}
        {activeTab === "custom" && (
          <div className="animate-fade-in">
            <div className="flex justify-end mb-4">
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

            {/* Custom Templates list */}
            {loading ? (
              <div className="flex justify-center py-20">
                <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
              </div>
            ) : templates.length === 0 ? (
              <div className="text-center py-20">
                <div className="relative inline-flex items-center justify-center w-20 h-20 mb-4">
                  <div className="absolute inset-0 bg-brand-100 rounded-2xl rotate-6" />
                  <div className="absolute inset-0 bg-brand-50 rounded-2xl -rotate-3" />
                  <div className="relative w-full h-full bg-white rounded-2xl border border-brand-100 flex items-center justify-center shadow-lg">
                    <Upload className="w-8 h-8 text-brand-400" />
                  </div>
                </div>
                <p className="text-gray-500 font-medium">Пользовательские шаблоны ещё не загружены</p>
                <p className="text-sm text-gray-400 mt-1">Загрузите собственный DOCX/RTF шаблон</p>
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
          </div>
        )}
      </main>
    </div>
  );
}
