"""RAG service for enriched legal norms (enriched_laws_200upk.jsonl).

Uses FAISS for fast vector similarity search with:
  - E5 multilingual embeddings (shared with main RAG)
  - norm_type score boosting (Обязывающая > Компетенционная > Запрещающая)
  - Optional organ-based filtering
  - Persistent index cached to disk

This service is separate from the ChromaDB-based RAGService to keep
the JSONL norms pipeline lightweight and self-contained.
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Norm-type score multipliers — prioritize binding/competence norms
# These are used ONLY for internal ranking; the displayed score is raw cosine similarity
NORM_TYPE_BOOST = {
    "Обязывающая": 1.15,
    "Компетенционная": 1.10,
    "Запрещающая": 1.05,
    "Управомочивающая": 1.00,
}

# Minimum cosine similarity - set very low since AI reranking handles relevance filtering
MIN_SCORE_THRESHOLD = 0.10

# Default JSONL file paths (checked in order)
_JSONL_CANDIDATES = [
    "unified_laws_200upk.jsonl",
    "enriched_laws_200upk.jsonl",
    "../unified_laws_200upk.jsonl",
    "../enriched_laws_200upk.jsonl",
    "/app/unified_laws_200upk.jsonl",
    "/app/enriched_laws_200upk.jsonl",
]


import threading


class RAGLawsService:
    """Singleton service for searching enriched legal norms via FAISS."""

    _instance: Optional["RAGLawsService"] = None
    _initialized = False
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, storage_dir: str = "./storage", jsonl_path: str | None = None):
        if RAGLawsService._initialized:
            return

        # Prevent concurrent initialization (background task + HTTP request)
        with RAGLawsService._init_lock:
            # Double-check after acquiring lock
            if RAGLawsService._initialized:
                return

            # Mark as initialized immediately to prevent re-entry
            RAGLawsService._initialized = True

            self._storage_dir = Path(storage_dir)
            self._index_dir = self._storage_dir / "faiss_laws"
            self._index_dir.mkdir(parents=True, exist_ok=True)

            self._records: list[dict] = []
            self._embeddings: np.ndarray | None = None
            self._index = None  # FAISS index
            self._embed_model = None
            self._jsonl_path = jsonl_path

            # Try loading from cache first
            if self._load_cache():
                logger.info("RAGLawsService loaded from cache (%d records)", len(self._records))
            else:
                # Find and index the JSONL file
                jpath = self._find_jsonl(jsonl_path)
                if jpath:
                    self._build_index(jpath)
                    logger.info("RAGLawsService indexed %d records from %s", len(self._records), jpath)
                else:
                    logger.warning(
                        "RAGLawsService: enriched_laws_200upk.jsonl not found. "
                        "RAG law search will return empty results."
                    )

    # ── Index building ──────────────────────────────────────────────────

    def _find_jsonl(self, explicit_path: str | None) -> str | None:
        """Find the JSONL file on disk."""
        if explicit_path and os.path.isfile(explicit_path):
            return explicit_path
        for candidate in _JSONL_CANDIDATES:
            if os.path.isfile(candidate):
                return candidate
        return None

    def _get_embed_model(self):
        """Lazy-load the E5 embedding model (shared logic with main RAG)."""
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer
            from config import get_settings
            settings = get_settings()
            model_name = settings.embedding_model  # intfloat/multilingual-e5-base
            logger.info("RAGLawsService: loading embedding model %s...", model_name)
            self._embed_model = SentenceTransformer(model_name)
            self._is_e5 = "e5" in model_name.lower()
            logger.info("RAGLawsService: embedding model loaded")
        return self._embed_model

    def _text_for_embedding(self, rec: dict) -> str:
        """Build the text to embed for each record.

        Concatenates the most semantically meaningful fields:
        violation_criteria + applicable_measures + original_text + organ
        """
        parts = []

        vc = rec.get("violation_criteria", "")
        if vc:
            parts.append(f"Нарушение: {vc}")

        am = rec.get("applicable_measures", "")
        if am:
            parts.append(f"Меры: {am}")

        ot = rec.get("original_text", "")
        if ot:
            parts.append(f"Норма: {ot[:500]}")

        sc = rec.get("subject_competence", {})
        if isinstance(sc, dict):
            organ = sc.get("organ", "")
            if organ:
                parts.append(f"Орган: {organ}")

        ln = rec.get("law_name", "")
        an = rec.get("article_number", "")
        if ln or an:
            parts.append(f"Закон: {ln}, {an}")

        return " ".join(parts)

    def _build_index(self, jsonl_path: str):
        """Load JSONL, compute embeddings, build FAISS index."""
        import faiss

        # 1. Load records
        logger.info("RAGLawsService: loading JSONL from %s ...", jsonl_path)
        records = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    records.append(rec)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed JSON at line %d", line_num)
        logger.info("RAGLawsService: loaded %d records", len(records))

        if not records:
            return

        # 2. Build embedding texts
        texts = [self._text_for_embedding(r) for r in records]

        # 3. Compute embeddings
        model = self._get_embed_model()
        is_e5 = getattr(self, "_is_e5", False)
        if is_e5:
            texts_prefixed = [f"passage: {t}" for t in texts]
        else:
            texts_prefixed = texts

        logger.info("RAGLawsService: computing embeddings for %d records...", len(records))
        embeddings = model.encode(
            texts_prefixed,
            show_progress_bar=True,
            normalize_embeddings=True,
            batch_size=256,
        )
        embeddings = np.array(embeddings, dtype=np.float32)

        # 4. Build FAISS index (Inner Product on normalized vectors = cosine)
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        self._records = records
        self._embeddings = embeddings
        self._index = index

        # 5. Save cache
        self._save_cache()

    def _save_cache(self):
        """Persist index and records to disk."""
        import faiss

        try:
            faiss.write_index(self._index, str(self._index_dir / "laws.index"))
            with open(self._index_dir / "laws_records.pkl", "wb") as f:
                pickle.dump(self._records, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("RAGLawsService: cache saved to %s", self._index_dir)
        except Exception as e:
            logger.error("RAGLawsService: failed to save cache: %s", e)

    def _load_cache(self) -> bool:
        """Try loading index and records from disk cache."""
        index_path = self._index_dir / "laws.index"
        records_path = self._index_dir / "laws_records.pkl"

        if not index_path.exists() or not records_path.exists():
            return False

        try:
            import faiss
            self._index = faiss.read_index(str(index_path))
            with open(records_path, "rb") as f:
                self._records = pickle.load(f)

            if self._index.ntotal != len(self._records):
                logger.warning(
                    "RAGLawsService: cache mismatch (index=%d, records=%d), rebuilding",
                    self._index.ntotal, len(self._records)
                )
                return False

            return True
        except Exception as e:
            logger.warning("RAGLawsService: cache load failed: %s", e)
            return False

    # ── Query Expansion ──────────────────────────────────────────────────

    @staticmethod
    def _expand_query(query: str) -> str:
        """Expand factual case description with obligation/duty keywords.

        The problem: case descriptions contain FACTS ('кража из магазина'),
        but legal norms contain OBLIGATIONS ('обязан обеспечить охрану').
        This method bridges the semantic gap by adding relevant legal terms.

        v2: More targeted expansions — fewer generic terms, extract UK article.
        """
        import re
        expansions = []
        q_lower = query.lower()

        # Extract criminal code article for context-aware search
        uk_articles = re.findall(r'ст(?:атья|\.)?\s*(\d+)', q_lower)
        if uk_articles:
            expansions.append(f"статья {' '.join(uk_articles)} Уголовный кодекс")

        # Map factual keywords → SHORT, targeted duty terms (max 6-8 words)
        EXPANSION_MAP = {
            # Theft/Property
            r'краж|хищен|похит|украл': 'охрана имущества сохранность собственности',
            r'видеонаблюден|камер': 'видеонаблюдение техническая охрана',
            r'магазин|торгов|склад': 'торговая деятельность хранение товаров',
            # Violence/Injury
            r'убийств|смерт|погиб': 'безопасность жизни здоровья граждан',
            r'побо|телесн|причин.{0,10}вред': 'общественный порядок безопасность',
            # Traffic
            r'дтп|аварий|дорож': 'дорожное движение содержание дорог',
            r'пешеход|наезд|сбил': 'пешеходный переход дорожная безопасность',
            # Drugs
            r'наркот|психотроп': 'оборот наркотических средств контроль',
            # Fraud
            r'мошенничеств|обман': 'финансовый контроль проверка документов',
            # Fire
            r'пожар|возгоран|огн': 'пожарная безопасность противопожарные',
            # Minors
            r'несовершеннолетн|подрост|ребен|дет': 'защита несовершеннолетних воспитание',
            # Corruption
            r'коррупц|взятк|злоупотреблен': 'противодействие коррупции',
            # Labor
            r'труд|работник|работодатель|охрана\s*труда': 'охрана труда безопасность',
            r'травм|увечь|производствен': 'безопасные условия труда',
            r'стройк|строительств|высот': 'строительная безопасность',
            # Ecology
            r'загрязнен|экологи|окружающ': 'охрана окружающей среды',
            # Housing
            r'жилищ|дом|здани|подъезд': 'содержание жилого фонда',
            # Education
            r'школ|учебн|образован': 'образовательное учреждение',
            # Medical
            r'больниц|лечебн|медицин|врач': 'медицинская помощь',
            r'суицид|самоубийств|психиче': 'профилактика суицидов',
        }

        matched_count = 0
        for pattern, expansion in EXPANSION_MAP.items():
            if re.search(pattern, q_lower):
                expansions.append(expansion)
                matched_count += 1
                if matched_count >= 3:  # Limit to top 3 most relevant expansions
                    break

        if expansions:
            duty_context = ' '.join(expansions)
            # Put facts FIRST, then duty context — preserves semantic focus
            expanded = f"{query[:2000]} нарушение обязанностей {duty_context}"
            logger.info("RAGLawsService: expanded query with %d patterns", len(expansions))
            return expanded[:3000]

        # No expansion — return original query with minimal context
        return f"{query[:2500]} причины условия нарушение"

    # ── Search ──────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        organ_filter: str | None = None,
    ) -> list[dict]:
        """Search for relevant legal norms given a case description.

        Hybrid search strategy:
          1. FAISS embedding retrieval for broad recall (top 100 candidates)
          2. BM25 keyword scoring as PRIMARY ranking signal
          3. Embedding score as secondary signal (tiebreaker)
          4. Norm-type boosting for binding/competence norms

        BM25 keyword scoring is critical because embedding similarity (~0.83)
        cannot distinguish between legal texts. BM25 correctly identifies
        documents containing actual query terms (кража, хищение, имущество).

        Args:
            query: Case description / фабула дела
            top_k: Number of results to return
            organ_filter: Optional organization type to filter by

        Returns:
            List of structured norm objects with score reflecting relevance
        """
        if not self._index or not self._records:
            logger.warning("RAGLawsService.search: no index or records")
            return []

        import re as _re

        # ── Step 1: Extract key terms from query for BM25 ──────────────
        q_lower = query.lower()

        # Extract article numbers (e.g. "ст.188", "статья 188")
        article_nums = _re.findall(r'ст(?:атья|\.)\s*(\d+)', q_lower)

        # Extract meaningful keywords (4+ chars, skip stop words)
        STOP_WORDS = {
            'который', 'которая', 'которое', 'которые', 'также', 'было',
            'были', 'была', 'этого', 'этой', 'этих', 'после', 'между',
            'через', 'более', 'менее', 'около', 'время', 'период',
            'данный', 'данная', 'данного', 'данной', 'данных', 'свой',
            'своей', 'своих', 'своего', 'часов', 'числа', 'году', 'года',
            'дело', 'дела', 'лицо', 'лица', 'что', 'для', 'при',
            'него', 'нему', 'него', 'материалы', 'фабула', 'указания',
        }
        query_words = [
            w for w in _re.findall(r'[а-яёa-z]{4,}', q_lower)
            if w not in STOP_WORDS
        ]
        # Deduplicate while preserving order
        seen_words = set()
        unique_words = []
        for w in query_words:
            if w not in seen_words:
                seen_words.add(w)
                unique_words.append(w)
        query_words = unique_words[:50]  # Limit for performance

        logger.info("RAGLawsService.search: query_len=%d, keywords=%d, articles=%s",
                     len(query), len(query_words), article_nums)

        # ── Step 2: FAISS embedding retrieval (broad recall) ───────────
        model = self._get_embed_model()
        is_e5 = getattr(self, "_is_e5", False)

        # Single query embedding (no expansion overhead)
        q_text = f"query: {query[:2000]}" if is_e5 else query[:2000]
        q_vec = model.encode(
            [q_text], normalize_embeddings=True, show_progress_bar=False
        )
        q_vec = np.array(q_vec, dtype=np.float32)

        # Fetch broad candidate set
        fetch_k = min(max(top_k * 10, 100), self._index.ntotal)
        faiss_scores, faiss_indices = self._index.search(q_vec, fetch_k)

        # ── Step 3: BM25 keyword scoring + hybrid ranking ──────────────
        candidates = []
        for emb_score, idx in zip(faiss_scores[0], faiss_indices[0]):
            if idx < 0 or idx >= len(self._records):
                continue

            rec = self._records[int(idx)]
            raw_emb = float(emb_score)

            # Organ filter
            if organ_filter:
                organ = ""
                sc = rec.get("subject_competence", {})
                if isinstance(sc, dict):
                    organ = sc.get("organ", "")
                if not self._organ_matches(organ, organ_filter):
                    continue

            # Build searchable text from record
            rec_text = (
                rec.get("violation_criteria", "") + " " +
                rec.get("original_text", "") + " " +
                rec.get("applicable_measures", "") + " " +
                rec.get("law_name", "") + " " +
                rec.get("article_number", "") + " " +
                (rec.get("norm_purpose", "") or "")
            ).lower()

            # ── BM25-style keyword score ──
            # Count how many query keywords appear in this record
            keyword_hits = 0
            for kw in query_words:
                if kw in rec_text:
                    keyword_hits += 1
                    # Bonus for longer keywords (more specific)
                    if len(kw) >= 6:
                        keyword_hits += 0.5

            # Normalize keyword score (0-1 range)
            bm25_score = min(keyword_hits / max(len(query_words) * 0.3, 1), 1.0)

            # ── Article number match bonus ──
            article_bonus = 0.0
            for art_num in article_nums:
                if f"статья {art_num}" in rec_text or f"ст. {art_num}" in rec_text or f"ст.{art_num}" in rec_text:
                    article_bonus = 0.3  # Strong bonus for matching article
                    break

            # ── Norm type boost ──
            norm_type = rec.get("norm_type", "")
            type_boost = NORM_TYPE_BOOST.get(norm_type, 1.0)

            # ── Hybrid score: BM25 primary, embedding secondary ──
            # BM25 weight: 0.6, Embedding weight: 0.2, Article: 0.3
            hybrid_score = (bm25_score * 0.6 + raw_emb * 0.2 + article_bonus) * type_boost

            # Display score: blend of BM25 and embedding for meaningful %
            display_score = min(bm25_score * 0.5 + raw_emb * 0.3 + article_bonus * 0.5, 1.0)

            if hybrid_score < 0.05 and not article_bonus:
                continue

            candidates.append({
                "law_name": rec.get("law_name", ""),
                "article_number": rec.get("article_number", ""),
                "original_text": rec.get("original_text", ""),
                "violation_criteria": rec.get("violation_criteria", ""),
                "applicable_measures": rec.get("applicable_measures", ""),
                "norm_type": norm_type,
                "norm_purpose": rec.get("norm_purpose", ""),
                "organ": (rec.get("subject_competence", {}) or {}).get("organ", ""),
                "score": round(display_score, 4),
                "_hybrid": round(hybrid_score, 4),
                "_bm25": round(bm25_score, 4),
                "_emb": round(raw_emb, 4),
                "_kw_hits": keyword_hits,
            })

        # ── Step 4: Sort by hybrid score, deduplicate ──────────────────
        candidates.sort(key=lambda x: x["_hybrid"], reverse=True)

        seen = set()
        results = []
        law_counts: dict[str, int] = {}
        max_per_law = max(3, top_k // 2)

        for c in candidates:
            key = (c["law_name"], c["article_number"])
            if key in seen:
                continue
            seen.add(key)

            # Limit results from same law for diversity
            law_name = c["law_name"]
            law_counts[law_name] = law_counts.get(law_name, 0) + 1
            if law_counts[law_name] > max_per_law and len(results) >= top_k // 2:
                continue

            # Remove internal scores before returning
            result = {k: v for k, v in c.items() if not k.startswith("_")}
            results.append(result)

            if len(results) >= top_k:
                break

        # Log top results for debugging
        if results:
            top3 = [(r["law_name"][:30], r["article_number"], r["score"]) for r in results[:3]]
            logger.info(
                "RAGLawsService.search: %d candidates → %d results. Top3: %s",
                len(candidates), len(results), top3
            )
        else:
            logger.warning("RAGLawsService.search: 0 results for query_len=%d", len(query))

        return results

    @staticmethod
    def _organ_matches(organ_text: str, filter_text: str) -> bool:
        """Fuzzy match for organ filtering.

        Returns True if any word from filter_text appears in organ_text.
        Case-insensitive.
        """
        if not filter_text or not organ_text:
            return not filter_text  # no filter = pass

        organ_lower = organ_text.lower()
        filter_lower = filter_text.lower().strip()

        # Direct substring match
        if filter_lower in organ_lower:
            return True

        # Word-level match (any filter word found in organ)
        filter_words = [w for w in filter_lower.split() if len(w) > 2]
        if filter_words:
            return any(w in organ_lower for w in filter_words)

        return False

    # ── Utility ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return index statistics."""
        return {
            "total_records": len(self._records),
            "index_size": self._index.ntotal if self._index else 0,
            "indexed": self._index is not None and self._index.ntotal > 0,
        }

    def rebuild(self, jsonl_path: str | None = None):
        """Force rebuild the index from JSONL."""
        RAGLawsService._initialized = False
        self._records = []
        self._index = None
        self._embeddings = None

        jpath = self._find_jsonl(jsonl_path or self._jsonl_path)
        if jpath:
            self._build_index(jpath)
            RAGLawsService._initialized = True
            logger.info("RAGLawsService rebuilt: %d records", len(self._records))
        else:
            RAGLawsService._initialized = True
            logger.warning("RAGLawsService rebuild: JSONL file not found")

    @classmethod
    def reset(cls):
        """Reset singleton for testing."""
        cls._instance = None
        cls._initialized = False
