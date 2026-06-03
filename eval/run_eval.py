"""
Регрессионный прогон подбора норм для «Представление Ai».

Запуск:
    python eval/run_eval.py --tag baseline
    python eval/run_eval.py --tag after_phase4 --judge gemini
    python eval/run_eval.py --tag pr --fail-under 0.85

ВАЖНО — перед запуском:
1. На локальной машине выстави GOOGLE_APPLICATION_CREDENTIALS на АБСОЛЮТНЫЙ путь к
   backend/credentials.json. В backend/.env стоит docker-путь /app/credentials.json,
   локально он не существует, и Vertex упадёт молча → видишь FAISS-fallback.
2. Проверь, что Vertex AI API включён в проекте gen-lang-client-0615048966 и у сервис-аккаунта
   rag-worker@... есть роль "Vertex AI User" (roles/aiplatform.user).

Что считается успехом — см. CLAUDE_CODE_playbook_RAG_fix.md, раздел «Целевое качество».

TODO для Claude Code (фаза 1):
- Дореализовать функции, помеченные как `raise NotImplementedError`.
- Подцепить реальный `RAGLawsService.search_multi_query` + `AIService.rerank_laws`.
- Реализовать Gemini-судью в judge_prompts.py.
- Сохранять результат в eval/results/<tag>_<timestamp>/<case_id>.json.
- Печатать сводную таблицу: Case | Recall@5 | Precision@5 | MRR | StdevTop5 | Clean.
"""
import argparse
import asyncio
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # репозиторий
CASES_DIR = Path(__file__).resolve().parent / "cases"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def setup_env() -> None:
    """Перед импортом backend-сервисов: backend в sys.path + абсолютный путь к credentials.

    `os.chdir` недостаточно — для `from services.rag_laws import ...` и
    `from config import ...` каталог backend должен быть в sys.path.
    """
    # Windows: stdout/stderr по умолчанию в cp1251 — печать σ (U+03C3, stdev) и
    # прочих не-кириллических символов падает с UnicodeEncodeError. Принудительно
    # переводим потоки в UTF-8 (а также делает лог-файл читаемым в UTF-8).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    backend_dir = ROOT / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.chdir(backend_dir)
    cred = backend_dir / "credentials.json"
    if cred.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred.resolve())
    else:
        print(f"[WARN] credentials.json НЕ найден по пути {cred} — "
              f"Vertex API упадёт, будет fallback. Это валидный сценарий для baseline.",
              file=sys.stderr)


def load_cases() -> list[dict]:
    cases = []
    for fp in sorted(CASES_DIR.glob("*.json")):
        with fp.open(encoding="utf-8") as f:
            cases.append(json.load(f))
    return cases


def build_query(case: dict) -> str:
    """Запрос, как его собирает фронт + роутер /api/legislation/search_laws."""
    parts = [case["fabula"]]
    if case.get("violations_input"):
        parts.append("НАРУШЕНИЯ: " + case["violations_input"])
    if case.get("addressee"):
        parts.append("АДРЕСАТ: " + case["addressee"])
    return "\n\n".join(parts)


# Сервисы инициализируем один раз на уровне модуля — индекс FAISS тяжёлый
# (21k+ норм, эмбеддинги e5-base), пересоздавать на каждый кейс нельзя.
_services: tuple | None = None


def _get_services() -> tuple:
    """Лениво инициализирует (RAGLawsService, AIService, settings) ровно один раз.

    Базу норм и каталог кэша можно переопределить через env — это позволяет
    сравнить unified vs curated, НЕ трогая rag_laws.py и не затирая основной кэш:
      EVAL_LAWS_JSONL    — путь к jsonl с нормами (по умолчанию — авто-поиск unified)
      EVAL_LAWS_STORAGE  — storage_dir под индекс (по умолчанию settings.storage_dir)
    """
    global _services
    if _services is None:
        from services.rag_laws import RAGLawsService
        from services.ai import AIService
        from config import get_settings
        settings = get_settings()
        jsonl = os.environ.get("EVAL_LAWS_JSONL") or None
        storage = os.environ.get("EVAL_LAWS_STORAGE") or settings.storage_dir
        if jsonl:
            print(f"[i] RAG база: {jsonl}", file=sys.stderr)
            print(f"[i] RAG кэш:   {storage}/faiss_laws", file=sys.stderr)
        rag = RAGLawsService(storage_dir=storage, jsonl_path=jsonl)
        ai = AIService()
        _services = (rag, ai, settings)
    return _services


