"""Курация базы норм (Фаза 2 playbook'а, раздел 5).

Из backend/unified_laws_200upk.jsonl делает backend/storage/laws_curated.jsonl,
выкидывая нормы, которые НЕ могут быть «нарушенной обязанностью адресата»
представления по ст.200 УПК РК. Исходный JSONL не трогает — только читает.

Правила (значения полей выверены по фактическому аудиту, см. audit_laws.py):

  norm_type в базе: Обязывающая / Запрещающая / Компетенционная / Управомочивающая.
  norm_purpose в базе: violation / remedy / both — все осмысленны, НЕ фильтруем.
  violation_criteria — пустых 0, поэтому фильтр почти ноль (страховка).

  Жёсткий минус-лист источников (всегда): УК, УПК, УИК, ГПК, АППК — это
    объекты квалификации и процессуальные нормы, не обязанности адресата.
  Условный минус-лист (--strict): Налоговый, Таможенный, ГК Особенная часть,
    Кодекс о недрах, Лесной кодекс — фискально-ресурсный шум.
  norm_type: Управомочивающая (права, не обязанности) выкидывается по умолчанию
    (--keep-permissive отключает); Компетенционная режется только по --drop-competence.
  violation_criteria: пустые или короче 30 символов выкидываются.

Запуск:
    python backend/scripts/curate_laws.py --strict
    python backend/scripts/curate_laws.py                 # мягкий режим
"""

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── Минус-листы источников (подстроки по нормализованному law_name) ──
# Жёсткие — НИКОГДА не обязанность адресата.
HARD_SOURCE_PATTERNS = [
    "уголовный кодекс",                       # УК (не матчит «уголовно-...»)
    "уголовно-процессуальный",                # УПК
    "уголовно-исполнительный",                # УИК
    "гражданский процессуальный",             # ГПК
    "административный процедурно-процессуальный",  # АППК (поведение органа)
]
# Условные (--strict) — фискально-ресурсный шум.
STRICT_SOURCE_PATTERNS = [
    "налоговый кодекс",
    "таможенном регулировании",
    "о недрах",
    "лесной кодекс",
]

# Типы норм, которые НЕ являются нарушаемой обязанностью.
PERMISSIVE_TYPE = "Управомочивающая"   # права/дозволения
COMPETENCE_TYPE = "Компетенционная"    # компетенция органа

MIN_VC_LEN = 30


