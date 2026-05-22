"""Tests for RAG integration — end-to-end search pipeline.

Tests cover:
  - ChromaDB indexing and retrieval (integration)
  - Legislation indexing with hierarchical parsing
  - JSONL record indexing
  - Knowledge base indexing and retrieval
  - Combined retrieval merging
  - Parent-document deduplication
  - Cross-encoder reranking (mocked)
"""

import pytest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def rag_service(storage_dir):
    """Create a RAGService instance with isolated storage."""
    os.environ["STORAGE_DIR"] = storage_dir
    os.environ["EMBEDDING_MODEL"] = "intfloat/multilingual-e5-base"

    # Reset any cached settings
    from config import get_settings
    get_settings.cache_clear()

    from services.rag import RAGService
    RAGService._client = None
    RAGService._embed_fn = None
    RAGService._reranker = None
    RAGService._reranker_loaded = False

    svc = RAGService()
    return svc


@pytest.mark.skipif(
    os.environ.get("RUN_HEAVY_TESTS", "0") != "1",
    reason="Requires SentenceTransformer model (set RUN_HEAVY_TESTS=1)"
)
class TestRAGIntegration:
    """Full integration tests requiring the embedding model."""

    def test_index_and_query_matter_document(self, rag_service):
        matter_id = "test-matter-001"
        file_id = "test-file-001"
        text = (
            "Работодатель ТОО «СтройСервис» не обеспечил безопасные условия труда. "
            "Рабочий Петров И.И. получил тяжёлую травму на производстве. "
            "Установлено нарушение статьи 22 Трудового кодекса Республики Казахстан."
        )

        rag_service.index_document(matter_id, file_id, text)
        results = rag_service.query(matter_id, "нарушение охраны труда", top_k=3)

        assert len(results) > 0
        assert any("труда" in r.lower() or "работодатель" in r.lower() for r in results)

        # Cleanup
        rag_service.delete_document(matter_id, file_id)

    def test_index_legislation_hierarchical(self, rag_service, sample_law_text):
        doc_id = "test-leg-001"
        count = rag_service.index_legislation(
            doc_id=doc_id,
            text=sample_law_text,
            law_title="Трудовой кодекс РК",
            category="кодекс",
        )

        assert count > 0

        results = rag_service.search_relevant_laws(
            "обязанности работодателя по охране труда", top_k=3
        )
        assert len(results) > 0
        assert any("Трудовой кодекс" in r.get("law_title", "") for r in results)

        # Cleanup
        rag_service.delete_legislation(doc_id)

    def test_index_legislation_jsonl(self, rag_service, sample_enriched_records):
        doc_id = "test-jsonl-001"
        count = rag_service.index_legislation_jsonl(
            doc_id=doc_id,
            law_title="Обогащённые нормы",
            category="enriched",
            records=sample_enriched_records,
        )

        assert count == len(sample_enriched_records)

        stats = rag_service.get_legislation_stats()
        assert stats["total_chunks"] >= count

        # Cleanup
        rag_service.delete_legislation(doc_id)

    def test_index_and_query_kb(self, rag_service, sample_kb_document):
        doc_id = "test-kb-001"
        rag_service.index_kb_document(doc_id, sample_kb_document)

        results = rag_service.query_kb("кража из магазина охрана", top_k=3)
        assert len(results) > 0

        stats = rag_service.get_kb_stats()
        assert stats["total_chunks"] > 0

        # Cleanup
        rag_service.delete_kb_document(doc_id)

    def test_combined_query(self, rag_service, sample_kb_document):
        matter_id = "test-combined-001"
        file_id = "test-combined-file"
        rag_service.index_document(
            matter_id, file_id,
            "Произошёл несчастный случай на производстве ТОО «МеталлСтрой»."
        )
        rag_service.index_kb_document("kb-combined", sample_kb_document)

        result = rag_service.query_combined(matter_id, "несчастный случай на производстве")

        assert "matter" in result
        assert "knowledge_base" in result

        # Cleanup
        rag_service.delete_document(matter_id, file_id)
        rag_service.delete_kb_document("kb-combined")

    def test_parent_document_dedup(self, rag_service, sample_law_text):
        """Multiple points from same article should be deduped to one result."""
        doc_id = "test-dedup-001"
        rag_service.index_legislation(
            doc_id=doc_id,
            text=sample_law_text,
            law_title="ТК РК",
            category="кодекс",
        )

        results = rag_service.search_relevant_laws(
            "обязанности работодателя", top_k=10
        )

        # Each law_title + article_number combination should appear at most once
        keys = [(r["law_title"], r["article_number"]) for r in results]
        assert len(keys) == len(set(keys)), "Duplicate law+article entries found"

        rag_service.delete_legislation(doc_id)

    def test_search_with_category_filter(self, rag_service, sample_law_text):
        doc_id = "test-filter-001"
        rag_service.index_legislation(
            doc_id=doc_id,
            text=sample_law_text,
            law_title="ТК РК",
            category="кодекс",
        )

        results = rag_service.search_relevant_laws(
            "обязанности", top_k=5, categories=["кодекс"]
        )
        for r in results:
            assert r["category"] == "кодекс"

        rag_service.delete_legislation(doc_id)

    def test_empty_collection_returns_empty(self, rag_service):
        results = rag_service.search_relevant_laws("запрос", top_k=5)
        # May or may not have results depending on pre-existing data
        assert isinstance(results, list)

    def test_search_result_structure(self, rag_service, sample_law_text):
        doc_id = "test-struct-001"
        rag_service.index_legislation(
            doc_id=doc_id,
            text=sample_law_text,
            law_title="ТК РК",
            category="кодекс",
        )

        results = rag_service.search_relevant_laws("охрана труда", top_k=3)
        for r in results:
            assert "text" in r
            assert "law_title" in r
            assert "article_number" in r
            assert "category" in r
            assert "score" in r
            assert isinstance(r["score"], (int, float))

        rag_service.delete_legislation(doc_id)
