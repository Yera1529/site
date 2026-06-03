"""Аудит достоверности метрик: НЕЗАВИСИМЫЙ пересчёт recall@5/@10, MRR@10, clean
из сохранённых result-файлов (другой код, чем в run_eval) и сверка с _summary.json.
Ловит баги в метриках/инфляцию. Показывает #1 каждого кейса (проверка MRR=1.0).

Запуск: python eval/audit_metrics.py <result_dir>
"""

import json
import re
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "cases"


def law_matches(pred: dict, exp: dict) -> bool:
    ln = pred.get("law_name", "") or ""
    art = pred.get("article_number", "") or ""
    return bool(re.search(exp["law_name_regex"], ln, re.I)) and bool(
        re.search(exp["article_pattern"], art, re.I)
    )


def recall_at(top: list, e3: list, k: int) -> float:
    if not e3:
        return 0.0
    head = top[:k]
    return sum(1 for e in e3 if any(law_matches(p, e) for p in head)) / len(e3)


def mrr_at(top: list, e3: list, k: int) -> float:
    for rank, p in enumerate(top[:k], 1):
        if any(law_matches(p, e) for e in e3):
            return 1.0 / rank
    return 0.0


def clean(top: list, mustnot: list) -> bool:
    for p in top[:5]:
        ln = (p.get("law_name") or "").lower()
        for bad in mustnot:
            if bad.lower() in ln:
                return False
    return True


def main() -> None:
    d = Path(sys.argv[1])
    summary = json.loads((d / "_summary.json").read_text(encoding="utf-8"))
    rs, ms, cs = [], [], []
    print(f"{'case':26} R@5   R@10  MRR   clean  #1-норма (матчит ли эталон)")
    print("-" * 92)
    for cf in sorted(CASES.glob("*.json")):
        case = json.loads(cf.read_text(encoding="utf-8"))
        res = json.loads((d / f"{case['id']}.json").read_text(encoding="utf-8"))
        top = res["top10"]
        e3 = case["expected_top3"]
        r5 = recall_at(top, e3, 5)
        r10 = recall_at(top, e3, 10)
        m = mrr_at(top, e3, 10)
        cl = clean(top, case.get("must_not_contain", []))
        rs.append(r5); ms.append(m); cs.append(1 if cl else 0)
        top1 = top[0] if top else {}
        hit1 = any(law_matches(top1, e) for e in e3)
        flag = "✓match" if hit1 else "✗ НЕ матчит!"
        print(f"{case['id']:26} {r5:.2f}  {r10:.2f}  {m:.2f}  {'Y' if cl else 'N'}     "
              f"{(top1.get('law_name','')[:34]):34} {flag}")

    ind_r = sum(rs) / len(rs)
    ind_m = sum(ms) / len(ms)
    ind_c = sum(cs) / len(cs)
    print("-" * 92)
    print(f"НЕЗАВИСИМО:  recall@5={ind_r:.3f}  MRR@10={ind_m:.3f}  clean={ind_c:.3f}")
    print(f"ОТЧИТАНО:    recall@5={summary['avg_recall@5']}  MRR@10={summary['avg_mrr@10']}  clean={summary['clean_ratio']}")
    ok = (abs(ind_r - summary['avg_recall@5']) < 0.005
          and abs(ind_m - summary['avg_mrr@10']) < 0.005
          and abs(ind_c - summary['clean_ratio']) < 0.005)
    print("\nИТОГ:", "✓ метрики ДОСТОВЕРНЫ (независимый пересчёт совпал)"
          if ok else "✗ РАСХОЖДЕНИЕ — баг в метриках!")


if __name__ == "__main__":
    main()
