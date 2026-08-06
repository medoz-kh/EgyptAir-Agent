import time
import json
import os
import sys

# Ensure the parent directory is in the path so we can import 'rag'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.vector_store import VectorStoreManager
from rag.naive_rag import NaiveRAGSearch
from rag.hybrid_rag import HybridRAGSearch


def load_test_suite(filepath: str = "retrieval_eval/test_suite.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_accuracy(retrieved_chunks, expected_keywords):
    """
    Checks if the retrieved chunks contain the expected keywords.
    In a real-world scenario, you might use an LLM-as-a-judge here.
    For this evaluation, keyword matching on the chunks is a solid proxy.
    """
    combined_text = " ".join([chunk["content"].lower() for chunk in retrieved_chunks])

    hits = 0
    for kw in expected_keywords:
        if kw.lower() in combined_text:
            hits += 1

    # If we found at least half the keywords, we count it as a "correct" retrieval
    return 1 if (hits / len(expected_keywords)) >= 0.5 else 0


def estimate_tokens(text: str) -> int:
    """Rough estimation of tokens (1 token ~= 4 characters)."""
    return len(text) // 4


def run_evaluation():
    print("🚀 Initializing Vector Store and Search Engines...")
    vector_store = VectorStoreManager(db_path="./db/chroma_db")
    naive_rag = NaiveRAGSearch(vector_store)
    hybrid_rag = HybridRAGSearch(vector_store)

    test_suite = load_test_suite()

    results = {
        "Naive RAG": {"correct": 0, "total_time": 0.0, "total_tokens": 0},
        "Hybrid Search": {"correct": 0, "total_time": 0.0, "total_tokens": 0}
    }

    total_questions = len(test_suite)

    print(f"📊 Running evaluation on {total_questions} questions...\n")

    for q in test_suite:
        query = q["query"]
        expected = q["expected_keywords"]

        # --- Evaluate Naive RAG ---
        start_time = time.time()
        naive_chunks = naive_rag.search(query=query, n_results=3)
        naive_time = time.time() - start_time

        naive_correct = calculate_accuracy(naive_chunks, expected)
        naive_tokens = sum([estimate_tokens(c["content"]) for c in naive_chunks])

        results["Naive RAG"]["correct"] += naive_correct
        results["Naive RAG"]["total_time"] += naive_time
        results["Naive RAG"]["total_tokens"] += naive_tokens

        # --- Evaluate Hybrid Search ---
        start_time = time.time()
        hybrid_chunks = hybrid_rag.search(query=query, n_results=3)
        hybrid_time = time.time() - start_time

        hybrid_correct = calculate_accuracy(hybrid_chunks, expected)
        hybrid_tokens = sum([estimate_tokens(c["content"]) for c in hybrid_chunks])

        results["Hybrid Search"]["correct"] += hybrid_correct
        results["Hybrid Search"]["total_time"] += hybrid_time
        results["Hybrid Search"]["total_tokens"] += hybrid_tokens

    # --- Generate Markdown Table ---
    print("\n✅ Evaluation Complete! Here is the Markdown table for your README.md:\n")
    print("| Architecture | Accuracy | Avg. Tokens/Query | Avg. Latency/Query |")
    print("| :--- | :--- | :--- | :--- |")

    for arch in ["Naive RAG", "Hybrid Search"]:
        accuracy = f"{results[arch]['correct']}/{total_questions}"
        avg_tokens = int(results[arch]['total_tokens'] / total_questions)
        avg_latency = round(results[arch]['total_time'] / total_questions, 3)

        print(f"| {arch} | {accuracy} | {avg_tokens} | {avg_latency}s |")

    print(
        "\n*(Note: Agentic RAG requires an autonomous multi-hop loop, which is handled directly by the Gemini agent in your live session, so its token usage and latency will naturally be much higher.)*")


if __name__ == "__main__":
    run_evaluation()
