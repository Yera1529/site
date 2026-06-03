"""Точность доменного классификатора на eval-кейсах (Фаза 3, цель >= 0.85).

Сравнивает classify_domain(фабула, нарушения, адресат) с case.expected_domain.
Нужны креды Vertex (выставляются здесь же).

Запуск:
    python eval/domain_accuracy.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
cred = ROOT / "backend" / "credentials.json"
if cred.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred.resolve())
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

CASES = ROOT / "eval" / "cases"

from services.ai import AIService  # noqa: E402
from services.domain_router import classify_domain  # noqa: E402


async def main() -> None:
    ai = AIService()
    cases = sorted(CASES.glob("*.json"))
    ok = 0
    rows = []
    for cf in cases:
        case = json.loads(cf.read_text(encoding="utf-8"))
        exp = case.get("expected_domain", "")
        dom, conf = await classify_domain(
            case.get("fabula", ""), case.get("violations_input", ""),
            case.get("addressee", ""), ai,
        )
        hit = dom == exp
        ok += int(hit)
        rows.append((case["id"], exp, dom, conf, hit))

    print(f"{'case':26} {'expected':18} {'predicted':18} conf  hit")
    print("-" * 74)
    for cid, exp, dom, conf, hit in rows:
        print(f"{cid:26} {exp:18} {dom:18} {conf:.2f}  {'OK' if hit else 'X'}")
    print("-" * 74)
    print(f"Точность классификатора: {ok}/{len(cases)} = {ok/len(cases):.2f}  (цель >= 0.85)")


if __name__ == "__main__":
    asyncio.run(main())
