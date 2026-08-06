import os
import chromadb
from typing import List, Dict, Any, Optional


class VectorStoreManager:
    """
    Manages local vector store using ChromaDB with explicit HNSW index configuration
    and metadata pre-filtering support.
    """

    def __init__(
        self,
        db_path: str = "./db/chroma_db",
        collection_name: str = "egyptair_policies"
    ):
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Configure explicit HNSW ANN space index (cosine similarity)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ):
        """Adds or updates chunks in the vector collection."""
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def vector_search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes ANN vector search with optional pre-filtering on metadata.
        """
        query_kwargs = {"query_texts": [query], "n_results": n_results}
        
        # Mid/Pre-search metadata filtering
        if filter_metadata:
            query_kwargs["where"] = filter_metadata

        results = self.collection.query(**query_kwargs)

        formatted_results = []
        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
            distances = results["distances"][0] if results["distances"] else [0.0] * len(docs)
            doc_ids = results["ids"][0] if results["ids"] else [f"doc_{i}" for i in range(len(docs))]

            for doc, meta, dist, doc_id in zip(docs, metas, distances, doc_ids):
                formatted_results.append({
                    "id": doc_id,
                    "content": doc,
                    "metadata": meta,
                    "score": 1.0 - dist  # Cosine similarity score
                })

        return formatted_results

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Retrieves all documents f
        or sparse BM25 indexing."""
        data = self.collection.get()
        docs = []
        if data and data["documents"]:
            for i, doc in enumerate(data["documents"]):
                docs.append({
                    "id": data["ids"][i],
                    "content": doc,
                    "metadata": data["metadatas"][i] if data["metadatas"] else {}
                })
        return docs