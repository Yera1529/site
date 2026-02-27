"""Retrieval-Augmented Generation service using ChromaDB with SentenceTransformer embeddings.

Four collections:
  - Per-matter: case files for each matter
  - knowledge_base_art200: article-200 representation samples
  - legislation: uploaded laws with article-level metadata
  - legislation_summaries: per-chunk summaries for improved global context

Two-stage retrieval for legislation:
  1. Fast bi-encoder (SentenceTransformer) fetches top-20 candidates
  2. Cross-encoder reranker (if available) rescores and returns top-N
"""

import re
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer, CrossEncoder
from config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
LEG_CHUNK_SIZE = 800
LEG_CHUNK_OVERLAP = 160
KB_COLLECTION = "knowledge_base_art200"
LEGISLATION_COLLECTION = "legislation"

LEGAL_SYNONYMS = {
    "убийство": "причинение смерти, насильственная смерть, лишение жизни, умышленное причинение смерти",
    "кража": "хищение, тайное хищение чужого имущества, тайное завладение",
    "мошенничество": "обман, злоупотребление доверием, завладение путём обмана",
    "хулиганство": "грубое нарушение общественного порядка, дерзость, хулиганские побуждения",
    "наркотик": "наркотическое средство, психотропное вещество, запрещённое вещество, оборот наркотиков",
    "алкоголь": "спиртные напитки, опьянение, употребление алкоголя, нетрезвое состояние, алкогольное опьянение",
    "нож": "холодное оружие, колюще-режущее, орудие преступления, клинковое оружие",
    "оружие": "огнестрельное оружие, боеприпасы, вооружение, незаконное хранение",
    "побои": "причинение вреда здоровью, телесные повреждения, избиение",
    "пожар": "возгорание, противопожарная безопасность, огонь, пожарная безопасность",
    "дтп": "дорожно-транспортное происшествие, авария, наезд, нарушение ПДД",
    "несовершеннолетн": "малолетний, ребёнок, подросток, лицо не достигшее 18 лет",
    "должностн": "государственный служащий, чиновник, служебное положение, должностное лицо",
    "взятк": "коррупция, получение взятки, дача взятки, подкуп, коррупционное",
    "превышени": "превышение должностных полномочий, злоупотребление властью",
    "халатност": "ненадлежащее исполнение обязанностей, бездействие, неисполнение",
    "безопасност": "охрана труда, техника безопасности, промышленная безопасность, правила безопасности",
    "торговл": "продажа, реализация, сбыт, незаконная торговля",
    "надзор": "контроль, проверка, инспекция, государственный надзор",
    "лицензи": "разрешение, лицензирование, разрешительный документ",
}


