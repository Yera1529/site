"""Chat routes with SSE streaming, RAG-augmented generation and DOCX export."""

import uuid
import json
from typing import List, Optional
from pydantic import BaseModel
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
)
from schemas.legislation import SearchLawsRequest, RetrievedLaw
from routers.auth import get_current_user
from routers.matters import get_authorized_matter
from services.ai import AIService, validate_representation, validate_law_citations
from services.rag import RAGService
from services.document import DocumentService
from models.template import DocumentTemplate

router = APIRouter(prefix="/api", tags=["chat"])


class CitationCheck(BaseModel):
    cited: List[str]
    unverified: List[str]


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
    await db.commit()

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

    tmpl_result = await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.name == data.template_name)
    )
    tmpl = tmpl_result.scalar_one_or_none()
    template_content = tmpl.extracted_text if tmpl else None
    if not template_content:
        raise HTTPException(
            status_code=404, detail=f"Шаблон «{data.template_name}» не найден"
        )

    rag = RAGService()

    query_for_kb = (
        f"представление ст.200 {data.template_name} "
        f"{data.additional_instructions or ''}"
    )
    kb_chunks = rag.query_kb(query_for_kb, top_k=5)
    kb_context = "\n\n---\n\n".join(kb_chunks) if kb_chunks else ""

    # Use user-selected laws if provided; otherwise search automatically
    if data.selected_laws and len(data.selected_laws) > 0:
        retrieved_laws = [law.model_dump() for law in data.selected_laws]
    else:
        law_query = all_text[:4000]
        if matter.description:
            law_query = f"{matter.description[:1000]} {law_query}"
        retrieved_laws = rag.search_relevant_laws(law_query, top_k=10)

    try:
        ai = AIService()
        generated = await ai.generate_document(
            template=template_content,
            facts=all_text,
            custom_instructions=matter.custom_instructions or "",
            additional_instructions=data.additional_instructions or "",
            kb_context=kb_context,
            retrieved_laws=retrieved_laws,
        )
    except Exception as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=502,
                detail=(
                    "Не удалось подключиться к ИИ-серверу. "
                    "Проверьте, что Ollama запущен и модель загружена. "
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
                template=template_content,
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
    rep = Representation(
        matter_id=data.matter_id,
        template_id=tmpl.id if tmpl else None,
        title=f"Представление — {data.template_name}",
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
        validation=ValidationReport(**validation),
        retrieved_laws=[RetrievedLaw(**law) for law in retrieved_laws],
        citation_check=CitationCheck(**citation_check),
    )


@router.post("/export-docx")
async def export_docx(
    content: dict,
    user: User = Depends(get_current_user),
):
    html_content = content.get("html", "")
    filename = content.get("filename", "document.docx")

    doc_service = DocumentService()
    file_path = doc_service.html_to_docx(html_content, filename)

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
