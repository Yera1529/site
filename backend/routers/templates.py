"""Custom document template upload and management routes."""

import uuid
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.template import DocumentTemplate
from routers.auth import get_current_user, require_admin
from services.storage import StorageService
from services.document import DocumentService

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    file_type: str
    file_size: int
    extracted_text: str | None
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentTemplate).order_by(DocumentTemplate.created_at.desc()))
    templates = result.scalars().all()
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            file_type=t.file_type,
            file_size=t.file_size,
            extracted_text=t.extracted_text,
            created_at=t.created_at.isoformat(),
        )
        for t in templates
    ]


@router.post("", response_model=TemplateResponse, status_code=201)
async def upload_template(
    name: str,
    description: str = "",
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file_ext not in ("docx", "doc", "rtf", "odt", "txt"):
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат. Используйте DOCX, RTF, ODT или TXT.")

    storage = StorageService()
    storage_path = storage.save_file("templates", file.filename, content)
    extracted_text = storage.extract_text(storage_path, file_ext)

    template = DocumentTemplate(
        name=name.strip(),
        description=description.strip(),
        file_type=file_ext,
        storage_path=storage_path,
        extracted_text=extracted_text,
        file_size=len(content),
        uploaded_by=user.id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        file_type=template.file_type,
        file_size=template.file_size,
        extracted_text=template.extracted_text,
        created_at=template.created_at.isoformat(),
    )


@router.get("/article200/blank")
async def get_blank_representation(
    user: User = Depends(get_current_user),
):
    """Return a blank article-200 representation template as HTML."""
    return {"html": DocumentService.representation_template_html(), "template_name": "Представление ст.200"}


@router.get("/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return TemplateResponse(
        id=t.id, name=t.name, description=t.description,
        file_type=t.file_type, file_size=t.file_size,
        extracted_text=t.extracted_text, created_at=t.created_at.isoformat(),
    )


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    storage = StorageService()
    storage.delete_file(t.storage_path)
    await db.delete(t)


@router.get("/{template_id}/download")
async def download_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    storage = StorageService()
    full_path = storage.get_full_path(t.storage_path)
    return FileResponse(path=full_path, filename=f"{t.name}.{t.file_type}")


@router.get("/{template_id}/html")
async def get_template_html(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return parsed DOCX template as HTML for TipTap editor."""
    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    if t.file_type in ("docx", "doc"):
        storage = StorageService()
        full_path = storage.get_full_path(t.storage_path)
        doc_service = DocumentService()
        html = doc_service.docx_to_html(full_path)
        return {"html": html, "template_name": t.name}

    return {"html": f"<p>{t.extracted_text or ''}</p>", "template_name": t.name}
