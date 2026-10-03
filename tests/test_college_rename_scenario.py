"""End-to-end integration test of the 4-step College Rename scenario.

Verifies:
1. Offline query returns initial college name from local KB.
2. Trusted online source publishes a rename update.
3. Connectivity restored: auto-detection or sync detects changed fact,
   updates local KB, and archives old value into history.
4. Offline query again: system answers with new college name and explains
   when it was updated, from which source, and previous value.
"""

import tempfile
from pathlib import Path
import pytest
import requests

from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.llm.llm_client import LLMService
from offlinemind.sync.sync_engine import SyncEngine
from data.mock_server import MockServerThread


@pytest.fixture
def scenario_setup():
    server = MockServerThread(host="127.0.0.1", port=0)
    server.start()
    server.reset_state()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "scenario.db"
        backup_dir = Path(tmpdir) / "backups"
        db = DatabaseManager(db_path)
        ke = KnowledgeEngine(db)
        bm = BackupManager(db_path, backup_dir)
        monitor = ConnectivityMonitor(
            check_interval=0.1,
            probe_timeout=1.0,
            ping_hosts=[f"{server.url}/health"],
        )
        llm = LLMService()
        sync_engine = SyncEngine(db, ke, bm, monitor, timeout=2.0)

        # Register trusted source
        feed_url = f"{server.url}/api/trusted_feed"
        sync_engine.add_trusted_source("Official University Registrar", feed_url, priority=90)

        yield {
            "server": server,
            "db": db,
            "ke": ke,
            "bm": bm,
            "monitor": monitor,
            "llm": llm,
            "sync": sync_engine,
            "feed_url": feed_url,
        }
        server.stop()
        db.close()


def test_full_college_rename_lifecycle(scenario_setup):
    ke = scenario_setup["ke"]
    monitor = scenario_setup["monitor"]
    llm = scenario_setup["llm"]
    sync_engine = scenario_setup["sync"]
    server = scenario_setup["server"]
    feed_url = scenario_setup["feed_url"]

    # =========================================================================
    # STEP 1: Offline Mode
    # Baseline fact in local KB: "Springfield Technical College"
    # =========================================================================
    ke.add_fact(
        entity="College",
        attribute="name",
        value="Springfield Technical College",
        source="Student Handbook 2024",
        source_priority=50,
        category="education",
    )

    # Force simulated offline
    monitor.set_simulated_offline(True)
    assert monitor.is_online() is False

    # User queries: "What is my college name?"
    search_res_1 = ke.search("What is my college name?")
    history_1 = ke.get_history(entity="College", attribute="name")
    ans_1 = llm.generate_answer("What is my college name?", search_res_1, history_1)

    assert "Springfield Technical College" in ans_1.text
    # No prior update history yet
    assert ans_1.history_note is None

    # =========================================================================
    # STEP 2: The college is renamed on the trusted online source
    # New name: "Springfield Institute of Technology & AI"
    # =========================================================================
    new_college_name = "Springfield Institute of Technology & AI"
    rename_resp = requests.post(
        f"{server.url}/api/admin/rename_college",
        json={"name": new_college_name, "reason": "State University Charter Amendment"},
        timeout=2.0,
    )
    assert rename_resp.status_code == 200

    # =========================================================================
    # STEP 3: Internet turns on -> System detects connectivity, syncs, updates fact
    # =========================================================================
    # Transition to online -> Auto-sync triggers automatically!
    monitor.set_simulated_offline(False)
    monitor.probe_now()
    assert monitor.is_online() is True

    # Check logs for auto-sync result
    recent_logs = sync_engine.get_latest_sync_logs(5)
    print(f"\nRECENT SYNC LOGS: {recent_logs}")
    current_college = ke.get_fact("College", "name")
    print(f"\nCURRENT COLLEGE AFTER AUTO-SYNC: {current_college}")

    # Either auto-sync updated it, or manual sync updates it
    if recent_logs and recent_logs[0]["facts_updated"] >= 1:
        sync_res = sync_engine.get_latest_sync_logs(1)[0]
        assert sync_res["facts_updated"] >= 1
    else:
        sync_res = sync_engine.sync_source(feed_url, priority=90, source_name="Official University Registrar")
        assert sync_res.status == "SUCCESS"
        assert sync_res.facts_updated >= 1

    # Verify fact updated in local KB
    updated_fact = ke.get_fact("College", "name")
    assert updated_fact.value == new_college_name
    assert updated_fact.version == 2

    # Verify old value was archived into history table
    history_records = ke.get_history(entity="College", attribute="name")
    assert len(history_records) >= 2
    # The mutation record has old_value
    mutation = [h for h in history_records if h.old_value is not None][0]
    assert mutation.old_value == "Springfield Technical College"
    assert mutation.new_value == new_college_name

    # =========================================================================
    # STEP 4: Internet turns off -> User asks again offline
    # System answers with New College Name and explains when, source & prior value
    # =========================================================================
    monitor.set_simulated_offline(True)
    assert monitor.is_online() is False

    search_res_2 = ke.search("What is my college name?")
    history_2 = ke.get_history(entity="College", attribute="name")
    ans_2 = llm.generate_answer("What is my college name?", search_res_2, history_2)

    # 1. Answers with new college name
    assert new_college_name in ans_2.text

    # 2. Explains that it was updated, from which source, and previous value
    assert ans_2.history_note is not None
    assert "Springfield Technical College" in ans_2.history_note
    assert new_college_name in ans_2.history_note
    assert "Official University Registrar" in ans_2.history_note

    # 3. Provenance check
    search_res_prov = ke.search("What is my college name? Include provenance")
    ans_prov = llm.generate_answer("What is my college name? Include provenance", search_res_prov, history_2)
    assert "Provenance:" in ans_prov.text
    assert "Official University Registrar" in ans_prov.text
    assert "v2" in ans_prov.text
