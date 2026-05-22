"""
Создание 5 уголовных дел и генерация представлений по разным сферам.
Запуск: python /tmp/generate_5_cases.py
"""
import requests
import json
import time
import sys

BASE = "http://localhost:8000/api"

# ═══════════════════════════════════════════════════════════════════════
# 5 уголовных дел по разным сферам
# ═══════════════════════════════════════════════════════════════════════
CASES = [
    {
        "sphere": "БАНК",
        "name": "2571230310001234",
        "description": (
            "Банковская сфера: 12.03.2026 г. гражданин Сериков К.Б., являясь начальником "
            "кредитного отдела АО «КазФинБанк» г.Алматы, используя служебное положение, "
            "систематически оформлял фиктивные кредиты на подставных лиц на общую сумму "
            "87 500 000 тенге. Деньги перечислялись на подконтрольные счета. Банк не обеспечил "
            "надлежащий внутренний контроль за кредитными операциями, не проводил проверку "
            "заёмщиков, система комплаенс-контроля не функционировала. "
            "ЕРДР №2571230310001234, ст.189 ч.3 п.2 УК РК."
        ),
        "custom_instructions": (
            "Сфера: банковская деятельность, кредитное мошенничество. "
            "Адресат: Председателю правления АО «КазФинБанк». Город: Алматы. "
            "Следователь: старший следователь СУ ДП г.Алматы капитан полиции Абдрахманов Е.Т."
        ),
    },
    {
        "sphere": "ИНТЕРНЕТ-МОШЕННИЧЕСТВО",
        "name": "2571230310005678",
        "description": (
            "Интернет-мошенничество: 05.01.2026 г. группа лиц в составе Ким Д.В., "
            "Нуркенова А.С. и Тлеубаева Р.М. создали фишинговый сайт, имитирующий портал "
            "eGov.kz, через который похищали персональные данные и денежные средства граждан. "
            "За период с января по март 2026 г. потерпевшими признаны 156 граждан, общий "
            "ущерб составил 42 300 000 тенге. Оператор связи АО «КазТелеком» не заблокировал "
            "фишинговый домен в течение 45 дней после обращения, хостинг-провайдер "
            "ТОО «DataLine KZ» не верифицировал данные владельца домена. "
            "ЕРДР №2571230310005678, ст.190 ч.3 п.1 УК РК."
        ),
        "custom_instructions": (
            "Сфера: интернет-мошенничество, фишинг. "
            "Адресат: Руководителю АО «КазТелеком» и Директору ТОО «DataLine KZ». "
            "Город: Нур-Султан. "
            "Следователь: следователь по ОВД СУ ДП г.Нур-Султан майор полиции Искаков Б.Н."
        ),
    },
    {
        "sphere": "АКИМАТ",
        "name": "2571230310009012",
        "description": (
            "Сфера акимата: 18.11.2025 г. в г.Караганда при строительстве социального "
            "жилого комплекса «Нурлы жер» на ул.Ермекова 45, финансируемого из местного "
            "бюджета, аким Октябрьского района Жумабеков Т.К. и начальник отдела строительства "
            "акимата Досмухамедов С.А. допустили нецелевое расходование бюджетных средств "
            "на сумму 156 000 000 тенге. Строительные работы выполнены с грубыми нарушениями "
            "СНиП, часть средств перечислена аффилированному ТОО «СтройГрупп KZ» без "
            "проведения конкурсных процедур. Акимат не осуществлял контроль за расходованием "
            "бюджетных средств. ЕРДР №2571230310009012, ст.189 ч.4 п.2 УК РК."
        ),
        "custom_instructions": (
            "Сфера: бюджетные нарушения, акимат. "
            "Адресат: Акиму г.Караганда. Город: Караганда. "
            "Следователь: старший следователь по ОВД СУ ДП Карагандинской области "
            "подполковник полиции Муканов А.Ж."
        ),
    },
    {
        "sphere": "ТОО (ОХРАНА ТРУДА)",
        "name": "2571230310003456",
        "description": (
            "Сфера ТОО: 22.08.2025 г. на территории ТОО «КазМеталлПром» г.Темиртау "
            "произошёл несчастный случай: при проведении сварочных работ на высоте 12 метров "
            "без страховочного оборудования погиб рабочий Петренко В.И., 1985 г.р. "
            "Расследованием установлено, что директор ТОО Калиев М.Р. не обеспечил работников "
            "средствами индивидуальной защиты, не провёл обязательный инструктаж по технике "
            "безопасности, не назначил ответственного за охрану труда. Срок действия лицензии "
            "на проведение высотных работ истёк 01.03.2025 г. "
            "ЕРДР №2571230310003456, ст.156 ч.3 УК РК."
        ),
        "custom_instructions": (
            "Сфера: охрана труда, несчастный случай на производстве. "
            "Адресат: Директору ТОО «КазМеталлПром». Город: Темиртау. "
            "Следователь: следователь СО УП г.Темиртау лейтенант полиции Сагындыков Д.К."
        ),
    },
    {
        "sphere": "МЕДИЦИНА",
        "name": "2571230310007890",
        "description": (
            "Медицинская сфера: 03.02.2026 г. в ГКП на ПХВ «Городская клиническая больница "
            "№7» г.Шымкент при проведении плановой операции по удалению аппендицита пациентке "
            "Алиевой Г.М., 1990 г.р., врач-хирург Нурпеисов Б.К. допустил грубую врачебную "
            "ошибку — повреждение кишечника, что повлекло перитонит и смерть пациентки "
            "05.02.2026 г. Установлено, что больница не обеспечила надлежащий контроль "
            "квалификации врачебного персонала, Нурпеисов не имел сертификата специалиста "
            "по хирургии с 2024 г., не проведён предоперационный консилиум. Медицинское "
            "оборудование в операционной не проходило техническое обслуживание с 2023 г. "
            "ЕРДР №2571230310007890, ст.317 ч.2 УК РК."
        ),
        "custom_instructions": (
            "Сфера: медицина, врачебная ошибка. "
            "Адресат: Главному врачу ГКП на ПХВ «Городская клиническая больница №7». "
            "Город: Шымкент. "
            "Следователь: следователь СУ ДП г.Шымкент капитан полиции Байжанова К.С."
        ),
    },
]


