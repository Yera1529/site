"""Knowledge-base routes: upload / list / delete markdown documents for RAG (article 200)."""

import uuid
import re
from pathlib import Path
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import get_settings
from models.user import User
from models.knowledge_base import KBDocument
from routers.auth import get_current_user, require_admin
from services.rag import RAGService

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

ALLOWED_EXTENSIONS = {"md", "txt", "markdown"}
ART200_KEYWORDS = [
    "200", "представлени", "устранени", "обстоятельств", "способствовавших",
    "упк", "уголовн", "процессуальн",
]


def _validate_article_200(text: str) -> bool:
    """Heuristic: at least 2 keywords must appear in the document."""
    lower = text.lower()
    hits = sum(1 for kw in ART200_KEYWORDS if kw in lower)
    return hits >= 2


class KBDocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    title: str
    article: str
    chunk_count: int
    file_size: int
    created_at: str

    class Config:
        from_attributes = True


class KBStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int


@router.get("/stats", response_model=KBStatsResponse)
async def kb_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_count = (await db.execute(select(sqlfunc.count()).select_from(KBDocument))).scalar() or 0
    rag = RAGService()
    vec_stats = rag.get_kb_stats()
    return KBStatsResponse(total_documents=doc_count, total_chunks=vec_stats["total_chunks"])


@router.get("", response_model=List[KBDocumentResponse])
async def list_kb_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KBDocument).order_by(KBDocument.created_at.desc()))
    return [
        KBDocumentResponse(
            id=d.id,
            filename=d.filename,
            title=d.title,
            article=d.article,
            chunk_count=d.chunk_count,
            file_size=d.file_size,
            created_at=d.created_at.isoformat(),
        )
        for d in result.scalars().all()
    ]


@router.post("", response_model=KBDocumentResponse, status_code=201)
async def upload_kb_document(
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload a markdown/txt document to the article-200 knowledge base."""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Допустимые форматы: {', '.join(sorted(ALLOWED_EXTENSIONS))}. "
                   f"Получен: «{ext}».",
        )

    content_bytes = await file.read()
    settings = get_settings()
    if len(content_bytes) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Файл превышает {max_mb} МБ.")

    text = content_bytes.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Файл пуст.")

    if not _validate_article_200(text):
        raise HTTPException(
            status_code=400,
            detail="Документ не относится к ст.200 УПК РК. "
                   "Загружайте только представления по ст.200.",
        )

    title_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else file.filename

    docs_dir = Path(settings.storage_dir) / "documents" / "representations"
    docs_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    (docs_dir / safe_name).write_text(text, encoding="utf-8")

    doc_id = uuid.uuid4()
    rag = RAGService()
    rag.index_kb_document(
        doc_id=str(doc_id),
        text=text,
        metadata={"source_file": file.filename, "title": title},
    )

    chunk_count = len(rag._chunk_text(text))

    db_doc = KBDocument(
        id=doc_id,
        filename=file.filename,
        title=title,
        article="200",
        content=text,
        chunk_count=chunk_count,
        file_size=len(content_bytes),
        uploaded_by=user.id,
    )
    db.add(db_doc)
    await db.flush()
    await db.refresh(db_doc)

    return KBDocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        title=db_doc.title,
        article=db_doc.article,
        chunk_count=db_doc.chunk_count,
        file_size=db_doc.file_size,
        created_at=db_doc.created_at.isoformat(),
    )


@router.post("/batch", response_model=List[KBDocumentResponse], status_code=201)
async def upload_kb_batch(
    files: List[UploadFile],
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple markdown files to the knowledge base at once."""
    results = []
    settings = get_settings()
    rag = RAGService()
    docs_dir = Path(settings.storage_dir) / "documents" / "representations"
    docs_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            continue

        content_bytes = await file.read()
        if len(content_bytes) > settings.max_upload_bytes:
            continue

        text = content_bytes.decode("utf-8", errors="ignore")
        if not text.strip() or not _validate_article_200(text):
            continue

        title_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file.filename

        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        (docs_dir / safe_name).write_text(text, encoding="utf-8")

        doc_id = uuid.uuid4()
        rag.index_kb_document(
            doc_id=str(doc_id),
            text=text,
            metadata={"source_file": file.filename, "title": title},
        )

        db_doc = KBDocument(
            id=doc_id,
            filename=file.filename,
            title=title,
            article="200",
            content=text,
            chunk_count=len(rag._chunk_text(text)),
            file_size=len(content_bytes),
            uploaded_by=user.id,
        )
        db.add(db_doc)
        await db.flush()
        await db.refresh(db_doc)

        results.append(KBDocumentResponse(
            id=db_doc.id,
            filename=db_doc.filename,
            title=db_doc.title,
            article=db_doc.article,
            chunk_count=db_doc.chunk_count,
            file_size=db_doc.file_size,
            created_at=db_doc.created_at.isoformat(),
        ))

    return results


@router.delete("/{doc_id}", status_code=204)
async def delete_kb_document(
    doc_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KBDocument).where(KBDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")

    rag = RAGService()
    rag.delete_kb_document(str(doc_id))
    await db.delete(doc)
