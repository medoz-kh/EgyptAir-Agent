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