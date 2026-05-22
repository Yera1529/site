"""Tests for DocumentService — HTML parsing and DOCX export.

Tests cover:
  - HTML to document items parsing
  - Float span detection (date/city, signature lines)
  - Heading and paragraph handling
  - List item extraction
  - DOCX export correctness
  - Template HTML structure
"""

import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.document import DocumentService, _parse_html_ordered


class TestHtmlParsing:
    """_parse_html_ordered: single-pass HTML → items."""

    def test_simple_paragraph(self):
        html = '<p style="text-align:justify">Текст параграфа.</p>'
        items = _parse_html_ordered(html)
        assert len(items) == 1
        assert items[0]["type"] == "p"
        assert items[0]["text"] == "Текст параграфа."
        assert items[0]["align"] == "justify"

    def test_heading_h1(self):
        html = '<h1 style="text-align:center">ПРЕДСТАВЛЕНИЕ</h1>'
        items = _parse_html_ordered(html)
        assert len(items) == 1
        assert items[0]["type"] == "h1"
        assert items[0]["text"] == "ПРЕДСТАВЛЕНИЕ"
        assert items[0]["align"] == "center"

    def test_heading_h2(self):
        html = '<h2 style="text-align:center">Подзаголовок</h2>'
        items = _parse_html_ordered(html)
        assert len(items) == 1
        assert items[0]["type"] == "h2"

    def test_list_items(self):
        html = "<ol><li>Пункт первый.</li><li>Пункт второй.</li></ol>"
        items = _parse_html_ordered(html)
        li_items = [i for i in items if i["type"] == "li"]
        assert len(li_items) == 2
        assert "Пункт первый" in li_items[0]["text"]

    def test_float_spans_parsed(self):
        html = (
            '<p><span style="float:left">15.01.2025 г.</span>'
            '<span style="float:right">г. Астана</span></p>'
        )
        items = _parse_html_ordered(html)
        assert len(items) == 1
        assert items[0]["type"] == "tab_row"
        assert items[0]["left"] == "15.01.2025 г."
        assert items[0]["right"] == "г. Астана"

    def test_right_aligned_paragraph(self):
        html = '<p style="text-align:right">Директору ТОО</p>'
        items = _parse_html_ordered(html)
        assert items[0]["align"] == "right"

    def test_empty_paragraph_is_blank(self):
        html = "<p></p>"
        items = _parse_html_ordered(html)
        assert len(items) == 1
        assert items[0]["type"] == "blank"

    def test_br_inside_text(self):
        html = "<p>Строка 1<br>Строка 2</p>"
        items = _parse_html_ordered(html)
        assert len(items) >= 1

    def test_entity_decoding(self):
        html = "<p>&amp; &lt; &gt; &nbsp;</p>"
        items = _parse_html_ordered(html)
        if items and items[0].get("text"):
            text = items[0]["text"]
            assert "&" in text
            assert "<" in text
            assert ">" in text

    def test_style_tags_ignored(self):
        html = "<style>.foo { color: red; }</style><p>Текст.</p>"
        items = _parse_html_ordered(html)
        p_items = [i for i in items if i["type"] == "p"]
        assert len(p_items) == 1
        assert ".foo" not in p_items[0]["text"]

    def test_complex_document_order_preserved(self):
        html = """
        <p style="text-align:right">Адресат</p>
        <h1 style="text-align:center">ЗАГОЛОВОК</h1>
        <p style="text-align:justify">Основной текст.</p>
        <ol><li>Пункт 1</li><li>Пункт 2</li></ol>
        <p>Подпись</p>
        """
        items = _parse_html_ordered(html)
        types = [i["type"] for i in items]
        # Verify order
        assert types.index("h1") > types.index("p")  # heading after addressee
        li_indices = [i for i, t in enumerate(types) if t == "li"]
        assert len(li_indices) == 2


class TestDocxExport:
    """DocumentService.html_to_docx: end-to-end export."""

    @pytest.fixture
    def doc_service(self, temp_dir):
        os.environ["STORAGE_DIR"] = temp_dir
        os.makedirs(os.path.join(temp_dir, "generated"), exist_ok=True)
        return DocumentService()

    def test_export_simple_html(self, doc_service):
        html = """
        <h1 style="text-align:center">П Р Е Д С Т А В Л Е Н И Е</h1>
        <p style="text-align:justify">Текст представления.</p>
        <ol><li>Принять меры.</li></ol>
        """
        path = doc_service.html_to_docx(html, "test.docx")
        assert os.path.exists(path)
        assert path.endswith(".docx")
        assert os.path.getsize(path) > 0

    def test_export_with_float_spans(self, doc_service):
        html = """
        <p><span style="float:left">15.01.2025 г.</span>
        <span style="float:right">г. Астана</span></p>
        <div style="clear:both"></div>
        <p>Текст</p>
        """
        path = doc_service.html_to_docx(html, "float_test.docx")
        assert os.path.exists(path)

    def test_export_empty_html(self, doc_service):
        path = doc_service.html_to_docx("<p></p>", "empty.docx")
        assert os.path.exists(path)


class TestTemplateHtml:
    """representation_template_html: structured template."""

    def test_template_contains_title(self):
        html = DocumentService.representation_template_html()
        assert "П Р Е Д С Т А В Л Е Н И Е" in html

    def test_template_contains_propose(self):
        html = DocumentService.representation_template_html()
        assert "ПРЕДЛАГАЮ" in html

    def test_template_contains_float_spans(self):
        html = DocumentService.representation_template_html()
        assert "float:left" in html
        assert "float:right" in html

    def test_template_contains_signature_block(self):
        html = DocumentService.representation_template_html()
        assert "звание" in html.lower() or "Ф.И.О" in html

    def test_template_has_erd_placeholder(self):
        html = DocumentService.representation_template_html()
        assert "ЕРДР" in html

    def test_template_has_addressee(self):
        html = DocumentService.representation_template_html()
        assert "text-align:right" in html
        assert "Руководителю" in html
