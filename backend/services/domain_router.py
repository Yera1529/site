"""L1 Domain Router (Фаза 3 playbook'а, раздел 6).

Классифицирует дело в один из 12 доменов и задаёт пул источников норм для
доменно-ограниченного retrieval (L2). Цель — убрать кросс-доменные «магниты»
(напр. Трудовой кодекс на делах охраны), чтобы профильные нормы не тонули.

Публичный контракт:
    async def classify_domain(fabula, violations, addressee, ai) -> tuple[str, float]
    def domain_source_patterns(domain) -> list[str]
    def match_domain(law_name, domain) -> bool

Реранк/Vertex для match_domain/domain_source_patterns не нужны — это чистые
функции. classify_domain делает один JSON-вызов Gemini через переданный AIService.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Домен → regex-паттерны по law_name = пул источников норм этого домена.
# Значения выверены по фактическим источникам базы (см. backend/scripts/audit_laws.py).
# Пустой список (у «общий») = без ограничения, поиск по всей базе.
DOMAIN_SOURCES: dict[str, list[str]] = {
    "алкоголь": [r"административных правонарушениях", r"регулировании торговой деятельности",
                 r"профилактике правонарушений", r"безопасности пищевой продукции"],
    "охрана": [r"охранной деятельности", r"оборотом отдельных видов оружия",
               r"профилактике правонарушений"],
    "ДТП": [r"дорожном движении", r"автомобильном транспорте", r"\bо транспорте\b",
            r"автомобильных дорогах"],
    "охрана_труда": [r"трудовой кодекс", r"гражданской защите",
                     r"страховании работника от несчастных", r"профилактике правонарушений"],
    "антитеррор": [r"противодействии терроризму", r"охранной деятельности",
                   r"оборотом отдельных видов оружия", r"гражданской защите"],
    "оборот_оружия": [r"оборотом отдельных видов оружия", r"охранной деятельности"],
    "профилактика": [r"профилактике правонарушений", r"правах ребенка",
                     r"органах внутренних дел"],
    "несовершеннолетние": [r"правах ребенка", r"об образовании", r"защите детей от информации",
                           r"браке \(супружестве\) и семье", r"статусе педагога",
                           r"профилактике правонарушений"],
    "наркотики": [r"наркотических средствах", r"здоровье народа",
                  r"профилактике правонарушений"],
    "пожарная": [r"гражданской защите", r"трудовой кодекс", r"профилактике правонарушений"],
    "антикоррупция": [r"противодействии коррупции", r"государственной службе",
                      r"государственном аудите"],
    "общий": [],
}

DOMAIN_DESCRIPTIONS: dict[str, str] = {
    "алкоголь": "продажа/оборот алкоголя (в неустановленное время, несовершеннолетним)",
    "охрана": "охранная деятельность, ЧОП, пропускной режим, досмотр на объектах",
    "ДТП": "дорожно-транспортные происшествия, эксплуатация и перевозки транспорта, такси",
    "охрана_труда": "охрана труда, производственные травмы, безопасность на рабочем месте",
    "антитеррор": "антитеррористическая защищённость объектов",
    "оборот_оружия": "оборот, хранение и ношение оружия",
    "профилактика": "профилактика правонарушений, бытовое насилие, бездействие по учёту",
    "несовершеннолетние": "несовершеннолетние: безнадзорность, школа, права ребёнка, травля",
    "наркотики": "оборот наркотиков и лекарств, отпуск рецептурных препаратов, передозировка",
    "пожарная": "пожарная безопасность, гражданская защита",
    "антикоррупция": "коррупция, госслужба, конфликт интересов",
    "общий": "общий случай, если не подходит ни один специфический домен",
}

VALID_DOMAINS: set[str] = set(DOMAIN_SOURCES)

_compiled: dict[str, list[re.Pattern]] = {}


def domain_source_patterns(domain: str) -> list[str]:
    """regex-паттерны источников для домена ([] = без ограничения)."""
    return DOMAIN_SOURCES.get(domain, [])


def match_domain(law_name: str, domain: str) -> bool:
    """Принадлежит ли норма пулу домена. Пустой пул («общий»/неизвестный) → True."""
    pats = DOMAIN_SOURCES.get(domain, [])
    if not pats:
        return True
    if domain not in _compiled:
        _compiled[domain] = [re.compile(p, re.I) for p in pats]
    ln = law_name or ""
    return any(rx.search(ln) for rx in _compiled[domain])


# ── классификатор (L1) ──
_cache: dict[str, tuple[str, float]] = {}
_ROUTER_LOG = Path("storage") / "router_log.jsonl"


def _key(fabula: str, violations: str, addressee: str) -> str:
    return hashlib.md5(f"{fabula}|{violations}|{addressee}".encode("utf-8")).hexdigest()


def _log(entry: dict) -> None:
    try:
        _ROUTER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ROUTER_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — лог не должен ронять пайплайн
        pass


async def classify_domain(
    fabula: str, violations: str, addressee: str, ai
) -> tuple[str, float]:
    """Классифицирует дело в один из доменов через Gemini (JSON-вывод).

    Возвращает (domain, confidence). При confidence < 0.5 или ошибке —
    ("общий", confidence). Результат кэшируется в памяти на ключ (fabula+violations+addressee).
    """
    k = _key(fabula, violations, addressee)
    if k in _cache:
        return _cache[k]

    domains_block = "\n".join(f"- {d}: {DOMAIN_DESCRIPTIONS[d]}" for d in DOMAIN_SOURCES)
    prompt = (
        "Ты классифицируешь уголовное дело для подбора норм к представлению по ст.200 УПК РК.\n"
        "Определи ОДИН домен из списка — сферу обязанностей АДРЕСАТА представления, "
        "нарушение которых способствовало преступлению.\n\n"
        f"ДОМЕНЫ:\n{domains_block}\n\n"
        f"ФАБУЛА: {fabula[:2000]}\n"
        f"НАРУШЕНИЯ: {violations[:1000]}\n"
        f"АДРЕСАТ: {addressee[:300]}\n\n"
        'Верни СТРОГО JSON: {"domain": "<один домен из списка>", '
        '"confidence": <число 0..1>, "rationale": "<кратко>"}'
    )

    domain, conf, rationale, err = "общий", 0.0, "", None
    try:
        from google.genai import types as genai_types

        # Gemini 2.5 Flash — «думающая» модель: thinking съедает max_output_tokens
        # и обрезает JSON. Классификации thinking не нужен — отключаем (budget=0),
        # плюс держим запас токенов на случай старого SDK без ThinkingConfig.
        cfg_args = dict(
            temperature=0.0, top_p=0.9, max_output_tokens=2048,
            response_mime_type="application/json",
        )
        if hasattr(genai_types, "ThinkingConfig"):
            cfg_args["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=0)
        config = genai_types.GenerateContentConfig(**cfg_args)
        resp = await asyncio.to_thread(
            ai._client.models.generate_content,
            model=ai.model_name, contents=prompt, config=config,
        )
        raw = (resp.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*\n", "", raw, flags=re.M)
        raw = re.sub(r"\n```\s*$", "", raw, flags=re.M).strip()
        data = json.loads(raw)
        d = str(data.get("domain", "")).strip()
        conf = float(data.get("confidence", 0.0))
        rationale = str(data.get("rationale", ""))[:200]
        if d in VALID_DOMAINS:
            domain = d
    except Exception as e:  # noqa: BLE001 — любая ошибка → дефолт «общий», но видимо
        err = str(e)[:200]
        logger.warning("classify_domain failed: %s", e)

    # Низкая уверенность → безопасный дефолт «общий» (без ограничения пула).
    result = (domain, conf) if (conf >= 0.5 and domain in VALID_DOMAINS) else ("общий", conf)
    _log({"ts": time.time(), "domain": result[0], "raw_domain": domain,
          "confidence": conf, "rationale": rationale, "error": err})
    _cache[k] = result
    return result


def reset_cache() -> None:
    """Сброс кэша (для тестов/переизмерений)."""
    _cache.clear()
