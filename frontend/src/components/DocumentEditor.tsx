"use client";

import { useEditor, EditorContent, BubbleMenu } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Placeholder from "@tiptap/extension-placeholder";
import LinkExt from "@tiptap/extension-link";
import TextStyle from "@tiptap/extension-text-style";
import FontFamily from "@tiptap/extension-font-family";
import Highlight from "@tiptap/extension-highlight";
import { Extension, Mark } from "@tiptap/core";
import { api } from "@/lib/api";
import { useState, useCallback, useEffect, useRef } from "react";
import {
  Bold,
  Italic,
  UnderlineIcon,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Undo,
  Redo,
  FileDown,
  Link as LinkIcon,
  Quote,
  Type,
  ChevronDown,
  Loader2,
  CheckCircle,
  Highlighter,
  FileText,
  Sparkles,
  Wand2,
  Minimize2,
} from "lucide-react";

const FontSize = Extension.create({
  name: "fontSize",
  addOptions() {
    return { types: ["textStyle"] };
  },
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (el) => el.style.fontSize?.replace(/['"]+/g, "") || null,
            renderHTML: (attrs) => {
              if (!attrs.fontSize) return {};
              return { style: `font-size: ${attrs.fontSize}` };
            },
          },
        },
      },
    ];
  },
});

// Preserve arbitrary inline styles on <span> tags (needed for float:left/right on date and signature lines)
const InlineStyle = Mark.create({
  name: "inlineStyle",
  priority: 1000,
  keepOnSplit: false,
  addAttributes() {
    return {
      style: {
        default: null,
        parseHTML: (el: HTMLElement) => el.getAttribute("style") || null,
        renderHTML: (attrs: Record<string, string>) =>
          attrs.style ? { style: attrs.style } : {},
      },
    };
  },
  parseHTML() {
    return [{ tag: "span[style]", priority: 51 }];
  },
  renderHTML({ HTMLAttributes }: { HTMLAttributes: Record<string, string> }) {
    return ["span", HTMLAttributes, 0];
  },
});


interface DocumentEditorProps {
  content?: string;
  onContentChange?: (html: string) => void;
  saving?: boolean;
  lastSaved?: string;
  onInsertContent?: null | ((html: string) => void);
}

const FONTS = [
  { label: "Times New Roman", value: "Times New Roman" },
  { label: "Arial", value: "Arial" },
  { label: "Georgia", value: "Georgia" },
  { label: "Courier New", value: "Courier New" },
  { label: "Inter", value: "Inter" },
];

const SIZES = [
  { label: "10", value: "10pt" },
  { label: "12", value: "12pt" },
  { label: "14", value: "14pt" },
  { label: "16", value: "16pt" },
  { label: "18", value: "18pt" },
  { label: "20", value: "20pt" },
  { label: "24", value: "24pt" },
];

