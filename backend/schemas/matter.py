"""Pydantic schemas for matter (case) operations."""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class MatterCreate(BaseModel):
    name: str
    description: Optional[str] = None
    custom_instructions: Optional[str] = ""


class MatterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    custom_instructions: Optional[str] = None


class MatterResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    custom_instructions: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MatterListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    file_count: int = 0

    class Config:
        from_attributes = True
