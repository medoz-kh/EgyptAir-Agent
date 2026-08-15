# EgyptAir Agent — Execution Demo & Pipeline Logs

This document provides execution logs and CLI output traces demonstrating all core memory, context, retrieval, and guardrail mechanisms operating under live conditions.

---

## 1. Promote-or-Drop Router (Buffer Eviction & Filtering)

Demonstrating short-term memory buffer evaluation where trivial noise is dropped/forgotten while key operational facts survive into episodic storage.

```text
[MEMORY ROUTER] Evaluating 2 short-term buffer items for promotion...

Item 1: "User said hello and asked how the weather was in Cairo."
  └─ Score: 0.12 (Threshold: 0.60)
  └─ Action: DROPPED / FORGOTTEN (Low informational density)

Item 2: "User confirmed booking preference for Flight MS800, Seat 12A, vegetarian meal requested."
  └─ Score: 0.88 (Threshold: 0.60)
  └─ Action: PROMOTED -> Saved to Episodic Memory Store [Episode ID: ep_9841]
```

---

## 2. Memory Consolidation Resolving a Contradiction

Demonstrating long-term consolidation scanning episodic memory, detecting conflicting policy statements, and resolving them into a single canonical record.

```text
[MEMORY CONSOLIDATION] Scanning 12 episodic records for semantic conflicts...

⚠️ Contradiction Detected:
  ├─ Fact A (ep_102): "Economy class international baggage allowance is 20kg." (Date: 2026-05-10)
  └─ Fact B (ep_405): "Updated economy class international baggage allowance is 1 checked bag up to 23kg." (Date: 2026-08-01)

[RESOLVER] Applying recency and official policy precedence rule...
✅ Contradiction Resolved:
  └─ Retained Canonical Fact: "Economy class international baggage allowance is 1 checked bag up to 23kg."
  └─ Deprecated Fact A (ep_102 archived).
```

---

## 3. Context Strategies Execution

Demonstrating all four context management strategies running across the test suite:

| Strategy | Total Tokens | Query Latency | Retrieval Accuracy |
| :--- | :--- | :--- | :--- |
| **Raw / Full Context** | 1,420 tokens | 1.120s | 11/12 |
| **Truncated / Sliding Window** | 450 tokens | 0.280s | 8/12 |
| **Summarized Context** | 310 tokens | 0.450s | 9/12 |
| **RAG-Grounded Context** | **65 tokens** | **0.328s** | **11/12** |

```text
[CONTEXT ENGINE] Strategy Selected: RAG-Grounded Context
[CONTEXT ENGINE] Compression Ratio: 95.4% reduction (1,420 tokens -> 65 tokens)
```

---

## 4. Multi-Architecture Retrieval Comparison

Executing the same query across all retrieval architectures:  
**Query:** *"What is the penalty fee under rebooking rule MS-772?"*

### Architecture 1: Naive Dense RAG
```text
[NAIVE RAG] Query: "What is the penalty fee under rebooking rule MS-772?"
[CHROMA DB] Top Match ID: policy_1 (Baggage Allowance) | Score: 0.42
[OUTPUT]: "General rebooking fees depend on ticket class and route..." (Missed exact rule code)
```

### Architecture 2: Hybrid Search (Dense + BM25 RRF)
```text
[HYBRID SEARCH] Query: "What is the penalty fee under rebooking rule MS-772?"
[BM25] Matched Keyword: "MS-772" (Score: 4.81)
[CHROMA DB] Vector Match: "Rule MS-772 Fees" (Score: 0.89)
[RRF FUSION] Final Rank 1: policy_2 ("Rule MS-772 Fees")
[OUTPUT]: "Under penalty rule MS-772, class Y rebooking incurs a mandatory $50 fee."
```

### Architecture 3: Agentic Multi-Hop RAG
```text
[AGENTIC RAG] Step 1: Query policies database for "MS-772".
[AGENTIC RAG] Step 2: Retrieve policy text -> Found $50 rebooking fee.
[AGENTIC RAG] Step 3: Query passenger context -> Confirm ticket is class Y.
[OUTPUT]: "Your class Y ticket under rule MS-772 incurs a $50 rebooking fee."
```

---

## 5. Self-RAG Verification Guardrail

Demonstrating Self-RAG inspecting retrieved context chunks for relevance and checking generated responses for groundedness.

### Scenario A: Irrelevant Chunk Caught & Filtered
```text
[SELF-RAG] Inspecting Retrieved Chunk ID: policy_5 ("Fleet Wi-Fi")
[QUERY]: "Can I bring my cat on the flight?"
[VERIFIER] Groundedness Check: FAIL (Chunk discusses Boeing 777 Wi-Fi, irrelevant to pet policy)
[ACTION]: Chunk discarded from context window.
```

### Scenario B: Relevant Chunk Passed & Verified
```text
[SELF-RAG] Inspecting Retrieved Chunk ID: policy_4 ("Pet Policy")
[QUERY]: "Can I bring my cat on the flight?"
[VERIFIER] Groundedness Check: PASS (Relevance Score: 0.96)
[ACTION]: Context passed to Gemini for generation.
```
---

### `planning_eval/README.md`

```markdown
# 🧪 QA & Ops: Planning & Grounding Evaluation Harness

This folder contains the complete test harness and benchmarks for **Person 3 (QA & Ops)**.

## 📂 Structure
- `dataset.py`: Benchmark suite of static vs. dynamic tasks and seat conflict scenarios.
- `eval_harness.py`: Automated benchmarking script generating execution metrics.
- `../self_correction/`: Implementations of **Self-Refine** and **Reflexion**.

## 📊 Evaluation Tradeoff Summary

1. **Static vs. Dynamic Decomposition:**
   - **Static Decomposition (PS):** Best for linear, single-intent queries (`TC01`). Lowest latency (~0.8s) and minimal token overhead.
   - **Dynamic Decomposition (ToT / LATS):** Essential for complex, state-dependent decisions (`TC02`, `TC03`, `TC04`). Automatically adapts when tool executions fail.

2. **Algorithm Tradeoff Matrix:**
   - **Plan-and-Solve (PS):** High speed, low cost, but unable to recover from state collisions.
   - **Tree of Thoughts (ToT):** Excellent for evaluating multi-variable tradeoffs without state mutation.
   - **LATS:** Highest resilience. Integrates SQLite state feedback to backpropagate failure nodes and select valid branches.