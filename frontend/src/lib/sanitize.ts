/**
 * Очистка HTML перед рендером через dangerouslySetInnerHTML — защита от XSS.
 * Документ-представление генерируется LLM из фабулы/файлов дела (ввод пользователя),
 * поэтому без санитизации возможен XSS (<script>, on*=, javascript:).
 *
 * Реализация без внешних зависимостей: парсим в инертный <template> (скрипты НЕ
 * исполняются, ресурсы НЕ загружаются), удаляем опасные теги и атрибуты, сохраняя
 * форматирование (заголовки, абзацы, списки, таблицы, inline-стили float/text-align).
 * На сервере (SSR) возвращаем пустую строку — непроверенный HTML в разметку не попадёт.
 */
const DANGEROUS_TAGS = "script,style,iframe,object,embed,link,meta,base,form,svg,math,noscript,template";
const URL_ATTRS = new Set(["href", "src", "xlink:href", "action", "formaction", "background", "poster"]);

// Разрешённые схемы URL. Всё остальное (javascript:, vbscript:, data:, file:, ...)
// вырезается. Относительные/якорные ссылки (без схемы) разрешены.
const ALLOWED_SCHEMES = new Set(["http", "https", "mailto", "tel"]);
const HAS_SCHEME = /^([a-z][a-z0-9+.-]*):/i;
const DANGEROUS_SCHEME = /^(?:javascript|vbscript|data|file):/i;

/**
 * Удаляет символы, которые браузер ИГНОРИРУЕТ внутри URL (управляющие, пробелы,
 * zero-width). Их обязательно вырезать ПЕРЕД определением схемы, иначе
 * "javascript\t:" обходит проверку, а браузер при клике склеивает обратно в
 * "javascript:" и исполняет JS. Делаем по кодам символов (без regex-escape).
 */
function stripUrlIgnored(value: string): string {
  let out = "";
  for (const ch of value) {
    const c = ch.charCodeAt(0);
    if (c <= 0x20 || c === 0xa0 || c === 0x2028 || c === 0x2029 || c === 0xfeff) continue;
    out += ch;
  }
  return out;
}

/** Возвращает схему URL после нормализации, или null для относительной/якорной ссылки. */
function urlScheme(value: string): string | null {
  const m = HAS_SCHEME.exec(stripUrlIgnored(value || ""));
  return m ? m[1].toLowerCase() : null;
}

export function sanitizeHtml(html: string | null | undefined): string {
  if (typeof window === "undefined" || typeof document === "undefined") return "";
  if (!html) return "";
  const tpl = document.createElement("template");
  tpl.innerHTML = html;

  tpl.content.querySelectorAll(DANGEROUS_TAGS).forEach((el) => el.remove());

  tpl.content.querySelectorAll("*").forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      const rawVal = attr.value || "";
      const normVal = stripUrlIgnored(rawVal);
      if (name.startsWith("on")) {
        el.removeAttribute(attr.name); // обработчики событий
      } else if (URL_ATTRS.has(name)) {
        const scheme = urlScheme(rawVal); // нормализует control-символы внутри
        if (scheme && !ALLOWED_SCHEMES.has(scheme)) el.removeAttribute(attr.name);
      } else if (DANGEROUS_SCHEME.test(normVal)) {
        el.removeAttribute(attr.name); // опасная схема в любом другом атрибуте
      } else if (name === "style" && /(javascript|expression|behavior|url\s*\()/i.test(rawVal)) {
        el.removeAttribute(attr.name); // опасные CSS (оставляем безопасные float/text-align)
      }
    }
  });

  return tpl.innerHTML;
}