def create_matters():
    """Step 1: Create 5 criminal case matters."""
    print("=" * 70)
    print("ЭТАП 1: СОЗДАНИЕ УГОЛОВНЫХ ДЕЛ")
    print("=" * 70)

    created = []
    for c in CASES:
        r = requests.post(
            f"{BASE}/matters",
            json={
                "name": c["name"],
                "description": c["description"],
                "custom_instructions": c["custom_instructions"],
            },
        )
        if r.status_code in (200, 201):
            data = r.json()
            created.append({
                "id": data["id"],
                "name": c["name"],
                "sphere": c["sphere"],
            })
            print(f"  [OK] {c['sphere']}: ЕРДР {c['name']} -> id={data['id']}")
        else:
            print(f"  [FAIL] {c['sphere']}: {r.status_code} {r.text[:200]}")
    return created


def search_laws(matter_id, sphere):
    """Step 2: Search for relevant laws via RAG for a given matter."""
    print(f"\n  --- Поиск законодательства для {sphere} ---")
    r = requests.post(
        f"{BASE}/search-laws",
        json={"matter_id": matter_id, "query": ""},
    )
    if r.status_code == 200:
        laws = r.json()
        print(f"  Найдено {len(laws)} нормативных актов:")
        for i, law in enumerate(laws[:5]):
            title = law.get("law_title", "?")[:50]
            article = law.get("article_number", "?")
            score = law.get("score", 0)
            print(f"    [{i+1}] {title} — ст.{article} (score={score:.3f})")
        return laws
    else:
        print(f"  [WARN] Поиск законов: {r.status_code} {r.text[:200]}")
        return []


def generate_document(matter_id, sphere, laws):
    """Step 3: Generate representation document."""
    print(f"\n  --- Генерация представления: {sphere} ---")
    payload = {
        "matter_id": matter_id,
        "template_name": "",
        "additional_instructions": "",
        "selected_laws": laws[:8] if laws else None,
    }
    r = requests.post(f"{BASE}/generate-document", json=payload, timeout=120)
    if r.status_code == 200:
        data = r.json()
        content = data.get("content", "")
        rep_id = data.get("representation_id", "")
        validation = data.get("validation", {})
        citation = data.get("citation_check", {})

        content_len = len(content)
        sections_ok = validation.get("ok", False)
        present = validation.get("present", [])
        missing = validation.get("missing", [])
        cited = citation.get("cited", [])
        unverified = citation.get("unverified", [])

        print(f"  [OK] Документ сгенерирован: {content_len} символов")
        print(f"       Representation ID: {rep_id}")
        print(f"       Валидация: {'PASSED' if sections_ok else 'PARTIAL'}")
        print(f"       Разделы найдены: {len(present)}/{len(present)+len(missing)}")
        if missing:
            print(f"       Отсутствуют: {', '.join(missing)}")
        if cited:
            print(f"       Процитированы: {', '.join(cited[:5])}")
        if unverified:
            print(f"       Непроверенные: {', '.join(unverified[:5])}")
        return data
    else:
        print(f"  [FAIL] Генерация: {r.status_code} {r.text[:300]}")
        return None


def main():
    print("\n" + "=" * 70)
    print("ГЕНЕРАЦИЯ 5 ПРЕДСТАВЛЕНИЙ ПО СТ.200 УПК РК")
    print("=" * 70)

    # Step 1: Create matters
    matters = create_matters()
    if not matters:
        print("Не удалось создать дела!")
        sys.exit(1)

    results = []

    # Step 2-3: For each matter — search laws + generate document
    for i, m in enumerate(matters):
        print(f"\n{'=' * 70}")
        print(f"ДЕЛО {i+1}/5: {m['sphere']} (ЕРДР {m['name']})")
        print(f"{'=' * 70}")

        # Search laws
        laws = search_laws(m["id"], m["sphere"])

        # Generate document
        doc = generate_document(m["id"], m["sphere"], laws)
        results.append({
            "sphere": m["sphere"],
            "matter_id": m["id"],
            "matter_name": m["name"],
            "laws_found": len(laws),
            "generated": doc is not None,
            "rep_id": doc.get("representation_id") if doc else None,
            "content_length": len(doc.get("content", "")) if doc else 0,
        })

    # Summary
    print(f"\n\n{'=' * 70}")
    print("ИТОГО")
    print(f"{'=' * 70}")
    for r in results:
        status = "OK" if r["generated"] else "FAIL"
        print(
            f"  [{status}] {r['sphere']:30s} | "
            f"Законов: {r['laws_found']:2d} | "
            f"Документ: {r['content_length']:6d} симв. | "
            f"Rep: {r['rep_id'] or 'N/A'}"
        )

    ok_count = sum(1 for r in results if r["generated"])
    print(f"\nУспешно: {ok_count}/{len(results)}")

    # Save results
    with open("/tmp/generation_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Результаты сохранены в /tmp/generation_results.json")


if __name__ == "__main__":
    main()
