"""
api/main.py
────────────
FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

import logging
import mimetypes
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Fix MIME type mapping issues on Windows systems
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from api.dependencies import get_pipeline
from api.routes import chat, documents, ingest, metrics

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: warm up heavy singletons before the first request
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting VendorIQ RAG backend…")
    try:
        # This triggers lru_cache on all three singletons:
        # get_vector_store(), get_embedding_service(), get_llm_service()
        get_pipeline()
        logger.info("All services ready ✓")
    except Exception as exc:
        logger.error("Startup failed: %s", exc)
        raise
    yield
    logger.info("Shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="VendorIQ RAG API",
    version="1.0.0",
    description="LangChain · ChromaDB · Groq — production RAG backend",
    lifespan=lifespan,
)

# CORS — allow the frontend (single HTML file opened locally or served)
raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:8000")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(chat.router,      prefix="/api", tags=["chat"])
app.include_router(metrics.router,   prefix="/api", tags=["metrics"])
app.include_router(ingest.router,    prefix="/api", tags=["ingest"])
app.include_router(documents.router, prefix="/api", tags=["documents"])


# ---------------------------------------------------------------------------
# Health check — cached result to avoid live Groq token spend per poll
# ---------------------------------------------------------------------------

import asyncio
import time

_health_cache: dict = {"result": None, "ts": 0.0}
_HEALTH_TTL = 30  # seconds


@app.get("/api/health", tags=["health"])
async def health():
    """
    Liveness check — verifies Groq connectivity.
    Result is cached for 30 seconds so the frontend can poll freely
    without burning Groq API tokens on every call.
    """
    from services.llm_service import get_llm_service
    from vectorstore import get_vector_store

    now = time.monotonic()
    if _health_cache["result"] and (now - _health_cache["ts"]) < _HEALTH_TTL:
        return _health_cache["result"]

    llm_status = await get_llm_service().health_check()
    doc_count = len(get_vector_store().list_documents())

    result = {
        "status": "ok" if llm_status["ok"] else "degraded",
        "llm": llm_status,
        "indexed_documents": doc_count,
    }
    _health_cache["result"] = result
    _health_cache["ts"] = now
    return result


# ---------------------------------------------------------------------------
# Serve the frontend from /
# ---------------------------------------------------------------------------

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
