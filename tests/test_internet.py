"""Unit tests for Phase 2: InternetManager state machine and resilience."""

from unittest.mock import patch, MagicMock
import pytest
from offlinemind.web.internet_manager import InternetManager, InternetState


def test_internet_manager_initial_state():
    mgr = InternetManager(check_interval=0.1, probe_timeout=0.1)
    assert mgr.state in (InternetState.ONLINE, InternetState.OFFLINE, InternetState.CONNECTING)


def test_internet_manager_force_offline():
    mgr = InternetManager(check_interval=0.1, probe_timeout=0.1)
    mgr.set_force_offline(True)
    assert mgr.is_online() is False
    assert mgr.state == InternetState.OFFLINE
    assert mgr.is_force_offline() is True

    mgr.set_force_offline(False)
    assert mgr.is_force_offline() is False


def test_internet_manager_mock_probe():
    mgr = InternetManager(check_interval=0.1, probe_timeout=0.1)
    
    # Mock online probe
    with patch.object(mgr, "_execute_probe", return_value=InternetState.ONLINE):
        state = mgr.probe_now()
        assert state == InternetState.ONLINE
        assert mgr.is_online() is True

    # Mock offline probe
    with patch.object(mgr, "_execute_probe", return_value=InternetState.OFFLINE):
        state = mgr.probe_now()
        assert state == InternetState.OFFLINE
        assert mgr.is_online() is False


def test_internet_manager_callbacks():
    mgr = InternetManager(check_interval=0.1, probe_timeout=0.1)
    online_called = []
    offline_called = []

    mgr.on_online(lambda: online_called.append(True))
    mgr.on_offline(lambda: offline_called.append(True))

    with patch.object(mgr, "_execute_probe", return_value=InternetState.ONLINE):
        mgr.probe_now()
    assert len(online_called) >= 1

    with patch.object(mgr, "_execute_probe", return_value=InternetState.OFFLINE):
        mgr.probe_now()
    assert len(offline_called) >= 1
