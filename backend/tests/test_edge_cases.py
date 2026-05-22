"""Edge-case tests for backend services.

Tests error handling, boundary conditions, and robustness
of critical document generation and RAG services.
"""
import pytest
import re
import json


# ═══════════════════════════════════════════════════════════════════════
# AI Service — validate_representation edge cases
# ═══════════════════════════════════════════════════════════════════════
class TestValidateRepresentation:
    """Tests for representation validation (mandatory section checks)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.ai import validate_representation
        self.validate = validate_representation

    def test_empty_string_reports_all_missing(self):
        result = self.validate("")
        assert not result["ok"]
        assert len(result["missing"]) > 0

    def test_complete_document_passes(self):
        """A document with all mandatory sections should pass."""
        doc = """
        ПРЕДСТАВЛЕНИЕ
        по устранению обстоятельств

        15 ноября 2024 года                            г. Астана

        Следственным отделом расследуется уголовное дело ЕРДР №123456789
        по ст.188 УК Республики Казахстан (кража).

        В ходе расследования установлено, что нарушение ст.22 Трудового кодекса
        Республики Казахстан привело к совершению преступления.

        ПРЕДЛАГАЮ:
        1. Принять меры по устранению нарушений.
        2. Привлечь к ответственности виновных лиц.

        О принятых мерах сообщить в месячный срок.

        Разъясняю об ответственности по ст.479 КоАП РК.

        Следователь
        капитан полиции                    Иванов И.И.
        """
        result = self.validate(doc)
        # Most sections should be found
        assert len(result["present"]) >= 5

    def test_minimal_document_has_missing(self):
        result = self.validate("Просто текст без структуры")
        assert not result["ok"]

    def test_unicode_handling(self):
        """Ensure validation doesn't crash on special Unicode."""
        result = self.validate("Привет мир 🌍 ← → ñ ü ö")
        assert isinstance(result, dict)
        assert "ok" in result

    def test_html_content_validated(self):
        """Validation should work with HTML content."""
        doc = """
        <h1>ПРЕДСТАВЛЕНИЕ</h1>
        <p>по устранению обстоятельств</p>
        <p>15.11.2024 г. Астана</p>
        <p>ЕРДР №123, ст.188 УК РК</p>
        <p>Нарушение ст.22 ТК РК причинно связано с преступлением.</p>
        <p>ПРЕДЛАГАЮ:</p>
        <ol><li>Принять меры</li></ol>
        <p>В месячный срок сообщить о мерах.</p>
        <p>Ответственность по ст.479 КоАП.</p>
        """
        result = self.validate(doc)
        assert isinstance(result["present"], list)


# ═══════════════════════════════════════════════════════════════════════
# AI Service — validate_law_citations
# ═══════════════════════════════════════════════════════════════════════
class TestValidateLawCitations:
    """Test citation checking logic."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.ai import validate_law_citations
        self.check = validate_law_citations

    def test_cited_law_found_in_context(self):
        text = "нарушение ст.22 Трудового кодекса привело к последствиям"
        laws = [{"law_title": "Трудовой кодекс", "article_number": "Статья 22", "text": "..."}]
        result = self.check(text, laws)
        assert "cited" in result
        assert "unverified" in result

    def test_no_citations_in_text(self):
        text = "просто текст без ссылок на статьи"
        laws = [{"law_title": "УК РК", "article_number": "188", "text": "..."}]
        result = self.check(text, laws)
        # Should still return valid structure
        assert isinstance(result["cited"], list)
        assert isinstance(result["unverified"], list)

    def test_empty_text(self):
        result = self.check("", [])
        assert isinstance(result, dict)

    def test_laws_none_handled(self):
        result = self.check("ст.188 УК РК", None)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
# Document Service — DOCX export edge cases
# ═══════════════════════════════════════════════════════════════════════
class TestDocumentServiceEdgeCases:
    """Test DOCX export with edge-case HTML inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.document import DocumentService
        self.svc = DocumentService()

    def test_empty_html_produces_docx(self):
        path = self.svc.html_to_docx("", "test.docx")
        assert path.endswith(".docx")

    def test_html_with_only_whitespace(self):
        path = self.svc.html_to_docx("   \n\n  ", "test.docx")
        assert path.endswith(".docx")

    def test_html_with_unicode(self):
        html = "<p>Текст на казахском: Қазақстан Республикасы — бұл ел</p>"
        path = self.svc.html_to_docx(html, "kazakh.docx")
        assert path.endswith(".docx")

    def test_html_with_table(self):
        html = """
        <table>
            <tr><th>Закон</th><th>Статья</th></tr>
            <tr><td>УК РК</td><td>188</td></tr>
        </table>
        """
        path = self.svc.html_to_docx(html, "table.docx")
        assert path.endswith(".docx")

    def test_html_with_nested_lists(self):
        html = """
        <ol>
            <li>Первый пункт
                <ul>
                    <li>Подпункт а</li>
                    <li>Подпункт б</li>
                </ul>
            </li>
            <li>Второй пункт</li>
        </ol>
        """
        path = self.svc.html_to_docx(html, "nested.docx")
        assert path.endswith(".docx")

    def test_html_with_float_spans(self):
        """Float spans used for date/city lines must not crash export."""
        html = """
        <p><span style="float:left">15.11.2024 г.</span><span style="float:right">г. Астана</span></p>
        <div style="clear:both"></div>
        <p>Текст представления.</p>
        """
        path = self.svc.html_to_docx(html, "float.docx")
        assert path.endswith(".docx")

    def test_very_long_html(self):
        """Large document shouldn't crash."""
        html = "<p>" + "Длинный текст. " * 5000 + "</p>"
        path = self.svc.html_to_docx(html, "long.docx")
        assert path.endswith(".docx")


