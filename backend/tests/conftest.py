"""Shared fixtures for the RAG test suite.

Provides lightweight, isolated test fixtures that do NOT require
the full Docker stack, Gemini API, or a database connection.
All heavy models (SentenceTransformer, CrossEncoder, FAISS) are
mocked or replaced with lightweight alternatives.
"""

import os
import sys
import tempfile
import shutil
import pytest
import numpy as np

# Ensure the backend root is on sys.path so `from services.rag import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override settings before any import touches config
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("AI_API_KEY", "test-key")
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp())


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def storage_dir():
    """Create a temp storage directory for the entire test session."""
    d = tempfile.mkdtemp(prefix="rag_test_")
    os.makedirs(os.path.join(d, "chroma_db"), exist_ok=True)
    os.makedirs(os.path.join(d, "faiss_laws"), exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def temp_dir():
    """Create a per-test temp directory."""
    d = tempfile.mkdtemp(prefix="rag_unit_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ── Sample legal texts ──────────────────────────────────────────────────────

SAMPLE_LAW_TEXT = """
Статья 22. Основные обязанности работодателя

1. Работодатель обязан обеспечивать безопасные условия труда на каждом рабочем месте.
2. Работодатель обязан обеспечивать работников оборудованием, инструментами и средствами индивидуальной защиты.
3. Работодатель обязан предоставлять работникам информацию о состоянии условий труда.

Статья 23. Права работодателя

1. Работодатель имеет право заключать, изменять и расторгать трудовые договоры.
2. Работодатель имеет право требовать от работников выполнения трудовых обязанностей.

Статья 182. Ответственность работодателя

1. За нарушение требований безопасности и охраны труда работодатель несёт ответственность.
2. Работодатель возмещает вред, причинённый здоровью работника.
"""

SAMPLE_CASE_DESCRIPTION = """
На производственном объекте ТОО «Стройсервис» произошёл несчастный случай: 
15.01.2025 года рабочий Петров И.И. получил тяжёлую травму в результате 
падения с высоты 5 метров при выполнении строительных работ. Установлено, 
что работодатель не обеспечил работника средствами индивидуальной защиты (каска, 
страховочный пояс), в нарушение требований ст.22 Трудового кодекса РК.
Кроме того, на строительной площадке отсутствовали ограждения.
"""

SAMPLE_KB_DOCUMENT = """
# Представление по ст.200 УПК РК — хищение из магазина

Следственным отделом УП района Алматы расследуется уголовное дело,
зарегистрированное в ЕРДР за № 221234567890123, возбужденное по признакам
уголовного правонарушения, предусмотренного ч.2 ст.188 УК РК.

В ходе расследования установлено, что совершению данного правонарушения
способствовали обстоятельства: руководство ТОО «МаркетПлюс» не обеспечило
надлежащую охрану торговых помещений, система видеонаблюдения находилась
в нерабочем состоянии, что является нарушением ст.10 Закона РК «О частной
охранной деятельности».

На основании изложенного, руководствуясь ст.200 УПК РК, ПРЕДЛАГАЮ:

1. Обеспечить установку исправной системы видеонаблюдения.
2. О принятых мерах сообщить в месячный срок.

Предупреждение: невыполнение влечёт ответственность по ст.479 и 664 КоАП РК.
"""

SAMPLE_ENRICHED_JSONL_RECORDS = [
    {
        "law_name": "Трудовой кодекс Республики Казахстан",
        "article_number": "Статья 22",
        "original_text": "Работодатель обязан обеспечивать безопасные условия труда.",
        "norm_type": "Обязывающая",
        "norm_purpose": "violation",
        "violation_criteria": "Необеспечение работников средствами индивидуальной защиты, отсутствие инструктажа по охране труда.",
        "applicable_measures": "Привлечение к дисциплинарной ответственности, штраф по ст.93 КоАП РК.",
        "subject_competence": {"organ": "Работодатель", "competence": "Обеспечение охраны труда"},
    },
    {
        "law_name": "Закон РК «О частной охранной деятельности»",
        "article_number": "Статья 10",
        "original_text": "Субъект охранной деятельности обязан обеспечивать пропускной режим на охраняемых объектах.",
        "norm_type": "Обязывающая",
        "norm_purpose": "violation",
        "violation_criteria": "Отсутствие пропускного режима, неисправность систем видеонаблюдения.",
        "applicable_measures": "Представление об устранении нарушений, административное взыскание.",
        "subject_competence": {"organ": "Охранная организация", "competence": "Обеспечение охраны объектов"},
    },
    {
        "law_name": "Закон РК «О пожарной безопасности»",
        "article_number": "Статья 15",
        "original_text": "Руководители организаций обязаны обеспечивать соблюдение требований пожарной безопасности.",
        "norm_type": "Обязывающая",
        "norm_purpose": "both",
        "violation_criteria": "Отсутствие средств пожаротушения, неисправность систем пожарной сигнализации.",
        "applicable_measures": "Приостановление деятельности, административное взыскание.",
        "subject_competence": {"organ": "Руководитель организации", "competence": "Обеспечение пожарной безопасности"},
    },
    {
        "law_name": "Закон РК «О дорожном движении»",
        "article_number": "Статья 35",
        "original_text": "Местные исполнительные органы обязаны обеспечивать содержание автомобильных дорог.",
        "norm_type": "Компетенционная",
        "norm_purpose": "remedy",
        "violation_criteria": "Ненадлежащее содержание дорог, отсутствие освещения, неисправность дорожных знаков.",
        "applicable_measures": "Представление акиму о ремонте дорог, установке освещения.",
        "subject_competence": {"organ": "Аким района/города", "competence": "Содержание автомобильных дорог"},
    },
    {
        "law_name": "Трудовой кодекс Республики Казахстан",
        "article_number": "Статья 182",
        "original_text": "За нарушение требований безопасности и охраны труда работодатель несёт ответственность.",
        "norm_type": "Запрещающая",
        "norm_purpose": "violation",
        "violation_criteria": "Нарушение требований охраны труда, повлёкшее причинение вреда здоровью.",
        "applicable_measures": "Возмещение вреда, привлечение к ответственности.",
        "subject_competence": {"organ": "Работодатель", "competence": "Соблюдение требований охраны труда"},
    },
]


@pytest.fixture
def sample_law_text():
    return SAMPLE_LAW_TEXT


@pytest.fixture
def sample_case_description():
    return SAMPLE_CASE_DESCRIPTION


@pytest.fixture
def sample_kb_document():
    return SAMPLE_KB_DOCUMENT


@pytest.fixture
def sample_enriched_records():
    return SAMPLE_ENRICHED_JSONL_RECORDS
