from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.v1.router import router as api_v1_router
from core.config import config
from dependencies.clients import get_qdrant_client, get_redis_client
from dependencies.services import (
    get_embedding_registry,
    get_google_oauth2_service,
    get_sparse_encoder,
)
from dependencies.db import engine
from exceptions.handler import register_exception_handlers
from models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    get_qdrant_client()
    get_redis_client()
    get_embedding_registry()
    get_sparse_encoder()
    yield
    await get_qdrant_client().close()
    await get_redis_client().close()


app = FastAPI(title="RAG Chatbot API", lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="oauth_state",
)

app.include_router(api_v1_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "RAG Chatbot API"}
