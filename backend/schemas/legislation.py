"""Pydantic schemas for legislation endpoints."""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class LegislationResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    year: Optional[int] = None
    filename: str
    article_count: int
    chunk_count: int
    file_size: int
    file_type: str
    indexed_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class LegislationDetailResponse(LegislationResponse):
    content: str


class ArticleNode(BaseModel):
    number: str
    title: str
    text: str


class RetrievedLaw(BaseModel):
    text: str
    law_title: str
    article_number: str
    category: str
    score: float


class SearchLawsRequest(BaseModel):
    matter_id: uuid.UUID
    query: Optional[str] = ""
