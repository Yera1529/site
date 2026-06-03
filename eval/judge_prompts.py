"""
Gemini-судья для метрики Precision@5.

TODO (Claude Code, фаза 1, шаг 5):
    1. Реализовать async judge_relevance(case: dict, candidates: list[dict]) -> list[int].
       На вход — фабула/нарушения/адресат + список 5 норм.
       На выход — массив 0/1 такой же длины: 1 = норма реально обязывает адресата
       и эта обязанность нарушена в фабуле; 0 = иначе.
    2. Вызывает Gemini через AIService с response_mime_type="application/json".
    3. На ошибке Gemini — возвращает None (тогда precision@5 в run_eval помечается как "n/a").
"""

import asyncio
import json
import re
import sys

JUDGE_SYSTEM = """\
Ты юрист-эксперт по уголовно-процессуальному праву Республики Казахстан.
Оценишь, релевантна ли каждая норма законодательства для включения в процессуальное \
представление по ст. 200 УПК РК.

Норма считается РЕЛЕВАНТНОЙ (label=1), только если ВСЕ условия выполнены:
1) Норма устанавливает ОБЯЗАННОСТЬ (или запрет) для адресата представления — \
конкретно для лица/организации, которому будет направлено представление.
2) Эта обязанность была НАРУШЕНА при обстоятельствах, описанных в фабуле дела.
3) Норма НЕ относится к УК, УПК, УИК или ГПК Республики Казахстан.
4) Норма НЕ описывает права/процедуру самого правоохранительного органа \
(если только адресат представления — не сам орган внутренних дел).

Иначе label=0.
"""

JUDGE_USER_TEMPLATE = """\
АДРЕСАТ: {addressee}

ФАБУЛА:
{fabula}

НАРУШЕНИЯ (со слов следователя):
{violations}

КАНДИДАТЫ:
{candidates_json}

Верни JSON-массив длиной ровно {n} элементов из 0 и 1, по позициям кандидатов. \
Никакого дополнительного текста.
"""


_AI = None


def _get_judge_ai():
    """Лениво создаёт AIService для судьи (один раз).

    Требует backend в sys.path — его добавляет run_eval.setup_env() до первого
    вызова судьи, поэтому импорт делаем здесь, а не на уровне модуля.
    """
    global _AI
    if _AI is None:
        from services.ai import AIService
        _AI = AIService()
    return _AI


async def judge_relevance(case: dict, candidates: list[dict]) -> list[int] | None:
    """Оценивает релевантность каждой нормы через Gemini (Vertex AI).

    Возвращает список 0/1 длиной ровно len(candidates) или None при любой ошибке
    Vertex / невалидном ответе модели (тогда precision@5 помечается как «n/a»).
    Ошибки не глотаем молча — пишем причину в stderr.
    """
    n = len(candidates)
    if n == 0:
        return []

    try:
        from google.genai import types as genai_types
        ai = _get_judge_ai()
    except Exception as e:  # noqa: BLE001 — на baseline любая поломка инициализации → n/a
        print(f"[JUDGE INIT FAIL] {case.get('id', '?')}: {e}", file=sys.stderr)
        return None

    # Компактное представление кандидатов для судьи
    lines = []
    for i, c in enumerate(candidates):
        ln = c.get("law_name", "")
        art = c.get("article_number", "")
        txt = (c.get("original_text", "") or c.get("text", "") or "")[:300]
        lines.append(f"[{i}] {ln}, {art}\n{txt}")
    candidates_json = "\n---\n".join(lines)

    user_prompt = JUDGE_USER_TEMPLATE.format(
        addressee=case.get("addressee", ""),
        fabula=case.get("fabula", ""),
        violations=case.get("violations_input", ""),
        candidates_json=candidates_json,
        n=n,
    )

    try:
        config = genai_types.GenerateContentConfig(
            temperature=0.0,
            top_p=0.9,
            max_output_tokens=2048,
            response_mime_type="application/json",
            system_instruction=JUDGE_SYSTEM,
        )
        response = await asyncio.to_thread(
            ai._client.models.generate_content,
            model=ai.model_name,
            contents=user_prompt,
            config=config,
        )
        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*\n", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\n```\s*$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001 — любая ошибка Vertex/парсинга → n/a, но видимо
        print(f"[JUDGE FAILED] {case.get('id', '?')}: {e}", file=sys.stderr)
        return None

    if not isinstance(data, list) or len(data) != n:
        got = len(data) if isinstance(data, list) else type(data).__name__
        print(
            f"[JUDGE INVALID] {case.get('id', '?')}: ожидали массив длины {n}, получили {got}",
            file=sys.stderr,
        )
        return None

    labels: list[int] = []
    for x in data:
        if x in (0, 1) or x in ("0", "1"):
            labels.append(int(x))
        else:
            print(
                f"[JUDGE INVALID] {case.get('id', '?')}: элемент не 0/1: {x!r}",
                file=sys.stderr,
            )
            return None
    return labels
