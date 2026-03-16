"""World-class RAG system for legal document retrieval.

Architecture:
  - Hierarchical legislation parsing: Law → Article → Point
  - Parent-document retrieval: index points, return full articles
  - Hybrid search: semantic (bi-encoder) + lexical (BM25) + Reciprocal Rank Fusion
  - Cross-encoder reranking for final precision
  - Proper E5 query/passage prefixing
  - Three collections: per-matter, knowledge-base, legislation
"""

import re
import logging
import os
import pickle
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 100
KB_COLLECTION = "knowledge_base_art200"
LEGISLATION_COLLECTION = "legislation_v2"

LEGAL_SYNONYMS = {
    "убийство": "причинение смерти лишение жизни умышленное причинение смерти",
    "кража": "хищение тайное хищение чужого имущества тайное завладение",
    "мошенничество": "обман злоупотребление доверием завладение путём обмана",
    "хулиганство": "грубое нарушение общественного порядка хулиганские побуждения",
    "наркотик": "наркотическое средство психотропное вещество оборот наркотиков",
    "алкоголь": "спиртные напитки опьянение нетрезвое состояние",
    "нож": "холодное оружие колюще-режущее орудие преступления",
    "оружие": "огнестрельное оружие боеприпасы незаконное хранение",
    "побои": "причинение вреда здоровью телесные повреждения",
    "пожар": "возгорание противопожарная безопасность пожарная безопасность",
    "дтп": "дорожно-транспортное происшествие авария наезд нарушение ПДД",
    "несовершеннолетн": "малолетний ребёнок подросток",
    "должностн": "государственный служащий служебное положение",
    "взятк": "коррупция получение взятки дача взятки подкуп",
    "халатност": "ненадлежащее исполнение обязанностей бездействие",
    "безопасност": "охрана труда техника безопасности",
    "надзор": "контроль проверка инспекция государственный надзор",
}


# ═══════════════════════════════════════════════════════════════════════
# Embedding adapter with E5 prefix support
# ═══════════════════════════════════════════════════════════════════════

