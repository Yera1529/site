"""AI service for Qwen3-30B-A3B (30B total / 3.3B active MoE, 32k–131k context).

Generates strictly structured representations per Article 200 of the Criminal
Procedure Code of Kazakhstan with 8 mandatory sections, law citations grounded
in retrieved legislation, cause-effect analysis, and liability warnings.
"""

import json
import re
import httpx
from typing import AsyncGenerator, List, Dict, Optional
from config import get_settings

# ---------------------------------------------------------------------------
# Eight mandatory sections derived from the official Instruction (ст.200 УПК)
# ---------------------------------------------------------------------------
MANDATORY_SECTIONS_SPEC = """\
Представление по ст.200 УПК РК ОБЯЗАТЕЛЬНО должно содержать ВСЕ 8 разделов:

РАЗДЕЛ 1 — ДАТА, МЕСТО, АВТОР
  Дата и место составления. Должность, звание и ФИО следователя/дознавателя.

РАЗДЕЛ 2 — ФАБУЛА ДЕЛА
  Краткое изложение обстоятельств: время, место, участники, действия,
  квалификация по статье УК РК, номер ЕРДР.

РАЗДЕЛ 3 — ВЫЯВЛЕННЫЕ НАРУШЕНИЯ
  Подробное описание конкретных нарушений (действий/бездействий) организаций
  и должностных лиц, которые создали условия для преступления.
  Для каждого нарушения: что именно нарушено, кем, когда.

РАЗДЕЛ 4 — НАРУШЕННЫЕ НОРМАТИВНЫЕ АКТЫ
  Для каждого нарушения из Раздела 3 укажи конкретную статью закона,
  правил, инструкций или регламента, которая нарушена.
  Формат: «ст. NNN Название закона» (используй ТОЛЬКО нормы из контекста).

РАЗДЕЛ 5 — ПРИЧИННО-СЛЕДСТВЕННАЯ СВЯЗЬ
  Объясни, каким образом каждое нарушение (из Раздела 3) привело или
  способствовало совершению преступления. Причинно-следственная цепочка
  должна быть явной и логичной.

РАЗДЕЛ 6 — ПРЕДЛАГАЕМЫЕ МЕРЫ
  Нумерованный список конкретных мер по устранению причин и условий
  преступления. Каждая мера — с указанием ответственного органа/лица
  и правового основания (ст.200 ч.2 УПК РК и др.).

РАЗДЕЛ 7 — СРОКИ ИСПОЛНЕНИЯ
  Указание на обязанность сообщить о принятых мерах не позднее
  одного месяца со дня получения представления (ч.2 ст.200 УПК РК).

РАЗДЕЛ 8 — ПРЕДУПРЕЖДЕНИЕ ОБ ОТВЕТСТВЕННОСТИ
  Предупреждение о том, что невыполнение представления или
  непредставление ответа в установленный срок влечёт
  ответственность по ст.479 и ст.664 КоАП РК.
"""

DOCUMENT_STRUCTURE = """\
Форматирование документа:
1. Шапка адресатов (руководители организаций) — по правому краю
2. Пустая строка
3. «П Р Е Д С Т А В Л Е Н И Е» — по центру, заглавными с пробелами
4. «по устранению обстоятельств, способствовавших совершению уголовного
   правонарушения и других нарушений закона» — по центру
5. Дата слева, город справа
6. Текст: вводная часть, нарушения, нормы, причинная связь — абзацы с выравниванием по ширине
7. «На основании изложенного, руководствуясь ст.200 УПК РК, ПРЕДЛАГАЮ:»
8. Нумерованный список мер
9. Указание о месячном сроке
10. Предупреждение об ответственности по ст.479, 664 КоАП
11. Подпись: должность, звание, ФИО
"""

