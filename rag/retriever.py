"""
rag/retriever.py
─────────────────
Retrieval layer: turns a raw user query into a formatted context string
ready for injection into the system prompt.

Flow
----
  1. Embed the user query via EmbeddingService
  2. Run similarity search against the vector store (top-k chunks)
  3. Filter out low-confidence results (score < threshold)
  4. Format surviving chunks into a single context string, grouped by
     source document, with page citations

The retriever is intentionally thin — it does not call the LLM.
It only retrieves and formats.  The pipeline (pipeline.py) orchestrates
retrieval + generation together.
"""

import logging
import os
from dataclasses import dataclass

from services.embedding_service import EmbeddingService
from vectorstore.base import VectorStoreAdapter

logger = logging.getLogger(__name__)

# Chunks below this similarity score are discarded as irrelevant
_DEFAULT_SCORE_THRESHOLD = 0.35


@dataclass
class RetrievalResult:
    """Holds retrieved chunks and the formatted context string."""
    chunks: list[dict]        # raw chunk dicts from the vector store
    context: str              # formatted string ready for prompt injection
    sources: list[str]        # unique source filenames (for UI citation pills)


class Retriever:
    """
    Wraps embedding + vector search into a single retrieve() call.

    Parameters
    ----------
    vector_store      : the active VectorStoreAdapter
    embedding_service : for encoding the query
    top_k             : max chunks to retrieve per query
    score_threshold   : minimum similarity score to keep a chunk
    """

    def __init__(
        self,
        vector_store: VectorStoreAdapter,
        embedding_service: EmbeddingService,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> None:
        self._store = vector_store
        self._embedder = embedding_service
        self._top_k = top_k or int(os.getenv("DEFAULT_TOP_K", "3"))
        self._score_threshold = score_threshold if score_threshold is not None else float(os.getenv("SIMILARITY_THRESHOLD", "0.35"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(self, query: str) -> RetrievalResult:
        """
        Retrieve relevant chunks for a query and return a formatted result.

        If the vector store is empty, returns an empty RetrievalResult
        immediately without hitting the embedding model.

        Parameters
        ----------
        query : str
            The raw user message.

        Returns
        -------
        RetrievalResult
            .chunks  — list of raw chunk dicts (may be empty)
            .context — formatted multi-chunk string (empty str if no hits)
            .sources — deduplicated list of source filenames
        """
        # Fast path: nothing indexed yet
        docs = self._store.list_documents()
        if not docs:
            logger.debug("Vector store is empty — skipping retrieval")
            return RetrievalResult(chunks=[], context="", sources=[])

        # Embed the query
        query_embedding = self._embedder.embed_query(query)

        # Vector search
        raw_chunks = self._store.similarity_search(
            query_embedding=query_embedding,
            top_k=self._top_k,
        )

        # Deduplication check on raw text content
        seen = set()
        deduplicated = []
        for chunk in raw_chunks:
            text_content = chunk.get("text", "").strip()
            if text_content not in seen:
                seen.add(text_content)
                deduplicated.append(chunk)

        # Filter by confidence threshold
        filtered = [c for c in deduplicated if c["score"] >= self._score_threshold]

        if not filtered:
            logger.debug(
                "All %d retrieved chunks scored below threshold %.2f",
                len(raw_chunks), self._score_threshold,
            )
            return RetrievalResult(chunks=[], context="", sources=[])

        logger.debug(
            "Retrieved %d chunks (kept %d after deduplication and threshold %.2f)",
            len(raw_chunks), len(filtered), self._score_threshold,
        )

        context = _format_context(filtered)
        sources = _unique_sources(filtered)

        return RetrievalResult(chunks=filtered, context=context, sources=sources)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_context(chunks: list[dict]) -> str:
    """
    Convert a list of chunk dicts into a readable context block.
    Simplify chunk headers to contain only minimal metadata: [Source: document.pdf, Page: X]
    Bound total retrieved context string size to 2500 characters maximum.
    """
    lines: list[str] = []
    current_len = 0
    max_chars = int(os.getenv("MAX_CONTEXT_CHARS", "2500"))

    for chunk in chunks:
        source = chunk.get("source", "unknown")
        page = chunk.get("page", "?")
        text = chunk.get("text", "").strip()

        # Minimal header formatting
        header = f"[Source: {source}, Page: {page}]"
        block = f"{header}\n{text}\n\n"

        if current_len + len(block) > max_chars:
            # We must truncate this block or stop
            suffix = " ... [Context truncated]"
            remaining = max_chars - current_len - len(header) - 1 - len(suffix)
            if remaining > 0:
                truncated_text = text[:remaining]
                last_space = truncated_text.rfind(" ")
                if last_space > 0:
                    truncated_text = truncated_text[:last_space]
                truncated_text += suffix
                lines.append(header)
                lines.append(truncated_text)
            break
        else:
            lines.append(header)
            lines.append(text)
            lines.append("")
            current_len += len(block)

    return "\n".join(lines).strip()


def _unique_sources(chunks: list[dict]) -> list[str]:
    """Return deduplicated source filenames in order of first appearance."""
    seen: set[str] = set()
    sources: list[str] = []
    for chunk in chunks:
        src = chunk.get("source", "unknown")
        if src not in seen:
            seen.add(src)
            sources.append(src)
    return sources
