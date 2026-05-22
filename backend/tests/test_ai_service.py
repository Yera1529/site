"""Tests for AIService — prompt building, validation, and document structure.

Tests cover:
  - System prompt assembly
  - Generation prompt with retrieved laws
  - Representation validation (mandatory sections)
  - Law citation validation
  - Refinement prompt building
  - Legal context structure (violation/remedy separation)
"""

import pytest
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.ai import (
    AIService,
    validate_representation,
    validate_law_citations,
    MANDATORY_SECTIONS,
    MANDATORY_SECTIONS_SPEC,
    REPRESENTATION_RULES,
)


class TestValidateRepresentation:
    """validate_representation: checks 9 mandatory markers."""

    def test_complete_document_passes(self):
        doc = """
        15.01.2025 г.

        Следственным отделом расследуется дело ЕРДР № 123456 по ст.188 Уголовного кодекса.
        
        Выявлены нарушения: ненадлежащее исполнение обязанностей.
        
        Данные нарушения являются нарушением ст.200 Уголовно-процессуального кодекса.
        
        Указанные нарушения создали условия, способствовавшие совершению преступления.
        
        ПРЕДЛАГАЮ:
        1. Принять меры.
        2. О принятых мерах сообщить в месячный срок (ч.2 ст.200 УПК).
        
        Ответственность по ст.479 и 664 КоАП РК.
        """
        result = validate_representation(doc)
        assert result["ok"] is True
        assert len(result["missing"]) == 0
        assert len(result["present"]) == len(MANDATORY_SECTIONS)

    def test_empty_document_fails(self):
        result = validate_representation("")
        assert result["ok"] is False
        assert len(result["missing"]) == len(MANDATORY_SECTIONS)

    def test_missing_erd(self):
        doc = "15.01.2025 г. ст.188 УК нарушения бездействие ст.200 УПК причинной связь ПРЕДЛАГАЮ месячный срок 479 КоАП"
        result = validate_representation(doc)
        assert "ердр" in result["missing"]

    def test_missing_date(self):
        doc = "ЕРДР ст.188 УК нарушения бездействие ст.200 УПК причинной связь ПРЕДЛАГАЮ месячный срок 479 КоАП"
        result = validate_representation(doc)
        assert "дата_место" in result["missing"]

    def test_missing_propose(self):
        doc = "15.01.2025 г. ЕРДР ст.188 УК нарушения бездействие ст.200 УПК причин связь месячный срок 479 КоАП"
        result = validate_representation(doc)
        assert "предлагаю" in result["missing"]

    def test_partial_document(self):
        doc = "15.01.2025 г. ЕРДР ст.188 Уголовного кодекса"
        result = validate_representation(doc)
        assert result["ok"] is False
        assert "предлагаю" in result["missing"]
        assert "предупреждение" in result["missing"]


class TestValidateLawCitations:
    """validate_law_citations: cross-check cited articles with retrieved laws."""

    def test_all_citations_verified(self):
        text = "Нарушение ст. 22 Трудового кодекса и ст. 200 УПК."
        laws = [{"article_number": "22"}]
        result = validate_law_citations(text, laws)
        assert "22" in result["cited"]
        assert "200" in result["cited"]
        assert len(result["unverified"]) == 0  # 200 is always valid

    def test_unverified_citation_detected(self):
        text = "Нарушение ст. 99 Закона. Также ст.200 УПК."
        laws = [{"article_number": "22"}]
        result = validate_law_citations(text, laws)
        assert "99" in result["unverified"]

    def test_always_valid_articles(self):
        text = "ст.200 УПК, ст.159 УК, ст.479 КоАП, ст.664 КоАП"
        result = validate_law_citations(text, [])
        assert len(result["unverified"]) == 0

    def test_no_citations(self):
        result = validate_law_citations("Нет ссылок на статьи.", [])
        assert len(result["cited"]) == 0
        assert len(result["unverified"]) == 0

    def test_multiple_formats_detected(self):
        text = "ст. 22 закона, статья 23 кодекса, Ст.24 правил"
        laws = [{"article_number": "22"}, {"article_number": "23"}, {"article_number": "24"}]
        result = validate_law_citations(text, laws)
        assert set(result["cited"]) >= {"22", "23", "24"}

    def test_duplicate_citations_deduplicated(self):
        text = "ст.22 первый раз, ст.22 второй раз, ст.22 третий раз"
        result = validate_law_citations(text, [{"article_number": "22"}])
        assert result["cited"].count("22") == 1


class TestBuildSystemPrompt:
    """AIService.build_system_prompt: builds chat system prompt."""

    def test_includes_base_instructions(self):
        prompt = AIService.build_system_prompt("", "")
        assert "юридический" in prompt.lower()
        assert "ст.200" in prompt
        assert "русском языке" in prompt

    def test_includes_custom_instructions(self):
        prompt = AIService.build_system_prompt("Мои инструкции", "")
        assert "Мои инструкции" in prompt

    def test_includes_context(self):
        prompt = AIService.build_system_prompt("", "Контекст дела")
        assert "Контекст дела" in prompt

    def test_includes_kb_context(self):
        prompt = AIService.build_system_prompt("", "", kb_context="База знаний")
        assert "База знаний" in prompt


