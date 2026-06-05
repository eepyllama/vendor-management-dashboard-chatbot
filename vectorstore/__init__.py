"""
vectorstore/__init__.py
────────────────────────
Factory function that reads VECTOR_STORE from the environment and
returns the appropriate VectorStoreAdapter implementation.

Usage (in dependencies.py):
    from vectorstore import get_vector_store
    store = get_vector_store()
"""

import os
from .base import VectorStoreAdapter


def get_vector_store() -> VectorStoreAdapter:
    """
    Instantiate and return the configured vector store.

    Reads:
        VECTOR_STORE        — "chroma" (default) or "pinecone"
        CHROMA_PERSIST_DIR  — path for ChromaDB persistence
        PINECONE_API_KEY    — required when VECTOR_STORE=pinecone
        PINECONE_INDEX      — required when VECTOR_STORE=pinecone
    """
    store_type = os.getenv("VECTOR_STORE", "chroma").lower()

    if store_type == "chroma":
        from .chroma_store import ChromaStore
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
        return ChromaStore(persist_dir=persist_dir)

    if store_type == "pinecone":
        from .pinecone_store import PineconeStore
        api_key = os.getenv("PINECONE_API_KEY", "")
        index_name = os.getenv("PINECONE_INDEX", "vendoriq")
        if not api_key:
            raise ValueError(
                "PINECONE_API_KEY must be set when VECTOR_STORE=pinecone"
            )
        return PineconeStore(api_key=api_key, index_name=index_name)

    raise ValueError(
        f"Unknown VECTOR_STORE value: '{store_type}'. "
        "Supported values: chroma, pinecone"
    )


__all__ = ["get_vector_store", "VectorStoreAdapter"]
