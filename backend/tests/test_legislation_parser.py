"""Tests for LegislationParser — hierarchical legislation parsing.

Tests cover:
  - Article detection and numbering
  - Point extraction within articles
  - Title cleaning heuristics
  - Edge cases: empty text, single article, no articles
  - Normalization of whitespace and line endings
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.rag import LegislationParser


class TestLegislationParserBasic:
    """Basic article parsing functionality."""

    def test_parse_multiple_articles(self, sample_law_text):
        articles = LegislationParser.parse(sample_law_text, "Трудовой кодекс РК")
        assert len(articles) == 3
        assert articles[0]["number"] == "22"
        assert articles[1]["number"] == "23"
        assert articles[2]["number"] == "182"

    def test_article_titles_extracted(self, sample_law_text):
        articles = LegislationParser.parse(sample_law_text, "Трудовой кодекс РК")
        assert "обязанности работодателя" in articles[0]["title"].lower()
        assert "права работодателя" in articles[1]["title"].lower()
        assert "ответственность работодателя" in articles[2]["title"].lower()

    def test_law_title_preserved_in_articles(self, sample_law_text):
        articles = LegislationParser.parse(sample_law_text, "Трудовой кодекс РК")
        for art in articles:
            assert art["law_title"] == "Трудовой кодекс РК"

    def test_full_text_includes_article_header(self, sample_law_text):
        articles = LegislationParser.parse(sample_law_text, "Трудовой кодекс РК")
        for art in articles:
            assert art["full_text"].startswith(f"Статья {art['number']}.")

    def test_empty_text_returns_empty(self):
        articles = LegislationParser.parse("", "Закон")
        assert articles == []

    def test_no_articles_returns_empty(self):
        text = "Это просто текст без статей. Нет структуры."
        articles = LegislationParser.parse(text, "Закон")
        assert articles == []


class TestLegislationParserPoints:
    """Point extraction within articles."""

    def test_points_extracted_from_article(self, sample_law_text):
        articles = LegislationParser.parse(sample_law_text, "ТК РК")
        art22 = articles[0]
        # Article 22 has 3 numbered points
        numbered_points = [p for p in art22["points"] if p["number"]]
        assert len(numbered_points) >= 3

    def test_point_text_contains_content(self, sample_law_text):
        articles = LegislationParser.parse(sample_law_text, "ТК РК")
        art22 = articles[0]
        point_texts = " ".join(p["text"] for p in art22["points"])
        assert "безопасные условия труда" in point_texts
        assert "средства индивидуальной защиты" in point_texts.lower() or "оборудованием" in point_texts

    def test_single_body_article_has_one_point(self):
        text = "Статья 1. Общие положения\nНастоящий закон регулирует отношения в сфере безопасности."
        articles = LegislationParser.parse(text, "Закон")
        assert len(articles) == 1
        assert len(articles[0]["points"]) == 1


class TestLegislationParserNormalization:
    """Text normalization edge cases."""

    def test_windows_line_endings(self):
        text = "Статья 1. Заголовок\r\n1. Пункт первый.\r\n2. Пункт второй.\r\n"
        articles = LegislationParser.parse(text, "Закон")
        assert len(articles) == 1

    def test_multiple_blank_lines_collapsed(self):
        text = "Статья 1. Заголовок\n\n\n\n\n1. Пункт первый.\n\n\n\n2. Пункт второй."
        articles = LegislationParser.parse(text, "Закон")
        assert len(articles) == 1
        assert len([p for p in articles[0]["points"] if p["number"]]) >= 2

    def test_extra_spaces_handled(self):
        text = "Статья    1.    Заголовок   с   пробелами\n1.  Пункт   первый."
        articles = LegislationParser.parse(text, "Закон")
        assert len(articles) == 1

    def test_article_with_dash_number(self):
        text = "Статья 22-1. Дополнительные обязанности\n1. Работодатель обязан..."
        articles = LegislationParser.parse(text, "ТК РК")
        assert len(articles) == 1
        assert articles[0]["number"] == "22-1"

    def test_article_with_decimal_number(self):
        text = "Статья 22.1. Подстатья\nТекст подстатьи."
        articles = LegislationParser.parse(text, "ТК РК")
        assert len(articles) == 1
        assert articles[0]["number"] == "22.1"


class TestLegislationParserTitleCleaning:
    """Title cleaning heuristics."""

    def test_title_capitalized(self):
        text = "Статья 1. общие положения\nТекст статьи."
        articles = LegislationParser.parse(text, "Закон")
        assert articles[0]["title"][0].isupper()

    def test_title_truncated_to_300_chars(self):
        long_title = "А" * 500
        text = f"Статья 1. {long_title}\nТекст."
        articles = LegislationParser.parse(text, "Закон")
        assert len(articles[0]["title"]) <= 300

    def test_title_trailing_punctuation_stripped(self):
        text = "Статья 1. Заголовок с точкой.,;:\n1. Пункт."
        articles = LegislationParser.parse(text, "Закон")
        title = articles[0]["title"]
        assert not title.endswith(".")
        assert not title.endswith(",")
        assert not title.endswith(";")
        assert not title.endswith(":")
