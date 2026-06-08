"""
api/dependencies.py
────────────────────
Shared FastAPI dependencies injected into route handlers.

All heavy objects (vector store, embedding model, LLM client, pipeline)
are created once at startup and reused across every request.
"""

import logging
import os
from functools import lru_cache

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from dotenv import load_dotenv

from rag.pipeline import RAGPipeline
from rag.retriever import Retriever
from services.embedding_service import get_embedding_service
from services.llm_service import get_llm_service
from vectorstore import get_vector_store

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API Key Authentication
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> str:
    """
    Dependency that enforces X-API-KEY header authentication.

    Set API_KEY in your .env file. If API_KEY is not configured,
    authentication is skipped (development convenience only).

    Usage in a route:
        @router.post("/chat")
        async def chat(request: ..., _auth: str = Depends(require_api_key)):
    """
    configured_key = os.getenv("API_KEY", "")

    # If no API_KEY is set in env, skip auth (dev mode)
    if not configured_key:
        logger.warning(
            "API_KEY is not set — authentication is disabled. "
            "Set API_KEY in your .env before deploying."
        )
        return "unauthenticated"

    if not key or key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key. Set X-API-KEY header.",
        )
    return key

# ---------------------------------------------------------------------------
# Pipeline singleton
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_pipeline() -> RAGPipeline:
    """
    Build and return the singleton RAGPipeline.

    Called once on first request; cached for the lifetime of the process.
    """
    vector_store = get_vector_store()
    embedding_service = get_embedding_service()
    llm = get_llm_service()

    retriever = Retriever(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    logger.info("RAG pipeline initialised")
    return RAGPipeline(retriever=retriever, llm=llm)
