"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import init_db
import models
from routers import auth, matters, files, chat, settings as settings_router
from routers.templates import router as templates_router
from routers.knowledge_base import router as kb_router
from routers.legislation import router as legislation_router
from routers.representations import router as representations_router
from routers.rag_laws import router as rag_laws_router
from routers.templates_sd import router as templates_sd_router


import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Pre-warm RAGService in background thread so the first API request
    # doesn't block the event loop while SentenceTransformer loads (~30s)
    asyncio.create_task(asyncio.to_thread(_init_rag))
    # Pre-warm RAGLawsService (FAISS index for enriched_laws_200upk.jsonl)
    asyncio.create_task(asyncio.to_thread(_init_rag_laws))
    yield


def _init_rag():
    try:
        from services.rag import RAGService
        RAGService()
        import logging
        logging.getLogger(__name__).info("RAGService pre-warmed successfully")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("RAGService pre-warm failed: %s", e)


def _init_rag_laws():
    try:
        from services.rag_laws import RAGLawsService
        svc = RAGLawsService()
        stats = svc.get_stats()
        import logging
        logging.getLogger(__name__).info(
            "RAGLawsService pre-warmed: %d records indexed", stats["total_records"]
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("RAGLawsService pre-warm failed: %s", e)



app = FastAPI(
    title="ПредставлениеAi API",
    description="Юридический помощник на базе ИИ — МВД РК",
    version="2.0.0",
    lifespan=lifespan,
)

config = get_settings()
origins = [o.strip() for o in config.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(matters.router)
app.include_router(files.router)
app.include_router(chat.router)
app.include_router(settings_router.router)
app.include_router(templates_router)
app.include_router(kb_router)
app.include_router(legislation_router)
app.include_router(representations_router)
app.include_router(rag_laws_router)
app.include_router(templates_sd_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
