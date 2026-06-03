"""Сравнение двух прогонов eval по Recall@5 и Recall@10.

Recall@10 отделяет «норму не извлекли» от «извлекли, но ранжировали ниже 5».

Запуск:
    python eval/compare_runs.py <dir_baseline> <dir_other>
"""

import json
import re
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "cases"


def law_matches(pred: dict, exp: dict) -> bool:
    ln = pred.get("law_name", "") or ""
    art = pred.get("article_number", "") or ""
    if not re.search(exp["law_name_regex"], ln, re.IGNORECASE):
        return False
    if not re.search(exp["article_pattern"], art, re.IGNORECASE):
        return False
    return True


def recall_at(top: list[dict], exp3: list[dict], k: int) -> float:
    if not exp3:
        return 0.0
    head = top[:k]
    hits = sum(1 for e in exp3 if any(law_matches(p, e) for p in head))
    return hits / len(exp3)


def load_case(cid: str) -> dict:
    return json.loads((CASES / f"{cid}.json").read_text(encoding="utf-8"))


def load_run(d: str) -> dict[str, list]:
    res = {}
    for fp in Path(d).glob("*.json"):
        if fp.name == "_summary.json":
            continue
        r = json.loads(fp.read_text(encoding="utf-8"))
        res[r["case_id"]] = r.get("top10", [])
    return res


def main() -> None:
    d1, d2 = sys.argv[1], sys.argv[2]
    r1, r2 = load_run(d1), load_run(d2)
    cids = sorted(set(r1) & set(r2))

    print(f"{'case':26} | A:R@5 R@10 | B:R@5 R@10 | Δ@5   Δ@10")
    print("-" * 72)
    s = {"a5": 0.0, "a10": 0.0, "b5": 0.0, "b10": 0.0}
    for cid in cids:
        e3 = load_case(cid)["expected_top3"]
        a5, a10 = recall_at(r1[cid], e3, 5), recall_at(r1[cid], e3, 10)
        b5, b10 = recall_at(r2[cid], e3, 5), recall_at(r2[cid], e3, 10)
        s["a5"] += a5; s["a10"] += a10; s["b5"] += b5; s["b10"] += b10
        print(f"{cid:26} | {a5:.2f}  {a10:.2f} | {b5:.2f}  {b10:.2f} | "
              f"{b5-a5:+.2f}  {b10-a10:+.2f}")
    n = len(cids)
    print("-" * 72)
    print(f"{'AVG':26} | {s['a5']/n:.3f} {s['a10']/n:.3f} | "
          f"{s['b5']/n:.3f} {s['b10']/n:.3f} | "
          f"{(s['b5']-s['a5'])/n:+.3f} {(s['b10']-s['a10'])/n:+.3f}")
    print(f"\nA = {d1}\nB = {d2}")


if __name__ == "__main__":
    main()
