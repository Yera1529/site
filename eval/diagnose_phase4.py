"""Диагностика Фазы 4: где ранжируются эталоны в сыром retrieval ВНУТРИ доменного пула,
при двух стратегиях запроса:
  A — текущая: facts = build_query(case) (фабула+нарушения+адресат склеены).
  B — нарушения как приоритетный под-запрос (violations=[{description, responsible}]).

Доменный пул берём oracle (из expected_domain). Vertex/реранк не нужны.
Запуск: python eval/diagnose_phase4.py
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
    return 0  # не найдено


def main() -> None:
    rag = RAGLawsService(
        storage_dir=str(ROOT / "backend" / "storage_curated"),
        jsonl_path=str(ROOT / "backend" / "storage" / "laws_curated.jsonl"),
    )

    tot = {"A5": 0, "A40": 0, "B5": 0, "B40": 0, "n": 0}
    for cf in sorted(CASES.glob("*.json")):
        case = json.loads(cf.read_text(encoding="utf-8"))
        sp = domain_source_patterns(case.get("expected_domain", "общий")) or None

        cands_a = rag.search_multi_query(facts=build_query(case)[:3000], top_k=40, source_patterns=sp)
        cands_b = rag.search_multi_query(
            facts=case["fabula"][:3000], top_k=40, source_patterns=sp,
            violations=[{"description": case.get("violations_input", ""),
                         "responsible": case.get("addressee", "")}],
        )
        print(f"\n=== {case['id']} ({case.get('expected_domain')}) | A={len(cands_a)} B={len(cands_b)} кандидатов ===")
        for i, exp in enumerate(case["expected_top3"], 1):
            tot["n"] += 1
            ra = best_rank(cands_a, exp)
            rb = best_rank(cands_b, exp)
            tot["A5"] += int(0 < ra <= 5); tot["A40"] += int(ra > 0)
            tot["B5"] += int(0 < rb <= 5); tot["B40"] += int(rb > 0)
            fa = f"#{ra}" if ra else "—"
            fb = f"#{rb}" if rb else "—"
            flag = " <= B лучше" if (rb and (not ra or rb < ra)) else (" (A лучше)" if (ra and (not rb or ra < rb)) else "")
            print(f"  [{i}] {exp['law_name_regex'][:40]:40}  A:{fa:>4}  B:{fb:>4}{flag}")

    n = tot["n"]
    print("\n" + "=" * 56)
    print(f"Эталонов: {n}")
    print(f"  A (facts):       в топ-5 {tot['A5']}/{n}, в топ-40 {tot['A40']}/{n}")
    print(f"  B (violations):  в топ-5 {tot['B5']}/{n}, в топ-40 {tot['B40']}/{n}")


if __name__ == "__main__":
    main()
