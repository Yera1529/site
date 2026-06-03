"""Детерминированная оценка RETRIEVAL (без реранка) — главная метрика Фазы 4.

Меряет, доходят ли эталонные нормы в сырой объединённый пул кандидатов
(facts + violations, oracle-домен, текущее слияние). Реранк не вызывается →
нет шума LLM, числа воспроизводимы. Реранк (топ-5) — это Фаза 5.

Запуск: python eval/retrieval_eval.py
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
CASES = ROOT / "eval" / "cases"

from services.rag_laws import RAGLawsService  # noqa: E402
from services.domain_router import domain_source_patterns  # noqa: E402


def build_query(case: dict) -> str:
    parts = [case["fabula"]]
    if case.get("violations_input"):
        parts.append("НАРУШЕНИЯ: " + case["violations_input"])
    if case.get("addressee"):
        parts.append("АДРЕСАТ: " + case["addressee"])
    return "\n\n".join(parts)


def law_matches(norm: dict, exp: dict) -> bool:
    ln = norm.get("law_name", "") or ""
    art = norm.get("article_number", "") or ""
    return bool(re.search(exp["law_name_regex"], ln, re.I)) and bool(
        re.search(exp["article_pattern"], art, re.I)
    )


def best_rank(cands: list[dict], exp: dict) -> int:
    for j, c in enumerate(cands, 1):
        if law_matches(c, exp):
            return j
    return 0


def main() -> None:
    rag = RAGLawsService(
        storage_dir=str(ROOT / "backend" / "storage_curated"),
        jsonl_path=str(ROOT / "backend" / "storage" / "laws_curated.jsonl"),
    )
    agg = {5: 0, 10: 0, 20: 0, 40: 0}
    n = 0
    for cf in sorted(CASES.glob("*.json")):
        case = json.loads(cf.read_text(encoding="utf-8"))
        sp = domain_source_patterns(case.get("expected_domain", "общий")) or None
        cands = rag.search_multi_query(
            facts=build_query(case)[:3000], top_k=40, source_patterns=sp,
            violations=[{"description": case.get("violations_input", ""),
                         "responsible": case.get("addressee", "")}],
        )
        ranks = []
        for exp in case["expected_top3"]:
            n += 1
            r = best_rank(cands, exp)
            ranks.append(f"#{r}" if r else "—")
            for k in (5, 10, 20, 40):
                if 0 < r <= k:
                    agg[k] += 1
        print(f"{case['id']:26} pool={len(cands):2d}  ранги: {ranks}")

    print("\n" + "=" * 50)
    print(f"Эталонов: {n}  (детерминированный retrieval, без реранка)")
    for k in (5, 10, 20, 40):
        print(f"  recall@{k:<2} = {agg[k]}/{n} = {agg[k]/n:.3f}")


if __name__ == "__main__":
    main()
