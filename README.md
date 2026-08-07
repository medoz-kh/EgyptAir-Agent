# EgyptAir MCP Server

# Memory System Implementation

## Overview

A custom memory system was implemented to enhance the AI agent's ability to maintain context, store important information, and manage conversations efficiently.

The goal was to give the agent a structured memory architecture instead of relying only on the current conversation context.

The memory system is responsible for:

* Storing recent conversation history.
* Preserving important past interactions.
* Managing long-term knowledge.
* Controlling what information should be kept or removed.

---

# Memory Architecture

The memory system is divided into multiple layers:

```
                User Conversation
                       |
                       v
              Memory Manager
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
 Short-Term       Episodic       Semantic
   Memory          Memory         Memory
```

---

# 1. Memory Manager

The `MemoryManager` acts as the central controller for all memory operations.

Responsibilities:

* Receiving new conversation data.
* Deciding where information should be stored.
* Retrieving relevant memories when needed.
* Managing communication between different memory components.

Main flow:

```
New Interaction
       |
       v
Memory Manager
       |
       +--> Store temporary context
       |
       +--> Save important events
       |
       +--> Retrieve previous knowledge
```

---

# 2. Short-Term Memory

Short-term memory stores recent conversation context.

Purpose:

* Maintain the current conversation flow.
* Allow the agent to understand references to recent messages.
* Provide immediate context during reasoning.

Example:

```
User:
My flight was delayed.

User:
Can I get compensation?

Agent:
Uses short-term memory to understand
that "my flight" refers to the delayed flight.
```

Implementation:

* Stores recent conversation turns.
* Uses a size limit to avoid unlimited memory growth.
* Removes older information when the limit is reached.

---

# 3. Episodic Memory

Episodic memory stores important events and previous interactions.

Purpose:

* Remember past experiences.
* Preserve important actions performed by the agent.
* Allow future conversations to benefit from previous events.

Example:

```
Passenger requested compensation.

Flight:
EA123

Action:
Compensation request submitted.

Result:
Request approved.
```

This allows the agent to understand previous cases and interactions.

---

# 4. Semantic Memory

Semantic memory stores reusable knowledge.

Purpose:

* Store general information.
* Keep facts that are useful across different conversations.
* Avoid repeatedly retrieving the same information.

Examples:

```
Compensation rules
Airline policies
Operational procedures
```

Unlike episodic memory, semantic memory stores knowledge rather than specific events.

---

# 5. Memory Routing

A routing mechanism was implemented to decide where information should be stored.

The agent analyzes each interaction:

```
New Information
       |
       v
Memory Router
       |
       +--> Temporary context?
       |
       +--> Important event?
       |
       +--> General knowledge?
```

Then the information is stored in the appropriate memory type.

---

# 6. Memory Consolidation

A consolidation process was added to organize stored information.

Purpose:

* Convert useful short-term information into long-term memory.
* Remove unnecessary data.
* Keep memory efficient.

Example:

```
Short-Term Memory:

User complained about delayed flight.

        |
        v

Consolidation:

Important event detected.

        |
        v

Stored in Episodic Memory.
```

---

# 7. Storage Layer

The memory system separates storage logic from memory logic.

Implemented components:

```
memory/
│
├── manager.py
├── models.py
├── short_term.py
├── episodic_store.py
├── semantic_store.py
├── consolidation.py
├── router.py
├── storage.py
└── config.py
```

Each module has a specific responsibility:

| File                | Responsibility                      |
| ------------------- | ----------------------------------- |
| `manager.py`        | Controls memory operations          |
| `models.py`         | Defines memory data structures      |
| `short_term.py`     | Handles recent conversation context |
| `episodic_store.py` | Stores past events                  |
| `semantic_store.py` | Stores reusable knowledge           |
| `router.py`         | Decides memory destination          |
| `consolidation.py`  | Transfers important information     |
| `storage.py`        | Handles persistence                 |
| `config.py`         | Stores memory configuration         |

---

# Challenges Solved

## Python Package Structure

Problem:

```
ModuleNotFoundError: No module named 'memory'
```

Cause:

The memory package used incorrect absolute imports.

Solution:

Changed internal imports from:

```python
from memory.models import ConversationTurn
```

to:

```python
from .models import ConversationTurn
```

This converted the memory folder into a proper Python package.

---

# Result

The agent now has a structured memory system capable of:

* Maintaining current conversation context.
* Remembering previous events.
* Storing reusable knowledge.
* Managing memory growth.
* Supporting more advanced autonomous agent behavior.

This memory architecture provides the foundation for building more reliable and context-aware AI agents.

---


## Short-Term Context Window Management


When operating in multi-turn support scenarios with heavy database and API outputs (flight status queries, manifest searches, disruption reports), the conversation history grows rapidly. Unmanaged context leads to **Token Budget Overflow**, **Attention Dilution** (the agent forgetting crucial early constraints like passenger names or special requests), and **increased latency**.

To solve this, we implemented and empirically benchmarked **4 Context Management Strategies**.

## 🛠️ Architecture Overview

The system delegates context manipulation to a dedicated pipeline layer (`ContextWindowManager`) before sending prompts to the Gemini API:

[ User Input / MCP Tool Result ]
│
▼
[ Raw Chat History ] ───▶ (Preserved as Ground Truth)
│
▼
[ ContextWindowManager ] ───▶ Applies Strategy (Sliding Window, Masking, Summarization, Zone Pruning)
│
▼
[ Pruned Context ] ───▶ Sent to gemini-2.5-flash API


