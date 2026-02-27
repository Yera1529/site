"""Pydantic schemas for file operations."""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FileResponse(BaseModel):
    id: uuid.UUID
    matter_id: uuid.UUID
    original_name: str
    file_type: str
    file_size: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class FileDetailResponse(FileResponse):
    extracted_text: Optional[str] = None