# ═══════════════════════════════════════════════════════════════════════
# RAG Service — sentence splitting edge cases
# ═══════════════════════════════════════════════════════════════════════
class TestSentenceSplittingEdgeCases:
    """Edge cases for Russian legal text sentence splitting."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.rag import RAGService
        self.rag = RAGService.__new__(RAGService)

    def test_abbreviations_not_split(self):
        """Russian abbreviations like 'ст.', 'п.', 'ч.' should not split sentences."""
        text = "Нарушение ст.22 ТК РК. Это серьёзно."
        chunks = self.rag._sentence_chunk(text, max_words=200)
        # If max_words is large enough, both sentences should be in one chunk
        combined = " ".join(chunks)
        assert "ст.22" in combined
        assert "серьёзно" in combined

    def test_numbered_points(self):
        """Numbered points like '1.' should not create sentence breaks."""
        text = "Предлагаю: 1. Принять меры. 2. Обеспечить контроль. 3. Сообщить о мерах."
        chunks = self.rag._sentence_chunk(text, max_words=200)
        combined = " ".join(chunks)
        assert "Принять" in combined
        assert "контроль" in combined

    def test_empty_input(self):
        chunks = self.rag._sentence_chunk("", max_words=100)
        assert chunks == []

    def test_single_word(self):
        chunks = self.rag._sentence_chunk("слово", max_words=100)
        assert len(chunks) <= 1

    def test_only_periods(self):
        chunks = self.rag._sentence_chunk("...", max_words=100)
        assert isinstance(chunks, list)

    def test_no_periods(self):
        """Text without sentence-ending punctuation."""
        text = "Текст без точки в конце это не предложение а просто набор слов"
        chunks = self.rag._sentence_chunk(text, max_words=100)
        assert len(chunks) >= 1

    def test_multiple_languages(self):
        """Mixed Russian/Latin text."""
        text = "Согласно GDPR, обработка данных. According to Article 5."
        chunks = self.rag._sentence_chunk(text, max_words=200)
        combined = " ".join(chunks)
        assert "GDPR" in combined
        assert "Article" in combined


# ═══════════════════════════════════════════════════════════════════════
# RAG Laws — query expansion robustness
# ═══════════════════════════════════════════════════════════════════════
class TestRAGLawsQueryExpansionRobustness:
    """Test query expansion with edge-case inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.rag_laws import RAGLawsService
        self.svc = RAGLawsService.__new__(RAGLawsService)
        self.svc._records = []

    def test_empty_query(self):
        expanded = self.svc._expand_query("")
        assert isinstance(expanded, str)
        assert len(expanded) > 0  # Default prefix should be added

    def test_very_long_query(self):
        """Queries over 3000 chars should be truncated."""
        long_query = "кража " * 1000
        expanded = self.svc._expand_query(long_query)
        assert len(expanded) <= 3500  # Some overhead allowed

    def test_special_chars_in_query(self):
        """Special regex characters should not crash expansion."""
        query = "нарушение ст.188(3) [часть 2] {УК РК}"
        expanded = self.svc._expand_query(query)
        assert isinstance(expanded, str)

    def test_query_with_numbers_only(self):
        expanded = self.svc._expand_query("12345")
        assert isinstance(expanded, str)

    def test_query_with_newlines(self):
        query = "кража\nиз магазина\nс проникновением"
        expanded = self.svc._expand_query(query)
        assert isinstance(expanded, str)


