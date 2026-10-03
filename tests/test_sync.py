"""Unit and integration tests for the Sync Engine, validation, and mid-sync rollback."""

import tempfile
from pathlib import Path
import pytest
from offlinemind.db.connection import DatabaseManager
from offlinemind.db.backup import BackupManager
from offlinemind.core.knowledge_engine import KnowledgeEngine
from offlinemind.core.connectivity import ConnectivityMonitor
from offlinemind.sync.sync_engine import SyncEngine
from offlinemind.sync.validator import FactValidator, validate_sync_url
from data.mock_server import MockServerThread


@pytest.fixture(scope="module")
def mock_server():
    server = MockServerThread(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def sync_env(mock_server):
    mock_server.reset_state()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync_test.db"
        backup_dir = Path(tmpdir) / "backups"
        db = DatabaseManager(db_path)
        ke = KnowledgeEngine(db)
        bm = BackupManager(db_path, backup_dir)
        monitor = ConnectivityMonitor(
            check_interval=0.1,
            probe_timeout=1.0,
            ping_hosts=[f"{mock_server.url}/health"],
        )
        monitor.probe_now()

        engine = SyncEngine(
            db=db,
            knowledge_engine=ke,
            backup_mgr=bm,
            connectivity=monitor,
            timeout=2.0,
        )
        yield {
            "engine": engine,
            "db": db,
            "ke": ke,
            "bm": bm,
            "monitor": monitor,
            "mock_server": mock_server,
        }
        db.close()


def test_validator_rules():
    # Valid fact
    fact, err = FactValidator.validate_fact_dict({
        "entity": "College",
        "attribute": "name",
        "value": "Stanford",
        "confidence": 0.95,
        "source_priority": 80,
    })
    assert err is None
    assert fact is not None
    assert fact.entity == "College"
    assert fact.confidence == 0.95

    # Invalid empty attribute
    _, err_empty = FactValidator.validate_fact_dict({
        "entity": "College",
        "attribute": "",
        "value": "Stanford",
    })
    assert "cannot be empty" in err_empty

    # Invalid confidence range
    _, err_conf = FactValidator.validate_fact_dict({
        "entity": "College",
        "attribute": "name",
        "value": "Stanford",
        "confidence": 2.5,
    })
    assert "between 0.0 and 1.0" in err_conf


def test_url_security_validation():
    # HTTPS allowed
    assert validate_sync_url("https://trusted.university.edu/feed.json") is True
    # Localhost HTTP allowed if allow_insecure_http is True
    assert validate_sync_url("http://127.0.0.1:8765/feed") is True
    assert validate_sync_url("http://localhost:8765/feed") is True
    # Insecure external HTTP disallowed
    assert validate_sync_url("http://untrusted-remote.com/feed.json", allow_insecure_http=False) is False
    # Dangerous schemes rejected
    assert validate_sync_url("file:///etc/passwd") is False
    assert validate_sync_url("ftp://server/feed") is False


def test_successful_sync(sync_env):
    engine = sync_env["engine"]
    ke = sync_env["ke"]
    mock_server = sync_env["mock_server"]

    feed_url = f"{mock_server.url}/api/trusted_feed"
    engine.add_trusted_source("University Registrar", feed_url, priority=85)

    result = engine.sync_source(feed_url, priority=85, source_name="University Registrar")
    assert result.status == "SUCCESS"
    assert result.facts_added >= 1

    # Verify fact stored
    fact = ke.get_fact("College", "name")
    assert fact is not None
    assert fact.value == "Springfield Technical College"
    assert fact.source_priority == 85

    # Verify sync log written
    logs = engine.get_latest_sync_logs(5)
    assert len(logs) >= 1
    assert logs[0]["status"] == "SUCCESS"


def test_sync_aborted_when_offline(sync_env):
    engine = sync_env["engine"]
    monitor = sync_env["monitor"]
    mock_server = sync_env["mock_server"]

    feed_url = f"{mock_server.url}/api/trusted_feed"
    # Force offline mode
    monitor.set_simulated_offline(True)

    result = engine.sync_source(feed_url, priority=85)
    assert result.status == "FAILED"
    assert "offline" in result.error_message.lower()


def test_sync_corrupted_payload_rollback(sync_env):
    engine = sync_env["engine"]
    db = sync_env["db"]
    ke = sync_env["ke"]
    mock_server = sync_env["mock_server"]

    # Seed baseline fact
    ke.add_fact("College", "name", "Original Stable College", "Seed", 90)

    # Enable corruption on mock server
    import requests
    requests.post(f"{mock_server.url}/api/admin/simulate_corruption", json={"enable": True})

    feed_url = f"{mock_server.url}/api/trusted_feed"
    result = engine.sync_source(feed_url, priority=85)

    # Must fail cleanly
    assert result.status == "FAILED"
    assert "Corrupted or invalid JSON" in result.error_message

    # Verify baseline data remained completely untouched
    stable_fact = ke.get_fact("College", "name")
    assert stable_fact.value == "Original Stable College"
    assert db.integrity_check() is True

    # Disable corruption
    requests.post(f"{mock_server.url}/api/admin/simulate_corruption", json={"enable": False})