async def run_pipeline(case: dict) -> list[dict]:
    """Полная цепочка подбора норм, как в routers/chat.py:search_laws.

    L3 (FAISS multi-query, 40 кандидатов) → L4 (Gemini-реранк, top_k=15).
    Возвращает список dict с полями {law_name, article_number, score, source,
    original_text, ai_reason}. Поле source = "rerank", если норму реально отобрал
    реранкер (_rerank_source == "ai"), иначе "fallback" (FAISS-добор/backfill или
    молчаливое падение Vertex — это ловит метрика rerank_share).
    """
    rag, ai, settings = _get_services()
    query = build_query(case)

    # L1 Domain Router (Фаза 3): EVAL_DOMAIN_ROUTER = off | oracle | gemini.
    #   oracle — домен берём из case.expected_domain (верхняя граница пользы пулов);
    #   gemini — классифицируем фабулу; off — без доменного ограничения.
    source_patterns = None
    router_mode = os.environ.get("EVAL_DOMAIN_ROUTER", "off")
    if router_mode in ("oracle", "gemini"):
        from services.domain_router import classify_domain, domain_source_patterns
        if router_mode == "oracle":
            domain = case.get("expected_domain", "общий")
        else:
            domain, _conf = await classify_domain(
                case.get("fabula", ""), case.get("violations_input", ""),
                case.get("addressee", ""), ai,
            )
        source_patterns = domain_source_patterns(domain) or None

    # Нарушения — отдельной структурой: текст нарушения дословно близок к
    # norm.violation_criteria, поэтому даёт сильные приоритетные под-запросы
    # (комплементарны фабуле — см. eval/diagnose_phase4.py). Так же делает прод.
    violations_struct = None
    if case.get("violations_input"):
        violations_struct = [{
            "description": case["violations_input"],
            "responsible": case.get("addressee", ""),
        }]

    fetch_k = settings.ai_rerank_candidates if settings.enable_ai_rerank else 15
    candidates = await asyncio.to_thread(
        lambda: rag.search_multi_query(
            facts=query[:3000], top_k=fetch_k, source_patterns=source_patterns,
            violations=violations_struct,
        )
    )
    if not candidates:
        print(f"[WARN] {case['id']}: FAISS вернул 0 кандидатов", file=sys.stderr)
        return []

    if settings.enable_ai_rerank and len(candidates) > 1:
        reranked = await ai.rerank_laws(
            case_description=query,
            candidate_laws=candidates,
            top_k=15,
            min_keep=settings.ai_rerank_min_keep,
        )
        results = reranked if reranked else candidates[:15]
    else:
        results = candidates[:15]

    out: list[dict] = []
    n_ai = 0
    for r in results:
        is_rerank = r.get("_rerank_source") == "ai"
        if is_rerank:
            n_ai += 1
        out.append({
            "law_name": r.get("law_name", ""),
            "article_number": r.get("article_number", ""),
            "score": float(r.get("score", 0.0) or 0.0),
            "source": "rerank" if is_rerank else "fallback",
            "original_text": (r.get("original_text", "") or "")[:400],
            "ai_reason": r.get("ai_reason", ""),
        })

    # Честный сигнал: реранк включён, но ни одной нормы он не выбрал →
    # Vertex упал молча или переотфильтровал всё в backfill. Не маскируем.
    if settings.enable_ai_rerank and n_ai == 0:
        print(
            f"[RERANK NO-OP] {case['id']}: 0 норм с _rerank_source=='ai' — "
            f"реранкер ничего не выбрал (Vertex упал/переотфильтровал), "
            f"все {len(out)} норм помечены source=fallback",
            file=sys.stderr,
        )
    return out


# ──────────────────── метрики ────────────────────

def _law_matches(predicted: dict, expected: dict) -> bool:
    """Совпадение нормы по regex для law_name + article_pattern."""
    ln = predicted.get("law_name", "") or ""
    art = predicted.get("article_number", "") or ""
    if not re.search(expected["law_name_regex"], ln, re.IGNORECASE):
        return False
    if not re.search(expected["article_pattern"], art, re.IGNORECASE):
        return False
    return True


def metric_recall_at_k(top: list[dict], expected_top3: list[dict], k: int = 5) -> float:
    """Доля эталонных норм, попавших в топ-k. Без штрафа за избыток."""
    if not expected_top3:
        return 0.0
    head = top[:k]
    hits = 0
    for exp in expected_top3:
        if any(_law_matches(p, exp) for p in head):
            hits += 1
    return hits / len(expected_top3)


def metric_mrr_at_k(top: list[dict], expected_top3: list[dict], k: int = 10) -> float:
    """Reciprocal rank позиции первой эталонной нормы."""
    for rank, p in enumerate(top[:k], start=1):
        if any(_law_matches(p, e) for e in expected_top3):
            return 1.0 / rank
    return 0.0


def metric_score_stdev(top: list[dict], k: int = 5) -> float:
    scores = [float(p.get("score", 0.0)) for p in top[:k]]
    if len(scores) < 2:
        return 0.0
    return statistics.pstdev(scores)


def metric_clean(top: list[dict], must_not: list[str]) -> bool:
    """В топ-5 не должно быть ничего из must_not_contain."""
    for p in top[:5]:
        ln = (p.get("law_name") or "").lower()
        for bad in must_not:
            if bad.lower() in ln:
                return False
    return True


def metric_rerank_source(top: list[dict], k: int = 5) -> float:
    """Какая доля top-k реально пришла из реранкера (а не из FAISS-fallback)."""
    head = top[:k]
    if not head:
        return 0.0
    n_rer = sum(1 for p in head if (p.get("source") or "").lower() == "rerank")
    return n_rer / len(head)


