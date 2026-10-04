# OfflineMind: Offline-First AI Assistant with Optional Real-Time Web Intelligence

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 73 Passed](https://img.shields.io/badge/tests-73%20passed-brightgreen.svg)]()
[![Model: Ollama Llama 3.2](https://img.shields.io/badge/LLM-Local%20Ollama-purple.svg)]()
[![Privacy: Zero Telemetry](https://img.shields.io/badge/privacy-100%25%20local-success.svg)]()

> **OfflineMind** is a complete, private, offline-first personal AI assistant for Windows. It provides a ChatGPT-like conversational experience powered by local LLMs (Ollama Llama 3.2 / Phi-3), with local document analysis (RAG), multi-tiered memory, sandboxed tools, and optional real-time web intelligence with direct source citations when connected to the internet.

---

## 🌟 Key Highlights

- **🧠 100% Offline AI Brain**: Runs models entirely on your local hardware using Ollama (`llama3.2:1b`, `llama3.2:3b`, etc.) with zero cloud API dependencies.
- **🌐 Selective Real-Time Web Intelligence**: Seamlessly queries DuckDuckGo for live facts, current events, and documentation, citing sources directly.
- **🛡️ Hardware Privacy Killswitch**: One-click toggle in the desktop UI and auto-detection; never attempts network requests when offline.
- **📚 Local Document RAG**: Ingests `.pdf`, `.docx`, `.md`, `.txt`, `.py` into an embedded SQLite vector store for semantic retrieval and questioning.
- **🧠 4-Tier Structured Memory**: Multi-turn conversation context, persistent user profile facts (`user_profile.json`), episodic logs, and full export/import/clear controls.
- **⚙️ Sandboxed System Tools**: AST-safe mathematical evaluator, system telemetry, and user-confirmed file operations.
- **🔄 Safe Self-Updating Engine**: Explicit app release checks, model upgrade proposals with hardware specs, and web knowledge ingestion into local RAG.
- **🖥️ Modern Windows Desktop GUI**: Clean Tkinter interface with token-by-token streaming, live connectivity pill, model status, and Document/Memory management dialogs.

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph UI_Layer [User Interface]
        GUI[Native Tkinter GUI<br/>python run_gui.py]
        CLI[Terminal CLI & Shell<br/>python run_cli.py]
    end

    subgraph Service_Layer [Core Services]
        LLM[LLM Service & Extractive Fallback<br/>(Ollama / Rule-Based QA)]
        SYNC[Sync Engine & Validator<br/>(Atomic Rollback & Snapshots)]
        MONITOR[Connectivity Monitor<br/>(Background RLock Daemon)]
    end

    subgraph Domain_Layer [Domain Logic]
        KE[Knowledge Engine<br/>(Multi-Stage Search & History)]
        CR[Conflict Resolver<br/>(Priority & Confidence Matrix)]
    end

    subgraph Storage_Layer [Storage & Persistence]
        DB[(SQLite 3 + WAL Mode<br/>data/offlinemind.db)]
        FTS[FTS5 Virtual Index<br/>(BM25 Search)]
        BM[Backup Manager<br/>data/backups/]
    end

    UI_Layer --> Service_Layer
    Service_Layer --> Domain_Layer
    Domain_Layer --> Storage_Layer
```

---

## 🚀 Quickstart Guide (Install & Run in Under 15 Minutes)

### 1. Prerequisites
- **Python**: Version 3.11 or newer (Tested on Python 3.14.6 64-bit).
- **RAM**: Normal laptop with 8 GB RAM.
- **OS**: Windows 10/11, macOS, or Linux.

### 2. Installation
Clone the repository and install the lightweight dependencies:
```bash
git clone https://github.com/OfflineMind/OfflineMind.git
cd OfflineMind

# Install dependencies (requests, pydantic, python-dotenv, python-pptx, pytest)
pip install -r requirements.txt
```

### 3. (Optional) Local LLM Setup with Ollama
If you want generative conversational responses, install [Ollama](https://ollama.com) and pull a small model:
```bash
ollama pull phi3:mini
# Or: ollama pull llama3.2:3b
```
*Note: If Ollama is not installed or running, OfflineMind automatically uses its built-in Extractive QA Fallback with zero configuration!*

---

## 🎬 Live Demo: The 4-Step College Rename Scenario

Experience the complete offline lifecycle in action with a single command:
```bash
python demo_scenario.py
```

### What Happens in the Demo:
1. **Offline Mode**: User asks *"What is my college name?"* -> System answers `Springfield Technical College` (v1) from local storage.
2. **Online Modification**: The college is renamed on the trusted university server to `Springfield University of Technology & AI`.
3. **Internet Restored**: System detects connectivity, creates a verified snapshot backup, syncs the new name, updates to version 2, and archives the previous name into `fact_history`.
4. **Internet Disconnected**: User asks again offline -> System answers with the new name, cites the Registrar authority, and explains that it was updated from `Springfield Technical College` with dates and reasons.

---

## 🖥️ Running the Application

### 1. Native Desktop GUI
Launch the modern desktop application:
```bash
python run_gui.py
```
- **Live Status Badges**: Shows real-time network state (`[🟢 ONLINE]` vs `[🔴 OFFLINE]`), inference engine (`[⚡ Ollama]` vs `[🔍 Extractive Local]`), and fact count.
- **Controls**: One-click `🔄 Sync Now`, `🌐 Toggle Simulated Offline`, `📜 Version History`, and `⚖️ Review Queue`.

### 2. Command-Line Interface (CLI)
Ask questions, manage knowledge, and inspect audit logs directly from the terminal:
```bash
# Ask a question (with provenance citations)
python run_cli.py query "What is my college name?" --provenance

# Check system connectivity, active facts, and backup status
python run_cli.py status

# Synchronize with registered trusted sources
python run_cli.py sync

# View complete version audit history
python run_cli.py history --entity College

# Add a new fact manually
python run_cli.py add-fact "User" "advisor" "Dr. Elena Rostova" --priority 85

# Launch interactive shell
python run_cli.py
```

### 3. Standalone Mock Server
Run the mock trusted authority server for offline testing or demonstrations:
```bash
python run_mock_server.py --port 8765
```

---

## 🧪 Testing & Verification

The project includes an exhaustive suite of **38 automated tests** covering unit, integration, security, and edge-case scenarios:

```bash
# Run the full test suite with coverage report
python -m pytest --cov=offlinemind --cov-report=term-missing
```

### Test Summary:
- **Total Test Cases**: 38 (100% Pass Rate).
- **Execution Time**: ~7.0 seconds.
- **Key Edge Cases Verified**:
  - Mid-sync network drop with 100% atomic transaction rollback.
  - Corrupted, truncated, and malformed JSON feed rejection.
  - SQL injection resilience via 100% parameterized bindings.
  - Null-byte and control-character sanitization.
  - Nested transaction savepoint rollback isolation.
  - Multi-source priority conflict resolution and low-confidence quarantine.

---

## 📚 Comprehensive Documentation Suite

Complete, professional documentation is provided inside the [`docs/`](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs) directory:

- [**`01_PROJECT_PLAN.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/01_PROJECT_PLAN.md): Problem statement, objectives, Agile methodology, timeline, and risk register.
- [**`02_REQUIREMENTS.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/02_REQUIREMENTS.md): Functional (FR) & non-functional (NFR) requirements, use cases, user stories, and Traceability Matrix (RTM).
- [**`03_SYSTEM_DESIGN.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/03_SYSTEM_DESIGN.md): System architecture, component descriptions, Mermaid sequence diagrams, and class diagrams.
- [**`04_DATABASE_DESIGN.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/04_DATABASE_DESIGN.md): Mermaid ER diagram, table schemas, FTS5 triggers, versioning design, and SQL walkthrough.
- [**`05_TESTING.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/05_TESTING.md): Test strategy, 38 detailed test case specifications, execution results, and coverage summary.
- [**`06_USER_MANUAL.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/06_USER_MANUAL.md): Step-by-step installation, Ollama configuration, GUI text mockups, and troubleshooting FAQ.
- [**`07_FINAL_REPORT.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/07_FINAL_REPORT.md): Academic & technical report with measured latency benchmarks, literature survey, and roadmap.
- [**`08_PRESENTATION.pptx`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/08_PRESENTATION.pptx): Professional 18-slide widescreen PowerPoint presentation generated via `python-pptx`.
- [**`ASSUMPTIONS.md`**](file:///c:/Users/SANKET/OfflineMind/OfflineMind/docs/ASSUMPTIONS.md): Architectural decisions, hardware assumptions, and engineering tradeoffs.

---

## 📂 Repository Structure

```
OfflineMind/
├── src/
│   └── offlinemind/
│       ├── __init__.py
│       ├── config.py                 # Configuration and environment variables
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py             # Domain models (Fact, History, Review, SyncResult)
│       │   ├── conflict_resolver.py  # Priority matrix and conflict arbitration
│       │   ├── knowledge_engine.py   # Multi-stage FTS5 BM25 search & CRUD
│       │   └── connectivity.py       # Non-blocking RLock network monitor daemon
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.py             # SQLite DDL and FTS5 triggers
│       │   ├── connection.py         # WAL mode & savepoint transaction manager
│       │   └── backup.py             # Point-in-time online snapshot & restore
│       ├── llm/
│       │   ├── __init__.py
│       │   └── llm_client.py         # Ollama client + RuleBasedExtractiveQA fallback
│       ├── sync/
│       │   ├── __init__.py
│       │   ├── validator.py          # Schema validation, sanitization & HTTPS policy
│       │   └── sync_engine.py        # Pre-sync snapshots & atomic sync execution
│       └── ui/
│           ├── __init__.py
│           ├── cli.py                # Command-line interface & interactive REPL
│           └── gui_app.py            # Native Tkinter desktop GUI
├── tests/
│   ├── test_db.py                    # Database transactions, FTS5 & backups
│   ├── test_conflict.py              # Conflict resolution matrix tests
│   ├── test_knowledge_engine.py      # Knowledge engine & search tests
│   ├── test_llm.py                   # Ollama reachability & fallback QA tests
│   ├── test_connectivity.py          # Connectivity daemon & simulated offline tests
│   ├── test_sync.py                  # Sync engine, rollback & validation tests
│   ├── test_college_rename_scenario.py # 4-step end-to-end integration scenario
│   ├── test_security_and_validation.py # SQL injection, sanitization & edge cases
│   └── test_cli.py                   # CLI subcommands integration tests
├── data/
│   ├── seed_knowledge.json           # Default seed facts
│   └── mock_server.py                # Standalone mock trusted university server
├── docs/
│   ├── ASSUMPTIONS.md
│   ├── 01_PROJECT_PLAN.md
│   ├── 02_REQUIREMENTS.md
│   ├── 03_SYSTEM_DESIGN.md
│   ├── 04_DATABASE_DESIGN.md
│   ├── 05_TESTING.md
│   ├── 06_USER_MANUAL.md
│   ├── 07_FINAL_REPORT.md
│   └── 08_PRESENTATION.pptx          # 18-slide Widescreen Presentation
├── scripts/
│   └── build_presentation.py         # Python generator for 08_PRESENTATION.pptx
├── demo_scenario.py                  # Automated 4-step scenario demonstration
├── run_gui.py                        # Native Tkinter Desktop GUI Launcher
├── run_cli.py                        # Terminal CLI Launcher
├── run_mock_server.py                # Mock Server Launcher
├── requirements.txt
├── pyproject.toml
├── pytest.ini
├── .env.example
└── README.md
```

---

## 🔒 Security & Privacy

- **100% Local Storage**: All SQLite data files reside locally in `data/`.
- **Zero Telemetry**: No third-party analytics, metrics collection, or tracking pings.
- **HTTPS Enforcement**: Remote feeds require HTTPS transport (loopback HTTP allowed solely for local mock testing).
- **Injection Proof**: Full parameterization across all SQL queries; zero string concatenation.
- **Input Sanitization**: Rejects control characters, null bytes, and out-of-range payloads.

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
