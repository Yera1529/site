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
    NormUsageReport,
    NormUsageItem,
    AddresseeCheck,
)
from schemas.legislation import SearchLawsRequest, RetrievedLaw
from routers.auth import get_current_user
from routers.matters import get_authorized_matter
from services.ai import AIService, validate_representation, validate_law_citations, validate_norm_usage, validate_addressee
from services.rag import RAGService
from services.rag_laws import RAGLawsService
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

    # Load extracted text from all uploaded files for this matter
    file_result = await db.execute(
        select(File).where(File.matter_id == data.matter_id)
    )
    files = file_result.scalars().all()
    files_text_parts = []
    for f in files:
        if f.extracted_text:
            label = f.original_name if hasattr(f, 'original_name') and f.original_name else (f.filename if hasattr(f, 'filename') else "документ")
            files_text_parts.append(f"[Файл: {label}]\n{f.extracted_text}")
    direct_file_context = "\n\n---\n\n".join(files_text_parts) if files_text_parts else ""

    rag = RAGService()
    combined = rag.query_combined(
        str(data.matter_id), data.message, top_k_matter=3, top_k_kb=5
    )
    rag_matter_context = "\n\n---\n\n".join(combined["matter"]) if combined["matter"] else ""
    kb_context = (
        "\n\n---\n\n".join(combined["knowledge_base"])
        if combined["knowledge_base"]
        else ""
    )

    # Combine direct file text with RAG results for full context
    if direct_file_context and rag_matter_context:
        matter_context = (
            "## Полный текст загруженных документов дела\n"
            + direct_file_context
            + "\n\n## Дополнительные релевантные фрагменты\n"
            + rag_matter_context
        )
    elif direct_file_context:
        matter_context = "## Полный текст загруженных документов дела\n" + direct_file_context
    else:
        matter_context = rag_matter_context

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
    Returns FAISS results directly — user can deselect irrelevant norms in the UI.
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

    logger.info("search-laws: query_len=%d", len(query_text))

    laws: list[dict] = []

    # Search FAISS-indexed enriched JSONL norms (primary source, 21k+ records)
    try:
        rag_laws = RAGLawsService()
        logger.info("search-laws: FAISS index=%s records=%d",
                     rag_laws._index is not None,
                     len(rag_laws._records) if rag_laws._records else 0)
        jsonl_norms = rag_laws.search(query=query_text[:3000], top_k=15)
        logger.info("search-laws: FAISS returned %d norms", len(jsonl_norms))
        for norm in jsonl_norms:
            laws.append({
                "law_title": norm["law_name"],
                "article_number": norm["article_number"],
                "text": (
                    f"{norm['original_text']}\n"
                    f"Критерии нарушения: {norm['violation_criteria']}\n"
                    f"Меры реагирования: {norm['applicable_measures']}"
                ),
                "norm_purpose": norm.get("norm_purpose", ""),
                "violation_criteria": norm.get("violation_criteria", ""),
                "applicable_measures": norm.get("applicable_measures", ""),
                "category": "enriched_jsonl",
                "score": norm.get("score", 0),
            })
    except Exception as e:
        logger.error("RAGLawsService search failed: %s", e, exc_info=True)

    # ChromaDB legislation search disabled — it contains irrelevant
    # podactov (transport, housing, mass-media, banking laws) that
    # drown out relevant FAISS codex results. FAISS has 21,462 codex norms.
    # Re-enable when ChromaDB is populated with relevant laws only.

    logger.info("search-laws: returning %d total laws", len(laws))
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
        # Search ChromaDB legislation (existing indexed laws)
        retrieved_laws = rag.search_relevant_laws(law_query, top_k=10)

        # Search FAISS-indexed enriched JSONL norms (enriched_laws_200upk.jsonl)
        try:
            rag_laws = RAGLawsService()
            # Extract organ hint from additional instructions or description
            organ_hint = None
            if data.additional_instructions:
                organ_hint = data.additional_instructions
            jsonl_norms = rag_laws.search(
                query=law_query[:3000],
                top_k=10,
                organ_filter=organ_hint,
            )
            # Merge JSONL norms with ChromaDB results, deduplicating by law+article
            seen_keys = {
                (l.get("law_title", l.get("law_name", "")), l.get("article_number", ""))
                for l in retrieved_laws
            }
            for norm in jsonl_norms:
                key = (norm["law_name"], norm["article_number"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    # Map JSONL fields to the format expected by build_generation_prompt
                    retrieved_laws.append({
                        "law_title": norm["law_name"],
                        "article_number": norm["article_number"],
                        "text": (
                            f"{norm['original_text']}\n"
                            f"Критерии нарушения: {norm['violation_criteria']}\n"
                            f"Меры реагирования: {norm['applicable_measures']}"
                        ),
                        "norm_purpose": norm.get("norm_purpose", ""),
                        "violation_criteria": norm.get("violation_criteria", ""),
                        "applicable_measures": norm.get("applicable_measures", ""),
                        "category": "enriched_jsonl",
                        "score": norm.get("score", 0),
                    })
            logger.info(
                "generate_document: merged %d ChromaDB + %d JSONL norms = %d total",
                len(retrieved_laws) - len(jsonl_norms), len(jsonl_norms), len(retrieved_laws)
            )
        except Exception as e:
            logger.warning("RAGLawsService search failed (non-fatal): %s", e)

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
        # Detailed logging of what goes into prompt
        logger.info(
            "generate_document: sending %d laws to prompt builder",
            len(retrieved_laws) if retrieved_laws else 0
        )
        if retrieved_laws:
            for i, law in enumerate(retrieved_laws[:5]):
                logger.info(
                    "  law[%d]: title=%s art=%s purpose=%s text_len=%d",
                    i, law.get("law_title", "")[:50], law.get("article_number", ""),
                    law.get("norm_purpose", "N/A"), len(law.get("text", ""))
                )
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

    # ── Norm usage validation: check all selected norms are cited ──
    norm_check = validate_norm_usage(generated, retrieved_laws)
    logger.info(
        "generate_document: norm_check all_used=%s used=%d unused=%d",
        norm_check["all_used"], len(norm_check["used"]), len(norm_check["unused"])
    )

    # Auto-retry if norms are not cited
    if not norm_check["all_used"] and norm_check["unused"]:
        unused_list = "\n".join(
            f"- {n['law']} {n['article']}" for n in norm_check["unused"]
        )
        logger.warning(
            "generate_document: %d norms not cited, retrying with explicit fix prompt",
            len(norm_check["unused"])
        )
        try:
            fix_prompt = (
                f"В документе НЕ использованы следующие нормы, "
                f"которые ОБЯЗАТЕЛЬНО должны быть процитированы:\n{unused_list}\n\n"
                f"Добавь для КАЖДОЙ из них:\n"
                f"1. Конкретное нарушение в основной части документа со ссылкой на эту статью\n"
                f"2. Конкретную меру в разделе ПРЕДЛАГАЮ со ссылкой на эту норму\n\n"
                f"НЕ удаляй существующие нарушения и меры — ДОБАВЬ новые.\n"
                f"Верни ПОЛНЫЙ документ (все разделы) в HTML.\n\n"
                f"Исходный документ:\n{generated}"
            )
            system_fix = (
                "Ты — юридический редактор. Дополни представление по ст.200 УПК РК "
                "недостающими нормами. Сохрани весь существующий текст и структуру."
            )
            generated_v2 = await ai._call_llm(system_fix, fix_prompt)
            if generated_v2 and len(generated_v2) > len(generated) * 0.5:
                norm_check_v2 = validate_norm_usage(generated_v2, retrieved_laws)
                original_unused = len(norm_check["unused"])
                if len(norm_check_v2["unused"]) < original_unused:
                    generated = generated_v2
                    norm_check = norm_check_v2
                    validation = validate_representation(generated)
                    citation_check = validate_law_citations(generated, retrieved_laws)
                    logger.info(
                        "generate_document: retry improved — unused norms: %d → %d",
                        original_unused, len(norm_check_v2["unused"])
                    )
        except Exception as e:
            logger.warning("generate_document: norm-fix retry failed: %s", e)

    # ── Addressee validation ──
    addressee_check = validate_addressee(generated)
    if not addressee_check["ok"]:
        logger.warning(
            "generate_document: BAD ADDRESSEE — %s", addressee_check["reason"]
        )

    # Legacy retry for missing sections (kept for backward compat)
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

    # Build extended validation result with norm and addressee info
    extended_validation = {
        **validation,
        "norm_usage": norm_check,
        "addressee": addressee_check,
    }

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
        validation_result=json.dumps(extended_validation),
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
        norm_usage=NormUsageReport(
            all_used=norm_check["all_used"],
            used=[NormUsageItem(**n) for n in norm_check["used"]],
            unused=[NormUsageItem(**n) for n in norm_check["unused"]],
        ),
        addressee_check=AddresseeCheck(**addressee_check),
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