FEW_SHOT_EXAMPLE = """\
=== Пример представления ===

П Р Е Д С Т А В Л Е Н И Е
по устранению обстоятельств, способствовавших совершению уголовного
правонарушения и других нарушений закона

15.01.2025 г.                                                    г. Астана

Следственным отделом Управления полиции района «Есиль» г. Астаны
расследуется уголовное дело, зарегистрированное в ЕРДР за
№ 251234567890123, возбужденное по признакам уголовного правонарушения,
предусмотренного ч.3 ст.188 Уголовного кодекса Республики Казахстан.

В ходе расследования установлено, что совершению данного уголовного
правонарушения способствовали следующие обстоятельства:

Руководство ТОО «Пример» в лице директора Петрова А.Б. не обеспечило
надлежащий контроль за соблюдением внутреннего трудового распорядка,
что является нарушением ст.22 Трудового кодекса Республики Казахстан,
согласно которой работодатель обязан обеспечивать безопасные условия труда.

Кроме того, служба охраны предприятия не осуществляла пропускной режим
в нарушение п.3 ст.10 Закона РК «О частной охранной деятельности»,
что позволило посторонним лицам беспрепятственно проникнуть на территорию.

Таким образом, ненадлежащее исполнение руководством ТОО «Пример»
обязанностей по обеспечению безопасности (ст.22 ТК РК) и бездействие
службы охраны (ст.10 Закона «О частной охранной деятельности») создали
условия, при которых стало возможным совершение указанного уголовного
правонарушения. Данные нарушения находятся в прямой причинно-следственной
связи с совершённым преступлением.

На основании изложенного, руководствуясь ст.200 Уголовно-процессуального
кодекса Республики Казахстан,

ПРЕДЛАГАЮ:

1. Директору ТОО «Пример» Петрову А.Б. принять меры по усилению
   внутреннего контроля и обеспечению безопасных условий труда
   в соответствии с требованиями ст.22 Трудового кодекса РК.
2. Обеспечить надлежащее функционирование пропускного режима
   в соответствии со ст.10 Закона «О частной охранной деятельности».
3. Привлечь к дисциплинарной ответственности лиц, допустивших
   указанные нарушения.
4. О принятых мерах сообщить в следственный отдел в месячный срок
   со дня получения настоящего представления (ч.2 ст.200 УПК РК).

Разъясняю, что невыполнение представления, а равно непредставление
ответа в установленный законом срок, влечёт ответственность по
статьям 479 и 664 Кодекса об административных правонарушениях
Республики Казахстан.

Следователь СО УП района «Есиль» г. Астаны
капитан полиции                                          И.И. Иванов
"""

LAW_TO_CITATION_DEMO = """\
=== Как использовать извлечённые нормативные акты ===

Если в списке нормативных актов есть:
  «Трудовой кодекс РК, Статья 22: Работодатель обязан обеспечивать
   безопасные условия труда…»

То в представлении напиши:
  «…не обеспечило надлежащий контроль за соблюдением правил безопасности,
   что является нарушением ст.22 Трудового кодекса Республики Казахстан,
   согласно которой работодатель обязан обеспечивать безопасные условия труда.»

И в мерах:
  «Принять меры по обеспечению безопасных условий труда в соответствии
   с требованиями ст.22 Трудового кодекса РК.»

ПРАВИЛО: для каждого нарушения должна быть цитата из конкретной статьи,
и для каждой меры — ссылка на правовое основание.
"""

# ---------------------------------------------------------------------------
# Mandatory section markers for post-generation validation
# ---------------------------------------------------------------------------
MANDATORY_SECTIONS = [
    ("дата_место", r"(\d{2}\.\d{2}\.\d{4}\s*г\.)|(\d{4}\s*год)"),
    ("ердр", r"(ЕРДР|ердр|Е\s*Р\s*Д\s*Р)"),
    ("статья_ук", r"(ст\.\s*\d+|стать[яией]\s*\d+).*(УК|Уголовн)"),
    ("нарушения", r"(нарушени[еяй]|бездействи|ненадлежащ)"),
    ("нормативные_акты", r"(ст\.\s*200\s*УПК|Уголовно-процессуальн)"),
    ("причинная_связь", r"(причин|способствовал|создал[оаи]?\s+условия|обусловил|повлекл)"),
    ("предлагаю", r"(ПРЕДЛАГАЮ|предлагаю)"),
    ("срок", r"(месячный срок|в течение месяца|не позднее|ч\.\s*2\s*ст\.\s*200)"),
    ("предупреждение", r"(479|664|КоАП|ответственност[ьи])"),
]


