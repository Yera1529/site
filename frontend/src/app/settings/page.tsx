"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import { AppSetting } from "@/types";
import {
  Loader2,
  Save,
  Server,
  Key,
  Cpu,
  BrainCircuit,
  ShieldAlert,
  Lightbulb,
} from "lucide-react";

const SETTING_FIELDS = [
  {
    key: "ai_api_url",
    label: "URL API модели ИИ",
    placeholder: "http://localhost:11434/v1/chat/completions",
    icon: Server,
    description:
      "URL-адрес OpenAI-совместимого эндпоинта (Ollama, vLLM, Google AI и др.)",
  },
  {
    key: "ai_api_key",
    label: "Ключ API",
    placeholder: "Оставьте пустым, если не требуется",
    icon: Key,
    description: "Необязательный ключ для аутентификации с эндпоинтом ИИ",
    type: "password",
  },
  {
    key: "ai_model",
    label: "Название модели ИИ",
    placeholder: "gemini-2.0-flash",
    icon: BrainCircuit,
    description:
      "Идентификатор модели для генерации текста. Укажите модель, доступную на выбранном эндпоинте.",
  },
  {
    key: "embedding_model",
    label: "Модель эмбеддингов",
    placeholder: "all-MiniLM-L6-v2",
    icon: Cpu,
    description: "Модель SentenceTransformer для векторного поиска (RAG)",
  },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then((data) => {
        const map: Record<string, string> = {};
        (data as AppSetting[]).forEach((s) => (map[s.key] = s.value));
        setSettings(map);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const allKeys = [
        ...SETTING_FIELDS.map((f) => f.key),
        "ai_thinking_mode",
      ];
      const updates = Object.entries(settings)
        .filter(([key]) => allKeys.includes(key))
        .map(([key, value]) => ({ key, value }));
      await api.updateSettings(updates);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  const thinkingMode = settings["ai_thinking_mode"] || "enabled";



  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-2xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Настройки</h1>
        <p className="text-sm text-gray-500 mb-8">
          Конфигурация модели ИИ и параметров генерации. Изменения
          применяются немедленно.
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-brand-600" />
          </div>
        ) : (
          <div className="space-y-6">
            {SETTING_FIELDS.map((field) => (
              <div
                key={field.key}
                className="bg-white rounded-xl border border-gray-200 p-5 hover:border-brand-200 hover:shadow-md transition-all duration-200"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-lg bg-brand-50 flex items-center justify-center">
                    <field.icon className="w-4 h-4 text-brand-600" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-900">
                      {field.label}
                    </label>
                    <p className="text-xs text-gray-500">{field.description}</p>
                  </div>
                </div>
                <input
                  type={field.type || "text"}
                  value={settings[field.key] || ""}
                  onChange={(e) =>
                    setSettings((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                  placeholder={field.placeholder}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm
                    focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
            ))}

            {/* Thinking mode toggle */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                  <Lightbulb className="w-4 h-4 text-amber-600" />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-900">
                    Режим рассуждения (Thinking Mode)
                  </label>
                  <p className="text-xs text-gray-500">
                    Модель поддерживает два режима работы для генерации
                    представлений
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                <label
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    thinkingMode === "enabled"
                      ? "border-brand-300 bg-brand-50/50"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="thinking_mode"
                    checked={thinkingMode === "enabled"}
                    onChange={() =>
                      setSettings((prev) => ({
                        ...prev,
                        ai_thinking_mode: "enabled",
                      }))
                    }
                    className="mt-1 text-brand-600 focus:ring-brand-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      Thinking Mode — рассуждение{" "}
                      <span className="text-xs text-brand-600 bg-brand-50 px-1.5 py-0.5 rounded ml-1">
                        рекомендуется
                      </span>
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Модель «думает» перед ответом: анализирует факты,
                      проверяет нормативные ссылки, формирует причинные связи.
                      Медленнее, но точнее для юридических текстов.
                    </p>
                  </div>
                </label>
                <label
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    thinkingMode === "disabled"
                      ? "border-brand-300 bg-brand-50/50"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="thinking_mode"
                    checked={thinkingMode === "disabled"}
                    onChange={() =>
                      setSettings((prev) => ({
                        ...prev,
                        ai_thinking_mode: "disabled",
                      }))
                    }
                    className="mt-1 text-brand-600 focus:ring-brand-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      Non-Thinking — быстрый режим
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Прямая генерация без этапа рассуждения.
                      Быстрее, подходит для простых
                      редактур и правок.
                    </p>
                  </div>
                </label>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white text-sm
                  font-medium rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Сохранить настройки
              </button>
              {saved && (
                <span className="text-sm text-green-600 font-medium">
                  Настройки сохранены!
                </span>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
