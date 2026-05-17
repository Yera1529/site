"""Enrichment pipeline for Kazakhstan legal norms (JSONL format).

Automates:
  1. Loading law text from DOCX/TXT
  2. Splitting into individual articles
  3. Enriching each article via Gemini with structured fields:
     - violation_criteria
     - applicable_measures
     - norm_type
     - norm_purpose
     - subject_competence
  4. Outputting enriched JSONL ready for FAISS indexing

Usage:
  python enrich_laws.py \
    --input "Закон_О_жилищных_отношениях.docx" \
    --law-name "Закон РК «О жилищных отношениях»" \
    --output enriched_housing.jsonl \
    --api-key YOUR_API_KEY

The output can be appended to unified_laws_200upk.jsonl and the FAISS
index rebuilt via the /api/rag-laws/rebuild endpoint.
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Article extraction ──────────────────────────────────────────────────

def extract_text_from_file(filepath: str) -> str:
    """Extract plain text from DOCX or TXT file."""
    path = Path(filepath)
    if path.suffix.lower() in (".docx",):
        try:
            from docx import Document
            doc = Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            logger.error("python-docx not installed. Run: pip install python-docx")
            sys.exit(1)
    elif path.suffix.lower() in (".txt", ".text"):
        return path.read_text(encoding="utf-8")
    else:
        logger.error("Unsupported file format: %s. Use DOCX or TXT.", path.suffix)
        sys.exit(1)


def split_into_articles(text: str) -> list[dict]:
    """Split law text into individual articles.

    Recognizes patterns:
      - Статья 1. Title
      - Статья 1-1. Title
      - Статья 1. (numbering with period)
    """
    # Pattern: "Статья N." or "Статья N-N." at the start of a line
    pattern = r'^(Статья\s+(\d+(?:-\d+)?)\.\s*(.*))'
    matches = list(re.finditer(pattern, text, re.MULTILINE))

    if not matches:
        logger.warning("No articles found. Trying alternative patterns...")
        # Try "Баб" (chapter) based splitting or numbered lines
        pattern = r'^(\d+(?:-\d+)?)\.\s+'
        matches = list(re.finditer(pattern, text, re.MULTILINE))

    articles = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        article_text = text[start:end].strip()

        # Extract article number
        num_match = re.search(r'(\d+(?:-\d+)?)', match.group(0))
        article_number = f"Статья {num_match.group(1)}" if num_match else f"Пункт {i + 1}"

        # Extract title (first line after "Статья N.")
        title_match = re.match(r'Статья\s+\d+(?:-\d+)?\.\s*(.*?)(?:\n|$)', article_text)
        title = title_match.group(1).strip() if title_match else ""

        articles.append({
            "article_number": article_number,
            "title": title,
            "text": article_text,
        })

    logger.info("Extracted %d articles from text (%d chars)", len(articles), len(text))
    return articles


# ── Gemini enrichment ───────────────────────────────────────────────────

def enrich_article_batch(
    articles: list[dict],
    law_name: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
    batch_size: int = 5,
    delay: float = 2.0,
) -> list[dict]:
    """Enrich articles with structured legal metadata using Gemini."""
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=api_key)
    enriched = []

    for batch_start in range(0, len(articles), batch_size):
        batch = articles[batch_start:batch_start + batch_size]
        logger.info(
            "Enriching batch %d-%d of %d...",
            batch_start + 1, min(batch_start + batch_size, len(articles)), len(articles),
        )

        for art in batch:
            prompt = f"""Проанализируй статью закона Республики Казахстан и заполни структурированные поля.

Закон: {law_name}
{art['article_number']}. {art['title']}

Текст статьи:
{art['text'][:3000]}

Ответь СТРОГО в формате JSON:
{{
  "violation_criteria": "Что является нарушением этой нормы? Кратко опиши конкретные действия/бездействия, которые нарушают эту статью. Если статья не устанавливает обязанностей — напиши 'Не применимо'.",
  "applicable_measures": "Какие меры можно предложить в представлении по ст.200 УПК для устранения нарушений? Конкретные действия. Если не применимо — 'Не применимо'.",
  "norm_type": "Один из: Обязывающая | Запрещающая | Управомочивающая | Компетенционная | Декларативная",
  "norm_purpose": "Один из: violation | remedy | both | info",
  "subject_competence": {{
    "organ": "Какой орган/организация обязан исполнять эту норму",
    "competence": "Краткое описание компетенции"
  }}
}}

