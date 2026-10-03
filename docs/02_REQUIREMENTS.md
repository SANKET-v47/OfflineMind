# OfflineMind: Software Requirements Specification (SRS)

**Document ID**: SRS-OM-2026-V1  
**Project**: OfflineMind – Offline-First, Self-Updating AI Assistant  
**Author**: Systems & Architecture Engineering  
**Version**: 1.0.0  

---

## 1. Stakeholders

1. **End Users**: Students, researchers, field engineers, and travelers operating in air-gapped, offline, or low-connectivity environments requiring immediate, accurate knowledge access.
2. **Knowledge Curators / Domain Administrators**: Registrars, departmental coordinators, or institutional publishers maintaining trusted authoritative feeds.
3. **Systems Engineers & Security Auditors**: Professionals requiring local data sovereignty, zero external data leakage, and verifiable transaction logs.

---

## 2. Functional Requirements (FR)

| Requirement ID | Module | Description | Priority |
|---|---|---|---|
| **FR-1** | Knowledge Base | The system shall store knowledge as discrete relational facts `(entity, attribute, value)` with confidence, version, category, and source metadata. | Critical |
| **FR-2** | Full-Text Search | The system shall provide sub-millisecond local BM25-ranked full-text search using SQLite FTS5. | High |
| **FR-3** | Offline QA | The system shall answer queries completely offline without relying on active network connections. | Critical |
| **FR-4** | Local LLM Integration | The system shall integrate with local Ollama endpoints (Phi-3 Mini / Llama 3.2 3B) for generative reasoning. | High |
| **FR-5** | Extractive Fallback | If Ollama is unavailable or uninstalled, the system shall automatically fall back to deterministic extractive QA without errors. | Critical |
| **FR-6** | Provenance Tracking | The system shall cite source name, last-updated timestamp, version, and confidence level upon request. | High |
| **FR-7** | History Explanation | When a fact has changed, the system shall explain that an update occurred, when it happened, from which source, and previous values. | Critical |
| **FR-8** | Connectivity Monitor | The system shall detect network availability transitions (`OFFLINE -> ONLINE` and `ONLINE -> OFFLINE`) in a non-blocking background thread. | High |
| **FR-9** | Simulated Offline Mode | The system shall provide a manual toggle to force simulated offline operation for demonstration and testing. | High |
| **FR-10** | Pre-Sync Snapshot | The system shall generate a verified point-in-time database snapshot backup before executing any sync. | Critical |
| **FR-11** | Automatic Sync | Upon detecting restored connectivity, the system shall automatically fetch updates from configured trusted sources. | High |
| **FR-12** | Atomic Rollback | If a network drop, timeout, or payload corruption occurs mid-sync, all uncommitted changes shall be rolled back. | Critical |
| **FR-13** | Conflict Resolution | The system shall resolve conflicts using source priority, monotonic timestamps, and confidence score thresholds. | Critical |
| **FR-14** | Review Queue | Conflicting facts from sources of equal priority with identical timestamps or lower confidence shall be quarantined in a review queue. | High |
| **FR-15** | Audit Log | Every sync execution and fact mutation shall be recorded immutably in `sync_logs` and `fact_history`. | High |
| **FR-16** | Desktop GUI | The system shall provide a native desktop GUI with chat, live status badge, sync button, and history view. | Medium |
| **FR-17** | CLI & REPL | The system shall provide command-line query, sync, history, review, and an interactive shell. | Medium |

---

## 3. Non-Functional Requirements (NFR)

### 3.1 Performance (NFR-P)
- **NFR-P1**: Local offline retrieval search latency must be under 100 milliseconds for knowledge bases of up to 100,000 facts.
- **NFR-P2**: Extractive fallback answer generation must complete within 20 milliseconds.
- **NFR-P3**: Database synchronization for a standard feed of 50 facts must complete in under 500 milliseconds on a standard broadband connection.
- **NFR-P4**: Memory consumption of the core application and desktop GUI must remain under 150 MB RAM.

### 3.2 Reliability & Fault Tolerance (NFR-R)
- **NFR-R1**: Zero database corruption during power loss or abrupt network disconnection, guaranteed via SQLite WAL mode and atomic transactions.
- **NFR-R2**: Pre-sync backups must be verified via SQLite `PRAGMA integrity_check` before proceeding with sync.
- **NFR-R3**: The system must achieve 99.9% uptime during offline operation without crashes or unhandled exceptions.

### 3.3 Security & Privacy (NFR-S)
- **NFR-S1**: All personal queries and stored knowledge must remain entirely on the local client device; zero telemetry or analytics data shall be transmitted.
- **NFR-S2**: Remote synchronization must enforce HTTPS. Cleartext HTTP is restricted strictly to loopback addresses (`127.0.0.1`, `localhost`) for testing.
- **NFR-S3**: Input payloads must be sanitized: null bytes (`\x00`) and ANSI control characters must be purged prior to storage.
- **NFR-S4**: SQL injection protection is enforced via 100% parameterized SQL bindings.

