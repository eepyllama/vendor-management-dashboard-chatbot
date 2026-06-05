"""
api/routes/ingest.py
─────────────────────
POST /api/ingest — accept a PDF upload and run the ingestion pipeline.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from api.dependencies import get_pipeline
from rag.ingestion import ingest_pdf
from rag.pipeline import RAGPipeline
from services.embedding_service import get_embedding_service
from vectorstore import get_vector_store

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestResponse(BaseModel):
    filename: str
    pages: int
    chunks: int
    skipped_pages: int
    message: str


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    chunk_size: int = Form(default=None),
    chunk_overlap: int = Form(default=None),
    _pipeline: RAGPipeline = Depends(get_pipeline),   # ensures singletons are warm
):
    """
    Upload and index a PDF file.

    Accepts multipart/form-data with:
      - file          : the PDF binary
      - chunk_size    : optional int override
      - chunk_overlap : optional int override
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    max_bytes = 50 * 1024 * 1024   # 50 MB
    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    try:
        result = await ingest_pdf(
            file_bytes=file_bytes,
            filename=file.filename,
            vector_store=get_vector_store(),
            embedding_service=get_embedding_service(),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except Exception as exc:
        logger.exception("Ingestion failed for '%s': %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    if result.chunks == 0:
        return IngestResponse(
            filename=result.filename,
            pages=result.pages,
            chunks=0,
            skipped_pages=result.skipped_pages,
            message=(
                "No text could be extracted. The PDF may be scanned or image-based."
            ),
        )

    return IngestResponse(
        filename=result.filename,
        pages=result.pages,
        chunks=result.chunks,
        skipped_pages=result.skipped_pages,
        message=(
            f"Successfully indexed {result.chunks} chunks "
            f"from {result.pages} pages."
        ),
    )
