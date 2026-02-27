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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
