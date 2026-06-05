"""
api/routes/documents.py
────────────────────────
GET  /api/documents        — list all indexed documents
DELETE /api/documents/{name} — remove a document from the vector store
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_pipeline
from rag.pipeline import RAGPipeline
from vectorstore import get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter()


class DocumentSummary(BaseModel):
    name: str
    chunks: int
    pages: int


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary]
    total_chunks: int


@router.get("/documents", response_model=DocumentsResponse)
async def list_documents(
    _pipeline: RAGPipeline = Depends(get_pipeline),
):
    """Return all indexed documents with chunk and page counts."""
    docs = get_vector_store().list_documents()
    total = sum(d["chunks"] for d in docs)
    return DocumentsResponse(
        documents=[DocumentSummary(**d) for d in docs],
        total_chunks=total,
    )


@router.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    _pipeline: RAGPipeline = Depends(get_pipeline),
):
    """Delete all chunks for the given document filename."""
    deleted = get_vector_store().delete_document(filename)
    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' not found in the index.",
        )
    logger.info("Deleted %d chunks for '%s'", deleted, filename)
    return {"deleted": deleted, "filename": filename}
