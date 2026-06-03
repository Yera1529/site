"""Аудит Фазы 2: существуют ли эталонные нормы в базе и не удалила ли их курация.

Для каждого expected_top3 каждого кейса ищет совпадения (law_name_regex +
article_pattern) в unified и в curated. Отвечает на ключевые вопросы:
  - какой реальный потолок recall (сколько эталонов вообще есть в базе);
  - не удалила ли курация то, что нужно (регрессия = есть в unified, нет в curated);
  - какие кейсы упираются в пробел данных (эталона нет даже в unified).

Запуск:
    python eval/audit_phase2.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = Path(__file__).resolve().parent / "cases"
UNIFIED = ROOT / "backend" / "unified_laws_200upk.jsonl"
CURATED = ROOT / "backend" / "storage" / "laws_curated.jsonl"


def load(path: Path) -> list[dict]:
    recs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return recs


def matches(norm: dict, exp: dict) -> bool:
    ln = norm.get("law_name", "") or ""
    art = norm.get("article_number", "") or ""
    return bool(re.search(exp["law_name_regex"], ln, re.I)) and bool(
        re.search(exp["article_pattern"], art, re.I)
    )


def find(recs: list[dict], exp: dict) -> list[dict]:
    return [r for r in recs if matches(r, exp)]


def main() -> None:
    unified = load(UNIFIED)
    curated = load(CURATED)
    print(f"unified={len(unified)} норм, curated={len(curated)} норм\n")

    cases = sorted(CASES.glob("*.json"))
    total = 0
    in_uni = 0
    in_cur = 0
    removed_by_curation = []
    data_gaps = []
    case_ceiling = {}  # сколько из 3 эталонов кейса есть в curated

    for cf in cases:
        case = json.loads(cf.read_text(encoding="utf-8"))
        cid = case["id"]
        print(f"=== {cid} ({case.get('expected_domain')}) ===")
        cur_hits = 0
        for i, exp in enumerate(case["expected_top3"], 1):
            total += 1
            mu = find(unified, exp)
            mc = find(curated, exp)
            u, c = len(mu), len(mc)
            if u:
                in_uni += 1
            if c:
                in_cur += 1
                cur_hits += 1
            if not u:
                tag = "ПРОБЕЛ ДАННЫХ (нет даже в unified)"
                data_gaps.append((cid, exp["law_name_regex"]))
            elif u and not c:
                tag = "!!! КУРАЦИЯ УДАЛИЛА (есть в unified, нет в curated)"
                removed_by_curation.append((cid, exp["law_name_regex"]))
            else:
                tag = "ok"
            print(f"  [{i}] {exp['law_name_regex'][:46]:46} / {exp['article_pattern'][:18]:18}"
                  f"  uni={u:3d} cur={c:3d}  {tag}")
            if mu:
                s = mu[0]
                print(f"       пример: {s.get('law_name','')[:42]} {s.get('article_number','')[:18]} "
                      f"[{s.get('norm_type','')}]")
        case_ceiling[cid] = cur_hits
        print(f"  → потолок recall@∞ для кейса: {cur_hits}/3\n")

    print("=" * 60)
    print(f"Эталонных норм всего: {total}")
    print(f"Есть в unified:  {in_uni}/{total}  ({100*in_uni/total:.0f}%)")
    print(f"Есть в curated:  {in_cur}/{total}  ({100*in_cur/total:.0f}%)")
    print(f"Удалено курацией (РЕГРЕССИЯ): {len(removed_by_curation)}")
    for cid, ln in removed_by_curation:
        print(f"    - {cid}: {ln}")
    print(f"Пробелы данных (нет в базе): {len(data_gaps)}")
    for cid, ln in data_gaps:
        print(f"    - {cid}: {ln}")
    print()
    print("Потолок recall по кейсам (сколько эталонов достижимо из curated):")
    full = sum(1 for v in case_ceiling.values() if v == 3)
    partial = sum(1 for v in case_ceiling.values() if 0 < v < 3)
    zero = sum(1 for v in case_ceiling.values() if v == 0)
    for cid, v in case_ceiling.items():
        bar = "█" * v + "·" * (3 - v)
        print(f"    {cid:26} {bar} {v}/3")
    print(f"\n  полных (3/3): {full}, частичных: {partial}, нулевых (0/3): {zero}")
    ceiling_recall = sum(case_ceiling.values()) / (3 * len(case_ceiling))
    print(f"  ТЕОРЕТИЧЕСКИЙ ПОТОЛОК avg recall (если retrieval идеален): {ceiling_recall:.3f}")


if __name__ == "__main__":
    main()
