"""Document DOCX export service with GOST-style formatting and template parsing."""

import re
import uuid
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from config import get_settings


ALIGN_MAP = {
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
}


class DocumentService:
    def __init__(self):
        settings = get_settings()
        self.generated_dir = Path(settings.storage_dir) / "generated"
        self.generated_dir.mkdir(parents=True, exist_ok=True)

    # ── DOCX → TipTap HTML (template parsing) ─────────────────────────

    def docx_to_html(self, docx_path: str) -> str:
        """Parse a DOCX file and return structured HTML suitable for TipTap."""
        doc = Document(docx_path)
        html_parts = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                html_parts.append("<p><br></p>")
                continue

            style_name = (para.style.name or "").lower()
            alignment = self._get_alignment(para)
            style_attr = f' style="text-align:{alignment}"' if alignment != "left" else ""

            if "heading 1" in style_name or style_name.startswith("heading 1"):
                html_parts.append(f"<h1{style_attr}>{self._runs_to_html(para)}</h1>")
            elif "heading 2" in style_name or style_name.startswith("heading 2"):
                html_parts.append(f"<h2{style_attr}>{self._runs_to_html(para)}</h2>")
            elif "heading 3" in style_name or style_name.startswith("heading 3"):
                html_parts.append(f"<h3{style_attr}>{self._runs_to_html(para)}</h3>")
            elif "list" in style_name:
                html_parts.append(f"<li>{self._runs_to_html(para)}</li>")
            else:
                centered_title = re.match(
                    r"^[ПП]\s*[РP]\s*[ЕE]\s*[ДD]\s*[СC]\s*[ТT]\s*[АA]\s*[ВB]\s*[ЛL]\s*[ЕE]\s*[НH]\s*[ИI]\s*[ЕE]",
                    text, re.IGNORECASE
                )
                if centered_title:
                    html_parts.append(
                        f'<h1 style="text-align:center"><strong>{text}</strong></h1>'
                    )
                else:
                    html_parts.append(f"<p{style_attr}>{self._runs_to_html(para)}</p>")

        html = "\n".join(html_parts)
        html = re.sub(r"(<li>.*?</li>(?:\s*<li>.*?</li>)*)", r"<ol>\1</ol>", html, flags=re.DOTALL)
        return html

    def _get_alignment(self, para) -> str:
        alignment = para.alignment
        if alignment is None and para.style and para.style.paragraph_format:
            alignment = para.style.paragraph_format.alignment
        return ALIGN_MAP.get(alignment, "left")

    def _runs_to_html(self, para) -> str:
        """Convert paragraph runs to inline HTML preserving bold/italic/underline."""
        parts = []
        for run in para.runs:
            text = run.text
            if not text:
                continue
            if run.bold:
                text = f"<strong>{text}</strong>"
            if run.italic:
                text = f"<em>{text}</em>"
            if run.underline:
                text = f"<u>{text}</u>"
            parts.append(text)
        return "".join(parts) if parts else para.text

    # ── Generate structured article-200 template HTML ──────────────────

    @staticmethod
    def representation_template_html() -> str:
        """Return a blank article-200 representation template as TipTap HTML."""
        return """\
<p style="text-align:right"><strong>Руководителю ___________________________</strong></p>
<p style="text-align:right">________________________________</p>
<p style="text-align:right">________________________________</p>
<p><br></p>
<h1 style="text-align:center"><strong>П Р Е Д С Т А В Л Е Н И Е</strong></h1>
<h2 style="text-align:center">по устранению обстоятельств, способствовавших совершению уголовного правонарушения</h2>
<p><br></p>
<p>«___» _____________ 20___ г.&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;г. _______________</p>
<p><br></p>
<p style="text-align:justify">Следственным отделом ___________________________ расследуется уголовное дело, зарегистрированное в ЕРДР за № _______________, возбужденное по признакам уголовного правонарушения, предусмотренного _____ Уголовного кодекса Республики Казахстан.</p>
<p><br></p>
<p style="text-align:justify">В ходе расследования данного уголовного дела установлено, что совершению указанного уголовного правонарушения способствовали следующие обстоятельства:</p>
<p><br></p>
<p style="text-align:justify">___________________________________________________________________________</p>
<p><br></p>
<p style="text-align:justify">На основании изложенного, руководствуясь статьей 200 Уголовно-процессуального кодекса Республики Казахстан,</p>
<p><br></p>
<h2 style="text-align:center"><strong>ПРЕДЛАГАЮ:</strong></h2>
<p><br></p>
<ol>
<li><p style="text-align:justify">Принять необходимые меры по устранению выявленных обстоятельств, способствовавших совершению уголовного правонарушения.</p></li>
<li><p style="text-align:justify">О принятых мерах сообщить в следственный отдел в месячный срок со дня получения настоящего представления.</p></li>
</ol>
<p><br></p>
<p>Следователь ________________________________</p>
<p>_________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;________________</p>
<p><em>(звание)</em>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<em>(Ф.И.О.)</em></p>
"""

    # ── HTML → DOCX export ─────────────────────────────────────────────

    def html_to_docx(self, html_content: str, filename: str = "document.docx") -> str:
        doc = Document()

        for section in doc.sections:
            section.top_margin = Cm(2)
            section.bottom_margin = Cm(2)
            section.left_margin = Cm(3)
            section.right_margin = Cm(1.5)

        style = doc.styles["Normal"]
        font = style.font
        font.name = "Times New Roman"
        font.size = Pt(14)
        pf = style.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = Pt(0)
        pf.first_line_indent = Cm(1.25)

        lines = self._parse_html(html_content)
        for item in lines:
            align = self._html_align_to_wd(item.get("align", "left"))

            if item["type"] == "h1":
                p = doc.add_heading(item["text"], level=1)
                p.alignment = align
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(16)
            elif item["type"] == "h2":
                p = doc.add_heading(item["text"], level=2)
                p.alignment = align
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(14)
            elif item["type"] == "h3":
                p = doc.add_heading(item["text"], level=3)
                p.alignment = align
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(14)
            elif item["type"] == "li":
                p = doc.add_paragraph(item["text"], style="List Number")
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(14)
            elif item["type"] == "bullet":
                p = doc.add_paragraph(item["text"], style="List Bullet")
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(14)
            else:
                if item["text"].strip():
                    p = doc.add_paragraph(item["text"])
                    p.alignment = align

        safe_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = self.generated_dir / safe_filename
        doc.save(str(file_path))
        return str(file_path)

    @staticmethod
    def _html_align_to_wd(align: str):
        mapping = {
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        return mapping.get(align, WD_ALIGN_PARAGRAPH.LEFT)

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        items = []
        html = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)

        def _extract_align(tag_html: str) -> str:
            m = re.search(r'text-align:\s*(left|center|right|justify)', tag_html, re.IGNORECASE)
            return m.group(1) if m else "left"

        for tag, level in [("h1", "h1"), ("h2", "h2"), ("h3", "h3")]:
            def _replace_heading(m, l=level):
                align = _extract_align(m.group(0))
                text = _strip_tags(m.group(1))
                return f"[[{l}:{align}]]{text}[[/{l}]]"

            html = re.sub(
                rf"<{tag}[^>]*>(.*?)</{tag}>",
                _replace_heading,
                html, flags=re.DOTALL | re.IGNORECASE,
            )

        def _replace_p(m):
            align = _extract_align(m.group(0))
            text = _strip_tags(m.group(1))
            return f"[[p:{align}]]{text}[[/p]]"

        html = re.sub(r"<p[^>]*>(.*?)</p>", _replace_p, html, flags=re.DOTALL | re.IGNORECASE)

        html = re.sub(
            r"<li[^>]*>(.*?)</li>",
            lambda m: f"[[li]]{_strip_tags(m.group(1))}[[/li]]",
            html, flags=re.DOTALL | re.IGNORECASE,
        )

        clean = re.sub(r"<[^>]+>", "\n", html)

        for line in clean.split("\n"):
            line = line.strip()
            if not line:
                continue
            for level in ["h1", "h2", "h3"]:
                m = re.match(rf"\[\[{level}:(\w+)\]\](.*?)\[\[/{level}\]\]", line)
                if m:
                    items.append({"type": level, "text": m.group(2).strip(), "align": m.group(1)})
                    break
            else:
                m = re.match(r"\[\[p:(\w+)\]\](.*?)\[\[/p\]\]", line)
                if m:
                    items.append({"type": "p", "text": m.group(2).strip(), "align": m.group(1)})
                elif line.startswith("[[li]]"):
                    items.append({"type": "li", "text": line.replace("[[li]]", "").replace("[[/li]]", "").strip()})
                else:
                    items.append({"type": "p", "text": line, "align": "left"})

        return items


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()
