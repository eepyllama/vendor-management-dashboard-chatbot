"""
rag/ingestion.py
─────────────────
PDF ingestion pipeline.

Flow
----
  1. Receive a PDF file (bytes + filename)
  2. Write to a temp file so LangChain's PyPDFLoader can read it
  3. Split text into overlapping chunks via RecursiveCharacterTextSplitter
  4. Generate embeddings for all chunks in one batched call
  5. Upsert chunks + embeddings + metadata into the vector store
  6. Return an IngestionResult summary for the API response

Chunk ID scheme
---------------
  "<sanitised_filename>_p<page>_c<chunk_index>"
  e.g. "finserv_msa_p3_c2"

This makes chunk IDs stable and deterministic — re-ingesting the same
PDF overwrites existing chunks (via upsert) rather than duplicating them.
"""

import logging
import os
import re
import tempfile
from dataclasses import dataclass

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from services.embedding_service import EmbeddingService
from vectorstore.base import VectorStoreAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IngestionResult:
    filename: str
    pages: int
    chunks: int
    skipped_pages: int       # pages with no extractable text (scanned images)


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

async def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    vector_store: VectorStoreAdapter,
    embedding_service: EmbeddingService,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> IngestionResult:
    """
    Ingest a PDF into the vector store.

    Parameters
    ----------
    file_bytes    : raw PDF bytes from the uploaded file
    filename      : original filename (used as metadata + chunk ID prefix)
    vector_store  : destination vector store (ChromaDB or other adapter)
    embedding_service : for generating chunk embeddings
    chunk_size    : override DEFAULT_CHUNK_SIZE from env
    chunk_overlap : override DEFAULT_CHUNK_OVERLAP from env
    """
    _chunk_size = chunk_size or int(os.getenv("DEFAULT_CHUNK_SIZE", "750"))
    _chunk_overlap = chunk_overlap or int(os.getenv("DEFAULT_CHUNK_OVERLAP", "150"))

    logger.info(
        "Ingesting '%s' — chunk_size=%d overlap=%d",
        filename, _chunk_size, _chunk_overlap,
    )

    # ------------------------------------------------------------------
    # 1. Write bytes to a temp file (PyPDFLoader requires a file path)
    # ------------------------------------------------------------------
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        # --------------------------------------------------------------
        # 2. Load PDF pages via LangChain
        # --------------------------------------------------------------
        loader = PyPDFLoader(tmp_path)
        pages = loader.load()          # list[Document], one per page
        total_pages = len(pages)
        logger.info("Loaded %d pages from '%s'", total_pages, filename)

        # --------------------------------------------------------------
        # 3. Split each page into overlapping chunks
        # --------------------------------------------------------------
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=_chunk_size,
            chunk_overlap=_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        chunks: list[str] = []
        metadatas: list[dict] = []
        skipped = 0
        prefix = _sanitise(filename)

        for page_doc in pages:
            page_num = page_doc.metadata.get("page", 0) + 1   # 1-indexed
            text = page_doc.page_content.strip()

            if not text:
                skipped += 1
                continue

            page_chunks = splitter.split_text(text)

            for i, chunk_text in enumerate(page_chunks):
                chunk_id = f"{prefix}_p{page_num}_c{i}"
                chunks.append(chunk_text)
                metadatas.append(
                    {
                        "source": filename,
                        "page": page_num,
                        "chunk_id": chunk_id,
                    }
                )

        if not chunks:
            logger.warning(
                "No text extracted from '%s' — may be a scanned PDF", filename
            )
            return IngestionResult(
                filename=filename,
                pages=total_pages,
                chunks=0,
                skipped_pages=skipped,
            )

        logger.info(
            "Split into %d chunks (%d pages skipped)", len(chunks), skipped
        )

        # --------------------------------------------------------------
        # 4. Generate embeddings (batched)
        # --------------------------------------------------------------
        logger.info("Generating embeddings for %d chunks…", len(chunks))
        embeddings = embedding_service.embed_documents(chunks)
        logger.info("Embeddings done")

        # --------------------------------------------------------------
        # 5. Upsert into vector store
        # --------------------------------------------------------------
        vector_store.add_chunks(
            texts=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(
            "Upserted %d chunks for '%s' into vector store", len(chunks), filename
        )

    finally:
        # Always clean up the temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return IngestionResult(
        filename=filename,
        pages=total_pages,
        chunks=len(chunks),
        skipped_pages=skipped,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitise(filename: str) -> str:
    """
    Convert a filename into a safe string for use in chunk IDs.
    e.g. "FinServ MSA 2024.pdf" → "finserv_msa_2024"
    """
    name = os.path.splitext(filename)[0]          # strip extension
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)       # non-alphanum → underscore
    name = name.strip("_")
    return name or "doc"