# ──────────────────── precision через Gemini-судью ────────────────────

async def metric_precision_at_k_judge(case: dict, top: list[dict], k: int = 5) -> float:
    """Precision@k через Gemini-судью (eval/judge_prompts.py).

    Судья возвращает 0/1 по каждой норме топ-k (1 = реально нарушенная
    обязанность адресата). Precision = доля единиц. Если судья недоступен или
    вернул невалидное — float("nan"), и в сводке метрика помечается как «n/a».
    """
    from judge_prompts import judge_relevance

    head = top[:k]
    if not head:
        return float("nan")
    labels = await judge_relevance(case, head)
    if labels is None:
        return float("nan")
    if not labels:
        return 0.0
    return sum(1 for x in labels if x == 1) / len(labels)


# ──────────────────── runner ────────────────────

async def run_one(case: dict, judge: bool) -> dict:
    t0 = time.time()
    try:
        top = await run_pipeline(case)
    except NotImplementedError as e:
        return {"case_id": case["id"], "error": str(e)}
    elapsed = time.time() - t0

    res = {
        "case_id": case["id"],
        "title": case["title"],
        "domain": case.get("expected_domain"),
        "elapsed_ms": int(elapsed * 1000),
        "top10": top[:10],
        "metrics": {
            "recall@5": round(metric_recall_at_k(top, case["expected_top3"], 5), 3),
            "mrr@10": round(metric_mrr_at_k(top, case["expected_top3"], 10), 3),
            "stdev_top5": round(metric_score_stdev(top, 5), 4),
            "clean": metric_clean(top, case.get("must_not_contain", [])),
            "rerank_share": round(metric_rerank_source(top, 5), 3),
        },
    }
    if judge:
        pv = await metric_precision_at_k_judge(case, top, 5)
        res["metrics"]["precision@5"] = (
            None if (pv is None or (isinstance(pv, float) and math.isnan(pv)))
            else round(pv, 3)
        )
    return res


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True, help="метка прогона (baseline / after_phase4 / pr ...)")
    p.add_argument("--judge", choices=["off", "gemini"], default="off")
    p.add_argument("--fail-under", type=float, default=None,
                   help="если средний recall@5 ниже этого — exit(1)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    setup_env()
    cases = load_cases()
    print(f"[i] Загружено кейсов: {len(cases)}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS_DIR / f"{args.tag}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in cases:
        print(f"[i] {case['id']} …", end=" ", flush=True)
        res = await run_one(case, judge=(args.judge == "gemini"))
        results.append(res)
        with (out_dir / f"{case['id']}.json").open("w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        if "error" in res:
            print(f"ERR: {res['error']}")
        else:
            m = res["metrics"]
            line = (
                f"R@5={m['recall@5']}  MRR={m['mrr@10']}  σ={m['stdev_top5']}  "
                f"clean={'Y' if m['clean'] else 'N'}  rer={m['rerank_share']}"
            )
            if "precision@5" in m:
                pv = m["precision@5"]
                line += f"  P@5={'n/a' if pv is None else pv}"
            print(line)

    # сводка
    ok = [r for r in results if "metrics" in r]
    if ok:
        avg_r = sum(r["metrics"]["recall@5"] for r in ok) / len(ok)
        avg_mrr = sum(r["metrics"]["mrr@10"] for r in ok) / len(ok)
        clean_ratio = sum(1 for r in ok if r["metrics"]["clean"]) / len(ok)
        avg_stdev = sum(r["metrics"]["stdev_top5"] for r in ok) / len(ok)
        avg_rer = sum(r["metrics"]["rerank_share"] for r in ok) / len(ok)
        summary = {
            "tag": args.tag,
            "timestamp": ts,
            "n_cases": len(results),
            "n_ok": len(ok),
            "avg_recall@5": round(avg_r, 3),
            "avg_mrr@10": round(avg_mrr, 3),
            "clean_ratio": round(clean_ratio, 3),
            "avg_stdev_top5": round(avg_stdev, 4),
            "avg_rerank_share": round(avg_rer, 3),
        }

        # Precision@5 (Gemini-судья) — агрегируем только реально измеренные значения,
        # n/a (None) считаем отдельно, чтобы не занижать среднее.
        prec_vals = [
            r["metrics"]["precision@5"] for r in ok if "precision@5" in r["metrics"]
        ]
        prec_num = [v for v in prec_vals if isinstance(v, (int, float))]
        if prec_num:
            summary["avg_precision@5"] = round(sum(prec_num) / len(prec_num), 3)
            summary["precision_na"] = len(prec_vals) - len(prec_num)
        elif prec_vals:
            summary["avg_precision@5"] = "n/a"
            summary["precision_na"] = len(prec_vals)

        with (out_dir / "_summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print("\n=== СВОДКА ===")
        for k, v in summary.items():
            print(f"  {k:>20}: {v}")

        if args.fail_under is not None and avg_r < args.fail_under:
            print(f"\n[FAIL] avg_recall@5 {avg_r:.3f} < {args.fail_under}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n[!] Все кейсы упали с ошибкой — пайплайн ещё не подключён.")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
