"use client";

import { useState, useRef } from "react";
import { FileItem } from "@/types";
import { api } from "@/lib/api";
import {
  Upload,
  FileText,
  File,
  Trash2,
  Download,
  Loader2,
  AlertCircle,
  CheckCircle,
  Image as ImageIcon,
} from "lucide-react";

interface FilesSidebarProps {
  matterId: string;
  files: FileItem[];
  onFileUploaded: () => void;
}

interface UploadStatus {
  name: string;
  status: "uploading" | "done" | "error";
  error?: string;
}

const MAX_FILE_SIZE_MB = 50;
const ACCEPTED = ".pdf,.docx,.doc,.txt,.rtf,.odt,.png,.jpg,.jpeg";

export default function FilesSidebar({
  matterId,
  files,
  onFileUploaded,
}: FilesSidebarProps) {
  const [uploads, setUploads] = useState<UploadStatus[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const items: UploadStatus[] = Array.from(fileList).map((f) => ({
      name: f.name,
      status: "uploading" as const,
    }));
    setUploads(items);

    for (let i = 0; i < fileList.length; i++) {
      const f = fileList[i];

      if (f.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        setUploads((prev) =>
          prev.map((u, idx) =>
            idx === i
              ? {
                  ...u,
                  status: "error",
                  error: `Слишком большой (${(f.size / (1024 * 1024)).toFixed(1)} МБ, макс. ${MAX_FILE_SIZE_MB} МБ)`,
                }
              : u
          )
        );
        continue;
      }

      const ext = f.name.split(".").pop()?.toLowerCase() || "";
      const allowed = new Set([
        "pdf",
        "docx",
        "doc",
        "txt",
        "rtf",
        "odt",
        "png",
        "jpg",
        "jpeg",
      ]);
      if (!allowed.has(ext)) {
        setUploads((prev) =>
          prev.map((u, idx) =>
            idx === i
              ? { ...u, status: "error", error: `Формат .${ext} не поддерживается` }
              : u
          )
        );
        continue;
      }

      try {
        await api.uploadFile(matterId, f);
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

    onFileUploaded();
    setTimeout(() => setUploads([]), 5000);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDelete = async (fileId: string, fileName: string) => {
    if (!confirm(`Удалить файл «${fileName}»?`)) return;
    try {
      await api.deleteFile(matterId, fileId);
      onFileUploaded();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleDownload = (fileId: string, fileName: string) => {
    const token = localStorage.getItem("token");
    fetch(api.downloadFileUrl(matterId, fileId), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = fileName;
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  const fileIcon = (type: string) => {
    if (type === "pdf")
      return <FileText className="w-4 h-4 text-red-500" />;
    if (type === "docx" || type === "doc")
      return <FileText className="w-4 h-4 text-blue-500" />;
    if (["png", "jpg", "jpeg"].includes(type))
      return <ImageIcon className="w-4 h-4 text-green-500" />;
    return <File className="w-4 h-4 text-gray-500" />;
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  };

  return (
    <div className="w-72 bg-white border-r border-gray-200 flex flex-col h-full">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">
          Документы дела
        </h3>
        <div
          className={`relative border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
            dragOver
              ? "border-brand-500 bg-brand-50"
              : "border-gray-300 hover:border-gray-400"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleUpload(e.dataTransfer.files);
          }}
        >
          {uploads.some((u) => u.status === "uploading") ? (
            <Loader2 className="w-6 h-6 mx-auto text-brand-600 animate-spin" />
          ) : (
            <Upload className="w-6 h-6 mx-auto text-gray-400" />
          )}
          <p className="text-xs text-gray-500 mt-1">Перетащите или нажмите</p>
          <p className="text-xs text-gray-400">
            PDF, DOCX, TXT, RTF, ODT, изображения (макс. {MAX_FILE_SIZE_MB} МБ)
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED}
            className="absolute inset-0 opacity-0 cursor-pointer"
            onChange={(e) => handleUpload(e.target.files)}
          />
        </div>

        {uploads.length > 0 && (
          <div className="mt-2 space-y-1">
            {uploads.map((u, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                {u.status === "uploading" && (
                  <Loader2 className="w-3 h-3 animate-spin text-brand-600 flex-shrink-0" />
                )}
                {u.status === "done" && (
                  <CheckCircle className="w-3 h-3 text-green-500 flex-shrink-0" />
                )}
                {u.status === "error" && (
                  <AlertCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
                )}
                <span
                  className={`truncate ${
                    u.status === "error" ? "text-red-600" : "text-gray-600"
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

      <div className="flex-1 overflow-y-auto p-2">
        {files.length === 0 ? (
          <p className="text-xs text-gray-400 text-center mt-8">
            Файлы ещё не загружены
          </p>
        ) : (
          <ul className="space-y-1">
            {files.map((f) => (
              <li
                key={f.id}
                className="group flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {fileIcon(f.file_type)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate">
                    {f.original_name}
                  </p>
                  <p className="text-xs text-gray-400">
                    {formatSize(f.file_size)}
                  </p>
                </div>
                <div className="hidden group-hover:flex items-center gap-1">
                  <button
                    onClick={() => handleDownload(f.id, f.original_name)}
                    className="p-1 text-gray-400 hover:text-brand-600 transition-colors"
                    title="Скачать"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(f.id, f.original_name)}
                    className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    title="Удалить"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
