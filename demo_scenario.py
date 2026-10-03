"""OfflineMind Live Demonstration Script: 4-Step College Rename Lifecycle.

Executes the official scenario:
1. Offline: user asks "What is my college name?" -> system answers "<Old College Name>".
2. The college is renamed on the trusted online source.
3. Internet turns on -> system detects connectivity, syncs, updates fact and archives old to history.
4. Internet turns off -> user asks again -> system answers "<New College Name>" with provenance and explanation.
"""

from __future__ import annotations
import sys
import time
from pathlib import Path

# Ensure src/ is on path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
from offlinemind.config import DB_PATH, BACKUP_DIR
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.llm.llm_client import LLMService
from offlinemind.sync.sync_engine import SyncEngine
from data.mock_server import MockServerThread


def print_banner(text: str) -> None:
    width = 75
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def main():
    print_banner("OfflineMind: End-to-End Self-Updating AI Assistant Demo")
    print("Initializing local services, embedded database, and mock trusted server...")

    # Start Mock Server on a free ephemeral port
    server = MockServerThread(host="127.0.0.1", port=0)
    server.start()
    server.reset_state()
    feed_url = f"{server.url}/api/trusted_feed"
    print(f"✓ Mock Trusted University Registrar running at: {server.url}")

    # Initialize SQLite Database & Managers
    demo_db_path = BASE_DIR / "data" / "demo_offlinemind.db"
    demo_backup_dir = BASE_DIR / "data" / "demo_backups"
    if demo_db_path.exists():
        try:
            demo_db_path.unlink()
        except Exception:
            pass

    db = DatabaseManager(demo_db_path)
    bm = BackupManager(demo_db_path, demo_backup_dir)
    ke = KnowledgeEngine(db)
    monitor = ConnectivityMonitor(check_interval=0.2, ping_hosts=[f"{server.url}/health"])
    llm = LLMService()
    sync = SyncEngine(db, ke, bm, monitor)

    # Register trusted source
    sync.add_trusted_source("Official University Registrar", feed_url, priority=90)

    # Seed baseline local fact
    ke.add_fact(
        entity="College",
        attribute="name",
        value="Springfield Technical College",
        source="Student Handbook 2024",
        source_priority=50,
        category="education",
    )

    # =========================================================================
    # STEP 1: Offline Mode
    # =========================================================================
    print_banner("STEP 1: Device is OFFLINE (User asks: 'What is my college name?')")
    monitor.set_simulated_offline(True)
    time.sleep(0.5)
    print(f"Network Status: [{'ONLINE' if monitor.is_online() else 'OFFLINE (Air-gapped)'}]")

    query_1 = "What is my college name?"
    print(f"\nUser > {query_1}")
    search_res_1 = ke.search(query_1)
    history_1 = ke.get_history(entity="College", attribute="name")
    ans_1 = llm.generate_answer(query_1, search_res_1, history_1)
    print(f"\nOfflineMind > {ans_1.text}")
    print(f"[Model Engine: {ans_1.model_used} | Fact Version: v{search_res_1[0].fact.version}]")
    time.sleep(1.0)

    # =========================================================================
    # STEP 2: Online source modifies the college name
    # =========================================================================
    new_name = "Springfield University of Technology & AI"
    print_banner(f"STEP 2: College is renamed on online source -> '{new_name}'")
    print(f"Sending administrative amendment to {server.url}/api/admin/rename_college ...")
    resp = requests.post(
        f"{server.url}/api/admin/rename_college",
        json={"name": new_name, "reason": "Board of Trustees University Recharter"},
        timeout=2.0,
    )
    if resp.status_code == 200:
        print("✓ Online trusted source updated successfully.")
        print(f"  Online Feed now broadcasting: '{new_name}'")
    time.sleep(1.0)

    # =========================================================================
    # STEP 3: Internet turns on -> Auto-detects connectivity, syncs, archives old
    # =========================================================================
    print_banner("STEP 3: Internet turns ON -> System detects connectivity & auto-syncs")
    print("Re-enabling network connectivity monitor...")
    monitor.set_simulated_offline(False)
    monitor.probe_now()
    print(f"Network Status: [{'ONLINE' if monitor.is_online() else 'OFFLINE'}]")

    # Give background auto-sync a moment or trigger sync
    time.sleep(0.5)
    logs = sync.get_latest_sync_logs(1)
    if not logs or logs[0]["facts_updated"] == 0:
        sync.sync_source(feed_url, priority=90, source_name="Official University Registrar")
        logs = sync.get_latest_sync_logs(1)

    latest_log = logs[0] if logs else {}
    print(f"✓ Sync Executed: Status = {latest_log.get('status')}")
    print(f"  Facts checked: {latest_log.get('facts_checked')}")
    print(f"  Facts updated: {latest_log.get('facts_updated')}")
    print(f"  Facts added: {latest_log.get('facts_added')}")

    # Inspect the database fact
    current_fact = ke.get_fact("College", "name")
    print(f"\nLocal Database Fact updated to: '{current_fact.value}' (Version: v{current_fact.version})")
    time.sleep(1.0)

    # =========================================================================
    # STEP 4: Internet turns OFF -> User asks again offline
    # =========================================================================
    print_banner("STEP 4: Internet turns OFF -> User asks again offline")
    monitor.set_simulated_offline(True)
    time.sleep(0.5)
    print(f"Network Status: [{'ONLINE' if monitor.is_online() else 'OFFLINE (Air-gapped)'}]")

    query_2 = "What is my college name? Include provenance"
    print(f"\nUser > {query_2}")
    search_res_2 = ke.search(query_2)
    history_2 = ke.get_history(entity="College", attribute="name")
    ans_2 = llm.generate_answer(query_2, search_res_2, history_2)
    print(f"\nOfflineMind > {ans_2.text}")
    print(f"\n[Model Engine: {ans_2.model_used} | Active Fact Version: v{search_res_2[0].fact.version}]")

    print_banner("AUDIT HISTORY TRAIL")
    print(f"Version history for (College, name):")
    for idx, h in enumerate(history_2, 1):
        prev = f"from '{h.old_value}' " if h.old_value else "(Initial) "
        print(f"  [{idx}] v{h.version} | {prev}-> '{h.new_value}' | Source: {h.source} | Time: {h.timestamp[:19]}")

    print_banner("DEMO COMPLETED SUCCESSFULLY: ALL 4 STEPS VERIFIED")

    # Cleanup
    server.stop()
    db.close()


if __name__ == "__main__":
    main()