def normalize_law_name(name: str) -> str:
    """lower + удаление кавычек/«РК»/«Республики Казахстан» + схлопнутые пробелы."""
    s = (name or "").lower()
    for q in ("«", "»", "\"", "'", "“", "”", "„", "‘", "’"):
        s = s.replace(q, " ")
    s = re.sub(r"республик[аиоуые]\s+казахстан", " ", s)
    s = re.sub(r"\bрк\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_gk_special(norm_name: str) -> bool:
    """ГК Особенная часть (но НЕ Общая)."""
    return "гражданский кодекс" in norm_name and "особенн" in norm_name


def classify(rec: dict, strict: bool, drop_competence: bool, keep_permissive: bool) -> str | None:
    """Возвращает причину выброса (str) или None, если норму оставляем.

    Источник проверяется раньше типа — чтобы Налоговый-Управомочивающая
    атрибутировалась источнику, а не типу.
    """
    name = normalize_law_name(rec.get("law_name", ""))

    for pat in HARD_SOURCE_PATTERNS:
        if pat in name:
            return "source_hard"
    if strict:
        for pat in STRICT_SOURCE_PATTERNS:
            if pat in name:
                return "source_strict"
        if is_gk_special(name):
            return "source_strict"

    vc = (rec.get("violation_criteria") or "").strip()
    if len(vc) == 0:
        return "empty_vc"
    if len(vc) < MIN_VC_LEN:
        return "short_vc"

    nt = (rec.get("norm_type") or "").strip()
    if not keep_permissive and nt == PERMISSIVE_TYPE:
        return "norm_type_permissive"
    if drop_competence and nt == COMPETENCE_TYPE:
        return "norm_type_competence"

    return None


# Профильные источники, которые ждёт eval — контроль, что курация их не убила.
PROFILE_CHECK = [
    "административных правонарушениях",   # КоАП (нужен ради ст.200 alcohol)
    "охранной деятельности",
    "оборотом отдельных видов оружия",
    "профилактике правонарушений",
    "регулировании торговой деятельности",
    "дорожном движении",
    "автомобильном транспорте",
    "наркотических средствах",
    "правах ребенка",
    "об образовании",
    "гражданской защите",
    "здоровье народа",
    "социальный кодекс",
    "трудовой кодекс",
]


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
    ap.add_argument("--output", default=str(ROOT / "backend" / "storage" / "laws_curated.jsonl"))
    ap.add_argument("--report", default=str(ROOT / "backend" / "storage" / "curation_report.md"))
    ap.add_argument("--strict", action="store_true", help="включить условный минус-лист (фискально-ресурсные коды)")
    ap.add_argument("--drop-competence", action="store_true", help="также выкидывать Компетенционная")
    ap.add_argument("--keep-permissive", action="store_true", help="оставлять Управомочивающая")
    args = ap.parse_args()

    recs = load_records(Path(args.input))
    n = len(recs)
    if not n:
        print(f"[!] 0 записей в {args.input}")
        return

    kept: list[dict] = []
    reasons: Counter = Counter()
    removed_by_source: Counter = defaultdict(int)
    kept_by_source: Counter = Counter()

    for r in recs:
        reason = classify(r, args.strict, args.drop_competence, args.keep_permissive)
        raw_src = r.get("law_name", "")
        if reason is None:
            kept.append(r)
            kept_by_source[raw_src] += 1
        else:
            reasons[reason] += 1
            if reason in ("source_hard", "source_strict"):
                removed_by_source[raw_src] += 1

    # ── запись curated JSONL ──
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ── сравнение сценариев (только счётчики, без записи) ──
    def count_kept(strict: bool, drop_comp: bool, keep_perm: bool) -> int:
        return sum(1 for r in recs if classify(r, strict, drop_comp, keep_perm) is None)

    scenarios = [
        ("мягкий (без --strict)", count_kept(False, False, False)),
        ("--strict", count_kept(True, False, False)),
        ("--strict --drop-competence", count_kept(True, True, False)),
    ]

    # ── отчёт ──
    random.seed(42)
    kept_sample = random.sample(kept, min(30, len(kept)))
    removed_recs = [r for r in recs if classify(r, args.strict, args.drop_competence, args.keep_permissive) is not None]
    removed_sample = random.sample(removed_recs, min(30, len(removed_recs)))

    flags = (f"strict={args.strict}, drop_competence={args.drop_competence}, "
             f"keep_permissive={args.keep_permissive}")
    out: list[str] = []
    out.append("# Отчёт курации норм\n")
    out.append(f"Флаги: `{flags}`\n")
    out.append(f"Было: **{n}** → стало: **{len(kept)}** "
               f"(удалено {n - len(kept)}, {100 * (n - len(kept)) / n:.1f}%)\n")

    out.append("## Сравнение сценариев (сколько норм останется)\n")
    out.append("| сценарий | останется | % от исходного |")
    out.append("|---|---:|---:|")
    for label, c in scenarios:
        out.append(f"| {label} | {c} | {100 * c / n:.1f} |")
    out.append("")

    out.append("## Причины удаления\n")
    out.append("| причина | кол-во |")
    out.append("|---|---:|")
    reason_names = {
        "source_hard": "Жёсткий минус-лист источника (УК/УПК/УИК/ГПК/АППК)",
        "source_strict": "Условный минус-лист (--strict: Налоговый/Таможенный/ГК-Особ/Недра/Лесной)",
        "norm_type_permissive": "norm_type=Управомочивающая (права, не обязанности)",
        "norm_type_competence": "norm_type=Компетенционная (--drop-competence)",
        "empty_vc": "violation_criteria пустой",
        "short_vc": f"violation_criteria короче {MIN_VC_LEN} символов",
    }
    for key, label in reason_names.items():
        if reasons.get(key):
            out.append(f"| {label} | {reasons[key]} |")
    out.append("")

    out.append("## Удалённые источники (полностью выброшенные минус-листом)\n")
    out.append("| источник | удалено норм |")
    out.append("|---|---:|")
    for src, c in sorted(removed_by_source.items(), key=lambda kv: kv[1], reverse=True):
        out.append(f"| {src[:70]} | {c} |")
    out.append("")

    out.append("## Топ-25 оставшихся источников\n")
    out.append("| # | источник | норм |")
    out.append("|---:|---|---:|")
    for i, (src, c) in enumerate(sorted(kept_by_source.items(), key=lambda kv: kv[1], reverse=True)[:25], 1):
        out.append(f"| {i} | {src[:70]} | {c} |")
    out.append("")

    out.append("## Контроль: профильные источники (нужны eval) — выжили?\n")
    out.append("| профильный источник | норм в curated |")
    out.append("|---|---:|")
    kept_norm_index: Counter = Counter()
    for src, c in kept_by_source.items():
        kept_norm_index[normalize_law_name(src)] += c
    for pat in PROFILE_CHECK:
        total = sum(c for nm, c in kept_norm_index.items() if pat in nm)
        mark = "✓" if total > 0 else "✗ ОТСУТСТВУЕТ"
        out.append(f"| …{pat}… | {total} {mark} |")
    out.append("")

    def fmt_sample(r: dict) -> str:
        ln = (r.get("law_name", "") or "")[:45]
        an = (r.get("article_number", "") or "")[:25]
        nt = r.get("norm_type", "")
        vc = (r.get("violation_criteria", "") or "")[:90].replace("\n", " ")
        return f"- **{ln}** {an} [{nt}] — {vc}"

    out.append("## 30 случайных ОСТАВЛЕННЫХ норм (спот-чек)\n")
    out.extend(fmt_sample(r) for r in kept_sample)
    out.append("")
    out.append("## 30 случайных УДАЛЁННЫХ норм (спот-чек)\n")
    out.extend(fmt_sample(r) for r in removed_sample)
    out.append("")

    Path(args.report).write_text("\n".join(out), encoding="utf-8")

    # ── stdout ──
    print(f"Было: {n} → стало: {len(kept)} (удалено {n - len(kept)}, {100*(n-len(kept))/n:.1f}%)")
    print(f"Флаги: {flags}")
    print("\nСценарии:")
    for label, c in scenarios:
        print(f"  {c:6d}  ({100*c/n:4.1f}%)  {label}")
    print("\nПричины удаления:")
    for key, label in reason_names.items():
        if reasons.get(key):
            print(f"  {reasons[key]:6d}  {label}")
    print("\nПрофильные источники в curated:")
    for pat in PROFILE_CHECK:
        total = sum(c for nm, c in kept_norm_index.items() if pat in nm)
        mark = "OK" if total > 0 else "!!! ОТСУТСТВУЕТ"
        print(f"  {total:5d}  …{pat}…  {mark}")
    print(f"\nCurated: {args.output}")
    print(f"Отчёт:   {args.report}")


if __name__ == "__main__":
    main()
