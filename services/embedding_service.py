"""
services/embedding_service.py
──────────────────────────────
Local embedding service using HuggingFace sentence-transformers.

Model: BAAI/bge-small-en-v1.5
  - 384-dimensional vectors
  - ~130 MB download on first use, cached in ~/.cache/huggingface
  - Runs on CPU — no GPU required
  - No API key, no cost, no rate limits

BGE models perform best with a query prefix for asymmetric tasks
(query vs. document retrieval).  We apply it automatically when
embedding queries but not when embedding document chunks.

Usage
-----
    svc = EmbeddingService()
    doc_vecs  = svc.embed_documents(["chunk one", "chunk two"])
    query_vec = svc.embed_query("which contracts expire soon?")
"""

import logging
import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# BGE models use this prefix to signal "this is a search query"
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingService:
    """
    Wraps a SentenceTransformer model for both document and query embedding.

    The model is loaded once and reused for all calls.  Loading takes
    ~2–4 seconds on first startup; subsequent calls are fast.

    Parameters
    ----------
    model_name : str
        HuggingFace model identifier.  Reads EMBEDDING_MODEL from env
        if not supplied explicitly.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
        )
        logger.info("Loading embedding model: %s", self._model_name)
        self._model = SentenceTransformer(self._model_name)
        logger.info(
            "Embedding model loaded — vector dim: %d",
            self._model.get_sentence_embedding_dimension(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of document chunks.

        No query prefix is applied — these are the passage side of the
        asymmetric retrieval task.

        Returns
        -------
        list[list[float]]
            One float vector per input text.
        """
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,   # cosine similarity works on unit vecs
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single search query.

        Applies the BGE query prefix so the model knows to optimise
        for retrieval rather than semantic similarity.

        Returns
        -------
        list[float]
            A single embedding vector.
        """
        prefixed = _BGE_QUERY_PREFIX + query.strip()
        vector = self._model.encode(
            prefixed,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vector.tolist()

    @property
    def dimension(self) -> int:
        """Embedding vector dimensionality."""
        return self._model.get_sentence_embedding_dimension()


# ---------------------------------------------------------------------------
# Module-level singleton — created once, reused across all requests
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """
    Return the shared EmbeddingService instance.

    Using lru_cache ensures the model is loaded exactly once even if
    this function is called from multiple FastAPI dependencies.
    """
    return EmbeddingService()
