"""Admin settings routes for configuring AI model endpoint and other options."""

from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.user import User
from models.settings import AppSetting
from routers.auth import require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingResponse(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True


ALLOWED_KEYS = {"ai_api_url", "ai_api_key", "ai_model", "ai_thinking_mode", "embedding_model"}


@router.get("", response_model=List[SettingResponse])
async def get_settings(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AppSetting))
    settings = result.scalars().all()
    return [SettingResponse(key=s.key, value=s.value if s.key != "ai_api_key" else "***") for s in settings]


@router.put("", response_model=List[SettingResponse])
async def update_settings(
    updates: List[SettingUpdate],
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    responses = []
    for update in updates:
        if update.key not in ALLOWED_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown setting key: {update.key}")

        result = await db.execute(select(AppSetting).where(AppSetting.key == update.key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = update.value
        else:
            setting = AppSetting(key=update.key, value=update.value)
            db.add(setting)
        await db.flush()
        responses.append(SettingResponse(key=update.key, value=update.value if update.key != "ai_api_key" else "***"))

    return responses