class _EmbeddingAdapter:
    def __init__(self, model_name: str):
        self._model_name = model_name
        self._model = None
        self._is_e5 = "e5" in model_name.lower()

    def _get_model(self):
        if self._model is None:
            logger.info("Loading embedding model: %s (this may take a while on first run)...", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            logger.info("Embedding model loaded successfully.")
        return self._model

    def __call__(self, input: list[str]) -> list[list[float]]:
        texts = [f"passage: {t}" for t in input] if self._is_e5 else input
        return self._get_model().encode(texts, show_progress_bar=False, normalize_embeddings=True).tolist()

    def encode_queries(self, queries: list[str]) -> list[list[float]]:
        texts = [f"query: {q}" for q in queries] if self._is_e5 else queries
        return self._get_model().encode(texts, show_progress_bar=False, normalize_embeddings=True).tolist()


# ═══════════════════════════════════════════════════════════════════════
# Legislation parser — hierarchical: Law → Article → Points
# ═══════════════════════════════════════════════════════════════════════

class LegislationParser:
    """Parses Kazakh/Russian legislation into a structured hierarchy."""

    ARTICLE_RE = re.compile(
        r"(?:^|\n)\s*Статья\s+(\d+(?:[-–]\d+)?(?:\.\d+)?)\s*[\.\)]\s*([^\n]*)",
        re.IGNORECASE,
    )
    POINT_RE = re.compile(r"^(\d+)\s*[\.\)]\s+", re.MULTILINE)

    @classmethod
    def parse(cls, text: str, law_title: str) -> list[dict]:
        """Parse full legislation text into structured articles.

        Returns list of:
          {number, title, full_text, points: [{number, text}]}
        """
        text = cls._normalize(text)
        splits = list(cls.ARTICLE_RE.finditer(text))

        if not splits:
            return []

        articles = []
        for idx, match in enumerate(splits):
            art_num = match.group(1).strip()
            art_title_raw = match.group(2).strip()
            start = match.end()
            end = splits[idx + 1].start() if idx + 1 < len(splits) else len(text)
            body = text[start:end].strip()

            art_title = cls._clean_title(art_title_raw, body)
            points = cls._extract_points(body)

            articles.append({
                "number": art_num,
                "title": art_title,
                "full_text": f"Статья {art_num}. {art_title}\n{body}",
                "points": points,
                "law_title": law_title,
            })

        return articles

    @classmethod
    def _normalize(cls, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _clean_title(cls, raw_title: str, body: str) -> str:
        t = raw_title.strip()
        t = re.sub(r"^[,;:\.\)\s]+", "", t)
        t = re.sub(r"[\(\[]+$", "", t).strip()
        t = t.rstrip(".,;:")

        if not t and body:
            first_line = body.split("\n", 1)[0].strip()
            first_line = re.sub(r"^\d+[\.\)]\s*", "", first_line)
            t = first_line[:200]
            t = re.sub(r"[\(\[]+$", "", t).strip()
            t = t.rstrip(".,;:")

        if t and t[0].islower():
            t = t[0].upper() + t[1:]
        return t[:300]

    @classmethod
    def _extract_points(cls, body: str) -> list[dict]:
        """Extract numbered points (1. ..., 2. ...) from article body."""
        point_matches = list(cls.POINT_RE.finditer(body))
        if not point_matches:
            return [{"number": "", "text": body.strip()}] if body.strip() else []

        points = []
        for idx, m in enumerate(point_matches):
            pnum = m.group(1)
            start = m.start()
            end = point_matches[idx + 1].start() if idx + 1 < len(point_matches) else len(body)
            ptext = body[start:end].strip()
            if ptext:
                points.append({"number": pnum, "text": ptext})

        preamble = body[: point_matches[0].start()].strip()
        if preamble and len(preamble.split()) > 10:
            points.insert(0, {"number": "0", "text": preamble})

        return points


# ═══════════════════════════════════════════════════════════════════════
# Main RAG Service
# ═══════════════════════════════════════════════════════════════════════

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

        self._bm25_path = f"{settings.storage_dir}/bm25_v2.pkl"
        self._bm25: dict = {"corpus": [], "meta": [], "model": None}
        self._load_bm25()

    @classmethod
    def _ensure_reranker(cls):
        """Lazy-load the cross-encoder reranker on first actual use."""
        if not cls._reranker_loaded:
            cls._reranker_loaded = True
            try:
                logger.info("Loading cross-encoder reranker (first use)...")
                cls._reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
                logger.info("Cross-encoder reranker loaded: BAAI/bge-reranker-v2-m3")
            except Exception as e:
                logger.warning("Reranker unavailable: %s", e)
                cls._reranker = None

    # ── BM25 persistence ───────────────────────────────────────────────

    def _load_bm25(self):
        if os.path.exists(self._bm25_path):
            try:
                with open(self._bm25_path, "rb") as f:
                    self._bm25 = pickle.load(f)
            except Exception:
                self._rebuild_bm25()
        else:
            self._rebuild_bm25()

    def _save_bm25(self):
        os.makedirs(os.path.dirname(self._bm25_path) or ".", exist_ok=True)
        try:
            with open(self._bm25_path, "wb") as f:
                pickle.dump(self._bm25, f)
        except Exception as e:
            logger.error("BM25 save failed: %s", e)

    def _rebuild_bm25(self):
        try:
            # Use lightweight collection access - we only read documents, no embedding needed
            col = self._client.get_or_create_collection(name=LEGISLATION_COLLECTION)
            data = col.get(include=["documents", "metadatas"])
            corpus = data.get("documents") or []
            meta = data.get("metadatas") or []
            tokenized = [d.lower().split() for d in corpus]
            model = BM25Okapi(tokenized) if tokenized else None
            self._bm25 = {"corpus": corpus, "meta": meta, "model": model}
            self._save_bm25()
        except Exception as e:
            logger.error("BM25 rebuild failed: %s", e)

    # ── Per-matter collections ─────────────────────────────────────────

    def _get_collection(self, matter_id: str):
        return self._client.get_or_create_collection(
            name=f"matter_{matter_id}",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embed_fn,
        )

    def index_document(self, matter_id: str, file_id: str, text: str) -> None:
        col = self._get_collection(matter_id)
        chunks = self._sentence_chunk(text, max_words=400, overlap_words=80)
        if not chunks:
            return
        ids = [f"{file_id}_c{i}" for i in range(len(chunks))]
        metas = [{"file_id": file_id, "chunk_index": i} for i in range(len(chunks))]
        col.upsert(documents=chunks, ids=ids, metadatas=metas)

    def query(self, matter_id: str, query_text: str, top_k: int = 5) -> list[str]:
        try:
            col = self._get_collection(matter_id)
            if col.count() == 0:
                return []
            q_emb = self._embed_fn.encode_queries([query_text])
            res = col.query(query_embeddings=q_emb, n_results=min(top_k, col.count()))
            return res["documents"][0] if res["documents"] else []
        except Exception:
            return []

    def delete_document(self, matter_id: str, file_id: str) -> None:
        try:
            col = self._get_collection(matter_id)
            existing = col.get(where={"file_id": file_id})
            if existing["ids"]:
                col.delete(ids=existing["ids"])
        except Exception:
            pass

    # ── Knowledge base ─────────────────────────────────────────────────

    def _get_kb_collection(self):
        return self._client.get_or_create_collection(
            name=KB_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embed_fn,
        )

    def index_kb_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        col = self._get_kb_collection()
        chunks = self._sentence_chunk(text, max_words=400, overlap_words=80)
        if not chunks:
            return
        base_meta = {"doc_id": doc_id, "article": "200", "doc_type": "представление"}
        if metadata:
            base_meta.update(metadata)
        ids = [f"kb_{doc_id}_c{i}" for i in range(len(chunks))]
        metas = [{**base_meta, "chunk_index": i} for i in range(len(chunks))]
        col.upsert(documents=chunks, ids=ids, metadatas=metas)

    def query_kb(self, query_text: str, top_k: int = 5, article: str = "200") -> list[str]:
        try:
            col = self._get_kb_collection()
            if col.count() == 0:
                return []
            q_emb = self._embed_fn.encode_queries([query_text])
            res = col.query(
                query_embeddings=q_emb,
                n_results=min(top_k, col.count()),
                where={"article": article},
            )
            return res["documents"][0] if res["documents"] else []
        except Exception:
            return []

    def delete_kb_document(self, doc_id: str) -> None:
        try:
            col = self._get_kb_collection()
            existing = col.get(where={"doc_id": doc_id})
            if existing["ids"]:
                col.delete(ids=existing["ids"])
        except Exception:
            pass

    def get_kb_stats(self) -> dict:
        try:
            # Use lightweight collection access (no embedding fn needed for count)
            col = self._client.get_or_create_collection(name=KB_COLLECTION)
            return {"total_chunks": col.count()}
        except Exception:
            return {"total_chunks": 0}

    # ── Combined retrieval ─────────────────────────────────────────────

    def query_combined(self, matter_id: str, query_text: str,
                       top_k_matter: int = 3, top_k_kb: int = 5) -> dict:
        return {
            "matter": self.query(matter_id, query_text, top_k=top_k_matter),
            "knowledge_base": self.query_kb(query_text, top_k=top_k_kb),
        }

    # ═══════════════════════════════════════════════════════════════════
    # LEGISLATION — hierarchical indexing + hybrid retrieval
    # ═══════════════════════════════════════════════════════════════════

    def _get_legislation_collection(self):
        return self._client.get_or_create_collection(
            name=LEGISLATION_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embed_fn,
        )

    def index_legislation(self, doc_id: str, text: str, law_title: str, category: str) -> int:
        """Index legislation with hierarchical article→point chunking.

        Strategy:
          - Parse into articles using LegislationParser
          - Each article point becomes a chunk (never cut mid-sentence)
          - Metadata includes article number, point number, full article title
          - Each chunk is prefixed with context: "Закон: X, Статья N. Заголовок"
          - Full article text stored in metadata for parent-document retrieval
        """
        col = self._get_legislation_collection()
        articles = LegislationParser.parse(text, law_title)

        if not articles:
            chunks = self._sentence_chunk(text, max_words=600, overlap_words=120)
            if not chunks:
                return 0
            ids = [f"leg_{doc_id}_f{i}" for i in range(len(chunks))]
            docs = [f"[{law_title}]\n{c}" for c in chunks]
            metas = [{
                "doc_id": doc_id, "law_title": law_title, "article_number": "",
                "point_number": "", "article_title": "", "category": category,
                "full_article": "", "chunk_type": "fallback",
            } for _ in chunks]
            col.upsert(documents=docs, ids=ids, metadatas=metas)
            self._rebuild_bm25()
            return len(chunks)

        ids, docs, metas = [], [], []
        chunk_idx = 0

        for art in articles:
            art_num = art["number"]
            art_title = art["title"]
            full_art = art["full_text"]
            context_prefix = f"[{law_title}, Статья {art_num}. {art_title}]"

            if not art["points"] or (len(art["points"]) == 1 and not art["points"][0]["number"]):
                chunk_text = f"{context_prefix}\n{full_art}"
                ids.append(f"leg_{doc_id}_a{art_num}_{chunk_idx}")
                docs.append(chunk_text)
                metas.append({
                    "doc_id": doc_id, "law_title": law_title,
                    "article_number": art_num, "point_number": "",
                    "article_title": art_title[:300], "category": category,
                    "full_article": full_art[:8000], "chunk_type": "full_article",
                })
                chunk_idx += 1
                continue

            for pt in art["points"]:
                pt_num = pt["number"]
                pt_text = pt["text"]

                if len(pt_text.split()) > 800:
                    sub_chunks = self._sentence_chunk(pt_text, max_words=500, overlap_words=100)
                    for sc in sub_chunks:
                        chunk_text = f"{context_prefix}\n{sc}"
                        ids.append(f"leg_{doc_id}_a{art_num}_p{pt_num}_{chunk_idx}")
                        docs.append(chunk_text)
                        metas.append({
                            "doc_id": doc_id, "law_title": law_title,
                            "article_number": art_num, "point_number": pt_num,
                            "article_title": art_title[:300], "category": category,
                            "full_article": full_art[:8000], "chunk_type": "point_sub",
                        })
                        chunk_idx += 1
                else:
                    chunk_text = f"{context_prefix}\n{pt_text}"
                    ids.append(f"leg_{doc_id}_a{art_num}_p{pt_num}_{chunk_idx}")
                    docs.append(chunk_text)
                    metas.append({
                        "doc_id": doc_id, "law_title": law_title,
                        "article_number": art_num, "point_number": pt_num,
                        "article_title": art_title[:300], "category": category,
                        "full_article": full_art[:8000], "chunk_type": "point",
                    })
                    chunk_idx += 1

        if not ids:
            return 0

        BATCH = 500
        for i in range(0, len(ids), BATCH):
            col.upsert(
                documents=docs[i:i + BATCH],
                ids=ids[i:i + BATCH],
                metadatas=metas[i:i + BATCH],
            )

        self._rebuild_bm25()
        logger.info("Indexed %s: %d chunks from %d articles", law_title, len(ids), len(articles))
        return len(ids)

    def search_relevant_laws(self, query: str, top_k: int = 10,
                             categories: list[str] | None = None) -> list[dict]:
        """Hybrid retrieval: semantic + BM25 + RRF + cross-encoder rerank.

        Returns full article text via parent-document retrieval.
        """
        try:
            col = self._get_legislation_collection()
            if col.count() == 0:
                return []

            where = self._build_where(categories, query)
            expanded = self._expand_query(query)
            queries = [query] + ([expanded] if expanded != query else [])

            # ── Stage 1: Semantic retrieval ────────────────────────────
            fetch_k = min(30, col.count())
            seen: set[str] = set()
            candidates: list[dict] = []

            for q in queries:
                q_emb = self._embed_fn.encode_queries([q])
                kw = {"query_embeddings": q_emb, "n_results": fetch_k}
                if where:
                    kw["where"] = where
                res = col.query(**kw, include=["documents", "metadatas", "distances"])

                if not res["documents"] or not res["documents"][0]:
                    continue
                for cid, doc, meta, dist in zip(
                    res["ids"][0], res["documents"][0],
                    res["metadatas"][0], res["distances"][0]
                ):
                    if cid in seen:
                        continue
                    seen.add(cid)
                    score = max(0, round(1.0 - dist, 4))
                    candidates.append({
                        "id": cid, "text": doc, "score": score,
                        "bm25_rank": float("inf"), "bi_rank": 0,
                        **{k: meta.get(k, "") for k in
                           ("law_title", "article_number", "article_title",
                            "category", "full_article")},
                    })

            # ── Stage 2: BM25 lexical retrieval ────────────────────────
            bm25 = self._bm25.get("model")
            bm25_corpus = self._bm25.get("corpus", [])
            bm25_meta = self._bm25.get("meta", [])

            if bm25 and bm25_corpus:
                tokens = query.lower().split()
                scores = bm25.get_scores(tokens)
                ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:fetch_k]

                for rank, (idx, sc) in enumerate(ranked, 1):
                    if sc <= 0 or idx >= len(bm25_corpus):
                        continue
                    meta = bm25_meta[idx] if idx < len(bm25_meta) else {}
                    if not self._meta_passes_filter(meta, where):
                        continue

                    doc = bm25_corpus[idx]
                    existing = next((c for c in candidates if c["text"] == doc), None)
                    if existing:
                        existing["bm25_rank"] = rank
                    else:
                        candidates.append({
                            "id": f"bm25_{idx}", "text": doc, "score": 0.0,
                            "bm25_rank": rank, "bi_rank": float("inf"),
                            **{k: meta.get(k, "") for k in
                               ("law_title", "article_number", "article_title",
                                "category", "full_article")},
                        })

            # ── Stage 3: Reciprocal Rank Fusion ────────────────────────
            candidates.sort(key=lambda x: x["score"], reverse=True)
            for r, c in enumerate(candidates, 1):
                c["bi_rank"] = r if c["score"] > 0 else float("inf")

            K = 60
            for c in candidates:
                s1 = 1.0 / (K + c["bi_rank"]) if c["bi_rank"] != float("inf") else 0
                s2 = 1.0 / (K + c["bm25_rank"]) if c["bm25_rank"] != float("inf") else 0
                c["rrf"] = s1 + s2

            candidates.sort(key=lambda x: x["rrf"], reverse=True)
            candidates = candidates[:fetch_k]

            # ── Stage 4: Cross-encoder reranking ───────────────────────
            self._ensure_reranker()
            if self._reranker and candidates:
                pairs = [[query, c["text"][:512]] for c in candidates]
                try:
                    re_scores = self._reranker.predict(pairs)
                    for c, s in zip(candidates, re_scores):
                        c["final_score"] = round(float(s), 4)
                except Exception:
                    for c in candidates:
                        c["final_score"] = c["rrf"]
            else:
                for c in candidates:
                    c["final_score"] = c["rrf"]

            candidates.sort(key=lambda x: x["final_score"], reverse=True)

            # ── Parent-document dedup: prefer full_article over point ──
            seen_arts: set[str] = set()
            results: list[dict] = []
            for c in candidates:
                art_key = f"{c['law_title']}::{c['article_number']}"
                if art_key in seen_arts:
                    continue
                seen_arts.add(art_key)

                text = c.get("full_article") or c["text"]
                text = text[:4000]

                results.append({
                    "text": text,
                    "law_title": c["law_title"],
                    "article_number": c["article_number"],
                    "category": c["category"],
                    "score": c["final_score"],
                })
                if len(results) >= top_k:
                    break

            return results
        except Exception as e:
            logger.error("search_relevant_laws failed: %s", e)
            return []

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_where(categories: list[str] | None, query: str) -> dict | None:
        parts = []
        if categories and len(categories) == 1:
            parts.append({"category": categories[0]})
        elif categories and len(categories) > 1:
            parts.append({"category": {"$in": categories}})

        if len(parts) == 0:
            return None
        if len(parts) == 1:
            return parts[0]
        return {"$and": parts}

    @staticmethod
    def _meta_passes_filter(meta: dict, where: dict | None) -> bool:
        if not where:
            return True
        if "$and" in where:
            return all(RAGService._meta_passes_filter(meta, sub) for sub in where["$and"])
        for field, cond in where.items():
            if field.startswith("$"):
                continue
            val = meta.get(field, "")
            if isinstance(cond, dict):
                op = next(iter(cond))
                if op == "$in" and val not in cond[op]:
                    return False
            elif val != cond:
                return False
        return True

    @staticmethod
    def _expand_query(query: str) -> str:
        lower = query.lower()
        adds = [exp for key, exp in LEGAL_SYNONYMS.items() if key in lower]
        return query + " " + " ".join(adds) if adds else query

    def delete_legislation(self, doc_id: str) -> None:
        try:
            col = self._get_legislation_collection()
            existing = col.get(where={"doc_id": doc_id})
            if existing["ids"]:
                col.delete(ids=existing["ids"])
            self._rebuild_bm25()
        except Exception:
            pass

    def get_legislation_stats(self) -> dict:
        try:
            col = self._client.get_or_create_collection(name=LEGISLATION_COLLECTION)
            return {"total_chunks": col.count()}
        except Exception:
            return {"total_chunks": 0}

    # ═══════════════════════════════════════════════════════════════════
    # Sentence-aware chunking — NEVER cuts mid-sentence
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def _sentence_chunk(text: str, max_words: int = 400, overlap_words: int = 80) -> list[str]:
        """Split text at sentence boundaries, respecting max chunk size."""
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            return []

        sentences = re.split(r"(?<=[.!?;])\s+(?=[А-ЯA-Z0-9«\"])", text)
        if not sentences:
            return [text]

        chunks = []
        current: list[str] = []
        current_len = 0

        for sent in sentences:
            sent_len = len(sent.split())
            if current_len + sent_len > max_words and current:
                chunks.append(" ".join(current))
                overlap_sents = []
                overlap_len = 0
                for s in reversed(current):
                    sl = len(s.split())
                    if overlap_len + sl > overlap_words:
                        break
                    overlap_sents.insert(0, s)
                    overlap_len += sl
                current = overlap_sents
                current_len = overlap_len

            current.append(sent)
            current_len += sent_len

        if current:
            chunks.append(" ".join(current))

        return [c for c in chunks if len(c.split()) > 5]

    # Legacy compatibility aliases
    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        return RAGService._sentence_chunk(text, max_words=400, overlap_words=80)

    @staticmethod
    def _chunk_text_large(text: str) -> list[str]:
        return RAGService._sentence_chunk(text, max_words=600, overlap_words=120)

    @staticmethod
    def _chunk_legislation(text: str, law_title: str) -> list[dict]:
        """Legacy: use LegislationParser instead."""
        articles = LegislationParser.parse(text, law_title)
        result = []
        for art in articles:
            result.append({
                "text": art["full_text"],
                "article_number": art["number"],
                "law_title": law_title,
            })
        return result

    # ═══════════════════════════════════════════════════════════════════
    # Article parser for UI display
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def parse_articles(text: str) -> list[dict]:
        """Parse legislation for UI tree view."""
        articles = LegislationParser.parse(text, "")
        return [
            {"number": a["number"], "title": a["title"][:300], "text": a["full_text"][:5000]}
            for a in articles
        ]

    @staticmethod
    def _clean_article_title(raw: str) -> str:
        return LegislationParser._clean_title(raw, "")
