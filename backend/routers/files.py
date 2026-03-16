"""File upload, download, listing, and deletion routes."""

import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import get_settings
from models.user import User
from models.file import File
from schemas.file import FileResponse as FileSchema, FileDetailResponse
from routers.auth import get_current_user
from routers.matters import get_authorized_matter
from services.storage import StorageService
from services.rag import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matters/{matter_id}/files", tags=["files"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "rtf", "odt", "png", "jpg", "jpeg"}
TEXT_EXTRACTABLE = {"pdf", "docx", "doc", "txt", "rtf", "odt"}


@router.get("", response_model=List[FileSchema])
async def list_files(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_authorized_matter(matter_id, user, db)
    result = await db.execute(
        select(File).where(File.matter_id == matter_id).order_by(File.uploaded_at.desc())
    )
    return [FileSchema.model_validate(f) for f in result.scalars().all()]


@router.post("", response_model=FileSchema, status_code=201)
async def upload_file(
    matter_id: uuid.UUID,
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_authorized_matter(matter_id, user, db)
    settings = get_settings()

    if not file.filename:
        raise HTTPException(status_code=400, detail="Имя файла отсутствует.")

    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат «.{file_ext}». "
                   f"Допустимые: {', '.join(sorted('.' + e for e in ALLOWED_EXTENSIONS))}.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Файл пуст.")

    if len(content) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой ({len(content) // (1024*1024)} МБ). "
                   f"Максимальный размер: {max_mb} МБ.",
        )

    storage = StorageService()
    storage_path = storage.save_file(str(matter_id), file.filename, content)

    extracted_text = ""
    if file_ext in TEXT_EXTRACTABLE:
        try:
            extracted_text = storage.extract_text(storage_path, file_ext)
        except Exception as e:
            extracted_text = f"[Ошибка извлечения текста: {str(e)[:200]}]"

    db_file = File(
        matter_id=matter_id,
        original_name=file.filename,
        storage_path=storage_path,
        file_type=file_ext,
        file_size=len(content),
        extracted_text=extracted_text,
    )
    db.add(db_file)
    await db.flush()
    await db.refresh(db_file)

    if extracted_text and not extracted_text.startswith("[Ошибка"):
        try:
            rag = RAGService()
            rag.index_document(str(matter_id), str(db_file.id), extracted_text)
        except Exception as e:
            logger.error("RAG indexing failed for file %s: %s", db_file.id, e)

    return FileSchema.model_validate(db_file)


@router.get("/{file_id}", response_model=FileDetailResponse)
async def get_file_detail(
    matter_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_authorized_matter(matter_id, user, db)
    result = await db.execute(select(File).where(File.id == file_id, File.matter_id == matter_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileDetailResponse.model_validate(f)


@router.get("/{file_id}/download")
async def download_file(
    matter_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_authorized_matter(matter_id, user, db)
    result = await db.execute(select(File).where(File.id == file_id, File.matter_id == matter_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Файл не найден")

    storage = StorageService()
    full_path = storage.get_full_path(f.storage_path)
    return FileResponse(path=full_path, filename=f.original_name)


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    matter_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_authorized_matter(matter_id, user, db)
    result = await db.execute(select(File).where(File.id == file_id, File.matter_id == matter_id))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="Файл не найден")

    storage = StorageService()
    storage.delete_file(f.storage_path)

    try:
        rag = RAGService()
        rag.delete_document(str(matter_id), str(file_id))
    except Exception as e:
        logger.error("RAG deletion failed for file %s: %s", file_id, e)

    await db.delete(f)
