"""Диагностика retrieval (без реранка): на каком ранге сырого пула эталонные нормы.

Отделяет проблему Фазы 4 (норма не доходит даже в топ-40 кандидатов) от
проблемы Фазы 3/5 (норма извлеклась, но потом вытеснена/недоранжирована).
Реранк и Vertex НЕ нужны — только FAISS+BM25 поверх curated-базы.

Запуск:
    python eval/diagnose_retrieval.py
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
CASES = ROOT / "eval" / "cases"

from services.rag_laws import RAGLawsService  # noqa: E402


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


def main() -> None:
    rag = RAGLawsService(
        storage_dir=str(ROOT / "backend" / "storage_curated"),
        jsonl_path=str(ROOT / "backend" / "storage" / "laws_curated.jsonl"),
    )

    n_found_top40 = 0
    n_found_top5 = 0
    n_total = 0
    for cf in sorted(CASES.glob("*.json")):
        case = json.loads(cf.read_text(encoding="utf-8"))
        q = build_query(case)
        cands = rag.search_multi_query(facts=q[:3000], top_k=40)
        print(f"\n=== {case['id']} ({case.get('expected_domain')}) — кандидатов {len(cands)} ===")
        for i, exp in enumerate(case["expected_top3"], 1):
            n_total += 1
            ranks = [j + 1 for j, c in enumerate(cands) if law_matches(c, exp)]
            if ranks:
                n_found_top40 += 1
                if ranks[0] <= 5:
                    n_found_top5 += 1
                best = ranks[0]
                mark = "топ-5" if best <= 5 else ("топ-40" if best <= 40 else "")
                print(f"  [{i}] {exp['law_name_regex'][:42]:42} → ранги {ranks[:6]}  (лучший #{best}, {mark})")
            else:
                print(f"  [{i}] {exp['law_name_regex'][:42]:42} → НЕ В ТОП-40 (retrieval-промах)")

    print("\n" + "=" * 60)
    print(f"Эталонов: {n_total}")
    print(f"Доходят в сырой топ-40: {n_found_top40}/{n_total} ({100*n_found_top40/n_total:.0f}%)")
    print(f"Уже в сыром топ-5:      {n_found_top5}/{n_total} ({100*n_found_top5/n_total:.0f}%)")
    print(f"Не доходят в топ-40:    {n_total - n_found_top40}/{n_total} → проблема Фазы 4 (retrieval)")
    print(f"В топ-40, но ниже 5:    {n_found_top40 - n_found_top5}/{n_total} → проблема Фазы 3/5 (ранжирование)")


if __name__ == "__main__":
    main()
