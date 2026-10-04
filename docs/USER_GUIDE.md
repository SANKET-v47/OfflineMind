# OfflineMind — User Guide & Operational Manual

**OfflineMind** is a complete, private, offline-first personal AI assistant for Windows. It provides a ChatGPT-like conversational experience running 100% on your local hardware, with optional real-time web intelligence when internet is available and enabled.

---

## 🌟 Key Features

1. **100% Offline AI Brain**: Runs models locally using Ollama (`llama3.2:1b`, `llama3.2:3b`, `phi3:mini`, etc.) with zero cloud API dependencies.
2. **Selective Real-Time Web Intelligence**: Seamlessly queries DuckDuckGo for live news, weather, stock quotes, and sports scores, citing web sources directly.
3. **Hardware Privacy Killswitch**: Toggle internet access with one click or via hardware detection. The AI will never attempt network calls when offline.
4. **Local Document RAG**: Ingest `.txt`, `.md`, `.py`, `.json`, `.pdf`, `.docx` into an embedded SQLite vector store for context-aware querying.
5. **Multi-Tiered Structured Memory**:
   - **Short-Term Memory**: Multi-turn conversation buffer.
   - **Long-Term Memory**: Persistent user profile facts stored in JSON.
   - **Episodic Memory**: Full session transcripts stored with export/import/clear controls.
6. **Sandboxed Tools**:
   - **Safe Calculator**: Safe AST-based mathematical evaluation (no shell/eval execution).
   - **System Info**: Read-only OS and hardware telemetry.
   - **File System Tools**: Read/write/delete with mandatory user confirmation for destructive operations.
7. **Safe Self-Updating**:
   - Explicit version checking against GitHub releases.
   - Model upgrade proposals with RAM/disk requirements and user approval.
   - Knowledge updater to ingest web topic digests into local RAG.

---

## 🚀 Getting Started

### Prerequisites

- **OS**: Windows 10/11 (64-bit)
- **RAM**: Minimum 8 GB (16 GB+ recommended)
- **Python**: Python 3.10+
- **Local Model Runner**: [Ollama for Windows](https://ollama.com/download/windows)

### Starting OfflineMind

You can start OfflineMind using the one-click batch script or command line:

```cmd
# Double click or run in terminal:
start_offlinemind.bat

# Or run directly with Python:
python run_gui.py
```

To run the interactive command-line interface:
```cmd
start_offlinemind_cli.bat
```

---

## 🖥️ Desktop GUI Walkthrough

### 1. Status Bar Header
- **Connectivity Badge**:
  - `🟢 Online`: Internet is reachable.
  - `🔴 Offline`: Device is disconnected or killswitch is active.
- **Web Intelligence Toggle**:
  - `🌐 Web: ON`: Assistant can search the web for real-time answers.
  - `🌐 Web: OFF`: Force strictly local generation.
- **Model Badge**: Displays the active local model (e.g., `llama3.2:1b`).
- **Documents Count**: Number of indexed files in your local RAG vector store.

### 2. Live Token Streaming
Responses stream token-by-token in real-time. If a generation takes too long or you wish to cancel, click the **⏹ Stop** button.

### 3. Document RAG Center
Click the **📚 Documents** button in the header:
- **Ingest Document**: Select any PDF, DOCX, Markdown, Python, or text file. OfflineMind chunks, embeds, and indexes it into the local SQLite vector database.
- **Search Documents**: View indexed documents, character counts, and chunk statistics.
- In chat, simply ask: *"What does section 3 of my contract say?"* and the assistant will retrieve relevant chunks and cite the document.

### 4. Memory Manager
Click the **🧠 Memory** button in the header:
- **Remembered Facts**: See what the assistant knows about you (e.g., name, preferences, project names).
- **Add Fact**: Teach the assistant a new permanent fact.
- **Forget Fact / Clear Memory**: Full user control to delete or reset memories.
- **Export / Import**: Back up your memory to a JSON file.

### 5. Memory Commands in Chat
You can manage memory directly inside the conversation:
- `Remember that my favorite programming language is Rust`
- `What do you remember about me?`
- `Forget my favorite programming language`

### 6. Tools & Calculations
Ask natural mathematical or system questions:
- `Calculate sqrt(144) + 25 * 3`
- `What is my current system status?`

---

## 🔒 Security & Privacy Guarantees

- **Zero Cloud API Telemetry**: OfflineMind does not send prompts or document contents to OpenAI, Google, Anthropic, or any remote server.
- **Air-Gapped Operation**: Unplugging your Ethernet or turning off Wi-Fi does not degrade conversation, memory, or document RAG capabilities.
- **Strict Anti-Hallucination**: If you ask for real-time information while offline, OfflineMind explicitly alerts you that you are offline rather than inventing facts.

---

## 📦 Tested & Verified

OfflineMind includes an automated test suite with **73 unit and integration tests** covering:
- Provider switching and Ollama streaming.
- State-machine internet monitoring and force-offline killswitch.
- DuckDuckGo HTML scraping and query routing.
- Document loading, text chunking, and SQLite vector similarity search.
- 4-tier structured memory persistence and export.
- AST math sandboxing and file permission controls.
- Atomic SQLite migrations and backup rollbacks.
