"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/types";
import { api } from "@/lib/api";
import { Send, Loader2, Bot, User, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent, streaming]);

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }
  };

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || streaming) return;

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "44px";
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
    <div className="flex flex-col h-full bg-gradient-to-b from-slate-50 to-white relative">
      {/* Subtle background pattern */}
      <div
        className="absolute inset-0 opacity-[0.015] pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, #0033aa 1px, transparent 0)`,
          backgroundSize: "32px 32px",
        }}
      />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden px-6 py-6 space-y-5 relative z-10">
        {messages.length === 0 && !streaming && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
            className="flex flex-col items-center justify-center h-full py-20 text-center"
          >
            <div className="animate-float mb-6">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-800 flex items-center justify-center shadow-lg shadow-brand-500/30">
                <Bot className="w-10 h-10 text-white" />
              </div>
            </div>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">ИИ-ассистент МВД РК</h3>
            <p className="text-sm text-gray-500 max-w-xs leading-relaxed">
              Задайте вопрос по материалам дела, попросите проанализировать документ или подготовить выжимку из фабулы.
            </p>
            <div className="flex gap-2 mt-6 flex-wrap justify-center">
              {["Кратко изложи фабулу дела", "Какие нарушения выявлены?", "Какие законы применимы?"].map((hint) => (
                <button
                  key={hint}
                  onClick={() => { setInput(hint); textareaRef.current?.focus(); }}
                  className="text-xs px-3 py-1.5 rounded-full border border-brand-200 text-brand-600 hover:bg-brand-50 transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: idx === messages.length - 1 ? 0 : 0 }}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 flex items-center justify-center flex-shrink-0 shadow-sm mt-0.5">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}
              <div className={msg.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"}>
                <div className="text-sm leading-relaxed break-words" style={{ overflowWrap: "anywhere", wordBreak: "break-word", whiteSpace: "pre-wrap" }}>{msg.content}</div>
                <div className={`flex items-center gap-1 mt-2 text-xs ${msg.role === "user" ? "text-white/60" : "text-gray-400"}`}>
                  {msg.role === "assistant" && <Sparkles className="w-3 h-3" />}
                  <span>{formatTime(msg.created_at)}</span>
                </div>
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-xl bg-gray-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-gray-500" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {streaming && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3 justify-start"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="chat-bubble-ai generating-shimmer">
              {streamContent ? (
                <div className="text-sm leading-relaxed relative z-10 break-words" style={{ overflowWrap: "anywhere", wordBreak: "break-word", whiteSpace: "pre-wrap" }}>{streamContent}</div>
              ) : (
                <div className="flex items-center gap-2 py-1">
                  <div className="thinking-dots flex gap-1.5">
                    <span /><span /><span />
                  </div>
                  <span className="text-sm text-gray-400">Анализирую...</span>
                </div>
              )}
            </div>
          </motion.div>
        )}

        <div ref={bottomRef} className="h-1" />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-100 bg-white/80 backdrop-blur-sm z-20">
        <div className="max-w-3xl mx-auto flex items-end gap-2">
          <div className="flex-1 relative border border-gray-200 rounded-2xl bg-white shadow-sm focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-500/15 transition-all duration-200">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); adjustHeight(); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Задайте вопрос по делу... (Enter — отправить, Shift+Enter — новая строка)"
              rows={1}
              className="w-full resize-none bg-transparent px-4 py-3 text-sm text-gray-900 focus:outline-none placeholder:text-gray-400 rounded-2xl"
              style={{ minHeight: 44, maxHeight: 120 }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            className="btn-primary w-11 h-11 p-0 flex-shrink-0 rounded-xl"
            title="Отправить (Enter)"
          >
            {streaming
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Send className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-center text-[10px] text-gray-400 mt-2">
          ИИ может допускать ошибки. Проверяйте важную информацию. • Qwen3-30B
        </p>
      </div>
    </div>
  );
}
