"""API endpoint for enriched legal norms RAG search (enriched_laws_200upk.jsonl).

Provides a dedicated search endpoint for the FAISS-indexed JSONL norms
and an endpoint to check index status/stats.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from models.user import User
from routers.auth import get_current_user
from services.rag_laws import RAGLawsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag-laws", tags=["rag-laws"])


class RAGLawsSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Текст фабулы дела")
    organ_filter: Optional[str] = Field(None, description="Фильтр по типу организации-адресата")
    top_k: int = Field(5, ge=1, le=20, description="Количество результатов")


class RAGLawsResult(BaseModel):
    law_name: str
    article_number: str
    original_text: str
    violation_criteria: str
    applicable_measures: str
    norm_type: str = ""
    organ: str = ""
    score: float = 0.0


class RAGLawsStatsResponse(BaseModel):
    total_records: int
    index_size: int
    indexed: bool


@router.post("/search", response_model=List[RAGLawsResult])
async def search_norms(
    data: RAGLawsSearchRequest,
    user: User = Depends(get_current_user),
):
    """Search enriched legal norms by case description.

    Uses FAISS vector search with norm_type boosting and optional organ filtering.
    """
    svc = RAGLawsService()
    results = svc.search(
        query=data.query,
        top_k=data.top_k,
        organ_filter=data.organ_filter,
    )
    return [RAGLawsResult(**r) for r in results]


@router.get("/stats", response_model=RAGLawsStatsResponse)
async def get_stats(
    user: User = Depends(get_current_user),
):
    """Get RAG laws index statistics."""
    svc = RAGLawsService()
    return RAGLawsStatsResponse(**svc.get_stats())


@router.post("/rebuild")
async def rebuild_index(
    user: User = Depends(get_current_user),
):
    """Force rebuild the FAISS index from the JSONL file."""
    svc = RAGLawsService()
    svc.rebuild()
    stats = svc.get_stats()
    return {
        "message": f"Index rebuilt: {stats['total_records']} records",
        **stats,
    }