class _EmbeddingAdapter:
    """Wraps SentenceTransformer for ChromaDB's EmbeddingFunction protocol.

    For E5-family models, documents are prefixed with 'passage: ' automatically.
    Use encode_queries() for query-time encoding with 'query: ' prefix.
    """

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)
        self._is_e5 = "e5" in model_name.lower()

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Encode documents (used by ChromaDB during add/upsert)."""
        if self._is_e5:
            input = [f"passage: {t}" for t in input]
        return self.model.encode(input, show_progress_bar=False).tolist()

    def encode_queries(self, queries: list[str]) -> list[list[float]]:
        """Encode queries with proper prefix for E5 models."""
        if self._is_e5:
            queries = [f"query: {q}" for q in queries]
        return self.model.encode(queries, show_progress_bar=False).tolist()


class RAGService:
    _client = None
    _embed_fn = None
    _reranker = None
    _reranker_loaded = False

    def __init__(self):
        settings = get_settings()
        if RAGService._client is None:
            RAGService._client = chromadb.PersistentClient(
                path=f"{settings.storage_dir}/chroma_db",
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        if RAGService._embed_fn is None:
            RAGService._embed_fn = _EmbeddingAdapter(settings.embedding_model)
        if not RAGService._reranker_loaded:
            RAGService._reranker_loaded = True
            try:
                RAGService._reranker = CrossEncoder(
                    "BAAI/bge-reranker-v2-m3", max_length=512
                )
                logger.info("Cross-encoder reranker loaded: BAAI/bge-reranker-v2-m3")
            except Exception as e:
                logger.warning("Cross-encoder reranker unavailable, skipping rerank stage: %s", e)
                RAGService._reranker = None

    # ── Per-matter collections ──────────────────────────────────────────

    def _get_collection(self, matter_id: str):
        return self._client.get_or_create_collection(
            name=f"matter_{matter_id}",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embed_fn,
        )

    def index_document(self, matter_id: str, file_id: str, text: str) -> None:
        collection = self._get_collection(matter_id)
        chunks = self._chunk_text(text)
        if not chunks:
            return
        ids = [f"{file_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"file_id": file_id, "chunk_index": i} for i in range(len(chunks))]
        collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    def query(self, matter_id: str, query_text: str, top_k: int = 5) -> list[str]:
        try:
            collection = self._get_collection(matter_id)
            if collection.count() == 0:
                return []
            # Use query embeddings with proper E5 prefix
            q_emb = self._embed_fn.encode_queries([query_text])
            results = collection.query(
                query_embeddings=q_emb,
                n_results=min(top_k, collection.count()),
            )
            return results["documents"][0] if results["documents"] else []
        except Exception:
            return []

    def delete_document(self, matter_id: str, file_id: str) -> None:
        try:
            collection = self._get_collection(matter_id)
            existing = collection.get(where={"file_id": file_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

    # ── Global knowledge base (article-200 representations) ────────────

    def _get_kb_collection(self):
        return self._client.get_or_create_collection(
            name=KB_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embed_fn,
        )

    def index_kb_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        collection = self._get_kb_collection()
        chunks = self._chunk_text(text)
        if not chunks:
            return
        base_meta = {"doc_id": doc_id, "article": "200", "doc_type": "представление"}
        if metadata:
            base_meta.update(metadata)
        ids = [f"kb_{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{**base_meta, "chunk_index": i} for i in range(len(chunks))]
        collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    def query_kb(self, query_text: str, top_k: int = 5, article: str = "200") -> list[str]:
        try:
            collection = self._get_kb_collection()
            if collection.count() == 0:
                return []
            q_emb = self._embed_fn.encode_queries([query_text])
            results = collection.query(
                query_embeddings=q_emb,
                n_results=min(top_k, collection.count()),
                where={"article": article},
            )
            return results["documents"][0] if results["documents"] else []
        except Exception:
            return []

    def delete_kb_document(self, doc_id: str) -> None:
        try:
            collection = self._get_kb_collection()
            existing = collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

    def get_kb_stats(self) -> dict:
        try:
            collection = self._get_kb_collection()
            return {"total_chunks": collection.count()}
        except Exception:
            return {"total_chunks": 0}

    # ── Combined retrieval ─────────────────────────────────────────────

    def query_combined(
        self,
        matter_id: str,
        query_text: str,
        top_k_matter: int = 3,
        top_k_kb: int = 5,
    ) -> dict[str, list[str]]:
        matter_chunks = self.query(matter_id, query_text, top_k=top_k_matter)
        kb_chunks = self.query_kb(query_text, top_k=top_k_kb)
        return {"matter": matter_chunks, "knowledge_base": kb_chunks}

    # ── Legislation collection ─────────────────────────────────────────

    def _get_legislation_collection(self):
        return self._client.get_or_create_collection(
            name=LEGISLATION_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embed_fn,
        )

    def index_legislation(
        self, doc_id: str, text: str, law_title: str, category: str
    ) -> int:
        """Index a legislation document with summary-augmented chunks."""
        collection = self._get_legislation_collection()
        articles = self._chunk_legislation(text, law_title)

        if not articles:
            chunks = self._chunk_text_large(text)
            articles = [
                {"text": c, "article_number": "", "law_title": law_title}
                for c in chunks
            ]

        if not articles:
            return 0

        ids = []
        documents = []
        metadatas = []

        for i, a in enumerate(articles):
            chunk_text = a["text"]
            art_num = a.get("article_number", "")

            summary = self._generate_chunk_summary(chunk_text, law_title, art_num)

            doc_with_summary = chunk_text
            if summary:
                doc_with_summary = f"[Краткое содержание: {summary}]\n\n{chunk_text}"

            ids.append(f"leg_{doc_id}_chunk_{i}")
            documents.append(doc_with_summary)
            metadatas.append({
                "doc_id": doc_id,
                "law_title": a.get("law_title", law_title),
                "article_number": art_num,
                "category": category,
                "chunk_type": "article" if art_num else "text",
                "summary": summary,
            })

        collection.add(documents=documents, ids=ids, metadatas=metadatas)
        return len(articles)

    @staticmethod
    def _generate_chunk_summary(text: str, law_title: str, article_number: str) -> str:
        """Generate a brief extractive summary for a legislation chunk.

        Uses the first meaningful sentence plus article reference rather than
        calling an LLM, to keep indexing fast and dependency-free.
        """
        clean = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+", clean)
        meaningful = [s for s in sentences if len(s.split()) > 5]

        if not meaningful:
            prefix = f"{law_title}, Статья {article_number}" if article_number else law_title
            return f"{prefix}: {clean[:150]}"

        first = meaningful[0][:200]
        prefix = f"ст.{article_number} {law_title}" if article_number else law_title
        return f"{prefix} — {first}"

    def search_relevant_laws(
        self, query: str, top_k: int = 10, categories: list[str] | None = None
    ) -> list[dict]:
        """Two-stage retrieval: bi-encoder fetch → cross-encoder rerank.

        Stage 1: Fetch top-20 candidates using the bi-encoder (via ChromaDB).
                 Runs both original and synonym-expanded queries.
        Stage 2: Rerank candidates with a cross-encoder (if available).
        Returns the top-k results with text, metadata and score.
        """
        try:
            collection = self._get_legislation_collection()
            if collection.count() == 0:
                return []

            where_filter = None
            if categories and len(categories) == 1:
                where_filter = {"category": categories[0]}
            elif categories and len(categories) > 1:
                where_filter = {"category": {"$in": categories}}

            # Stage 1: bi-encoder retrieval with query expansion
            expanded = self._expand_legal_query(query)
            queries = [query]
            if expanded != query:
                queries.append(expanded)

            fetch_k = min(30, collection.count())
            seen_ids: set[str] = set()
            candidates: list[dict] = []

            for q in queries:
                # Encode query with proper E5 prefix
                q_emb = self._embed_fn.encode_queries([q])
                kwargs = {
                    "query_embeddings": q_emb,
                    "n_results": fetch_k,
                }
                if where_filter:
                    kwargs["where"] = where_filter

                results = collection.query(
                    **kwargs, include=["documents", "metadatas", "distances"]
                )

                if results["documents"] and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
                    dists = results["distances"][0] if results["distances"] else [0.0] * len(docs)
                    ids = results["ids"][0] if results["ids"] else [str(i) for i in range(len(docs))]

                    for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists):
                        if chunk_id in seen_ids:
                            continue
                        seen_ids.add(chunk_id)
                        bi_score = round(1.0 - dist, 4) if dist <= 1.0 else round(1.0 / (1.0 + dist), 4)
                        candidates.append({
                            "text": doc,
                            "law_title": meta.get("law_title", ""),
                            "article_number": meta.get("article_number", ""),
                            "category": meta.get("category", ""),
                            "summary": meta.get("summary", ""),
                            "bi_score": bi_score,
                            "score": bi_score,
                        })

            # Stage 2: cross-encoder reranking
            if self._reranker and candidates:
                pairs = [[query, c["text"][:512]] for c in candidates]
                try:
                    rerank_scores = self._reranker.predict(pairs)
                    for c, rs in zip(candidates, rerank_scores):
                        c["score"] = round(float(rs), 4)
                except Exception:
                    pass

            candidates.sort(key=lambda x: x["score"], reverse=True)

            result = []
            for c in candidates[:top_k]:
                result.append({
                    "text": c["text"],
                    "law_title": c["law_title"],
                    "article_number": c["article_number"],
                    "category": c["category"],
                    "score": c["score"],
                })
            return result
        except Exception:
            return []

    @staticmethod
    def _expand_legal_query(query: str) -> str:
        """Add legal synonyms to the query to improve recall."""
        lower = query.lower()
        additions = []
        for key, expansion in LEGAL_SYNONYMS.items():
            if key in lower:
                additions.append(expansion)
        if additions:
            return query + " " + " ".join(additions)
        return query

    def delete_legislation(self, doc_id: str) -> None:
        try:
            collection = self._get_legislation_collection()
            existing = collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

    def get_legislation_stats(self) -> dict:
        try:
            collection = self._get_legislation_collection()
            return {"total_chunks": collection.count()}
        except Exception:
            return {"total_chunks": 0}

    # ── Text chunking ──────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        """Split text into ~512-word overlapping chunks."""
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = start + CHUNK_SIZE
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk.strip())
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    @staticmethod
    def _chunk_text_large(text: str) -> list[str]:
        """Larger chunks for legislation (800 words, 160 overlap — ~20%)."""
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = start + LEG_CHUNK_SIZE
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk.strip())
            start += LEG_CHUNK_SIZE - LEG_CHUNK_OVERLAP
        return chunks

    @staticmethod
    def _chunk_legislation(text: str, law_title: str) -> list[dict]:
        """Split legislation text at article boundaries."""
        pattern = r"(Статья\s+(\d+[\.\d]*)[\.\s\)])"
        splits = re.split(pattern, text, flags=re.IGNORECASE)

        if len(splits) < 4:
            return []

        articles = []
        i = 0
        while i < len(splits):
            if i + 3 <= len(splits) and re.match(pattern, splits[i + 1] if i + 1 < len(splits) else "", re.IGNORECASE):
                article_header = splits[i + 1]
                article_num = splits[i + 2]
                article_body = splits[i + 3] if i + 3 < len(splits) else ""
                full_text = (article_header + article_body).strip()

                if len(full_text.split()) > 1600:
                    sub_chunks = RAGService._chunk_text_large(full_text)
                    for sc in sub_chunks:
                        articles.append({
                            "text": sc,
                            "article_number": article_num,
                            "law_title": law_title,
                        })
                elif full_text:
                    articles.append({
                        "text": full_text,
                        "article_number": article_num,
                        "law_title": law_title,
                    })
                i += 4
            else:
                preamble = splits[i].strip()
                if preamble and len(preamble.split()) > 20:
                    articles.append({
                        "text": preamble,
                        "article_number": "",
                        "law_title": law_title,
                    })
                i += 1

        return articles

    @staticmethod
    def parse_articles(text: str) -> list[dict]:
        """Parse legislation text into a list of {number, title, text} for UI display."""
        pattern = r"Статья\s+(\d+[\.\d]*)\s*[\.\)]\s*(.*?)(?=Статья\s+\d+[\.\d]*\s*[\.\)]|$)"
        matches = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        articles = []
        for num, body in matches:
            lines = body.strip().split("\n", 1)
            title = lines[0].strip().rstrip(".") if lines else ""
            art_text = lines[1].strip() if len(lines) > 1 else body.strip()
            articles.append({"number": num, "title": title[:200], "text": art_text[:2000]})
        return articles
