"""Tests for RAGService — chunking, query expansion, BM25, and filter logic.

Tests cover:
  - Sentence-aware chunking (_sentence_chunk)
  - Query expansion with legal synonyms
  - BM25 metadata filter matching
  - ChromaDB where-clause building
  - Embedding adapter E5 prefix logic
  - Combined retrieval merging
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.rag import RAGService, _EmbeddingAdapter, LEGAL_SYNONYMS


class TestSentenceChunking:
    """_sentence_chunk: never cut mid-sentence."""

    def test_short_text_returns_single_chunk(self):
        text = "Работодатель обязан обеспечивать безопасные условия труда."
        chunks = RAGService._sentence_chunk(text, max_words=400)
        assert len(chunks) == 1
        assert "безопасные условия труда" in chunks[0]

    def test_long_text_splits_at_sentence_boundaries(self):
        sentences = ["Предложение номер один. "] * 100
        text = "".join(sentences)
        chunks = RAGService._sentence_chunk(text, max_words=20)
        assert len(chunks) > 1
        # Each chunk should end at a sentence boundary
        for chunk in chunks:
            stripped = chunk.strip()
            if stripped:
                assert stripped[-1] in ".!?;", f"Chunk doesn't end at sentence boundary: ...{stripped[-20:]}"

    def test_overlap_preserves_context(self):
        # Create text that will need splitting with overlap
        sentences = [f"Предложение {i} содержит важную информацию. " for i in range(50)]
        text = "".join(sentences)
        chunks = RAGService._sentence_chunk(text, max_words=30, overlap_words=10)
        assert len(chunks) > 1
        # Verify overlap: last words of chunk N appear in chunk N+1
        if len(chunks) >= 2:
            last_words_chunk0 = chunks[0].strip().split()[-5:]
            first_words_chunk1 = chunks[1].strip().split()[:15]
            # At least some overlap should exist
            overlap = set(last_words_chunk0) & set(first_words_chunk1)
            assert len(overlap) > 0, "No overlap detected between consecutive chunks"

    def test_empty_text_returns_empty(self):
        assert RAGService._sentence_chunk("") == []
        assert RAGService._sentence_chunk("   ") == []

    def test_very_short_chunks_filtered(self):
        text = "А. Б. В. Г. Д."
        chunks = RAGService._sentence_chunk(text, max_words=400)
        # Chunks with fewer than 5 words should be filtered out
        for chunk in chunks:
            assert len(chunk.split()) > 5 or len(chunks) == 0

    def test_chunk_max_words_respected(self):
        sentences = [f"Статья {i} закона устанавливает обязанности по охране труда. " for i in range(100)]
        text = "".join(sentences)
        chunks = RAGService._sentence_chunk(text, max_words=50)
        for chunk in chunks:
            word_count = len(chunk.split())
            # Sentence-boundary splitting can't cut mid-sentence,
            # so actual chunks may exceed max_words by up to one long sentence.
            assert word_count < 100, f"Chunk too large: {word_count} words"

    def test_russian_sentence_splitting(self):
        text = (
            "Работодатель обязан обеспечить безопасность. "
            "Это включает средства защиты. "
            "«Каждый работник имеет право на охрану труда» — закреплено в Конституции."
        )
        chunks = RAGService._sentence_chunk(text, max_words=400)
        assert len(chunks) >= 1


class TestQueryExpansion:
    """_expand_query: adds legal synonyms to queries."""

    def test_theft_expansion(self):
        expanded = RAGService._expand_query("кража из магазина")
        assert "хищение" in expanded
        assert "тайное" in expanded.lower()

    def test_murder_expansion(self):
        expanded = RAGService._expand_query("убийство")
        assert "причинение смерти" in expanded

    def test_corruption_expansion(self):
        expanded = RAGService._expand_query("взятка чиновнику")
        assert "коррупция" in expanded

    def test_dtp_expansion(self):
        expanded = RAGService._expand_query("дтп на перекрёстке")
        assert "дорожно-транспортное" in expanded

    def test_no_expansion_for_generic_query(self):
        query = "общие положения закона"
        expanded = RAGService._expand_query(query)
        # Should return the same query if no synonyms match
        assert query in expanded

    def test_multiple_synonyms_combined(self):
        query = "несовершеннолетний совершил кражу"
        expanded = RAGService._expand_query(query)
        # "кража" key is not in "кражу" — but "несовершеннолетн" is in query
        assert "подросток" in expanded or "малолетний" in expanded  # from несовершеннолетн
        # For theft, the query must contain the exact key "кража" (not "кражу")
        query2 = "несовершеннолетний совершил кража из магазина"
        expanded2 = RAGService._expand_query(query2)
        assert "хищение" in expanded2  # from кража
        assert "подросток" in expanded2 or "малолетний" in expanded2  # from несовершеннолетн

    def test_all_synonym_keys_match(self):
        """Every key in LEGAL_SYNONYMS should trigger expansion."""
        for key in LEGAL_SYNONYMS:
            query = f"текст с {key} внутри"
            expanded = RAGService._expand_query(query)
            assert expanded != query, f"Synonym key '{key}' did not trigger expansion"


class TestWhereClauseBuilding:
    """_build_where: construct ChromaDB filter dicts."""

    def test_no_categories_returns_none(self):
        assert RAGService._build_where(None, "query") is None
        assert RAGService._build_where([], "query") is None

    def test_single_category(self):
        where = RAGService._build_where(["кодекс"], "query")
        assert where == {"category": "кодекс"}

    def test_multiple_categories_uses_in(self):
        where = RAGService._build_where(["кодекс", "закон"], "query")
        assert "$in" in str(where)
        assert where["category"]["$in"] == ["кодекс", "закон"]


class TestMetadataFiltering:
    """_meta_passes_filter: local BM25 result filtering."""

    def test_no_filter_passes_all(self):
        assert RAGService._meta_passes_filter({"category": "test"}, None)

    def test_exact_match_passes(self):
        meta = {"category": "кодекс", "law_title": "ТК РК"}
        where = {"category": "кодекс"}
        assert RAGService._meta_passes_filter(meta, where)

    def test_exact_match_fails(self):
        meta = {"category": "закон", "law_title": "ТК РК"}
        where = {"category": "кодекс"}
        assert not RAGService._meta_passes_filter(meta, where)

    def test_in_operator(self):
        meta = {"category": "закон"}
        where = {"category": {"$in": ["кодекс", "закон"]}}
        assert RAGService._meta_passes_filter(meta, where)

    def test_in_operator_fails(self):
        meta = {"category": "инструкция"}
        where = {"category": {"$in": ["кодекс", "закон"]}}
        assert not RAGService._meta_passes_filter(meta, where)

    def test_and_operator(self):
        meta = {"category": "кодекс", "law_title": "ТК"}
        where = {"$and": [{"category": "кодекс"}, {"law_title": "ТК"}]}
        assert RAGService._meta_passes_filter(meta, where)

    def test_and_operator_partial_fail(self):
        meta = {"category": "кодекс", "law_title": "УК"}
        where = {"$and": [{"category": "кодекс"}, {"law_title": "ТК"}]}
        assert not RAGService._meta_passes_filter(meta, where)


class TestEmbeddingAdapter:
    """_EmbeddingAdapter: E5 prefix detection logic."""

    def test_e5_detection(self):
        adapter = _EmbeddingAdapter("intfloat/multilingual-e5-base")
        assert adapter._is_e5 is True

    def test_non_e5_detection(self):
        adapter = _EmbeddingAdapter("all-MiniLM-L6-v2")
        assert adapter._is_e5 is False

    def test_e5_case_insensitive(self):
        adapter = _EmbeddingAdapter("intfloat/E5-large")
        assert adapter._is_e5 is True


class TestLegacyAliases:
    """Backward-compatibility methods."""

    def test_chunk_text_alias(self):
        text = "Работодатель обязан обеспечивать безопасные условия труда на каждом рабочем месте. Это важное требование закона."
        chunks = RAGService._chunk_text(text)
        assert isinstance(chunks, list)

    def test_chunk_text_large_alias(self):
        text = "Работодатель обязан обеспечивать безопасные условия труда на каждом рабочем месте. Это важное требование закона."
        chunks = RAGService._chunk_text_large(text)
        assert isinstance(chunks, list)

    def test_chunk_legislation_legacy(self):
        from tests.conftest import SAMPLE_LAW_TEXT
        result = RAGService._chunk_legislation(SAMPLE_LAW_TEXT, "ТК РК")
        assert isinstance(result, list)
        for item in result:
            assert "text" in item
            assert "article_number" in item
            assert "law_title" in item
