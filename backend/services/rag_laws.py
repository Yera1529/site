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

        Enhanced multi-strategy search:
          1. Expanded query for obligation-oriented matching
          2. Original query for direct factual matching
          3. Text-match bonus for exact keyword hits
          4. Norm-type boosting (internal ranking only)
          5. Minimum score threshold to filter irrelevant results
          6. Balanced retrieval ensuring violation/remedy diversity

        Score output: raw cosine similarity (0.0–1.0) for frontend display.
        Boosts are applied internally for ranking but stripped before output.

        Args:
            query: Case description / фабула дела
            top_k: Number of results to return
            organ_filter: Optional organization type to filter by

        Returns:
            List of structured norm objects with fields:
              law_name, article_number, original_text,
              violation_criteria, applicable_measures, score (0-1)
        """
        if not self._index or not self._records:
            return []

        # 1. Multi-query strategy: search with both expanded and original queries
        expanded_query = self._expand_query(query)

        model = self._get_embed_model()
        is_e5 = getattr(self, "_is_e5", False)

        # Encode expanded query
        q_text_expanded = f"query: {expanded_query}" if is_e5 else expanded_query
        q_vec_expanded = model.encode(
            [q_text_expanded], normalize_embeddings=True, show_progress_bar=False
        )
        q_vec_expanded = np.array(q_vec_expanded, dtype=np.float32)

        # Encode original query (for direct fact matching)
        q_text_original = f"query: {query}" if is_e5 else query
        q_vec_original = model.encode(
            [q_text_original], normalize_embeddings=True, show_progress_bar=False
        )
        q_vec_original = np.array(q_vec_original, dtype=np.float32)

        # 2. FAISS search with both queries
        fetch_k = min(max(top_k * 6, 40), self._index.ntotal)

        scores_exp, indices_exp = self._index.search(q_vec_expanded, fetch_k)
        scores_orig, indices_orig = self._index.search(q_vec_original, fetch_k)

        # 3. Merge results — track raw cosine score separately from ranking score
        # raw_scores: actual cosine similarity for display (0-1)
        # rank_scores: boosted scores used only for internal ranking
        candidate_raw: dict[int, float] = {}   # idx -> best raw cosine score
        candidate_rank: dict[int, float] = {}  # idx -> boosted ranking score

        for score, idx in zip(scores_exp[0], indices_exp[0]):
            if idx < 0 or idx >= len(self._records):
                continue
            idx_int = int(idx)
            raw = float(score)  # cosine similarity (inner product on normalized vecs)
            candidate_raw[idx_int] = raw
            candidate_rank[idx_int] = raw

        for score, idx in zip(scores_orig[0], indices_orig[0]):
            if idx < 0 or idx >= len(self._records):
                continue
            idx_int = int(idx)
            raw = float(score)
            # Keep best raw score
            candidate_raw[idx_int] = max(candidate_raw.get(idx_int, 0), raw)
            # Small ranking bonus for appearing in both searches
            if idx_int in candidate_rank:
                candidate_rank[idx_int] = max(candidate_rank[idx_int], raw) + 0.02
            else:
                candidate_rank[idx_int] = raw

        # 4. Build candidate list with boosting for ranking, raw score for display
        query_lower = query.lower()
        query_keywords = set(w for w in query_lower.split() if len(w) > 3)

        candidates = []
        for idx in candidate_raw:
            raw_score = candidate_raw[idx]

            # Skip results below minimum threshold
            if raw_score < MIN_SCORE_THRESHOLD:
                continue

            rec = self._records[idx]

            # Organ filter
            if organ_filter:
                organ = ""
                sc = rec.get("subject_competence", {})
                if isinstance(sc, dict):
                    organ = sc.get("organ", "")
                if not self._organ_matches(organ, organ_filter):
                    continue

            # Norm type boosting (for ranking only)
            norm_type = rec.get("norm_type", "")
            boost = NORM_TYPE_BOOST.get(norm_type, 1.0)

            # Text-match bonus: reward records whose text contains query keywords
            text_for_match = (
                rec.get("violation_criteria", "") + " " +
                rec.get("original_text", "") + " " +
                rec.get("applicable_measures", "")
            ).lower()
            keyword_hits = sum(1 for kw in query_keywords if kw in text_for_match)
            text_bonus = min(keyword_hits * 0.02, 0.10)  # Cap at 0.10

            # Ranking score: base + boost + bonus (for sorting only)
            rank_score = candidate_rank[idx] * boost + text_bonus

            candidates.append({
                "law_name": rec.get("law_name", ""),
                "article_number": rec.get("article_number", ""),
                "original_text": rec.get("original_text", ""),
                "violation_criteria": rec.get("violation_criteria", ""),
                "applicable_measures": rec.get("applicable_measures", ""),
                "norm_type": norm_type,
                "norm_purpose": rec.get("norm_purpose", ""),
                "organ": (rec.get("subject_competence", {}) or {}).get("organ", ""),
                "score": round(raw_score, 4),       # Display score: raw cosine (0-1)
                "_rank_score": round(rank_score, 4),  # Internal ranking only
            })

        # 5. Sort by RANKING score, deduplicate by law+article
        candidates.sort(key=lambda x: x["_rank_score"], reverse=True)
        seen = set()
        results = []
        violation_count = 0
        remedy_count = 0
        min_violation = max(1, top_k // 2)
        min_remedy = max(1, top_k // 3)

        # Track law diversity — avoid too many results from same law
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

            purpose = c.get("norm_purpose", "")
            if len(results) >= top_k:
                if purpose == "violation" and violation_count < min_violation:
                    pass
                elif purpose == "remedy" and remedy_count < min_remedy:
                    pass
                else:
                    continue

            # Remove internal ranking score before returning
            result = {k: v for k, v in c.items() if not k.startswith("_")}
            results.append(result)
            if purpose in ("violation", "both"):
                violation_count += 1
            if purpose in ("remedy", "both"):
                remedy_count += 1

            if len(results) >= top_k + 3:  # Hard cap
                break

        logger.info(
            "RAGLawsService.search: query_len=%d, candidates=%d (above threshold), returned=%d, score_range=%.3f-%.3f",
            len(query), len(candidates), len(results),
            results[-1]["score"] if results else 0,
            results[0]["score"] if results else 0,
        )
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
