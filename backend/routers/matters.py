"""CRUD routes for matters (legal cases)."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.user import User
from models.matter import Matter, MatterUser
from models.file import File
from schemas.matter import MatterCreate, MatterUpdate, MatterResponse, MatterListResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/api/matters", tags=["matters"])


async def get_authorized_matter(
    matter_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Matter:
    """Verify the user has access to the matter, then return it."""
    result = await db.execute(
        select(Matter)
        .join(MatterUser)
        .where(Matter.id == matter_id, MatterUser.user_id == user.id)
        .options(selectinload(Matter.files))
    )
    matter = result.scalar_one_or_none()
    if not matter:
        # Admins can access any matter
        if user.role == "admin":
            result = await db.execute(
                select(Matter).where(Matter.id == matter_id).options(selectinload(Matter.files))
            )
            matter = result.scalar_one_or_none()
        if not matter:
            raise HTTPException(status_code=404, detail="Matter not found")
    return matter


@router.get("", response_model=List[MatterListResponse])
async def list_matters(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == "admin":
        query = select(Matter).order_by(Matter.updated_at.desc())
    else:
        query = (
            select(Matter)
            .join(MatterUser)
            .where(MatterUser.user_id == user.id)
            .order_by(Matter.updated_at.desc())
        )
    result = await db.execute(query.options(selectinload(Matter.files)))
    matters = result.scalars().all()

    response = []
    for m in matters:
        response.append(
            MatterListResponse(
                id=m.id,
                name=m.name,
                description=m.description,
                created_at=m.created_at,
                file_count=len(m.files),
            )
        )
    return response


@router.post("", response_model=MatterResponse, status_code=201)
async def create_matter(
    data: MatterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = Matter(
        name=data.name,
        description=data.description,
        custom_instructions=data.custom_instructions or "",
    )
    db.add(matter)
    await db.flush()

    link = MatterUser(matter_id=matter.id, user_id=user.id, role="owner")
    db.add(link)
    await db.flush()
    await db.refresh(matter)

    return MatterResponse.model_validate(matter)


@router.get("/{matter_id}", response_model=MatterResponse)
async def get_matter(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = await get_authorized_matter(matter_id, user, db)
    return MatterResponse.model_validate(matter)


@router.put("/{matter_id}", response_model=MatterResponse)
async def update_matter(
    matter_id: uuid.UUID,
    data: MatterUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = await get_authorized_matter(matter_id, user, db)
    if data.name is not None:
        matter.name = data.name
    if data.description is not None:
        matter.description = data.description
    if data.custom_instructions is not None:
        matter.custom_instructions = data.custom_instructions
    await db.flush()
    await db.refresh(matter)
    return MatterResponse.model_validate(matter)


@router.delete("/{matter_id}", status_code=204)
async def delete_matter(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = await get_authorized_matter(matter_id, user, db)
    await db.delete(matter)
