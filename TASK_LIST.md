# OfflineMind Task List & Implementation Plan

## Phase 1: Directory Setup & Configuration
- [ ] Create directory structure (`src/offlinemind/...`, `tests/`, `data/`, `docs/`)
- [ ] Implement `src/offlinemind/config.py` with environment variable loading and sensible defaults
- [ ] Create `requirements.txt` and `.env.example`
- [ ] Create initial `docs/ASSUMPTIONS.md`

## Phase 2: Database Layer & Transactions
- [ ] Implement `src/offlinemind/db/schema.py` (SQLite schema with FTS5, tables: `facts`, `fact_history`, `review_queue`, `sync_logs`, `trusted_sources`)
- [ ] Implement `src/offlinemind/db/connection.py` (connection management, atomic transaction context manager, WAL mode, integrity checks)
- [ ] Implement `src/offlinemind/db/backup.py` (point-in-time database backup using SQLite Backup API, rotation, restore)
- [ ] Write unit tests for DB layer (`tests/test_db.py`) and verify

## Phase 3: Knowledge Engine & Conflict Resolver
- [ ] Implement `src/offlinemind/core/models.py` (Pydantic / dataclass models for Fact, History, SyncResult, etc.)
- [ ] Implement `src/offlinemind/core/conflict_resolver.py` (priority, newest-wins, confidence, review queue)
- [ ] Implement `src/offlinemind/core/knowledge_engine.py` (CRUD, FTS5 search, BM25 ranking, version history, rollback)
- [ ] Write unit tests for Knowledge Engine and Conflict Resolver (`tests/test_knowledge_engine.py`, `tests/test_conflict.py`) and verify

## Phase 4: LLM Client & Retrieval Fallback
- [ ] Implement `src/offlinemind/llm/llm_client.py` (Ollama integration + intelligent rule-based / extractive QA fallback)
- [ ] Implement provenance generator and explanation module
- [ ] Write unit tests for LLM layer (`tests/test_llm.py`) and verify

## Phase 5: Connectivity Monitor & Mock Server
- [ ] Implement `src/offlinemind/core/connectivity.py` (background thread, socket/HTTP probe, simulated offline toggle, callbacks)
- [ ] Implement `data/mock_server.py` (lightweight mock HTTP server for trusted sources with live fact modification endpoint)
- [ ] Write tests for connectivity monitor (`tests/test_connectivity.py`) and verify

## Phase 6: Sync Engine & Safe Atomic Updates
- [ ] Implement `src/offlinemind/sync/validator.py` (payload schema validation, sanitization, confidence checks)
- [ ] Implement `src/offlinemind/sync/sync_engine.py` (pre-sync backup, fetch, conflict resolution, rollback on mid-sync failure, audit logging)
- [ ] Write tests for sync engine including mid-sync failure, corrupted data, conflicting updates (`tests/test_sync.py`)

## Phase 7: User Interfaces (CLI & Native Tkinter GUI)
- [ ] Implement `src/offlinemind/ui/cli.py` (interactive REPL + command-line query, sync, history, review, status)
- [ ] Implement `src/offlinemind/ui/gui_app.py` (Tkinter GUI with chat, live online/offline badge, sync button, history drawer)
- [ ] Create top-level runner scripts: `run_cli.py`, `run_gui.py`, `run_mock_server.py`, `demo_scenario.py`

## Phase 8: End-to-End Testing & Verification
- [ ] Write `tests/test_college_rename_scenario.py` (automated 4-step demo scenario)
- [ ] Run complete test suite (unit, integration, e2e) with pytest and measure code coverage
- [ ] Execute `demo_scenario.py` and capture console outputs and performance metrics

## Phase 9: Comprehensive Documentation (8 Documents + Presentation)
- [ ] `docs/ASSUMPTIONS.md`
- [ ] `docs/01_PROJECT_PLAN.md`
- [ ] `docs/02_REQUIREMENTS.md`
- [ ] `docs/03_SYSTEM_DESIGN.md` (with Mermaid diagrams)
- [ ] `docs/04_DATABASE_DESIGN.md` (with Mermaid ER diagram and SQL)
- [ ] `docs/05_TESTING.md` (at least 30 test cases, real pytest output and coverage)
- [ ] `docs/06_USER_MANUAL.md` (complete user guide with UI mockups)
- [ ] `docs/07_FINAL_REPORT.md` (measured performance, survey, limitations)
- [ ] `docs/08_PRESENTATION.pptx` (15-18 slides using python-pptx)
- [ ] `README.md` (clear 15-minute quickstart guide)