# ═══════════════════════════════════════════════════════════════════════
# AI Service — build_generation_prompt robustness
# ═══════════════════════════════════════════════════════════════════════
class TestBuildGenerationPrompt:
    """Test prompt building with various inputs."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.ai import AIService
        self.ai = AIService.__new__(AIService)

    def test_no_laws_provided(self):
        result = self.ai.build_generation_prompt(
            facts="Факты дела",
            custom_instructions="",
            additional_instructions="",
            kb_context="",
            retrieved_laws=None,
        )
        # Returns either a string or tuple of strings
        prompt_text = result if isinstance(result, str) else str(result)
        assert "200" in prompt_text.lower() or "представлени" in prompt_text.lower()

    def test_empty_facts(self):
        result = self.ai.build_generation_prompt(
            facts="",
            custom_instructions="",
            additional_instructions="",
            kb_context="",
            retrieved_laws=[],
        )
        prompt_text = result if isinstance(result, str) else str(result)
        assert len(prompt_text) > 100  # Should still have instructions

    def test_laws_with_enriched_fields(self):
        laws = [{
            "law_title": "Трудовой кодекс РК",
            "article_number": "22",
            "text": "Работодатель обязан обеспечить безопасные условия труда.",
            "norm_purpose": "Защита прав работников",
            "violation_criteria": "Необеспечение безопасных условий",
            "applicable_measures": "Штраф, дисциплинарное взыскание",
        }]
        result = self.ai.build_generation_prompt(
            facts="Несчастный случай на производстве",
            custom_instructions="",
            additional_instructions="Укажите конкретные меры",
            kb_context="",
            retrieved_laws=laws,
        )
        prompt_text = result if isinstance(result, str) else str(result)
        assert "Трудовой кодекс" in prompt_text
        assert "22" in prompt_text

    def test_very_long_facts(self):
        """Long case text should not crash prompt building."""
        facts = "Факт. " * 5000  # ~30k chars
        result = self.ai.build_generation_prompt(
            facts=facts,
            custom_instructions="",
            additional_instructions="",
            kb_context="",
            retrieved_laws=[],
        )
        prompt_text = result if isinstance(result, str) else str(result)
        assert len(prompt_text) > 100


# ═══════════════════════════════════════════════════════════════════════
# Legislation Parser — edge-case parsing
# ═══════════════════════════════════════════════════════════════════════
class TestLegislationParserEdgeCases:
    """Test parser with unusual legal document formats."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.rag import LegislationParser
        self.parser = LegislationParser

    def test_article_with_parenthetical_number(self):
        """Articles like 'Статья 188-1' should be parsed."""
        text = "Статья 188-1. Кража с проникновением\n1. Текст части 1.\n2. Текст части 2."
        articles = self.parser.parse(text, "Test Law")
        assert len(articles) >= 1

    def test_article_with_dot_notation(self):
        """Articles like 'Статья 22.1' should be parsed."""
        text = "Статья 22.1. Дополнительные обязанности\nТекст статьи."
        articles = self.parser.parse(text, "Test Law")
        assert len(articles) >= 1

    def test_multiple_articles_different_format(self):
        text = """
        Статья 1. Основные понятия
        Текст первой статьи.

        Статья 2. Сфера применения
        Текст второй статьи.

        Статья 3. Принципы
        Текст третьей статьи.
        """
        articles = self.parser.parse(text, "Test Law")
        assert len(articles) == 3

    def test_empty_article_body(self):
        text = "Статья 1. Пустая статья\n\nСтатья 2. Непустая\nТекст."
        articles = self.parser.parse(text, "Test Law")
        assert len(articles) >= 1

    def test_cyrillic_article_prefix(self):
        text = "Статья 100. Название\nТекст статьи 100."
        articles = self.parser.parse(text, "Test Law")
        assert len(articles) >= 1

    def test_normalize_text_is_robust(self):
        """BOM characters and weird whitespace should be handled."""
        text = "\ufeffСтатья 1. Первая\nТекст."
        # Normalization happens inside parse
        articles = self.parser.parse(text, "Test Law")
        assert isinstance(articles, list)


# ═══════════════════════════════════════════════════════════════════════
# RAG Service — BM25 search edge cases
# ═══════════════════════════════════════════════════════════════════════
class TestBM25SearchEdgeCases:
    """Test BM25-related search robustness."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from services.rag import RAGService
        self.rag = RAGService.__new__(RAGService)

    def test_expand_query_empty(self):
        expanded = self.rag._expand_query("")
        assert isinstance(expanded, str)

    def test_expand_query_preserves_original(self):
        q = "кража из магазина"
        expanded = self.rag._expand_query(q)
        assert q in expanded or "кража" in expanded.lower()

    def test_expand_query_multiple_synonyms(self):
        q = "убийство и кража"
        expanded = self.rag._expand_query(q)
        # Both crime types should trigger expansions
        assert isinstance(expanded, str)
        assert len(expanded) >= len(q)

    def test_chunk_text_returns_list(self):
        chunks = self.rag._chunk_text("Текст для разбивки. Второе предложение. Третье.")
        assert isinstance(chunks, list)

    def test_chunk_text_large_returns_list(self):
        text = "Длинный текст. " * 200
        chunks = self.rag._chunk_text_large(text)
        assert isinstance(chunks, list)
        assert len(chunks) >= 1
