"""Юнит-тесты L1 Domain Router (Фаза 3). Gemini не вызывается — мокаем клиент."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ в sys.path

from services import domain_router  # noqa: E402
from services.domain_router import (  # noqa: E402
    classify_domain,
    domain_source_patterns,
    match_domain,
    DOMAIN_SOURCES,
    DOMAIN_DESCRIPTIONS,
    VALID_DOMAINS,
)


# ── чистая логика пулов (без Gemini) ──

def test_match_domain_keeps_profile_sources():
    assert match_domain("Закон Об охранной деятельности", "охрана")
    assert match_domain("Закон О наркотических средствах, психотропных веществах", "наркотики")
    assert match_domain("Закон О дорожном движении", "ДТП")


def test_match_domain_excludes_cross_domain_magnet():
    # Трудовой кодекс исключён из пулов, где он чистый шум…
    assert not match_domain("Трудовой кодекс", "охрана")
    assert not match_domain("Трудовой кодекс", "наркотики")
    # …но допущен туда, где обязанности работодателя релевантны (травма на
    # производстве, пожар на объекте с работниками, коммерческий водитель);
    # «магнит» теперь держит диверсификация реранка (≤2 статьи на закон).
    assert match_domain("Трудовой кодекс", "охрана_труда")
    assert match_domain("Трудовой кодекс", "пожарная")
    # «О гражданской защите» — профильный для пожарной.
    assert match_domain("Закон О гражданской защите", "пожарная")


def test_obshiy_no_restriction():
    assert domain_source_patterns("общий") == []
    assert match_domain("Любой Закон Республики Казахстан", "общий")
    assert match_domain("Налоговый кодекс", "общий")


def test_unknown_domain_no_restriction():
    assert match_domain("Что угодно", "несуществующий_домен")


def test_descriptions_cover_all_domains():
    assert set(DOMAIN_DESCRIPTIONS) == set(DOMAIN_SOURCES) == VALID_DOMAINS


# ── классификатор с моком Gemini ──

class _FakeResp:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, text: str):
        self._text = text

    def generate_content(self, **kwargs):
        return _FakeResp(self._text)


class _FakeClient:
    def __init__(self, text: str):
        self.models = _FakeModels(text)


class _FakeAI:
    def __init__(self, text: str):
        self._client = _FakeClient(text)
        self.model_name = "fake-model"


def test_classify_valid_domain():
    domain_router.reset_cache()
    ai = _FakeAI(json.dumps({"domain": "наркотики", "confidence": 0.9, "rationale": "r"}))
    d, c = asyncio.run(classify_domain("передоз в аптеке", "отпуск без рецепта", "аптека", ai))
    assert d == "наркотики"
    assert c == 0.9


def test_classify_low_confidence_falls_to_obshiy():
    domain_router.reset_cache()
    ai = _FakeAI(json.dumps({"domain": "наркотики", "confidence": 0.3, "rationale": "r"}))
    d, c = asyncio.run(classify_domain("a", "b", "c", ai))
    assert d == "общий"  # confidence<0.5 → общий
    assert c == 0.3


def test_classify_invalid_domain_falls_to_obshiy():
    domain_router.reset_cache()
    ai = _FakeAI(json.dumps({"domain": "марсианское_право", "confidence": 0.99, "rationale": "r"}))
    d, c = asyncio.run(classify_domain("a", "b", "c", ai))
    assert d == "общий"


def test_classify_broken_json_falls_to_obshiy():
    domain_router.reset_cache()
    ai = _FakeAI("это не JSON")
    d, c = asyncio.run(classify_domain("a", "b", "c", ai))
    assert d == "общий"
    assert c == 0.0
