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

from dotenv import load_dotenv

from rag.pipeline import RAGPipeline
from rag.retriever import Retriever
from services.embedding_service import get_embedding_service
from services.llm_service import get_llm_service
from vectorstore import get_vector_store

load_dotenv()
logger = logging.getLogger(__name__)


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
