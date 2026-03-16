"""Legislation management routes: upload, list, search, reindex, article parsing."""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Query
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import get_settings
from models.user import User
from models.legislation import LegislationDoc
from routers.auth import get_current_user, require_admin
from services.storage import StorageService
from services.rag import RAGService
from schemas.legislation import LegislationResponse, LegislationDetailResponse, ArticleNode

router = APIRouter(prefix="/api/legislation", tags=["legislation"])

ALLOWED_EXTENSIONS = {"docx", "doc", "md", "txt", "markdown", "rtf", "odt"}


def _to_response(d: LegislationDoc) -> LegislationResponse:
    return LegislationResponse(
        id=d.id,
        title=d.title,
        category=d.category,
        year=d.year,
        filename=d.filename,
        article_count=d.article_count,
        chunk_count=d.chunk_count,
        file_size=d.file_size,
        file_type=d.file_type,
        indexed_at=d.indexed_at.isoformat() if d.indexed_at else None,
        created_at=d.created_at.isoformat(),
    )


@router.get("/categories", response_model=List[str])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LegislationDoc.category).distinct().order_by(LegislationDoc.category)
    )
    return [r[0] for r in result.all() if r[0]]


@router.get("", response_model=List[LegislationResponse])
async def list_legislation(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(LegislationDoc).order_by(LegislationDoc.created_at.desc())
    if category:
        stmt = stmt.where(LegislationDoc.category == category)
    if q:
        stmt = stmt.where(LegislationDoc.title.ilike(f"%{q}%"))
    offset = (page - 1) * limit
    result = await db.execute(stmt.offset(offset).limit(limit))
    return [_to_response(d) for d in result.scalars().all()]


@router.post("", response_model=LegislationResponse, status_code=201)
async def upload_legislation(
    title: str,
    category: str = "уголовное право",
    year: Optional[int] = None,
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат «.{ext}». Допустимые: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    content_bytes = await file.read()
    settings = get_settings()
    if len(content_bytes) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Файл превышает {max_mb} МБ.")

    storage = StorageService()
    storage_path = storage.save_file("legislation", file.filename, content_bytes)

    if ext in ("md", "txt", "markdown"):
        text = content_bytes.decode("utf-8", errors="ignore")
    else:
        text = storage.extract_text(storage_path, ext)

    rag = RAGService()
    articles = rag.parse_articles(text)
    article_count = len(articles)

    doc_id = uuid.uuid4()
    chunk_count = rag.index_legislation(
        doc_id=str(doc_id), text=text, law_title=title.strip(), category=category.strip()
    )

    doc = LegislationDoc(
        id=doc_id,
        title=title.strip(),
        category=category.strip(),
        year=year,
        filename=file.filename,
        storage_path=storage_path,
        content=text,
        article_count=article_count,
        file_size=len(content_bytes),
        file_type=ext,
        chunk_count=chunk_count,
        indexed_at=datetime.now(timezone.utc),
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return _to_response(doc)


@router.get("/{doc_id}", response_model=LegislationDetailResponse)
async def get_legislation(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LegislationDoc).where(LegislationDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    resp = _to_response(doc)
    return LegislationDetailResponse(**resp.model_dump(), content=doc.content)


@router.get("/{doc_id}/articles", response_model=List[ArticleNode])
async def get_legislation_articles(
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LegislationDoc).where(LegislationDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    rag = RAGService()
    articles = rag.parse_articles(doc.content)
    return [ArticleNode(**a) for a in articles]


@router.put("/{doc_id}", response_model=LegislationResponse)
async def update_legislation(
    doc_id: uuid.UUID,
    title: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[int] = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LegislationDoc).where(LegislationDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    if title is not None:
        doc.title = title.strip()
    if category is not None:
        doc.category = category.strip()
    if year is not None:
        doc.year = year
    await db.flush()
    await db.refresh(doc)
    return _to_response(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_legislation(
    doc_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LegislationDoc).where(LegislationDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")

    rag = RAGService()
    rag.delete_legislation(str(doc_id))

    storage = StorageService()
    storage.delete_file(doc.storage_path)

    await db.delete(doc)


@router.post("/{doc_id}/reindex", response_model=LegislationResponse)
async def reindex_legislation(
    doc_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LegislationDoc).where(LegislationDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")

    rag = RAGService()
    rag.delete_legislation(str(doc_id))

    chunk_count = rag.index_legislation(
        doc_id=str(doc_id), text=doc.content, law_title=doc.title, category=doc.category
    )
    articles = rag.parse_articles(doc.content)

    doc.chunk_count = chunk_count
    doc.article_count = len(articles)
    doc.indexed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(doc)
    return _to_response(doc)


@router.post("/import-jsonl", response_model=List[LegislationResponse], status_code=201)
async def import_legislation_jsonl(
    file: UploadFile = FastAPIFile(...),
    category: str = Query("уголовное право"),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Import enriched legislation from a JSONL file.

    Each line is a JSON object with: law_name, article_number, original_text,
    norm_type, subject_competence, violation_criteria, applicable_measures.

    Records are grouped by law_name → one LegislationDoc per law.
    """
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("jsonl", "json"):
        raise HTTPException(
            status_code=400,
            detail="Ожидается файл .jsonl или .json",
        )

    content_bytes = await file.read()
    settings = get_settings()
    if len(content_bytes) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Файл превышает {max_mb} МБ.")

    # Parse JSONL lines
    text = content_bytes.decode("utf-8", errors="ignore")
    records: list[dict] = []
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"Ошибка JSON в строке {line_num}",
            )

    if not records:
        raise HTTPException(status_code=400, detail="Файл не содержит записей.")

    # Group by law_name
    grouped: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        law_name = rec.get("law_name", "Без названия")
        grouped[law_name].append(rec)

    # Save file
    storage = StorageService()
    storage_path = storage.save_file("legislation", file.filename, content_bytes)

    rag = RAGService()
    created_docs: list[LegislationResponse] = []

    for law_name, law_records in grouped.items():
        doc_id = uuid.uuid4()

        # Build human-readable content from enriched fields
        content_parts = [f"# {law_name}\n"]
        for rec in law_records:
            art_num = rec.get("article_number") or ""
            original = rec.get("original_text") or ""
            norm_type = rec.get("norm_type") or ""
            violation = rec.get("violation_criteria") or ""
            measures = rec.get("applicable_measures") or ""
            if isinstance(measures, list):
                measures = "; ".join(str(m) for m in measures)
            subj = rec.get("subject_competence") or {}
            if isinstance(subj, dict):
                subj_str = f"{subj.get('organ', '')} — {subj.get('competence', '')}"
            elif isinstance(subj, list):
                subj_str = "; ".join(
                    f"{s.get('organ', '')} — {s.get('competence', '')}"
                    for s in subj if isinstance(s, dict)
                )
            else:
                subj_str = str(subj)

            content_parts.append(
                f"## {art_num}\n"
                f"**Тип нормы:** {norm_type}\n\n"
                f"{original}\n\n"
                f"**Субъект/компетенция:** {subj_str}\n\n"
                f"**Критерии нарушения:** {violation}\n\n"
                f"**Меры реагирования:** {measures}\n\n---\n"
            )

        content = "\n".join(content_parts)

        # Index into ChromaDB
        chunk_count = rag.index_legislation_jsonl(
            doc_id=str(doc_id),
            law_title=law_name,
            category=category.strip(),
            records=law_records,
        )

        doc = LegislationDoc(
            id=doc_id,
            title=law_name,
            category=category.strip(),
            year=None,
            filename=file.filename,
            storage_path=storage_path,
            content=content,
            article_count=len(law_records),
            file_size=len(content_bytes),
            file_type="jsonl",
            chunk_count=chunk_count,
            indexed_at=datetime.now(timezone.utc),
            uploaded_by=user.id,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        created_docs.append(_to_response(doc))

    return created_docs