export default function DocumentEditor({
  content,
  onContentChange,
  saving,
  lastSaved,
}: DocumentEditorProps) {
  const [showFontMenu, setShowFontMenu] = useState(false);
  const [showSizeMenu, setShowSizeMenu] = useState(false);
  const [exporting, setExporting] = useState(false);
  const prevContentRef = useRef<string>("");

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        blockquote: {},
        bulletList: {},
        orderedList: {},
      }),
      Underline,
      TextAlign.configure({
        types: ["heading", "paragraph"],
        alignments: ["left", "center", "right", "justify"],
        defaultAlignment: "left",
      }),
      Placeholder.configure({ placeholder: "Сгенерированный документ появится здесь…" }),
      LinkExt.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { class: "text-brand-600 underline cursor-pointer" },
      }),
      TextStyle,
      FontFamily.configure({ types: ["textStyle"] }),
      FontSize,
      InlineStyle,
      Highlight.configure({ multicolor: true }),
    ],
    content: content || "",
    onUpdate: ({ editor: ed }) => {
      onContentChange?.(ed.getHTML());
    },
    editorProps: {
      attributes: {
        class: "tiptap prose prose-sm max-w-none focus:outline-none",
        style: "--editor-float-row: block",
      },
      transformPastedHTML: (html: string) => html,
    },
  });

  // CSS for float rows is injected globally via <style> in the return

  useEffect(() => {
    if (editor && content !== undefined && content !== prevContentRef.current) {
      prevContentRef.current = content;
      const currentHTML = editor.getHTML();
      if (content !== currentHTML) {
        editor.commands.setContent(content);
      }
    }
  }, [editor, content]);

  const handleExportDocx = async () => {
    if (!editor) return;
    setExporting(true);
    try {
      const blob = await api.exportDocx(editor.getHTML(), "документ.docx");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "документ.docx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert("Ошибка экспорта: " + e.message);
    } finally {
      setExporting(false);
    }
  };

  const setLink = useCallback(() => {
    if (!editor) return;
    const previousUrl = editor.getAttributes("link").href;
    const url = window.prompt("Введите URL ссылки:", previousUrl || "https://");
    if (url === null) return;
    if (url === "" || url === "https://") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    try {
      new URL(url);
    } catch {
      alert("Некорректный URL. Введите полный адрес, например: https://example.com");
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  }, [editor]);

  if (!editor) return null;

  const closeMenus = () => {
    setShowFontMenu(false);
    setShowSizeMenu(false);
  };

  const ToolBtn = ({
    onClick,
    active,
    disabled,
    children,
    title,
  }: {
    onClick: () => void;
    active?: boolean;
    disabled?: boolean;
    children: React.ReactNode;
    title: string;
  }) => (
    <button
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => {
        onClick();
        closeMenus();
      }}
      title={title}
      disabled={disabled}
      className={`p-1.5 rounded transition-colors ${active
          ? "bg-brand-100 text-brand-700"
          : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
        } ${disabled ? "opacity-30 cursor-not-allowed" : ""}`}
    >
      {children}
    </button>
  );

  const currentFont =
    editor.getAttributes("textStyle").fontFamily || "Times New Roman";
  const currentSize =
    editor.getAttributes("textStyle").fontSize || "14pt";

  return (
    <div className="flex flex-col h-full bg-white/60 dark:bg-slate-900/60 backdrop-blur-glass rounded-2xl border border-glass-border dark:border-glass-borderDark overflow-hidden shadow-glass dark:shadow-glass-dark transition-all duration-300">
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-3 py-2 border-b border-gray-200/50 dark:border-slate-700/50 bg-white/40 dark:bg-slate-800/40 backdrop-blur-md flex-wrap relative z-20">
        {/* Font family */}
        <div className="relative">
          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              setShowFontMenu(!showFontMenu);
              setShowSizeMenu(false);
            }}
            className="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-white/60 dark:hover:bg-slate-700/60 rounded-lg transition-all duration-200 min-w-[110px]"
            title="Шрифт"
          >
            <Type className="w-3.5 h-3.5" />
            <span className="truncate">{currentFont}</span>
            <ChevronDown className="w-3 h-3" />
          </button>
          {showFontMenu && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-20 min-w-[170px]">
              {FONTS.map((f) => (
                <button
                  key={f.value}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    editor.chain().focus().setFontFamily(f.value).run();
                    setShowFontMenu(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 transition-colors ${currentFont === f.value
                      ? "bg-brand-50 text-brand-700 font-medium"
                      : ""
                    }`}
                  style={{ fontFamily: f.value }}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Font size */}
        <div className="relative">
          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              setShowSizeMenu(!showSizeMenu);
              setShowFontMenu(false);
            }}
            className="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-white/60 dark:hover:bg-slate-700/60 rounded-lg transition-all duration-200 min-w-[48px]"
            title="Размер шрифта"
          >
            <span>{currentSize.replace("pt", "")}</span>
            <ChevronDown className="w-3 h-3" />
          </button>
          {showSizeMenu && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-20 min-w-[64px]">
              {SIZES.map((s) => (
                <button
                  key={s.value}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    editor
                      .chain()
                      .focus()
                      .setMark("textStyle", { fontSize: s.value })
                      .run();
                    setShowSizeMenu(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 transition-colors ${currentSize === s.value
                      ? "bg-brand-50 text-brand-700 font-medium"
                      : ""
                    }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="w-px h-5 bg-gray-300 mx-1" />

        <ToolBtn
          onClick={() => editor.chain().focus().toggleBold().run()}
          active={editor.isActive("bold")}
          title="Жирный (Ctrl+B)"
        >
          <Bold className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().toggleItalic().run()}
          active={editor.isActive("italic")}
          title="Курсив (Ctrl+I)"
        >
          <Italic className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          active={editor.isActive("underline")}
          title="Подчёркнутый (Ctrl+U)"
        >
          <UnderlineIcon className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().toggleHighlight().run()}
          active={editor.isActive("highlight")}
          title="Выделение"
        >
          <Highlighter className="w-4 h-4" />
        </ToolBtn>

        <div className="w-px h-5 bg-gray-300 mx-1" />

        <ToolBtn
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 1 }).run()
          }
          active={editor.isActive("heading", { level: 1 })}
          title="Заголовок 1"
        >
          <Heading1 className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 2 }).run()
          }
          active={editor.isActive("heading", { level: 2 })}
          title="Заголовок 2"
        >
          <Heading2 className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 3 }).run()
          }
          active={editor.isActive("heading", { level: 3 })}
          title="Заголовок 3"
        >
          <Heading3 className="w-4 h-4" />
        </ToolBtn>

        <div className="w-px h-5 bg-gray-300 mx-1" />

        <ToolBtn
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          active={editor.isActive("bulletList")}
          title="Маркированный список"
        >
          <List className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          active={editor.isActive("orderedList")}
          title="Нумерованный список"
        >
          <ListOrdered className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          active={editor.isActive("blockquote")}
          title="Цитата"
        >
          <Quote className="w-4 h-4" />
        </ToolBtn>

        <div className="w-px h-5 bg-gray-300 mx-1" />

        <ToolBtn
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
          active={editor.isActive({ textAlign: "left" })}
          title="По левому краю"
        >
          <AlignLeft className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
          active={editor.isActive({ textAlign: "center" })}
          title="По центру"
        >
          <AlignCenter className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().setTextAlign("right").run()}
          active={editor.isActive({ textAlign: "right" })}
          title="По правому краю"
        >
          <AlignRight className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().setTextAlign("justify").run()}
          active={editor.isActive({ textAlign: "justify" })}
          title="По ширине"
        >
          <AlignJustify className="w-4 h-4" />
        </ToolBtn>

        <div className="w-px h-5 bg-gray-300 mx-1" />

        <ToolBtn
          onClick={setLink}
          active={editor.isActive("link")}
          title="Вставить ссылку"
        >
          <LinkIcon className="w-4 h-4" />
        </ToolBtn>

        <div className="w-px h-5 bg-gray-300 mx-1" />

        <ToolBtn
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Отменить (Ctrl+Z)"
        >
          <Undo className="w-4 h-4" />
        </ToolBtn>
        <ToolBtn
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Повторить (Ctrl+Y)"
        >
          <Redo className="w-4 h-4" />
        </ToolBtn>

        <div className="flex-1" />

        {saving && (
          <span className="flex items-center gap-1 text-xs text-gray-400 mr-2">
            <Loader2 className="w-3 h-3 animate-spin" /> Сохранение…
          </span>
        )}
        {lastSaved && !saving && (
          <span className="flex items-center gap-1 text-xs text-gray-400 mr-2">
            <CheckCircle className="w-3 h-3 text-green-500" /> Сохранено
          </span>
        )}

        <button
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleExportDocx}
          disabled={exporting}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50"
        >
          {exporting ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <FileDown className="w-3.5 h-3.5" />
          )}
          Экспорт DOCX
        </button>
      </div>

      <div
        className="flex-1 overflow-y-auto bg-transparent custom-scrollbar relative z-10"
        onClick={closeMenus}
      >
        <BubbleMenu
          editor={editor}
          tippyOptions={{ duration: 100 }}
          className="flex items-center p-1 bg-white/95 dark:bg-slate-800/95 backdrop-blur-xl border border-glass-border dark:border-glass-borderDark shadow-xl rounded-xl overflow-hidden"
        >
          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => alert("Вызван ИИ: Улучшить текст")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/30 rounded-lg transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Улучшить
          </button>
          <div className="w-px h-4 bg-gray-200 dark:bg-slate-700 mx-1" />
          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => alert("Вызван ИИ: Сделать короче")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <Minimize2 className="w-3 h-3" />
            Короче
          </button>
          <div className="w-px h-4 bg-gray-200 dark:bg-slate-700 mx-1" />
          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => alert("Вызван ИИ: Исправить ошибки")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <Wand2 className="w-3 h-3" />
            Исправить
          </button>
        </BubbleMenu>
        <EditorContent editor={editor} />
        {/* CSS for float-based date/city and signature/name lines */}
        <style>{`
          .tiptap p:has(span[style*="float"]) {
            display: flow-root;
            overflow: hidden;
          }
          .tiptap span[style*="float:left"],
          .tiptap span[style*="float: left"] {
            float: left;
          }
          .tiptap span[style*="float:right"],
          .tiptap span[style*="float: right"] {
            float: right;
          }
        `}</style>
      </div>
    </div>
  );
}