class TestBuildGenerationPrompt:
    """AIService.build_generation_prompt: builds full generation prompts."""

    def test_returns_tuple(self):
        system, user = AIService.build_generation_prompt(
            facts="Факты дела",
            kb_context="",
            custom_instructions="",
            additional_instructions="",
        )
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_system_prompt_structure(self):
        system, _ = AIService.build_generation_prompt(
            facts="", kb_context="", custom_instructions="", additional_instructions=""
        )
        assert "ПРЕДСТАВЛЕНИЕ" in system or "представлени" in system.lower()
        assert "ПРЕДЛАГАЮ" in system or "РАЗДЕЛ" in system
        assert "ст.200" in system
        assert "479" in system
        assert "664" in system

    def test_facts_in_user_prompt(self):
        _, user = AIService.build_generation_prompt(
            facts="На заводе произошла авария",
            kb_context="",
            custom_instructions="",
            additional_instructions="",
        )
        assert "На заводе произошла авария" in user

    def test_retrieved_laws_in_user_prompt(self):
        laws = [
            {
                "law_title": "Трудовой кодекс РК",
                "article_number": "22",
                "text": "Работодатель обязан обеспечить безопасность.",
                "norm_purpose": "violation",
                "violation_criteria": "Нарушение охраны труда",
                "applicable_measures": "",
            }
        ]
        _, user = AIService.build_generation_prompt(
            facts="Факты",
            kb_context="",
            custom_instructions="",
            additional_instructions="",
            retrieved_laws=laws,
        )
        assert "Трудовой кодекс" in user
        assert "22" in user
        assert "legal_context" in user

    def test_violation_remedy_separation(self):
        laws = [
            {
                "law_title": "ТК РК",
                "article_number": "22",
                "text": "Обязанность",
                "norm_purpose": "violation",
                "violation_criteria": "Критерий",
                "applicable_measures": "",
            },
            {
                "law_title": "Закон о дорогах",
                "article_number": "35",
                "text": "Содержание дорог",
                "norm_purpose": "remedy",
                "violation_criteria": "",
                "applicable_measures": "Ремонт дорог",
            },
        ]
        _, user = AIService.build_generation_prompt(
            facts="Факты", kb_context="", custom_instructions="",
            additional_instructions="", retrieved_laws=laws,
        )
        assert "НАРУШЕННЫЕ НОРМЫ" in user
        assert 'purpose="violation"' in user
        assert "НОРМЫ-ОСНОВАНИЯ" in user
        assert 'purpose="remedy"' in user

    def test_additional_instructions_included(self):
        _, user = AIService.build_generation_prompt(
            facts="", kb_context="", custom_instructions="",
            additional_instructions="Обратить внимание на охрану труда",
        )
        assert "Обратить внимание на охрану труда" in user

    def test_kb_context_with_warning(self):
        _, user = AIService.build_generation_prompt(
            facts="", kb_context="Пример представления",
            custom_instructions="", additional_instructions="",
        )
        assert "Пример представления" in user
        assert "НЕ используй имена" in user  # Warning not to copy examples

    def test_html_formatting_instructions(self):
        _, user = AIService.build_generation_prompt(
            facts="", kb_context="", custom_instructions="",
            additional_instructions="",
        )
        assert "HTML" in user
        assert "float:left" in user or "text-align" in user


class TestRefinementPrompt:
    """build_refinement_prompt: adds missing sections."""

    def test_lists_missing_sections(self):
        prompt = AIService.build_refinement_prompt(
            "Исходный документ",
            ["предлагаю", "срок", "предупреждение"]
        )
        assert "ПРЕДЛАГАЮ" in prompt or "предлагаю" in prompt.lower()
        assert "срок" in prompt.lower()
        assert "479" in prompt or "ответственност" in prompt.lower()

    def test_includes_original_document(self):
        prompt = AIService.build_refinement_prompt(
            "Мой исходный документ",
            ["предлагаю"]
        )
        assert "Мой исходный документ" in prompt


class TestMandatorySections:
    """MANDATORY_SECTIONS: regex patterns compile correctly."""

    def test_all_patterns_compile(self):
        for label, pattern in MANDATORY_SECTIONS:
            compiled = re.compile(pattern, re.IGNORECASE)
            assert compiled is not None, f"Pattern for '{label}' failed to compile"

    def test_date_pattern_matches(self):
        _, pattern = MANDATORY_SECTIONS[0]
        assert re.search(pattern, "15.01.2025 г.", re.IGNORECASE)

    def test_erd_pattern_matches(self):
        _, pattern = MANDATORY_SECTIONS[1]
        assert re.search(pattern, "зарегистрировано в ЕРДР", re.IGNORECASE)

    def test_article_uk_pattern_matches(self):
        _, pattern = MANDATORY_SECTIONS[2]
        assert re.search(pattern, "ст. 188 Уголовного кодекса", re.IGNORECASE)

    def test_propose_pattern_matches(self):
        _, pattern = MANDATORY_SECTIONS[6]
        assert re.search(pattern, "ПРЕДЛАГАЮ:", re.IGNORECASE)