### 3.4 Usability & Portability (NFR-U)
- **NFR-U1**: The system must execute without modification on Windows 10/11, macOS, and modern Linux distributions.
- **NFR-U2**: Installation and first-run startup must be achievable in under 15 minutes by a user following the README.

---

## 4. Use Cases & User Stories

### Use Case UC-1: Offline Factual Question Answering
- **Primary Actor**: End User
- **Preconditions**: Application installed, seed database populated, network offline.
- **Main Flow**:
  1. User enters query: *"What is my college name?"*
  2. System searches local facts using FTS5 and exact entity/attribute matching.
  3. Extractive QA engine formats a natural language response.
  4. User receives: *"Your college name is **Springfield Technical College**."* with provenance citations.

### Use Case UC-2: Safe Synchronization on Connectivity Restored
- **Primary Actor**: System (Automatic Sync Daemon)
- **Preconditions**: Trusted source feed updated online; client device moves from offline to online.
- **Main Flow**:
  1. Connectivity monitor detects internet availability and fires `on_connect` event.
  2. Sync engine creates verified snapshot backup in `data/backups/`.
  3. Sync engine fetches remote feed over HTTPS.
  4. Validator cleanses and verifies JSON schema and data types.
  5. Knowledge engine applies priority-based conflict resolution within an atomic transaction.
  6. Existing fact is archived to `fact_history`; active fact is updated to version 2.
  7. Success audit entry is written to `sync_logs`.

### User Story US-1: University Rebranding Notice
> *As a student returning to campus after a semester abroad,*  
> *I want my offline assistant to inform me of university rebrandings and historical changes,*  
> *So that I use the correct institutional name while understanding the update timeline and source authority.*  
> **Acceptance Criteria**:
> - Answers query with new college name.
> - Explicitly notes prior name, update date, and authoritative source.

---

## 5. Requirements Traceability Matrix (RTM)

| Requirement ID | Module | Verification Method | Automated Test Case | Status |
|---|---|---|---|---|
| **FR-1** | Knowledge Base | Unit Test | `tests/test_knowledge_engine.py::test_add_and_get_fact` | Verified |
| **FR-2** | Full-Text Search | Unit Test | `tests/test_knowledge_engine.py::test_search_exact_and_fts` | Verified |
| **FR-3** | Offline QA | Integration Test | `tests/test_college_rename_scenario.py::test_full_college_rename_lifecycle` (Step 1) | Verified |
| **FR-4** | Local LLM | Unit Test | `tests/test_llm.py::test_mocked_ollama_call` | Verified |
| **FR-5** | Extractive Fallback | Unit Test | `tests/test_llm.py::test_fallback_extractive_answer_with_history` | Verified |
| **FR-6** | Provenance | Unit Test | `tests/test_llm.py::test_provenance_flag_in_query` | Verified |
| **FR-7** | History Explanation | Integration Test | `tests/test_college_rename_scenario.py::test_full_college_rename_lifecycle` (Step 4) | Verified |
| **FR-8** | Connectivity Monitor | Unit Test | `tests/test_connectivity.py::test_connectivity_simulated_offline_and_callbacks` | Verified |
| **FR-9** | Simulated Offline | Unit Test | `tests/test_connectivity.py::test_connectivity_simulated_offline_and_callbacks` | Verified |
| **FR-10** | Pre-Sync Snapshot | Unit Test | `tests/test_db.py::test_backup_and_restore` | Verified |
| **FR-11** | Automatic Sync | Integration Test | `tests/test_college_rename_scenario.py::test_full_college_rename_lifecycle` (Step 3) | Verified |
| **FR-12** | Atomic Rollback | Integration Test | `tests/test_sync.py::test_sync_corrupted_payload_rollback` | Verified |
| **FR-13** | Conflict Resolution | Unit Test | `tests/test_conflict.py::test_priority_wins`, `test_equal_priority_newest_timestamp_wins` | Verified |
| **FR-14** | Review Queue | Unit Test | `tests/test_conflict.py::test_lower_confidence_quarantined_to_review` | Verified |
| **FR-15** | Audit Log | Unit Test | `tests/test_sync.py::test_successful_sync` | Verified |
| **FR-16** | Desktop GUI | Lifecycle Test | `tests/test_cli.py` & automated GUI instantiation | Verified |
| **FR-17** | CLI & REPL | Unit Test | `tests/test_cli.py::test_cli_status`, `test_cli_query`, `test_cli_add_fact` | Verified |
| **NFR-S2** | HTTPS Enforcement | Unit Test | `tests/test_sync.py::test_url_security_validation` | Verified |
| **NFR-S3** | Input Sanitization | Unit Test | `tests/test_security_and_validation.py::test_control_character_and_null_byte_sanitization` | Verified |
| **NFR-S4** | SQL Injection | Unit Test | `tests/test_security_and_validation.py::test_sql_injection_resilience` | Verified |
