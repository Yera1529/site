"""Representation CRUD routes — tracks drafted представления linked to matters."""

import uuid
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.representation import Representation
from schemas.representation import RepresentationCreate, RepresentationUpdate, RepresentationResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/api/representations", tags=["representations"])


def _to_response(r: Representation) -> RepresentationResponse:
    return RepresentationResponse(
        id=r.id,
        matter_id=r.matter_id,
        template_id=r.template_id,
        title=r.title,
        content=r.content,
        status=r.status,
        selected_law_ids=r.selected_law_ids,
        validation_result=r.validation_result,
        created_by=r.created_by,
        created_at=r.created_at.isoformat(),
        updated_at=r.updated_at.isoformat(),
    )


@router.get("", response_model=List[RepresentationResponse])
async def list_representations(
    matter_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Representation).order_by(Representation.updated_at.desc())
    if matter_id:
        stmt = stmt.where(Representation.matter_id == matter_id)
    if status:
        stmt = stmt.where(Representation.status == status)
    if user.role != "admin":
        stmt = stmt.where(Representation.created_by == user.id)
    result = await db.execute(stmt)
    return [_to_response(r) for r in result.scalars().all()]


@router.post("", response_model=RepresentationResponse, status_code=201)
async def create_representation(
    data: RepresentationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rep = Representation(
        matter_id=data.matter_id,
        template_id=data.template_id,
        title=data.title,
        content=data.content,
        status=data.status,
        selected_law_ids=json.dumps(data.selected_law_ids or []),
        created_by=user.id,
    )
    db.add(rep)
    await db.flush()
    await db.refresh(rep)
    return _to_response(rep)


@router.get("/{rep_id}", response_model=RepresentationResponse)
async def get_representation(
    rep_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Representation).where(Representation.id == rep_id))
    rep = result.scalar_one_or_none()
    if not rep:
        raise HTTPException(status_code=404, detail="Представление не найдено")
    if user.role != "admin" and rep.created_by != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return _to_response(rep)


@router.put("/{rep_id}", response_model=RepresentationResponse)
async def update_representation(
    rep_id: uuid.UUID,
    data: RepresentationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Representation).where(Representation.id == rep_id))
    rep = result.scalar_one_or_none()
    if not rep:
        raise HTTPException(status_code=404, detail="Представление не найдено")
    if user.role != "admin" and rep.created_by != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    if data.title is not None:
        rep.title = data.title
    if data.content is not None:
        rep.content = data.content
    if data.status is not None:
        rep.status = data.status
    if data.selected_law_ids is not None:
        rep.selected_law_ids = json.dumps(data.selected_law_ids)
    if data.validation_result is not None:
        rep.validation_result = data.validation_result

    await db.flush()
    await db.refresh(rep)
    return _to_response(rep)


@router.delete("/{rep_id}", status_code=204)
async def delete_representation(
    rep_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Representation).where(Representation.id == rep_id))
    rep = result.scalar_one_or_none()
    if not rep:
        raise HTTPException(status_code=404, detail="Представление не найдено")
    if user.role != "admin" and rep.created_by != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    await db.delete(rep)
