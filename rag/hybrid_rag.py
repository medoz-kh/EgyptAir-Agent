import re
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from .vector_store import VectorStoreManager


def tokenize(text: str) -> List[str]:
    """Tokenizes text into lowercase alphanumeric tokens for BM25."""
    return re.findall(r"\w+", text.lower())


class HybridRAGSearch:
    """
    Combines ChromaDB vector search and BM25 sparse search using Reciprocal Rank Fusion.
    """

    def __init__(self, vector_store: VectorStoreManager):
        self.vector_store = vector_store

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        # 1. Retrieve Dense Vector Search Results
        dense_results = self.vector_store.vector_search(
            query=query,
            n_results=n_results * 2,
            filter_metadata=filter_metadata
        )

        # 2. Retrieve All Corpus Docs for BM25 Sparse Search
        all_docs = self.vector_store.get_all_documents()
        if not all_docs:
            return dense_results[:n_results]

        corpus_texts = [doc["content"] for doc in all_docs]
        tokenized_corpus = [tokenize(text) for text in corpus_texts]
        tokenized_query = tokenize(query)

        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(tokenized_query)

        # Rank documents by BM25 score
        sparse_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[: n_results * 2]

        sparse_results = []
        for idx in sparse_indices:
            if bm25_scores[idx] > 0:
                doc_item = all_docs[idx]
                sparse_results.append({
                    "id": doc_item["id"],
                    "content": doc_item["content"],
                    "metadata": doc_item["metadata"],
                    "score": float(bm25_scores[idx])
                })

        # 3. Reciprocal Rank Fusion (RRF)
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}

        # Process dense ranks
        for rank, item in enumerate(dense_results):
            doc_id = item["id"]
            doc_map[doc_id] = item
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Process sparse ranks
        for rank, item in enumerate(sparse_results):
            doc_id = item["id"]
            doc_map[doc_id] = item
            doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Sort combined results by RRF score
        sorted_doc_ids = sorted(
            doc_scores.keys(),
            key=lambda d_id: doc_scores[d_id],
            reverse=True
        )

        fused_results = []
        for d_id in sorted_doc_ids[:n_results]:
            res = doc_map[d_id]
            res["rrf_score"] = doc_scores[d_id]
            fused_results.append(res)

        return fused_results