---

## 📂 Implementation Modules

Each strategy is cleanly isolated in its own file under `mcp_client/strategies/` to promote modularity and scannability:

| Strategy File | Core Mechanism | Pros & Cons |
| :--- | :--- | :--- |
| **`sliding_window.py`** | Truncates history to keep only the last $N$ turns (e.g., last 6 messages). Safely adjusts bounds to preserve atomic `function_call` $\rightarrow$ `function_response` pairs. | ⚡ **Fast & Zero LLM Cost**<br>❌ Drops early critical context (booking IDs, passenger names). |
| **`observation_masking.py`** | Preserves all conversation turns, but replaces verbose tool outputs/JSON payloads from previous turns with lightweight placeholders (`[TOOL OUTPUT MASKED]`). | ⚡ **Low token footprint**<br>❌ Chat turn length still grows linearly. |
| **`recursive_summarization.py`** | Uses Gemini structured output (`Pydantic Schema`) to periodically compress older context into key facts, user intents, and pending action items. | 🧠 **High reasoning retention**<br>🐢 Adds latency and cost due to extra LLM summarization calls. |
| **`zone_based_pruning.py`** | Segments conversation history into 4 progressive degradation zones. Preserves protected user entity zones while purging heavy execution logs. | 🏆 **Optimal accuracy-to-token ratio**<br>⚖️ Requires careful zone boundary tuning. |

---

## 📊 Strategy Benchmark & Comparison Matrix

We evaluated all four strategies against a **long-context benchmark transcript** consisting of early entity declarations (passenger name, booking ID #3, wheelchair request) buried under heavy, multi-turn tool noise (massive JSON disruption reports and policy resource dumps).

### Empirical Evaluation Results

| Strategy | Task Accuracy (%) | Tokens Consumed | Latency (s) | Evaluation Status |
| :--- | :---: | :---: | :---: | :--- |
| **Sliding Window** | **0.0%** | **~380** | **0.72s** | ⚠️ **Failed** (Forgot booking ID #3 and wheelchair request) |
| **Observation Masking** | **100.0%** | **~1,150** | **1.10s** | ⚠️ **Sub-optimal** (Kept all turn history intact) |
| **Recursive Summarization** | **100.0%** | **~1,420** | **2.35s** | ⚠️ **Sub-optimal** (High latency from extra LLM call) |
| **Zone-Based Pruning** | **100.0%** | **~780** | **0.95s** | ✅ **SHIPPED WINNER** |

---

## 🏆 Final System Justification (Why We Shipped Zone-Based Pruning)

Our decision to ship **Zone-Based Pruning** as the primary strategy in production is backed directly by the benchmark data, rather than intuition:

1. **Accuracy Retention:** Achieved **100% accuracy** on entity retention (booking IDs, passenger assistance preferences), compared to **0% accuracy** for Naive Sliding Window.
2. **Token Efficiency:** Reduced prompt token consumption by **~45%** compared to Recursive Summarization by scrubbing raw SQLite/MCP tool payloads in Zone 2/3 without incurring extra LLM summarization overhead.
3. **Sub-second Latency:** Maintained an average latency of **0.95s**, avoiding the +1.4s latency tax required by Recursive Summarization chains.
4. **Tool Call Integrity:** Enforces pair-wise pruning to prevent `400 INVALID_ARGUMENT` errors caused by orphaned `function_response` turns.

---

## 🚀 How to Run the System & Benchmarks

### 1. Requirements & Setup

Ensure dependencies are installed and environment variables are set:

```bash
pip install google-genai pydantic python-dotenv mcp
export GEMINI_API_KEY="your-api-key-here"


---

## 🛠️ Architecture Overview

The system delegates context manipulation to a dedicated pipeline layer (`ContextWindowManager`) before sending prompts to the Gemini API:
## Retrieval Architecture Evaluation

We benchmarked Naive RAG against Hybrid Search across a 12-question domain-specific test suite covering standard baggage policies, exact rule codes (e.g., `MS-772`, `EU-261`), fleet specifications, and complex passenger scenarios.

| Architecture | Accuracy | Avg. Tokens/Query | Avg. Latency/Query |
| :--- | :--- | :--- | :--- |
| Naive RAG | 11/12 | 68 | 0.381s |
| Hybrid Search | 11/12 | 65 | 0.328s |

*(Note: Agentic multi-hop retrieval is executed dynamically by the primary Gemini agent loop during complex multi-turn sessions, resulting in higher token overhead and latency compared to single-hop retrievals.)*

### Architectural Choice & Justification
We selected **Hybrid Search (Dense Vector + BM25 via Reciprocal Rank Fusion)** as our production retrieval engine. 

While Naive RAG performs well on general semantic queries, standard dense vector embeddings frequently blur explicit alphanumeric identifiers, such as rule numbers (`MS-772`), flight numbers (`MS800`), or regulatory codes (`EU-261`). Hybrid Search combines sparse keyword matching (`rank_bm25`) with dense similarity search in ChromaDB. 

As shown in our benchmark table, Hybrid Search achieved top-tier accuracy (**11/12**) while reducing average query latency (**0.328s**) and lowering token consumption per prompt (**65 tokens**).

# Technologies

- Python
- SQLite
- FastMCP
- Model Context Protocol (MCP)
- LangChain (planned)
- JSON Schema

---

# Team

- yousef salah
- Ahmed Ashraf
- Youssef Hatem

---

> **Note:** This README represents the current development stage. Additional protocol features will be added as 
