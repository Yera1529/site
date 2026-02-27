"""Pydantic schemas for representation endpoints."""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class RepresentationCreate(BaseModel):
    matter_id: uuid.UUID
    template_id: Optional[uuid.UUID] = None
    title: str = ""
    content: str = ""
    status: str = "draft"
    selected_law_ids: Optional[List[str]] = []


class RepresentationUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    selected_law_ids: Optional[List[str]] = None
    validation_result: Optional[str] = None


class RepresentationResponse(BaseModel):
    id: uuid.UUID
    matter_id: uuid.UUID
    template_id: Optional[uuid.UUID] = None
    title: str
    content: str
    status: str
    selected_law_ids: str
    validation_result: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
