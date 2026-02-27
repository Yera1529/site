import { RetrievedLaw } from "@/types";
/** URL бэкенда (запросы идут из браузера — указывайте адрес, доступный с клиента). Задаётся в .env.local как NEXT_PUBLIC_API_URL. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

function authHeaders(): HeadersInit {
  const token = getToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function normalizeErrorMessage(raw: string): string {
  const s = raw.toLowerCase();
  if (s.includes("failed to fetch") || s.includes("network request failed") || s === "failed to fetch") {
    return "Не удалось подключиться к серверу. Проверьте подключение к интернету и что сервер запущен.";
  }
  if (s.includes("networkerror") || s.includes("load failed")) {
    return "Ошибка сети. Проверьте подключение и повторите попытку.";
  }
  if (s.includes("timeout") || s.includes("aborted")) {
    return "Превышено время ожидания ответа сервера. Попробуйте снова.";
  }
  return raw;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) },
    });
  } catch (err: any) {
    throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = body.detail || `Ошибка запроса: ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // Auth
  register: (data: { email: string; full_name: string; password: string }) =>
    request("/api/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify(data) }),

  me: () => request("/api/auth/me"),

  resetPassword: (data: { email: string; new_password: string; admin_key: string }) =>
    request("/api/auth/reset-password", { method: "POST", body: JSON.stringify(data) }),

  // Matters
  listMatters: () => request("/api/matters"),

  createMatter: (data: { name: string; description?: string; custom_instructions?: string }) =>
    request("/api/matters", { method: "POST", body: JSON.stringify(data) }),

  getMatter: (id: string) => request(`/api/matters/${id}`),

  updateMatter: (id: string, data: { name?: string; description?: string; custom_instructions?: string }) =>
    request(`/api/matters/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteMatter: (id: string) => request(`/api/matters/${id}`, { method: "DELETE" }),

  // Files
  listFiles: (matterId: string) => request(`/api/matters/${matterId}/files`),

  uploadFile: async (matterId: string, file: File) => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/matters/${matterId}/files`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Ошибка загрузки: ${res.status}`);
    }
    return res.json();
  },

  downloadFileUrl: (matterId: string, fileId: string) =>
    `${API_URL}/api/matters/${matterId}/files/${fileId}/download`,

  deleteFile: (matterId: string, fileId: string) =>
    request(`/api/matters/${matterId}/files/${fileId}`, { method: "DELETE" }),

  // Chat
  getChatHistory: (matterId: string) => request(`/api/matters/${matterId}/chat`),

  sendMessage: async function* (matterId: string, message: string) {
    const token = getToken();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ matter_id: matterId, message }),
      });
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Ошибка чата: ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.done) return;
            if (data.content) yield data.content;
          } catch {
            // skip
          }
        }
      }
    }
  },

  // Document Generation
  generateDocument: (matterId: string, templateName: string, additionalInstructions?: string, selectedLaws?: RetrievedLaw[]) =>
    request("/api/generate-document", {
      method: "POST",
      body: JSON.stringify({
        matter_id: matterId,
        template_name: templateName,
        additional_instructions: additionalInstructions || "",
        selected_laws: selectedLaws || null,
      }),
    }),

  exportDocx: async (html: string, filename: string) => {
    const token = getToken();
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/export-docx`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ html, filename }),
      });
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) throw new Error("Ошибка экспорта");
    return res.blob();
  },

  // Templates
  listTemplates: () => request("/api/templates"),

  getTemplate: (id: string) => request(`/api/templates/${id}`),

  getTemplateHtml: (id: string) =>
    request<{ html: string; template_name: string }>(`/api/templates/${id}/html`),

  getBlankRepresentation: () =>
    request<{ html: string; template_name: string }>("/api/templates/article200/blank"),

  uploadTemplate: async (name: string, description: string, file: File) => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    let res: Response;
    try {
      res = await fetch(
        `${API_URL}/api/templates?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        }
      );
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Ошибка загрузки: ${res.status}`);
    }
    return res.json();
  },

  deleteTemplate: (id: string) => request(`/api/templates/${id}`, { method: "DELETE" }),

  // Knowledge Base
  listKBDocuments: () => request("/api/knowledge-base"),

  getKBStats: () => request<{ total_documents: number; total_chunks: number }>("/api/knowledge-base/stats"),

  uploadKBDocument: async (file: File) => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/knowledge-base`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Ошибка загрузки: ${res.status}`);
    }
    return res.json();
  },

  uploadKBBatch: async (files: File[]) => {
    const token = getToken();
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/knowledge-base/batch`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Ошибка загрузки: ${res.status}`);
    }
    return res.json();
  },

  deleteKBDocument: (id: string) => request(`/api/knowledge-base/${id}`, { method: "DELETE" }),

  // Legislation
  listLegislation: (query?: string, category?: string) => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (category) params.set("category", category);
    const qs = params.toString();
    return request(`/api/legislation${qs ? "?" + qs : ""}`);
  },

  getLegislationCategories: () => request<string[]>("/api/legislation/categories"),

  uploadLegislation: async (title: string, category: string, year: number | null, file: File) => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams({ title, category });
    if (year) params.set("year", String(year));
    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/legislation?${params}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });
    } catch (err: any) {
      throw new Error(normalizeErrorMessage(err?.message || "Unknown error"));
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || `Ошибка загрузки: ${res.status}`);
    }
    return res.json();
  },

  getLegislation: (id: string) => request(`/api/legislation/${id}`),

  getLegislationArticles: (id: string) => request(`/api/legislation/${id}/articles`),

  updateLegislation: (id: string, data: { title?: string; category?: string; year?: number }) =>
    request(`/api/legislation/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteLegislation: (id: string) => request(`/api/legislation/${id}`, { method: "DELETE" }),

  reindexLegislation: (id: string) =>
    request(`/api/legislation/${id}/reindex`, { method: "POST" }),

  // Search laws (for generation wizard)
  searchLaws: (matterId: string, query?: string) =>
    request("/api/search-laws", {
      method: "POST",
      body: JSON.stringify({ matter_id: matterId, query: query || "" }),
    }),

  // Representations
  listRepresentations: (matterId?: string, status?: string) => {
    const params = new URLSearchParams();
    if (matterId) params.set("matter_id", matterId);
    if (status) params.set("status", status);
    const qs = params.toString();
    return request(`/api/representations${qs ? "?" + qs : ""}`);
  },

  createRepresentation: (data: {
    matter_id: string;
    template_id?: string;
    title?: string;
    content?: string;
    status?: string;
    selected_law_ids?: string[];
  }) => request("/api/representations", { method: "POST", body: JSON.stringify(data) }),

  getRepresentation: (id: string) => request(`/api/representations/${id}`),

  updateRepresentation: (id: string, data: {
    title?: string;
    content?: string;
    status?: string;
    selected_law_ids?: string[];
  }) => request(`/api/representations/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteRepresentation: (id: string) => request(`/api/representations/${id}`, { method: "DELETE" }),

  // Settings
  getSettings: () => request("/api/settings"),

  updateSettings: (updates: { key: string; value: string }[]) =>
    request("/api/settings", { method: "PUT", body: JSON.stringify(updates) }),
};
