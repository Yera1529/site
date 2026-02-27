"""Pydantic schemas for chat operations."""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    matter_id: uuid.UUID


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    matter_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SelectedLaw(BaseModel):
    text: str
    law_title: str
    article_number: str
    category: str
    score: float


class GenerateDocumentRequest(BaseModel):
    matter_id: uuid.UUID
    template_name: str
    additional_instructions: Optional[str] = ""
    selected_laws: Optional[List[SelectedLaw]] = None


class ValidationReport(BaseModel):
    ok: bool
    missing: List[str]
    present: List[str]


class RetrievedLawResponse(BaseModel):
    text: str
    law_title: str
    article_number: str
    category: str
    score: float


class CitationCheckResponse(BaseModel):
    cited: List[str]
    unverified: List[str]


class GenerateDocumentResponse(BaseModel):
    content: str
    template_name: str
    validation: Optional[ValidationReport] = None
    retrieved_laws: Optional[List[RetrievedLawResponse]] = None
    citation_check: Optional[CitationCheckResponse] = None
