# OfflineMind: User Manual & Operator Guide

**Document ID**: UMN-OM-2026-V1  
**Target Audience**: End Users, Field Operators, System Administrators  
**Version**: 1.0.0  

---

## 1. Introduction

**OfflineMind** is a self-updating, offline-first artificial intelligence assistant that runs directly on your personal computer. It requires **no active internet connection** for daily question answering, knowledge search, and reasoning. When internet access is detected, OfflineMind automatically synchronizes verified updates from trusted remote sources, preserves an audit trail of previous knowledge, and safely returns to offline operation.

---

## 2. Installation & Quickstart

### 2.1 System Prerequisites
- **Operating System**: Windows 10/11, macOS 12+, or modern Linux (Ubuntu 22.04+).
- **RAM**: 8 GB RAM minimum (OfflineMind consumes < 100 MB RAM).
- **Python**: Version 3.11 or newer (Python 3.14 recommended).

### 2.2 Setup Instructions (Under 5 Minutes)
1. **Clone or Download the Repository**:
   ```bash
   git clone https://github.com/OfflineMind/OfflineMind.git
   cd OfflineMind
   ```

2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables (Optional)**:
   ```bash
   cp .env.example .env
   ```

---

## 3. Local LLM Setup (Ollama Integration)

OfflineMind works out of the box with zero external models using its built-in **Extractive Retrieval Engine**. For generative natural conversational answers, you can optionally enable **Ollama**:

1. **Install Ollama**:
   - Download the installer from [https://ollama.com/download](https://ollama.com/download).
2. **Pull a Lightweight Model**:
   ```bash
   # Recommended for 8 GB RAM systems:
   ollama pull phi3:mini
   # Or Llama 3.2:
   ollama pull llama3.2:3b
   ```
3. **Verify Ollama is Running**:
   ```bash
   ollama list
   ```
OfflineMind automatically detects when Ollama is running and seamlessly switches from extractive fallback to generative inference.

---

## 4. Launching OfflineMind

### 4.1 Launching the Native Desktop GUI
To launch the graphical desktop interface:
```bash
python run_gui.py
```

#### GUI Layout & Text Mockup:
```
+-----------------------------------------------------------------------------------------+
| 🧠 OfflineMind - Offline-First AI Assistant                                            |
+-----------------------------------------------------------------------------------------+
| 🧠 OfflineMind                                            [🟢 ONLINE] [⚡ Ollama] [📚 8 Facts] |
| Offline-First Self-Updating Knowledge Engine                                             |
+-----------------------------------------------------------------------------------------+
| [🔄 Sync Now]  [🌐 Force Simulated Offline]  [📜 Version History]  [⚖️ Review Queue]     |
+-----------------------------------------------------------------------------------------+
| Chat History:                                                                           |
|                                                                                         |
| You                                                                                     |
| What is my college name?                                                                |
|                                                                                         |
| OfflineMind                                                                             |
| Your college name is Springfield University of Technology & AI.                         |
|                                                                                         |
| > ℹ️ Notice: This fact was updated from 'Springfield Technical College' to             |
|   'Springfield University of Technology & AI' on 2026-10-03 from source                 |
|   'Official University Registrar'. (Reason: State Charter Upgrade)                      |
|                                                                                         |
| [Source: Official University Registrar (Priority: 85) | v2 | Confidence: 100%]          |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
| [ Ask a question (e.g. 'What is my college name?')................... ] [x] Prov  [Send] |
+-----------------------------------------------------------------------------------------+
```

### 4.2 Launching the Terminal CLI & REPL
To run interactive terminal mode:
```bash
python run_cli.py
```
Or use single-command execution:
```bash
# Query with provenance
python run_cli.py query "What is my college name?" --provenance

# Check system status
python run_cli.py status

# Inspect audit history
python run_cli.py history --entity College

# Synchronize with trusted sources
python run_cli.py sync
```

---

## 5. Core Workflows & How-To Guides

### 5.1 Asking Questions Offline
1. In the input box or terminal prompt, enter any natural language question (e.g. *"What is my major?"* or *"When was my college founded?"*).
2. Press **Enter** or click **Send**.
3. OfflineMind retrieves the most relevant fact from its embedded SQLite database and displays the verified answer in milliseconds.

### 5.2 Understanding Status Badges
- **`[🟢 ONLINE]`**: Network is detected; auto-sync daemon is active.
- **`[🔴 OFFLINE]`**: Device has no internet or is operating in air-gapped mode. All queries continue functioning normally.
- **`[🔴 SIM OFFLINE]`**: Simulated offline mode is active. Internet is blocked internally for testing without disconnecting your computer's Wi-Fi.
- **`[⚡ Ollama]`**: Ollama daemon is detected and active for generative inference.
- **`[🔍 Local Extractive]`**: Operating in high-speed, deterministic retrieval fallback mode.

### 5.3 Synchronizing Knowledge
- **Automatic Sync**: When connectivity is restored, OfflineMind automatically syncs in the background.
- **Manual Sync**: Click the **🔄 Sync Now** button or execute `python run_cli.py sync`.

### 5.4 Viewing Audit Version History
Click **📜 Version History** to inspect an interactive table showing every change made to facts over time, including previous values, timestamps, and origin sources.

---

## 6. Running the Automated Demo Scenario

To observe the official 4-step college rename lifecycle in real time:
```bash
python demo_scenario.py
```
This script launches the local mock server, simulates offline querying, modifies the college name on the online authority, triggers auto-sync upon reconnection, and verifies offline reasoning after disconnection.

---

## 7. Troubleshooting FAQ

**Q1: The GUI opens but says `[🔍 Local Extractive]` instead of `[⚡ Ollama]`.**  
*Answer*: Ensure the Ollama daemon is running in the background (`ollama serve`) and that you have pulled the model (`ollama pull phi3:mini`). OfflineMind defaults to extractive QA if Ollama is not detected, ensuring uninterrupted service.

**Q2: Will my data be sent to remote cloud servers during a sync?**  
*Answer*: Absolutely not. Sync only **fetches** public authoritative knowledge from trusted endpoints into your local database. Your queries, personal facts, and usage patterns never leave your machine.

**Q3: What happens if my Wi-Fi disconnects in the middle of a sync?**  
*Answer*: OfflineMind executes all sync modifications inside atomic SQLite transactions and creates a point-in-time snapshot backup before every sync. If a connection drops mid-sync, the transaction immediately rolls back, leaving your database completely unharmed.

**Q4: How do I resolve quarantined conflicts in the review queue?**  
*Answer*: In the GUI, click **⚖️ Review Queue**, or run `python run_cli.py review --interactive` from the terminal to accept or reject pending conflicts.
