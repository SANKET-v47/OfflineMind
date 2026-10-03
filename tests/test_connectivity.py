"""Unit tests for the ConnectivityMonitor and MockServer."""

import time
import pytest
import requests
from offlinemind.core.connectivity import ConnectivityMonitor
from data.mock_server import MockServerThread


@pytest.fixture(scope="module")
def mock_server():
    server = MockServerThread(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


def test_mock_server_feed_and_rename(mock_server):
    mock_server.reset_state()
    base_url = mock_server.url

    # 1. Fetch initial feed
    resp = requests.get(f"{base_url}/api/trusted_feed", timeout=2.0)
    assert resp.status_code == 200
    data = resp.json()
    assert "facts" in data
    names = [f["value"] for f in data["facts"] if f["entity"] == "College" and f["attribute"] == "name"]
    assert names[0] == "Springfield Technical College"

    # 2. Rename college via admin endpoint
    rename_resp = requests.post(
        f"{base_url}/api/admin/rename_college",
        json={"name": "Springfield State University", "reason": "State charter"},
        timeout=2.0,
    )
    assert rename_resp.status_code == 200

    # 3. Verify feed reflects rename
    resp2 = requests.get(f"{base_url}/api/trusted_feed", timeout=2.0)
    data2 = resp2.json()
    names2 = [f["value"] for f in data2["facts"] if f["entity"] == "College" and f["attribute"] == "name"]
    assert names2[0] == "Springfield State University"

    # 4. Reset state
    mock_server.reset_state()
    resp3 = requests.get(f"{base_url}/api/trusted_feed", timeout=2.0)
    names3 = [f["value"] for f in resp3.json()["facts"] if f["entity"] == "College" and f["attribute"] == "name"]
    assert names3[0] == "Springfield Technical College"


def test_connectivity_simulated_offline_and_callbacks(mock_server):
    monitor = ConnectivityMonitor(
        check_interval=0.1,
        probe_timeout=1.0,
        ping_hosts=[f"{mock_server.url}/health"],
    )

    connect_events = []
    disconnect_events = []

    monitor.on_connect(lambda: connect_events.append(True))
    monitor.on_disconnect(lambda: disconnect_events.append(True))

    # Initial probe to discover we are online
    is_up = monitor.probe_now()
    assert is_up is True
    assert monitor.is_online() is True

    # Force simulated offline
    monitor.set_simulated_offline(True)
    assert monitor.is_online() is False
    assert monitor.is_simulated_offline() is True
    assert len(disconnect_events) >= 1

    # Disable simulated offline
    monitor.set_simulated_offline(False)
    assert monitor.is_online() is True
    assert len(connect_events) >= 1