def validate_representation(text: str) -> dict:
    """Check generated text for all 9 mandatory markers.
    Returns {ok: bool, missing: [str], present: [str]}.
    """
    present, missing = [], []
    for label, pattern in MANDATORY_SECTIONS:
        if re.search(pattern, text, re.IGNORECASE):
            present.append(label)
        else:
            missing.append(label)
    return {"ok": len(missing) == 0, "missing": missing, "present": present}


def validate_law_citations(
    generated_text: str, retrieved_laws: list[dict]
) -> dict:
    """Check that cited articles in generated text match the retrieved law set.
    Returns {cited: [str], unverified: [str]}.
    """
    cited_raw = re.findall(r"ст(?:атья|\.)\s*(\d+[\.\d]*)", generated_text, re.IGNORECASE)
    cited = sorted(set(cited_raw))

    provided_articles = set()
    for law in (retrieved_laws or []):
        art = law.get("article_number", "")
        if art:
            provided_articles.add(art)

    always_valid = {"200", "159", "479", "664"}
    unverified = [c for c in cited if c not in provided_articles and c not in always_valid]

    return {"cited": cited, "unverified": unverified}


class AIService:
    def __init__(self):
        settings = get_settings()
        self.api_url = settings.ai_api_url
        self.api_key = settings.ai_api_key
        self.model = settings.ai_model
        self.thinking_mode = getattr(settings, "ai_thinking_mode", "enabled")

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_sampling_params(self, override_thinking: Optional[bool] = None) -> dict:
        thinking = override_thinking if override_thinking is not None else (self.thinking_mode == "enabled")
        if thinking:
            return {"temperature": 0.6, "top_p": 0.95, "top_k": 20}
        return {"temperature": 0.7, "top_p": 0.8, "top_k": 20}

    # ── System prompt builders ────────────────────────────────────────

    @staticmethod
    def build_system_prompt(
        custom_instructions: str,
        context: str,
        kb_context: str = "",
    ) -> str:
        parts = [
            "Ты — Qwen3, русскоязычный юридический ИИ-помощник МВД РК. "
            "Ты специализируешься на составлении представлений по ст.200 "
            "Уголовно-процессуального кодекса Республики Казахстан. "
            "Отвечай точно, официально, строго по существу, опираясь "
            "исключительно на факты дела и предоставленные документы. "
            "Избегай домыслов и вымышленных фактов. "
            "Структурируй представление по образцам. "
            "Используй профессиональный юридический язык. "
            "Все ответы давай на русском языке.",
        ]

        if kb_context:
            parts.append(
                "\n\n## Примеры представлений из базы знаний (ст.200 УПК РК)\n"
                "Используй следующие фрагменты реальных представлений как "
                "образцы стиля и структуры:\n\n" + kb_context
            )

        if context:
            parts.append(
                "\n\n## Выдержки из документов дела\n"
                "Используй следующие фрагменты из загруженных материалов дела:\n\n"
                + context
            )

        if custom_instructions:
            parts.append(f"\n\n## Пользовательские инструкции\n{custom_instructions}")

        return "\n".join(parts)

    @staticmethod
    def build_generation_prompt(
        template_text: str,
        facts: str,
        kb_context: str,
        custom_instructions: str,
        additional_instructions: str,
        retrieved_laws: list[dict] | None = None,
    ) -> tuple[str, str]:
        system = (
            "Ты — Qwen3, следователь-юрист МВД РК. Составь представление "
            "по ст.200 УПК РК, строго соблюдая все 8 обязательных разделов.\n\n"
            f"{MANDATORY_SECTIONS_SPEC}\n\n"
            f"{DOCUMENT_STRUCTURE}\n\n"
            f"{FEW_SHOT_EXAMPLE}\n\n"
            f"{LAW_TO_CITATION_DEMO}\n\n"
            "ПЕРЕД НАПИСАНИЕМ ПРОВЕДИ АНАЛИТИЧЕСКИЙ РАЗБОР (chain-of-thought):\n"
            "Шаг 1: Определи ТИП ПРЕСТУПЛЕНИЯ и статью УК РК из фабулы дела.\n"
            "Шаг 2: Выяви ПРИЧИНЫ И УСЛОВИЯ — какие действия/бездействия "
            "организаций и должностных лиц создали возможность для преступления.\n"
            "Шаг 3: Для КАЖДОГО выявленного нарушения найди КОНКРЕТНУЮ НОРМУ "
            "из раздела «Нормативные акты» ниже. Подбери статью, которая "
            "устанавливает обязанность, которая была нарушена.\n"
            "Шаг 4: Построй ПРИЧИННО-СЛЕДСТВЕННУЮ ЦЕПОЧКУ: нарушение нормы → "
            "создание условий → совершение преступления.\n"
            "Шаг 5: Сформулируй КОНКРЕТНЫЕ МЕРЫ по устранению каждого "
            "выявленного нарушения с указанием правового основания.\n"
            "Шаг 6: Теперь напиши полное представление, включив результаты "
            "аналитического разбора.\n\n"
            "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
            "- Включи ВСЕ 8 разделов. Пропуск любого раздела НЕДОПУСТИМ.\n"
            "- Цитируй ТОЛЬКО статьи из раздела «Нормативные акты» ниже.\n"
            "- Для КАЖДОГО нарушения укажи конкретную статью и закон.\n"
            "- Привязывай нормы к КОНКРЕТНЫМ фактам дела, а не абстрактно.\n"
            "- Причинно-следственная связь ОБЯЗАТЕЛЬНА: используй фразы "
            "«создало условия», «в прямой причинно-следственной связи», "
            "«способствовало совершению».\n"
            "- Если факты дела явно не описывают нарушения, ВЫЯВИ их сам: "
            "проанализируй обязанности лиц и организаций по извлечённым "
            "нормативным актам и определи, какие обязанности были нарушены.\n"
            "- Каждая мера должна иметь правовое основание.\n"
            "- В предупреждении ссылайся на ст.479 и 664 КоАП РК.\n"
            "- Используй формальный юридический язык."
        )
        if custom_instructions:
            system += f"\n\nИнструкции пользователя: {custom_instructions}"

        # ── User prompt ───────────────────────────────────────────────
        user_parts = []

        user_parts.append(
            "Составь полное представление по ст.200 УПК РК. Выполни следующие шаги:\n"
            "1. Укажи дату, место составления, должность и ФИО следователя.\n"
            "2. Кратко изложи фабулу и назови статью УК РК.\n"
            "3. Подробно опиши выявленные нарушения (действия/бездействия) "
            "и для КАЖДОГО нарушения назови нарушенную норму (номер статьи и название закона).\n"
            "4. Раскрой причинно-следственную связь между каждым нарушением и преступлением.\n"
            "5. Предложи конкретные меры по устранению с указанием правовых оснований.\n"
            "6. Установи сроки исполнения в соответствии с ч.2 ст.200 УПК.\n"
            "7. Внеси предупреждение об ответственности по ст.479 и 664 КоАП РК.\n"
            "8. Структуру и заголовок не изменяй."
        )

        if retrieved_laws:
            laws_section = "\n\n## Нормативные акты (извлечены из базы законодательства)\n"
            laws_section += (
                "Ниже — нормы, применимые к данному делу. Используй ТОЛЬКО эти нормы "
                "при указании нарушенных законов и мер. Для каждого нарушения в Разделе 3 "
                "процитируй соответствующую статью из этого списка.\n\n"
            )
            for i, law in enumerate(retrieved_laws, 1):
                title = law.get("law_title", "")
                art = law.get("article_number", "")
                text = law.get("text", "")[:2000]
                header = f"{title}, Статья {art}" if art else title
                laws_section += f"{i}. {header}:\n   {text}\n\n"
            user_parts.append(laws_section)

        if template_text:
            user_parts.append(f"\n\n## Шаблон документа\n{template_text}")
        if kb_context:
            user_parts.append(
                f"\n\n## Примеры из базы знаний\n"
                f"Ориентируйся на стиль и структуру этих фрагментов:\n\n{kb_context}"
            )
        if facts:
            user_parts.append(
                f"\n\n## Факты из материалов дела\n"
                f"Фабула: {facts[:24000]}"
            )
        if additional_instructions:
            user_parts.append(f"\n\n## Дополнительные указания\n{additional_instructions}")

        user_parts.append(
            "\n\nФорматируй результат в HTML:\n"
            "- Шапку адресатов: <p style=\"text-align:right\">\n"
            "- Заголовок: <h1 style=\"text-align:center\">П Р Е Д С Т А В Л Е Н И Е</h1>\n"
            "- Подзаголовок: <h2 style=\"text-align:center\">по устранению…</h2>\n"
            "- Основной текст: <p style=\"text-align:justify\">\n"
            "- Список мер: <ol><li>\n"
            "- Шрифт: Times New Roman 14pt, межстрочный интервал 1,5."
        )

        return system, "\n".join(user_parts)

    @staticmethod
    def build_refinement_prompt(original: str, missing_sections: list[str]) -> str:
        section_names = {
            "дата_место": "дата и место вынесения, должность и ФИО следователя",
            "ердр": "номер ЕРДР",
            "статья_ук": "ссылка на статью УК РК",
            "нарушения": "описание конкретных нарушений",
            "нормативные_акты": "ссылка на ст.200 УПК РК и другие нормативные акты",
            "причинная_связь": "причинно-следственная связь между нарушениями и преступлением",
            "предлагаю": "резолютивная часть «ПРЕДЛАГАЮ» с нумерованным списком мер",
            "срок": "указание о месячном сроке уведомления (ч.2 ст.200 УПК)",
            "предупреждение": "предупреждение об ответственности по ст.479 и 664 КоАП РК",
        }
        missing_labels = [section_names.get(s, s) for s in missing_sections]
        return (
            "В документе ниже отсутствуют ОБЯЗАТЕЛЬНЫЕ элементы:\n"
            f"  — {chr(10).join('  — ' + lbl for lbl in missing_labels[1:]) if len(missing_labels) > 1 else ''}"
            f"  — {missing_labels[0]}\n\n"
            "Дополни документ ВСЕМИ перечисленными элементами. "
            "Сохрани существующий текст и структуру, добавляя недостающие части "
            "в соответствующие места.\n\n"
            f"## Исходный документ\n{original}"
        )

    # ── Streaming chat ────────────────────────────────────────────────

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        enable_thinking: Optional[bool] = None,
    ) -> AsyncGenerator[str, None]:
        params = self._get_sampling_params(enable_thinking)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": 16384,
            **params,
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream(
                "POST", self.api_url, json=payload, headers=self._get_headers()
            ) as response:
                if response.status_code != 200:
                    error_text = ""
                    async for chunk in response.aiter_text():
                        error_text += chunk
                    yield f"[Ошибка связи с ИИ: {response.status_code} — {error_text[:200]}]"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (ValueError, KeyError, IndexError):
                        continue

    # ── Document generation (non-streaming, with validation + retry) ──

    async def generate_document(
        self,
        template: str,
        facts: str,
        custom_instructions: str,
        additional_instructions: str,
        kb_context: str = "",
        retrieved_laws: list[dict] | None = None,
        enable_thinking: Optional[bool] = None,
    ) -> str:
        system_prompt, user_prompt = self.build_generation_prompt(
            template_text=template,
            facts=facts,
            kb_context=kb_context,
            custom_instructions=custom_instructions,
            additional_instructions=additional_instructions,
            retrieved_laws=retrieved_laws,
        )

        generated = await self._call_llm(system_prompt, user_prompt, enable_thinking)

        validation = validate_representation(generated)
        if not validation["ok"] and validation["missing"]:
            refinement_prompt = self.build_refinement_prompt(
                generated, validation["missing"]
            )
            generated = await self._call_llm(
                system_prompt, refinement_prompt, enable_thinking
            )

        return generated

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        enable_thinking: Optional[bool] = None,
    ) -> str:
        params = self._get_sampling_params(enable_thinking)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "max_tokens": 8192,
            **params,
        }

        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                self.api_url, json=payload, headers=self._get_headers()
            )
            if response.status_code != 200:
                raise Exception(
                    f"Ошибка API ИИ: {response.status_code} — {response.text[:200]}"
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            content = re.sub(
                r"<think>.*?</think>", "", content, flags=re.DOTALL
            ).strip()

            return content
