"""Chat routes with SSE streaming, RAG-augmented generation and DOCX export."""

import logging
import uuid
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, async_session
from models.user import User
from models.chat import ChatMessage
from models.file import File
from models.representation import Representation
from schemas.chat import (
    ChatRequest,
    ChatMessageResponse,
    GenerateDocumentRequest,
    GenerateDocumentResponse,
    ValidationReport,
    CitationCheckResponse,
    RetrievedLawResponse,
)
from schemas.legislation import SearchLawsRequest, RetrievedLaw
from routers.auth import get_current_user
from routers.matters import get_authorized_matter
from services.ai import AIService, validate_representation, validate_law_citations
from services.rag import RAGService
from services.document import DocumentService
from models.template import DocumentTemplate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class ExportDocxRequest(BaseModel):
    html: str = Field(..., min_length=1)
    filename: str = Field(default="document.docx", max_length=255)


@router.get("/matters/{matter_id}/chat", response_model=List[ChatMessageResponse])
async def get_chat_history(
    matter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_authorized_matter(matter_id, user, db)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.matter_id == matter_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/chat")
async def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = await get_authorized_matter(data.matter_id, user, db)

    user_msg = ChatMessage(
        matter_id=data.matter_id,
        user_id=user.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.flush()

    rag = RAGService()
    combined = rag.query_combined(
        str(data.matter_id), data.message, top_k_matter=3, top_k_kb=5
    )
    matter_context = "\n\n---\n\n".join(combined["matter"]) if combined["matter"] else ""
    kb_context = (
        "\n\n---\n\n".join(combined["knowledge_base"])
        if combined["knowledge_base"]
        else ""
    )

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.matter_id == data.matter_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history = list(reversed(result.scalars().all()))

    ai = AIService()
    system_prompt = ai.build_system_prompt(
        custom_instructions=matter.custom_instructions or "",
        context=matter_context,
        kb_context=kb_context,
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        llm_messages.append({"role": msg.role, "content": msg.content})

    matter_id_val = data.matter_id
    user_id_val = user.id

    async def event_stream():
        full_response = []
        async for chunk in ai.stream_chat(llm_messages):
            full_response.append(chunk)
            event_data = json.dumps({"content": chunk, "done": False})
            yield f"data: {event_data}\n\n"

        assistant_content = "".join(full_response)
        async with async_session() as session:
            assistant_msg = ChatMessage(
                matter_id=matter_id_val,
                user_id=user_id_val,
                role="assistant",
                content=assistant_content,
            )
            session.add(assistant_msg)
            await session.commit()

        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/search-laws", response_model=List[RetrievedLaw])
async def search_laws(
    data: SearchLawsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search legislation vector store using case facts as query.

    Builds a focused query from: qualification (article of criminal code),
    matter description, custom instructions, and extracted file text.
    """
    matter = await get_authorized_matter(data.matter_id, user, db)

    if data.query and data.query.strip():
        query_text = data.query.strip()
    else:
        parts = []
        if matter.name:
            parts.append(f"Дело: {matter.name}")
        if matter.description:
            parts.append(f"Фабула: {matter.description[:1000]}")
        if matter.custom_instructions:
            parts.append(f"Указания: {matter.custom_instructions[:500]}")

        result = await db.execute(select(File).where(File.matter_id == data.matter_id))
        files = result.scalars().all()
        facts = " ".join(f.extracted_text for f in files if f.extracted_text)
        if facts:
            parts.append(f"Материалы: {facts[:3000]}")

        query_text = " ".join(parts) if parts else "представление по ст.200 УПК РК"

    rag = RAGService()
    laws = rag.search_relevant_laws(query_text, top_k=10)
    return [RetrievedLaw(**law) for law in laws]


@router.post("/generate-document", response_model=GenerateDocumentResponse)
async def generate_document(
    data: GenerateDocumentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    matter = await get_authorized_matter(data.matter_id, user, db)

    result = await db.execute(select(File).where(File.matter_id == data.matter_id))
    files = result.scalars().all()
    all_text = "\n\n".join(f.extracted_text for f in files if f.extracted_text)

    logger.info(
        "generate_document: matter=%s template=%s files=%d text_len=%d",
        data.matter_id, data.template_name, len(files), len(all_text)
    )

    tmpl_result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.name == data.template_name)
    ) if data.template_name else None
    tmpl = tmpl_result.scalar_one_or_none() if tmpl_result else None
    template_content = tmpl.extracted_text if tmpl else None
    # template_content не используется в промпте — правила заданы в REPRESENTATION_RULES
    # шаблон нужен только для template_id в записи Representation

    rag = RAGService()

    query_for_kb = (
        f"представление ст.200 {data.template_name} "
        f"{data.additional_instructions or ''}"
    )
    kb_chunks = rag.query_kb(query_for_kb, top_k=5)
    kb_context = "\n\n---\n\n".join(kb_chunks) if kb_chunks else ""

    # Use user-selected laws if provided; otherwise search automatically
    if data.selected_laws and len(data.selected_laws) > 0:
        retrieved_laws = [law.model_dump() for law in data.selected_laws]  # -> list[dict]
    else:
        law_query = all_text[:4000]
        if matter.description:
            law_query = f"{matter.description[:1000]} {law_query}"
        retrieved_laws = rag.search_relevant_laws(law_query, top_k=10)

    # Build a structured case context block so AI clearly sees what data is available
    case_context_parts = []
    if matter.name:
        case_context_parts.append(f"ЕРДР / Номер дела: {matter.name}")
    if matter.description:
        case_context_parts.append(f"Фабула дела: {matter.description}")
    if matter.custom_instructions:
        case_context_parts.append(f"Инструкции следователя: {matter.custom_instructions}")
    if all_text:
        # Pass generous portion of case file text so AI can extract FIO, dates, etc.
        case_context_parts.append(
            f"Полный текст материалов дела (используй для извлечения ФИО, дат, обстоятельств):\n"
            f"{all_text[:20000]}"
        )
    case_context_str = "\n\n".join(case_context_parts)

    # Combine user additional instructions with explicit case data reminder
    enriched_instructions = (
        (data.additional_instructions or "") + "\n\n"
        "ВАЖНО: Используй ТОЛЬКО реальные данные из раздела '## Факты из материалов дела'. "
        "Никаких заглушек (___, ???, [заполнить]). "
        "Если данные есть в тексте — обязательно вставь их в документ."
    ).strip()

    try:
        ai = AIService()
        generated = await ai.generate_document(
            facts=case_context_str,
            custom_instructions=matter.custom_instructions or "",
            additional_instructions=enriched_instructions,
            kb_context=kb_context,
            retrieved_laws=retrieved_laws,
        )
        logger.info("generate_document: generated %d chars", len(generated))
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=502,
                detail=(
                    "Не удалось подключиться к Gemini API. "
                    "Проверьте API-ключ и соединение с интернетом. "
                    f"Детали: {error_msg[:200]}"
                ),
            )
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации: {error_msg[:300]}",
        )

    validation = validate_representation(generated)
    citation_check = validate_law_citations(generated, retrieved_laws)

    if not validation["ok"] and validation["missing"]:
        refined_query = (
            f"нарушения обязанности ответственность меры устранение "
            f"{' '.join(validation['missing'])} {(matter.description or '')[:2000]}"
        )
        extra_laws = rag.search_relevant_laws(refined_query, top_k=5)
        seen = {(l["law_title"], l["article_number"]) for l in retrieved_laws}
        for el in extra_laws:
            key = (el["law_title"], el["article_number"])
            if key not in seen:
                retrieved_laws.append(el)
                seen.add(key)

        try:
            generated = await ai.generate_document(
                facts=all_text,
                custom_instructions=matter.custom_instructions or "",
                additional_instructions=data.additional_instructions or "",
                kb_context=kb_context,
                retrieved_laws=retrieved_laws,
            )
        except Exception:
            pass  # Keep the first generation result
        else:
            validation = validate_representation(generated)
            citation_check = validate_law_citations(generated, retrieved_laws)

    # Auto-save as Representation record
    rep_title = (
        f"Представление — {data.template_name}"
        if data.template_name
        else f"Представление — {matter.name}"
    )
    rep = Representation(
        matter_id=data.matter_id,
        template_id=tmpl.id if tmpl else None,
        title=rep_title,
        content=generated,
        status="draft",
        selected_law_ids=json.dumps([
            law.get("law_title", "") + " ст." + law.get("article_number", "")
            for law in retrieved_laws if law.get("article_number")
        ]),
        validation_result=json.dumps(validation),
        created_by=user.id,
    )
    db.add(rep)
    await db.flush()
    await db.refresh(rep)

    assistant_msg = ChatMessage(
        matter_id=data.matter_id,
        user_id=user.id,
        role="assistant",
        content=f"[Документ сгенерирован: {data.template_name}]\n\n{generated}",
    )
    db.add(assistant_msg)

    return GenerateDocumentResponse(
        content=generated,
        template_name=data.template_name,
        representation_id=rep.id,
        validation=ValidationReport(**validation),
        retrieved_laws=[
            RetrievedLawResponse(**law) if isinstance(law, dict) else RetrievedLawResponse(**law.model_dump())
            for law in retrieved_laws
        ],
        citation_check=CitationCheckResponse(**citation_check),
    )


@router.post("/export-docx")
async def export_docx(
    data: ExportDocxRequest,
    user: User = Depends(get_current_user),
):
    doc_service = DocumentService()
    file_path = doc_service.html_to_docx(data.html, data.filename)

    return FileResponse(
        path=file_path,
        filename=data.filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
