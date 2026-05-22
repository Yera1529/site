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
    norm_purpose: Optional[str] = None
    violation_criteria: Optional[str] = None
    applicable_measures: Optional[str] = None


class StructuredViolation(BaseModel):
    """A user-specified violation that contributed to the crime."""
    description: str  # What happened (e.g. "Отсутствие освещения двора")
    responsible: str = ""  # Who is responsible (e.g. "КСК «Качар»")
    link_to_crime: str = ""  # How it enabled the crime


class GenerateDocumentRequest(BaseModel):
    matter_id: uuid.UUID
    template_name: Optional[str] = None   # больше не обязателен — правила в промпте
    additional_instructions: Optional[str] = ""
    selected_laws: Optional[List[SelectedLaw]] = None
    # Phase 3: structured violations (causes/conditions specified by user)
    structured_violations: Optional[List[StructuredViolation]] = None
    addressee_override: Optional[str] = None  # User-specified addressee
    # Norm ↔ violation bindings: maps law index → violation index
    norm_violation_bindings: Optional[dict[str, int]] = None


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
    norm_purpose: Optional[str] = None
    violation_criteria: Optional[str] = None
    applicable_measures: Optional[str] = None


class CitationCheckResponse(BaseModel):
    cited: List[str]
    unverified: List[str]


class NormUsageItem(BaseModel):
    law: str
    article: str


class NormUsageReport(BaseModel):
    all_used: bool
    used: List[NormUsageItem] = []
    unused: List[NormUsageItem] = []


class AddresseeCheck(BaseModel):
    ok: bool
    reason: str = ""


class QualityIssue(BaseModel):
    severity: str = "low"   # high | medium | low
    text: str = ""


class QualityReview(BaseModel):
    """Deep LLM legal-soundness review of the generated document."""
    causal_chain_ok: bool = True
    measures_mapped_ok: bool = True
    addressee_reasoning_ok: bool = True
    grounding_ok: bool = True
    overall: str = "good"   # good | warnings | poor
    issues: List[QualityIssue] = []
    available: bool = False  # False when the review could not run


class GenerateDocumentResponse(BaseModel):
    content: str
    template_name: Optional[str] = None
    representation_id: Optional[uuid.UUID] = None
    validation: Optional[ValidationReport] = None
    retrieved_laws: Optional[List[RetrievedLawResponse]] = None
    citation_check: Optional[CitationCheckResponse] = None
    norm_usage: Optional[NormUsageReport] = None
    addressee_check: Optional[AddresseeCheck] = None
    quality_review: Optional[QualityReview] = None

