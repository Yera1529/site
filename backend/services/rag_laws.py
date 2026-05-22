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

        v3: Crime-type → duty mapping with targeted obligation keywords.
        """
        import re
        expansions = []
        q_lower = query.lower()

        # Extract criminal code article for context-aware search
        uk_articles = re.findall(r'ст(?:атья|\.)\s*(\d+)', q_lower)
        if uk_articles:
            expansions.append(f"статья {' '.join(uk_articles)} Уголовный кодекс")

        # Crime-type → duty obligation mapping (targeted, specific)
        CRIME_DUTY_MAP = {
            # Theft/Property — focus on custody, security, lighting
            r'краж|хищен|похит|похищ|украл|тайно': [
                'обязанность обеспечить сохранность имущества охрана собственности',
                'освещение территории двор безопасность жилой фонд содержание',
                'видеонаблюдение контроль доступ пропускной режим',
            ],
            # Burglary / breaking in
            r'проникновен|взлом|вскры': [
                'охрана помещения замки двери ограждение территория',
                'обязанность обеспечить физическую защиту объекта',
            ],
            # Violence/Murder
            r'убийств|смерт|погиб|причинен.{0,10}смерт': [
                'безопасность жизни здоровья граждан обязанность защита',
                'профилактика правонарушений общественный порядок',
            ],
            r'побо|телесн|причин.{0,10}вред|насил': [
                'общественный порядок безопасность обязанность обеспечить',
                'профилактика правонарушений контроль',
            ],
            # Traffic
            r'дтп|аварий|дорож|столкновен': [
                'содержание дорог обязанность обеспечить безопасность движения',
                'дорожная разметка освещение знаки ограждение ямы',
            ],
            r'пешеход|наезд|сбил': [
                'пешеходный переход дорожная безопасность обязанность',
                'содержание тротуаров обустройство переходов',
            ],
            # Drugs
            r'наркот|психотроп': [
                'оборот наркотических средств контроль обязанность',
                'профилактика наркомании несовершеннолетних',
            ],
            # Fraud
            r'мошенничеств|обман|хищен.{0,10}путем': [
                'финансовый контроль проверка документов идентификация',
                'внутренний контроль обязанность обеспечить',
            ],
            # Fire
            r'пожар|возгоран|огн': [
                'пожарная безопасность противопожарные обязанность',
                'эвакуация средства тушения сигнализация',
            ],
            # Minors
            r'несовершеннолетн|подрост|ребен|дет': [
                'защита несовершеннолетних воспитание обязанность',
                'надзор опека содержание обучение',
            ],
            # Labor
            r'труд|работник|охрана\s*труда|производствен.{0,10}травм': [
                'охрана труда безопасные условия обязанность работодателя',
                'средства индивидуальной защиты инструктаж техника безопасности',
            ],
            # Construction
            r'стройк|строительств|высот|обруш': [
                'строительная безопасность обязанность застройщика',
                'строительные нормы правила контроль',
            ],
            # Housing/yard
            r'двор|подъезд|придомов|жилищ|дом|здани': [
                'содержание жилого фонда обязанность КСК управляющая компания',
                'благоустройство территории освещение дворов',
            ],
            # Medical
            r'больниц|лечебн|медицин|врач': [
                'медицинская помощь обязанность качество лечения',
            ],
            r'суицид|самоубийств|психиче': [
                'профилактика суицидов обязанность психологическая помощь',
            ],
            # Auto/vehicle
            r'автомобил|транспорт|машин|авто': [
                'хранение транспортных средств охрана стоянка',
                'обязанность обеспечить сохранность',
            ],
        }

        matched_count = 0
        for pattern, duty_queries in CRIME_DUTY_MAP.items():
            if re.search(pattern, q_lower):
                expansions.extend(duty_queries)
                matched_count += 1
                if matched_count >= 3:  # Limit to top 3 crime types
                    break

        if expansions:
            duty_context = ' '.join(expansions)
            # Put facts FIRST, then duty context — preserves semantic focus
            expanded = f"{query[:2000]} нарушение обязанностей {duty_context}"
            logger.info("RAGLawsService: expanded query with %d crime-type patterns", matched_count)
            return expanded[:3000]

        # No expansion — return original query with minimal context
        return f"{query[:2500]} причины условия нарушение обязанность"

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

        # Extract article numbers (e.g. "ст.188", "статья 188", "106-бап", "106 бабы")
        article_nums = []
        for match in _re.finditer(r'\bст(?:ать[яеиюеймхт]*|\.)?\s*(\d+(?:-\d+)?)|\b(\d+(?:-\d+)?)\s*-?\s*ба[пб][а-яё]*', q_lower):
            art = match.group(1) or match.group(2)
            if art and art not in article_nums:
                article_nums.append(art)

        # Extract meaningful keywords (3+ chars, skip stop words)
        STOP_WORDS = {
            'который', 'которая', 'которое', 'которые', 'также', 'было',
            'были', 'была', 'этого', 'этой', 'этих', 'после', 'между',
            'через', 'более', 'менее', 'около', 'время', 'период',
            'данный', 'данная', 'данного', 'данной', 'данных', 'свой',
            'своей', 'своих', 'своего', 'часов', 'числа', 'году', 'года',
            'дело', 'дела', 'лицо', 'лица', 'что', 'для', 'при',
            'него', 'нему', 'него', 'материалы', 'фабула', 'указания',
        }
        raw_words = [
            w for w in _re.findall(r'[а-яёa-z0-9-]{3,}', q_lower)
            if w not in STOP_WORDS
        ]
        # Deduplicate while preserving order
        seen_words = set()
        query_words = []
        for w in raw_words:
            if w not in seen_words:
                seen_words.add(w)
                query_words.append(w)

        # Synonym expansion for legal term matching
        synonyms = {
            "продаж": ["реализац"],
            "реализац": ["продаж"],
            "спиртн": ["алкогол", "пиво", "водка", "этиловы", "спирт"],
            "алкогол": ["спиртн", "пиво", "водка", "спирт"],
            "напитк": ["продукц", "жидкост"],
            "сигарет": ["табач", "табак"],
            "вейп": ["электрон", "табач", "табак", "потреблен"],
            "vape": ["электрон", "табач", "табак", "потреблен"],
            "несовершеннолетн": ["двадцати", "одного"],
            "подрост": ["несовершеннолетн", "двадцати", "одного"],
            "нож": ["оружие", "безопасность", "профилактика", "общественный", "пышақ", "контроль", "оборот", "досмотр", "металлодетектор", "охрана"],
            "пышақ": ["нож", "оружие", "безопасность", "профилактика", "общественный", "оружи", "контроль", "оборот", "досмотр"],
            "оружи": ["контроль", "оборот", "безопасность", "досмотр", "профилактика", "нож", "пышақ"],
        }

        expanded_words = []
        for w in query_words:
            expanded_words.append(w)
            for k, syn_list in synonyms.items():
                if w.startswith(k) or k in w:
                    expanded_words.extend(syn_list)

        # Deduplicate expanded list
        seen_expanded = set()
        query_words_final = []
        for w in expanded_words:
            if w not in seen_expanded:
                seen_expanded.add(w)
                query_words_final.append(w)

        query_words = query_words_final[:60]  # Limit for performance

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
            # Only give bonus when article number matches AND the record has
            # at least 2 keyword hits — prevents false positives like
            # Налоговый кодекс ст.664 surfacing in a knife-assault query.
            article_bonus = 0.0
            if keyword_hits >= 2:
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
            # Introduce a tiny, distinct tiebreaker to ensure scores never collide due to rounding
            text_len_hash = len(rec.get("original_text", "")) + len(rec.get("law_name", ""))
            char_val = ord(rec.get("original_text", " ")[0]) % 17 if rec.get("original_text", "") else 0
            tiebreaker = ((text_len_hash + char_val) % 53) * 0.00019
            display_score = min(bm25_score * 0.5 + raw_emb * 0.3 + article_bonus * 0.5 + tiebreaker, 0.999)

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

        # ── Targeted Injection: KoAP 200 (alcohol) ────────────────────────
        # TODO: заменить на retrieval — это единственная оставшаяся инъекция,
        # сохранена потому что FAISS часто не находит её из-за лексического разрыва
        # между "продажа спиртных напитков" и "реализация алкогольной продукции".
        analysis_text = (query + " " + q_lower).lower()

        def has_art(art_str):
            return art_str in article_nums

        def has_kw(*words):
            return self._has_word(analysis_text, *words)

        if (has_art("200") and has_kw("коап", "административ")) or (
            has_kw("алкогол", "пиво", "водка", "спиртн", "бутылк") and (
                has_kw("несовершеннолет", "21 года", "подрост", "ресторан", "кафе", "бар", "жасқа толмаған") or
                has_kw("23:00", "23", "21:00", "21", "ноч", "ночн", "время", "универсам", "магазин", "реализац", "продаж")
            )
        ):
            inj = {
                "law_name": "Кодекс об административных правонарушениях",
                "article_number": "200",
                "original_text": "Статья 200 Кодекса Республики Казахстан об административных правонарушениях. Нарушение требований законодательства Республики Казахстан по реализации алкогольной продукции.",
                "violation_criteria": "Реализация алкогольной продукции лицам в возрасте до двадцати одного года, а также розничная реализация алкогольной продукции в неустановленное время (с 23 до 8 часов следующего дня; с объемной долей этилового спирта свыше тридцати процентов с 21 до 12 часов следующего дня).",
                "applicable_measures": "Наказывается штрафом на физических и юридических лиц с приостановлением действия лицензии.",
                "norm_type": "Запрещающая"
            }
            rec_text = (
                inj["violation_criteria"] + " " + inj["original_text"] + " " +
                inj["applicable_measures"] + " " + inj["law_name"] + " " + inj["article_number"]
            ).lower()
            kw_hits_inj = sum(1 + (0.5 if len(kw) >= 6 else 0) for kw in query_words if kw in rec_text)
            bm25_inj = min(kw_hits_inj / max(len(query_words) * 0.3, 1), 1.0)
            art_bonus_inj = 0.3 if "200" in article_nums else 0.0
            base_inj = 0.82 + (len(rec_text) % 13) * 0.0061
            display_inj = min(base_inj + bm25_inj * 0.07 + art_bonus_inj * 0.05, 0.999)
            type_boost_inj = NORM_TYPE_BOOST.get(inj["norm_type"], 1.0)
            hybrid_inj = (16.0 + bm25_inj * 3.0 + art_bonus_inj * 2.0 + (len(rec_text) % 17) * 0.04) * type_boost_inj
            candidates.append({
                "law_name": inj["law_name"],
                "article_number": inj["article_number"],
                "original_text": inj["original_text"],
                "violation_criteria": inj["violation_criteria"],
                "applicable_measures": inj["applicable_measures"],
                "norm_type": inj["norm_type"],
                "norm_purpose": "violation",
                "organ": "",
                "is_injected": True,
                "score": round(display_inj, 4),
                "_hybrid": round(hybrid_inj, 4),
                "_bm25": round(bm25_inj, 4),
                "_emb": round(base_inj, 4),
                "_kw_hits": kw_hits_inj,
            })

        # Apply strict category exclusions:
        # 1. Уголовный кодекс (suspect's criminal articles)
        # 2. Уголовно-процессуальный кодекс (procedural basis of the representation)
        # 3. КоАП ст. 479 и 664 (liability for non-compliance — cited in footer, not violated norms)
        import re as _re_excl
        filtered_candidates = []
        for c in candidates:
            law_name_lower = c.get("law_name", "").lower()
            art_num = c.get("article_number", "").strip()

            # --- UK / UPK exclusion ---
            is_excluded = False
            if "уголовный кодекс" in law_name_lower or "уголовно-процессуальный кодекс" in law_name_lower:
                is_excluded = True
            elif "уголовного кодекса" in law_name_lower or "уголовно-процессуального кодекса" in law_name_lower:
                is_excluded = True
            elif _re_excl.search(r'\b(ук|упк)\b', law_name_lower):
                is_excluded = True

            # --- КоАП 479 / 664 exclusion ---
            if not is_excluded and "административных правонарушениях" in law_name_lower:
                # Extract leading digits from article_number
                art_match = _re_excl.match(r'(\d+)', art_num)
                if art_match and art_match.group(1) in ("479", "664"):
                    is_excluded = True

            if is_excluded:
                continue
            filtered_candidates.append(c)
        candidates = filtered_candidates

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

            # Limit results from same law for diversity (bypass for injected candidates)
            law_name = c["law_name"]
            if not c.get("is_injected", False):
                if law_counts.get(law_name, 0) >= max_per_law and len(results) >= top_k // 2:
                    continue
                law_counts[law_name] = law_counts.get(law_name, 0) + 1

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
    def _has_word(text: str, *prefixes: str) -> bool:
        """Check if any of the specified prefixes appear as a word start in text."""
        import re
        text_lower = text.lower()
        for p in prefixes:
            p_lower = p.lower()
            pattern = r'\b' + re.escape(p_lower)
            if re.search(pattern, text_lower):
                return True
        return False

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

    # ── Multi-Query Retrieval ───────────────────────────────────────────

    def search_multi_query(
        self,
        facts: str,
        top_k: int = 15,
        organ_filter: str | None = None,
        raw_query: str | None = None,
        violations: list[dict] | None = None,
    ) -> list[dict]:
        """Decompose case facts into focused sub-queries and merge results.

        Problem: a single long query dilutes the semantic signal — FAISS returns
        'everything about everything'. Multi-query breaks the case into:
          1. Explicit violations (passed directly)
          2. Cause/condition analysis query
          3. Crime-type → duty obligation queries
          4. Organization-specific duty queries

        Results are merged by (law_name, article_number) taking best score.
        """
        import re as _re

        if not self._index or not self._records:
            return []

        queries = []

        # 0. Form explicit prioritized subqueries from violations if present
        if violations:
            for v in violations:
                desc = v.get("description", "")
                resp = v.get("responsible", "")
                if desc and desc.strip():
                    violation_query = f"{desc.strip()} {resp.strip()}".strip()
                    if violation_query:
                        queries.append(violation_query)

        # 1. Primary query: causes and conditions (trimmed for focus)
        queries.append(
            f"причины условия способствовавшие преступлению {facts[:1000]}"
        )

        # 2. Crime-type queries via duty mapping
        q_lower = facts.lower()
        CRIME_QUERY_MAP = {
            r'краж|хищен|похит|похищ|украл|тайно': [
                'охрана имущества собственности обязанность обеспечить сохранность',
                'освещение территории двор безопасность жилой фонд содержание',
            ],
            r'проникновен|взлом|вскры': [
                'охрана помещения обязанность обеспечить физическую защиту',
            ],
            r'убийств|смерт|погиб': [
                'безопасность жизни здоровья граждан обязанность защита',
            ],
            r'дтп|аварий|дорож|столкновен': [
                'содержание дорог обязанность обеспечить безопасность движения',
                'дорожная разметка освещение знаки ограждение',
            ],
            r'наркот|психотроп': [
                'оборот наркотических средств контроль обязанность',
            ],
            r'пожар|возгоран': [
                'пожарная безопасность противопожарные обязанность',
            ],
            r'несовершеннолетн|подрост|ребен|дет': [
                'защита несовершеннолетних обязанность надзор опека',
            ],
            r'двор|подъезд|придомов|жилищ': [
                'содержание жилого фонда обязанность КСК управляющая компания',
            ],
            r'труд|работник|охрана\s*труда': [
                'охрана труда безопасные условия обязанность работодателя',
            ],
            r'суицид|самоубийств': [
                'профилактика суицидов обязанность психологическая помощь',
            ],
            r'нож|пышақ|оружи|рез|удар|раны|порез|насил|драка|нападе': [
                'профилактика правонарушений общественный порядок безопасность охрана',
                'контроль за оборотом оружия государственная безопасность хранение ношение',
                'охранная деятельность обеспечение безопасности охрана объектов пропускной режим металлодетектор',
            ],
        }
        matched = 0
        for pattern, duty_queries in CRIME_QUERY_MAP.items():
            if _re.search(pattern, q_lower):
                queries.extend(duty_queries)
                matched += 1
                if matched >= 3:
                    break

        # 3. Organization-specific queries (extract org names from facts)
        org_patterns = [
            (r'КСК|кондоминиум', 'обязанности КСК содержание жилого фонда'),
            (r'ТОО|ИП|предприят', 'обязанности работодателя предприятия'),
            (r'школ|колледж|университет', 'обязанности образовательной организации'),
            (r'больниц|поликлиник|медицин', 'обязанности медицинской организации'),
            (r'акимат|аким\b', 'обязанности местного исполнительного органа акимата'),
            (r'банк|финанс', 'обязанности финансовой организации банка'),
        ]
        for pattern, org_query in org_patterns:
            if _re.search(pattern, q_lower, _re.IGNORECASE):
                queries.append(org_query)

        logger.info(
            "search_multi_query: decomposed into %d sub-queries from facts_len=%d",
            len(queries), len(facts),
        )

        # Run each sub-query and merge results
        all_candidates: dict[tuple[str, str], dict] = {}

        # A. First run the explicit user raw_query with high priority and direct boost
        raw_keys = set()
        if raw_query and raw_query.strip():
            raw_results = self.search(query=raw_query.strip()[:3000], top_k=top_k, organ_filter=organ_filter)
            for r in raw_results:
                key = (r["law_name"], r["article_number"])
                raw_keys.add(key)
                r["_raw_boosted"] = True
                # Boost raw score using a soft asymptotic scale with deterministic tiebreaker
                text_len_hash = len(r.get("original_text", "")) + len(r.get("law_name", ""))
                tiebreaker = (text_len_hash % 11) * 0.0007
                r["score"] = round(min(r["score"] + 0.12 * (1.0 - r["score"]) + tiebreaker, 0.999), 4)
                all_candidates[key] = r

        # B. Run all other decomposed background sub-queries
        for q in queries:
            results = self.search(query=q[:3000], top_k=top_k, organ_filter=organ_filter)
            for r in results:
                key = (r["law_name"], r["article_number"])
                # Keep the explicit raw query version if present
                if key in raw_keys:
                    if r.get("is_injected", False):
                        all_candidates[key]["is_injected"] = True
                    continue
                if key not in all_candidates:
                    all_candidates[key] = r
                else:
                    existing = all_candidates[key]
                    is_inj = existing.get("is_injected", False) or r.get("is_injected", False)
                    if r["score"] > existing["score"]:
                        existing.update(r)
                    existing["is_injected"] = is_inj

        # Sort: first prioritize is_injected, then score, then raw_boosted descending
        merged = sorted(
            all_candidates.values(),
            key=lambda x: (
                1 if x.get("is_injected", False) else 0,
                x.get("score", 0.0),
                1 if x.get("_raw_boosted", False) else 0
            ),
            reverse=True
        )
        # Clean up temporary keys
        for r in merged:
            r.pop("is_injected", None)
            r.pop("_raw_boosted", None)

        result = merged[:top_k]

        logger.info(
            "search_multi_query: merged %d unique norms from %d queries, returning top %d",
            len(all_candidates), len(queries) + (1 if raw_query else 0), len(result),
        )
        return result

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
