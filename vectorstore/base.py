"""
vectorstore/base.py
────────────────────
Abstract base class that every vector store adapter must implement.

Any new store (Pinecone, Weaviate, Qdrant …) only needs to subclass
VectorStoreAdapter and implement the four methods below.  The rest of
the RAG pipeline never imports a concrete store directly — it always
works through this interface.
"""

from abc import ABC, abstractmethod


class VectorStoreAdapter(ABC):
    """
    Minimal interface that every vector store implementation must satisfy.
    """

    # ------------------------------------------------------------------
    # Write path (ingestion)
    # ------------------------------------------------------------------

    @abstractmethod
    def add_chunks(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """
        Persist a batch of pre-computed text chunks with their embeddings
        and associated metadata.

        Parameters
        ----------
        texts : list[str]
            The raw chunk text strings.
        embeddings : list[list[float]]
            One embedding vector per chunk (must be same length as texts).
        metadatas : list[dict]
            One metadata dict per chunk.  Recommended keys:
              - source   : str  — original filename
              - page     : int  — page number within the PDF
              - chunk_id : str  — stable unique id (e.g. "<source>_p<page>_<i>")
        """

    # ------------------------------------------------------------------
    # Read path (retrieval)
    # ------------------------------------------------------------------

    @abstractmethod
    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
    ) -> list[dict]:
        """
        Return the top-k most similar chunks to the query embedding.

        Parameters
        ----------
        query_embedding : list[float]
            The embedding of the user's query.
        top_k : int
            Maximum number of results to return.

        Returns
        -------
        list[dict]
            Each dict contains at minimum:
              - text     : str   — the chunk text
              - source   : str   — original filename
              - page     : int   — page number
              - score    : float — similarity score (higher = more similar)
        """

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    @abstractmethod
    def list_documents(self) -> list[dict]:
        """
        Return a summary of every document that has been indexed.

        Returns
        -------
        list[dict]
            Each dict contains:
              - name   : str — filename
              - chunks : int — number of chunks indexed for this file
              - pages  : int — total pages in the original PDF
        """

    @abstractmethod
    def delete_document(self, source: str) -> int:
        """
        Delete all chunks that belong to the given source filename.

        Parameters
        ----------
        source : str
            The filename used as the `source` metadata field at ingest time.

        Returns
        -------
        int
            Number of chunks deleted.
        """
