"""Профилирование базы норм unified_laws_200upk.jsonl (Фаза 2, шаг 2 playbook'а).

Считает распределения, нужные для проектирования курации:
  - глобально: значения и частоты norm_type, norm_purpose;
  - пустота и длина violation_criteria;
  - по каждому источнику (нормализованный law_name): count, топ norm_type,
    топ norm_purpose, % пустых violation_criteria.

Пишет отчёт в backend/scripts/_audit_laws.md и печатает ключевое в stdout.
НИЧЕГО не изменяет в исходном JSONL — только читает.

Запуск:
    python backend/scripts/audit_laws.py
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def normalize_law_name(name: str) -> str:
    """Нормализованный ключ источника.

    lower + удаление кавычек/«РК»/«Республики Казахстан» + схлопнутые пробелы.
    Нужно, потому что один и тот же закон встречается с разными кавычками и
    с/без «Республики Казахстан».
    """
    s = (name or "").lower()
    for q in ("«", "»", "\"", "'", "“", "”", "„", "‘", "’"):
        s = s.replace(q, " ")
    s = re.sub(r"республик[аиоуые]\s+казахстан", " ", s)
    s = re.sub(r"\bрк\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_records(path: Path) -> list[dict]:
    recs: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return recs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "backend" / "unified_laws_200upk.jsonl"))
    ap.add_argument("--report", default=str(ROOT / "backend" / "scripts" / "_audit_laws.md"))
    args = ap.parse_args()

    recs = load_records(Path(args.input))
    n = len(recs)
    if not n:
        print(f"[!] 0 записей в {args.input}")
        return

    type_counts: Counter = Counter()
    purpose_counts: Counter = Counter()
    vc_empty = 0
    vc_short = 0  # 1..29 символов
    buckets: Counter = Counter()
    per_source: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "type": Counter(), "purpose": Counter(), "vc_empty": 0, "raw": ""}
    )

    for r in recs:
        nt = (r.get("norm_type") or "").strip() or "(пусто)"
        pp = (r.get("norm_purpose") or "").strip() or "(пусто)"
        type_counts[nt] += 1
        purpose_counts[pp] += 1

        vc = (r.get("violation_criteria") or "").strip()
        L = len(vc)
        if L == 0:
            vc_empty += 1
            buckets["0"] += 1
        elif L < 30:
            vc_short += 1
            buckets["1-29"] += 1
        elif L < 100:
            buckets["30-99"] += 1
        elif L < 300:
            buckets["100-299"] += 1
        else:
            buckets["300+"] += 1

        key = normalize_law_name(r.get("law_name", ""))
        s = per_source[key]
        s["count"] += 1
        s["type"][nt] += 1
        s["purpose"][pp] += 1
        if L == 0:
            s["vc_empty"] += 1
        if not s["raw"]:
            s["raw"] = r.get("law_name", "")

    sources_sorted = sorted(per_source.items(), key=lambda kv: kv[1]["count"], reverse=True)

    # ── markdown отчёт ──
    out: list[str] = []
    out.append("# Аудит unified_laws_200upk.jsonl\n")
    out.append(f"Всего норм: **{n}**, источников (по нормализованному law_name): **{len(per_source)}**\n")

    out.append("## norm_type (глобально)\n")
    out.append("| norm_type | кол-во | % |")
    out.append("|---|---:|---:|")
    for v, c in type_counts.most_common():
        out.append(f"| {v} | {c} | {100 * c / n:.1f} |")
    out.append("")

    out.append("## norm_purpose (глобально)\n")
    out.append("| norm_purpose | кол-во | % |")
    out.append("|---|---:|---:|")
    for v, c in purpose_counts.most_common():
        out.append(f"| {v} | {c} | {100 * c / n:.1f} |")
    out.append("")

    out.append("## violation_criteria — длина\n")
    out.append(
        f"Пустых: **{vc_empty}** ({100 * vc_empty / n:.1f}%), "
        f"короче 30 симв.: **{vc_short}** ({100 * vc_short / n:.1f}%)\n"
    )
    out.append("| длина | кол-во |")
    out.append("|---|---:|")
    for b in ["0", "1-29", "30-99", "100-299", "300+"]:
        out.append(f"| {b} | {buckets.get(b, 0)} |")
    out.append("")

    out.append(f"## Источники (все {len(per_source)}, по убыванию количества)\n")
    out.append("| # | Источник (raw) | норм | топ norm_type | топ norm_purpose | пустой VC % |")
    out.append("|---:|---|---:|---|---|---:|")
    for i, (key, s) in enumerate(sources_sorted, 1):
        tt = ", ".join(f"{v}:{c}" for v, c in s["type"].most_common(3))
        tp = ", ".join(f"{v}:{c}" for v, c in s["purpose"].most_common(3))
        empct = 100 * s["vc_empty"] / s["count"] if s["count"] else 0
        out.append(f"| {i} | {s['raw'][:70]} | {s['count']} | {tt} | {tp} | {empct:.0f} |")
    out.append("")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(out), encoding="utf-8")

    # ── stdout: самое важное для проектирования фильтров ──
    print(f"Всего норм: {n}, источников: {len(per_source)}")
    print("\nnorm_type (значение → кол-во):")
    for v, c in type_counts.most_common():
        print(f"  {c:6d}  {v}")
    print("\nnorm_purpose (значение → кол-во):")
    for v, c in purpose_counts.most_common():
        print(f"  {c:6d}  {v}")
    print(f"\nviolation_criteria: пустых {vc_empty} ({100 * vc_empty / n:.1f}%), "
          f"<30 симв. {vc_short} ({100 * vc_short / n:.1f}%)")
    print("\nТоп-30 источников:")
    for i, (key, s) in enumerate(sources_sorted[:30], 1):
        print(f"  {i:3d}. {s['count']:5d}  {s['raw'][:60]}")
    print(f"\nПолный отчёт: {args.report}")


if __name__ == "__main__":
    main()
