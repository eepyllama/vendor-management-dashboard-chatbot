"""
vectorstore/chroma_store.py
────────────────────────────
ChromaDB implementation of VectorStoreAdapter.

- Runs fully locally with no signup or API key.
- Data is persisted to disk at CHROMA_PERSIST_DIR (default ./data/chroma).
- Uses a single collection named "vendoriq_docs".
- ChromaDB's built-in cosine similarity is used for retrieval.
- Metadata is stored alongside each chunk so we can reconstruct
  document-level summaries without a separate database.
"""

import uuid
from collections import defaultdict

import chromadb
from chromadb.config import Settings

from .base import VectorStoreAdapter


COLLECTION_NAME = "vendoriq_docs"


class ChromaStore(VectorStoreAdapter):
    """
    Persistent ChromaDB-backed vector store.

    Parameters
    ----------
    persist_dir : str
        Directory where ChromaDB will write its SQLite + parquet files.
        Created automatically if it does not exist.
    """

    def __init__(self, persist_dir: str = "./data/chroma") -> None:
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},   # cosine similarity
        )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def add_chunks(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """
        Upsert chunks into ChromaDB.

        We use upsert (not add) so that re-ingesting the same PDF
        overwrites existing chunks instead of duplicating them.
        Chunk IDs are derived from (source, page, chunk_index) so
        they are stable across re-ingestion.
        """
        if not texts:
            return

        ids = [
            m.get("chunk_id", str(uuid.uuid4()))
            for m in metadatas
        ]

        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 4,
    ) -> list[dict]:
        """
        Query ChromaDB for the closest chunks to query_embedding.

        ChromaDB returns distances (lower = closer) when using cosine
        space, so we convert: score = 1 - distance.
        """
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for text, meta, dist in zip(documents, metadatas, distances):
            chunks.append(
                {
                    "text": text,
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page", 0),
                    "score": round(1.0 - float(dist), 4),
                }
            )

        return chunks

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def list_documents(self) -> list[dict]:
        """
        Aggregate chunk-level metadata into per-document summaries.

        We pull all metadata from the collection (documents field is
        excluded to keep the response small) and group by source.
        """
        total = self._collection.count()
        if total == 0:
            return []

        # Fetch all metadatas — ChromaDB supports this in one call
        results = self._collection.get(include=["metadatas"])
        metadatas = results.get("metadatas", [])

        # Group by source filename
        doc_map: dict[str, dict] = defaultdict(
            lambda: {"chunks": 0, "pages": set()}
        )
        for meta in metadatas:
            source = meta.get("source", "unknown")
            doc_map[source]["chunks"] += 1
            doc_map[source]["pages"].add(meta.get("page", 0))

        return [
            {
                "name": source,
                "chunks": info["chunks"],
                "pages": len(info["pages"]),
            }
            for source, info in sorted(doc_map.items())
        ]

    def delete_document(self, source: str) -> int:
        """
        Delete all chunks whose metadata `source` equals the given filename.
        Returns the number of chunks deleted.
        """
        results = self._collection.get(
            where={"source": source},
            include=["metadatas"],
        )
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def chunk_count(self) -> int:
        """Total number of chunks currently in the collection."""
        return self._collection.count()
