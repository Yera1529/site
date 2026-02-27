"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/types";
import { api } from "@/lib/api";
import { Send, Loader2, Bot, User, Clock } from "lucide-react";

interface ChatPanelProps {
  matterId: string;
  messages: ChatMessage[];
  onMessagesUpdated: () => void;
}

export default function ChatPanel({ matterId, messages, onMessagesUpdated }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || streaming) return;

    setInput("");
    setStreaming(true);
    setStreamContent("");

    try {
      let accumulated = "";
      for await (const chunk of api.sendMessage(matterId, msg)) {
        accumulated += chunk;
        setStreamContent(accumulated);
      }
    } catch (e: any) {
      setStreamContent(`Ошибка: ${e.message}`);
    } finally {
      setStreaming(false);
      setStreamContent("");
      onMessagesUpdated();
    }
  };

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && !streaming && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Bot className="w-12 h-12 mb-3 text-gray-300" />
            <p className="text-sm font-medium">Начните диалог</p>
            <p className="text-xs mt-1 text-center max-w-xs">
              Задайте вопрос по материалам дела или запросите создание документа.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-brand-700" />
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-brand-600 text-white"
                  : "bg-white border border-gray-200 text-gray-800"
              }`}
            >
              <div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</div>
              <div
                className={`flex items-center gap-1 mt-1 text-xs ${
                  msg.role === "user" ? "text-brand-200" : "text-gray-400"
                }`}
              >
                <Clock className="w-3 h-3" />
                {formatTime(msg.created_at)}
              </div>
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-gray-600" />
              </div>
            )}
          </div>
        ))}

        {streaming && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-brand-700" />
            </div>
            <div className="max-w-[75%] rounded-2xl px-4 py-3 bg-white border border-gray-200 text-gray-800">
              {streamContent ? (
                <div className="text-sm whitespace-pre-wrap leading-relaxed">{streamContent}</div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Обработка запроса…</span>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white p-4">
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Задайте вопрос по материалам дела…"
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm
              focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent
              placeholder:text-gray-400"
            style={{ minHeight: 44, maxHeight: 120 }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            className="flex items-center justify-center w-11 h-11 rounded-xl bg-brand-600
              text-white hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors flex-shrink-0"
          >
            {streaming ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
