from typing import List, Dict, Any, Optional
from .vector_store import VectorStoreManager


class NaiveRAGSearch:
    """Baseline RAG implementation using only dense similarity search."""

    def __init__(self, vector_store: VectorStoreManager):
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return self.vector_store.vector_search(
            query=query,
            n_results=n_results,
            filter_metadata=filter_metadata
        )