Правила:
- violation = норма устанавливает обязанность, нарушение которой можно зафиксировать
- remedy = норма даёт основание для мер по устранению
- both = и то и другое
- info = информационная/декларативная норма
- Ответ — ТОЛЬКО JSON, без комментариев"""

            try:
                config = genai_types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                )
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                raw = response.text.strip()
                # Strip markdown code blocks
                raw = re.sub(r'^```(?:json)?\s*\n', '', raw, flags=re.MULTILINE)
                raw = re.sub(r'\n```\s*$', '', raw, flags=re.MULTILINE)
                raw = raw.strip()

                data = json.loads(raw)

                enriched_record = {
                    "law_name": law_name,
                    "article_number": art["article_number"],
                    "article_title": art["title"],
                    "original_text": art["text"][:2000],
                    "violation_criteria": data.get("violation_criteria", ""),
                    "applicable_measures": data.get("applicable_measures", ""),
                    "norm_type": data.get("norm_type", ""),
                    "norm_purpose": data.get("norm_purpose", ""),
                    "subject_competence": data.get("subject_competence", {}),
                }
                enriched.append(enriched_record)
                logger.info("  ✓ %s — %s", art["article_number"], data.get("norm_type", "?"))

            except json.JSONDecodeError as e:
                logger.warning("  ✗ %s — JSON parse error: %s", art["article_number"], e)
                enriched.append({
                    "law_name": law_name,
                    "article_number": art["article_number"],
                    "article_title": art["title"],
                    "original_text": art["text"][:2000],
                    "violation_criteria": "",
                    "applicable_measures": "",
                    "norm_type": "",
                    "norm_purpose": "",
                    "subject_competence": {},
                    "_enrichment_error": str(e),
                })
            except Exception as e:
                logger.error("  ✗ %s — API error: %s", art["article_number"], e)
                time.sleep(5)  # Back off on errors

        # Rate limiting between batches
        if batch_start + batch_size < len(articles):
            logger.info("  Waiting %.1fs before next batch...", delay)
            time.sleep(delay)

    return enriched


# ── Output ──────────────────────────────────────────────────────────────

def write_jsonl(records: list[dict], output_path: str):
    """Write enriched records to JSONL file."""
    path = Path(output_path)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Written %d records to %s", len(records), path)


def append_to_unified(records: list[dict], unified_path: str):
    """Append enriched records to existing unified JSONL file."""
    path = Path(unified_path)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Appended %d records to %s", len(records), path)


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enrich Kazakhstan legal norms for FAISS indexing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enrich_laws.py \\
    --input "Закон_О_жилищных_отношениях.docx" \\
    --law-name "Закон РК «О жилищных отношениях»" \\
    --output enriched_housing.jsonl \\
    --api-key AIzaSy...

  # Append to unified file and rebuild index:
  python enrich_laws.py \\
    --input law.docx --law-name "Закон" \\
    --append-to unified_laws_200upk.jsonl \\
    --api-key KEY
        """,
    )
    parser.add_argument("--input", required=True, help="Path to law file (DOCX or TXT)")
    parser.add_argument("--law-name", required=True, help="Official name of the law")
    parser.add_argument("--output", default=None, help="Output JSONL file path")
    parser.add_argument("--append-to", default=None, help="Append to existing unified JSONL")
    parser.add_argument("--api-key", required=True, help="Google Gemini API key")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model name")
    parser.add_argument("--batch-size", type=int, default=5, help="Articles per batch")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between batches (sec)")

    args = parser.parse_args()

    if not args.output and not args.append_to:
        args.output = Path(args.input).stem + "_enriched.jsonl"

    # 1. Extract text
    logger.info("Loading file: %s", args.input)
    text = extract_text_from_file(args.input)
    logger.info("Extracted %d characters", len(text))

    # 2. Split into articles
    articles = split_into_articles(text)
    if not articles:
        logger.error("No articles found in the document. Check formatting.")
        sys.exit(1)

    # 3. Enrich via Gemini
    logger.info("Enriching %d articles via %s...", len(articles), args.model)
    enriched = enrich_article_batch(
        articles=articles,
        law_name=args.law_name,
        api_key=args.api_key,
        model=args.model,
        batch_size=args.batch_size,
        delay=args.delay,
    )

    # 4. Output
    if args.output:
        write_jsonl(enriched, args.output)
    if args.append_to:
        append_to_unified(enriched, args.append_to)

    # Summary
    total = len(enriched)
    errors = sum(1 for r in enriched if r.get("_enrichment_error"))
    violations = sum(1 for r in enriched if r.get("norm_purpose") in ("violation", "both"))
    remedies = sum(1 for r in enriched if r.get("norm_purpose") in ("remedy", "both"))

    logger.info("=" * 60)
    logger.info("ENRICHMENT COMPLETE")
    logger.info("  Total articles: %d", total)
    logger.info("  Errors: %d", errors)
    logger.info("  Violation norms: %d", violations)
    logger.info("  Remedy norms: %d", remedies)
    logger.info("=" * 60)
    if args.append_to:
        logger.info(
            "Don't forget to rebuild the FAISS index: "
            "POST /api/rag-laws/rebuild"
        )


if __name__ == "__main__":
    main()
