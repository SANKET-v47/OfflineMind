# OfflineMind — 10-Phase Complete System Architecture

OfflineMind is structured into modular layers designed to operate offline-first on Windows with zero cloud API dependencies.

```
                           +----------------------------------------+
                           |         Desktop UI (Tkinter)           |
                           |   - Live Online/Offline Status Badge   |
                           |   - Web Search Enable/Disable Toggle   |
                           |   - Document RAG Management Modal      |
                           |   - Memory Management Modal            |
                           |   - Token-by-Token Streaming Output    |
                           +-------------------+--------------------+
                                               |
                                               v
+------------------------------------------------------------------------------------------+
|                               Assistant Orchestrator                                     |
|  - Manages Context, Memory, System Prompts, Routing, Retrieval, & Response Generation    |
+----------+-----------------------+---------------------+---------------------+-----------+
           |                       |                     |                     |
           v                       v                     v                     v
   +---------------+       +---------------+     +---------------+     +---------------+
   | Query Router  |       | Structured    |     | Local RAG     |     | Safe Tools    |
   | - Local Only  |       | Memory        |     | Vector Store  |     | Sandbox       |
   | - Web Need    |       | - Short-Term  |     | - SQLite DB   |     | - AST Calc    |
   | - Docs Need   |       | - Long-Term   |     | - 128d Dense  |     | - System Info |
   | - Tool Need   |       | - Episodic    |     | - Text Chunks |     | - File Tools  |
   +-------+-------+       +---------------+     +---------------+     +---------------+
           |
           +-----------------------------+
           |                             |
           v                             v
   [Device Online?]               [Device Offline?]
           |                             |
           v                             v
   +---------------+             +---------------+
   | DuckDuckGo    |             | Strictly      |
   | Web Search    |             | Local Query   |
   | & Summarizer  |             | & Disclaimer  |
   +-------+-------+             +-------+-------+
           |                             |
           +--------------+--------------+
                          |
                          v
           +-----------------------------+
           | Local Model Manager (Ollama)|
           |  - llama3.2:1b              |
           |  - llama3.2:3b              |
           |  - phi3:mini / mistral:7b   |
           +-----------------------------+
```

---

## The 10 System Phases

### Phase 1: Local AI Chat Engine
- **Module**: `offlinemind.llm.ollama_provider`, `offlinemind.llm.model_manager`
- **Features**: Direct socket HTTP streaming communication with local Ollama daemon (`127.0.0.1:11434`). Pre-warming mechanism prevents cold-start timeouts.

### Phase 2: Internet Connectivity Detection
- **Module**: `offlinemind.web.internet_manager`
- **Features**: State machine (`ONLINE`, `OFFLINE`, `CONNECTING`, `DEGRADED`) with dual HTTP probe and socket fallback. Hardware privacy killswitch (`force_offline = True`).

### Phase 3: Web Search & Query Router
- **Module**: `offlinemind.web.search`, `offlinemind.web.router`
- **Features**: Fast DuckDuckGo HTML scraping with zero external dependencies (no BeautifulSoup required). `QueryRouter` classifies query intent into `LOCAL_ONLY`, `WEB_REQUIRED`, `WEB_OPTIONAL`, `LOCAL_DOCUMENT_REQUIRED`, and `TOOL_REQUIRED`.

### Phase 4: Local Document RAG & Vector Store
- **Module**: `offlinemind.rag.document_loader`, `offlinemind.rag.chunker`, `offlinemind.rag.embeddings`, `offlinemind.rag.vector_store`
- **Features**: Extract text from `.txt`, `.md`, `.py`, `.json`, `.pdf`, and `.docx`. Sliding window chunker with sentence boundary detection. High-performance 128-dimensional dense hashing embeddings with cosine similarity search in SQLite.

### Phase 5: Structured Memory System
- **Module**: `offlinemind.memory.memory_manager`
- **Features**: 4 tiers:
  1. *Short-Term Memory*: Rolling in-memory context buffer.
  2. *Long-Term Memory*: Key-value facts saved in `data/memory/user_profile.json`.
  3. *Episodic Memory*: Session logs saved to `data/memory/conversations/`.
  4. *Audit & Privacy Controls*: Export, import, and full memory erasure.

### Phase 6 & 7: Sandboxed System Tools & Security
- **Module**: `offlinemind.tools`
- **Features**:
  - `CalculatorTool`: Evaluates mathematical expressions using Python AST nodes. Forbids function calls, variable assignments, and shell execution.
  - `SystemInfoTool`: Read-only telemetry (CPU, RAM, OS, platform).
  - `FileTools`: Sandboxed read, write, and delete operations with mandatory confirmation flags for destructive actions.

### Phase 8: Safe Self-Updating
- **Module**: `offlinemind.updates.update_manager`
- **Features**:
  - `AppUpdateChecker`: Checks GitHub Releases for newer software versions.
  - `ModelUpdateChecker`: Recommends curated models with disk and RAM requirements, requiring explicit user approval before download.
  - `KnowledgeUpdater`: Ingests trusted web topic research directly into the local RAG database.

### Phase 9: Desktop Application & Assistant Orchestrator
- **Module**: `offlinemind.core.orchestrator`, `offlinemind.ui.gui_app`
- **Features**: Unifies all 8 preceding components into a modern Windows desktop app. Provides live status pills, Web ON/OFF toggle, modal dialogues for Documents and Memory, real-time token streaming, and generation cancellation.

### Phase 10: Packaging, Verification & Production Readiness
- **Module**: `start_offlinemind.bat`, `start_offlinemind_cli.bat`, `tests/`
- **Features**: 73 automated tests verifying all subsystems pass with 100% success rate. One-click Windows batch scripts.
