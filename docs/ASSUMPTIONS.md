# Project Assumptions & Design Decisions

This document outlines the foundational assumptions, engineering tradeoffs, and design choices made during the development of **OfflineMind**.

---

## 1. Operating Environment & Hardware
- **Target OS**: Windows 10/11 (with cross-platform compatibility for Linux/macOS).
- **RAM Constraints**: Normal laptop with 8 GB RAM. The entire application runs with minimal memory footprint (< 100 MB RAM for core + GUI), leaving ample headroom for OS and optional Ollama inference.
- **Python Version**: Python 3.11+ (Tested and verified on Python 3.14.6).

---

## 2. Knowledge Storage & Search Engine
- **Database Engine**: SQLite 3 with WAL (Write-Ahead Logging) mode and foreign keys enabled.
- **Full-Text Search**: SQLite FTS5 (Full-Text Search 5) extension is utilized for high-speed offline BM25-ranked keyword and token search without requiring heavyweight vector databases (like Chroma or FAISS) which could overwhelm an 8 GB RAM laptop.
- **Fact Model**: Triples of `(entity, attribute, value)` supplemented with `category`, `confidence` [0.0 - 1.0], `source`, `source_priority` (1-100, where higher is more authoritative), `version` (strictly monotonic integer), and status (`ACTIVE`, `ARCHIVED`, `NEEDS_REVIEW`).
- **Audit & History**: Facts are never deleted or silently overwritten. Every mutation records the prior state in `fact_history` with timestamps, source, and reason.

---

## 3. Local LLM & Graceful Fallback
- **Ollama Integration**: OfflineMind natively integrates with Ollama's local REST API (`http://localhost:11434/api/generate`) targeting lightweight models such as `phi3:mini` or `llama3.2:3b`.
- **Graceful Fallback**: If Ollama is not installed or the model is not currently loaded in memory, OfflineMind automatically switches to its high-precision **Retrieval-Augmented Extractive Engine (RuleBasedRetrievalQA)**. This ensures that users always receive accurate, structured answers accompanied by provenance citations (source and update date) without crashing or requiring internet connectivity.

---

## 4. Connectivity & Synchronization
- **Zero-Freeze Monitoring**: A dedicated daemon thread conducts lightweight probes (DNS socket connect on port 53 and HTTP health probe) with debouncing. The UI and query engine remain 100% non-blocking.
- **Simulated Connectivity**: For automated tests, air-gapped field demonstrations, and grading, the connectivity monitor supports simulated online/offline toggling without touching the actual OS network adapters.
- **Security & HTTPS**: External sync endpoints require HTTPS. HTTP is permitted strictly for loopback localhost (`127.0.0.1` / `localhost`) to accommodate local test mock servers.
- **Atomic Transactions & Pre-Sync Backup**: Prior to executing any sync against remote sources, OfflineMind performs a point-in-time snapshot backup using SQLite's online backup API. The sync writes occur within an atomic database transaction. If connection drops mid-sync, the transaction automatically rolls back, preventing corruption.

---

## 5. Conflict Resolution Strategy
- **Source Priority**: Higher priority sources (e.g. Official University Registrar = 90) supersede lower priority sources (e.g. Student Blog = 40).
- **Timestamp & Confidence**: When priorities are equal, newer timestamps win if confidence is equal or greater.
- **Review Queue**: Ambiguous cases (conflicting facts with identical timestamps or lower confidence from equal priority sources) are safely quarantined into a `review_queue` table for manual or programmatic review, preventing silent data pollution.

---

## 6. User Interface
- **Tkinter GUI**: Tkinter was selected as the native GUI framework. Unlike Electron or browser-based frameworks, Tkinter introduces zero background server processes, zero port conflicts, starts instantaneously, and consumes less than 30 MB of memory.
- **CLI & Demo Script**: A comprehensive CLI with subcommands (`query`, `sync`, `history`, `review`, `status`) and an end-to-end automated demo script (`demo_scenario.py`) are provided for headless, scripted, or interactive environments.
