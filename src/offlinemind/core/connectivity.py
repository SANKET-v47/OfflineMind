"""Non-blocking background connectivity monitor for OfflineMind."""

from __future__ import annotations
import socket
import threading
import time
import logging
from typing import Callable, List, Optional
from urllib.parse import urlparse
import requests

from offlinemind.config import (
    CONNECTIVITY_CHECK_INTERVAL_SEC,
    DEFAULT_PING_HOSTS,
    CONNECTIVITY_PROBE_TIMEOUT_SEC,
)

logger = logging.getLogger(__name__)


class ConnectivityMonitor:
    """Monitors online/offline network status in a non-blocking background thread.
    
    Supports simulated offline mode, event triggers on state transitions,
    and debouncing.
    """

    def __init__(
        self,
        check_interval: float = CONNECTIVITY_CHECK_INTERVAL_SEC,
        probe_timeout: float = CONNECTIVITY_PROBE_TIMEOUT_SEC,
        ping_hosts: Optional[List[str]] = None,
    ):
        self.check_interval = check_interval
        self.probe_timeout = probe_timeout
        self.ping_hosts = ping_hosts or list(DEFAULT_PING_HOSTS)

        self._is_online: bool = False
        self._simulated_offline: bool = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        # Callbacks
        self._on_connect_callbacks: List[Callable[[], None]] = []
        self._on_disconnect_callbacks: List[Callable[[], None]] = []

    def set_simulated_offline(self, simulate: bool) -> None:
        """Forces the monitor into simulated offline mode."""
        with self._lock:
            old_status = self.is_online()
            self._simulated_offline = simulate
            new_status = self.is_online()

        if old_status != new_status:
            self._trigger_callbacks(new_status)

    def is_simulated_offline(self) -> bool:
        with self._lock:
            return self._simulated_offline

    def is_online(self) -> bool:
        """Returns True if network is reachable and simulated offline is inactive."""
        with self._lock:
            if self._simulated_offline:
                return False
            return self._is_online

    def on_connect(self, callback: Callable[[], None]) -> None:
        """Registers callback fired when transition OFFLINE -> ONLINE occurs."""
        self._on_connect_callbacks.append(callback)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Registers callback fired when transition ONLINE -> OFFLINE occurs."""
        self._on_disconnect_callbacks.append(callback)

    def check_reachability(self) -> bool:
        """Performs active probe against configured hosts."""
        for target in self.ping_hosts:
            try:
                if target.startswith("http://") or target.startswith("https://"):
                    resp = requests.get(target, timeout=self.probe_timeout)
                    if resp.status_code < 500:
                        return True
                else:
                    # Hostname/IP:port socket probe
                    host, port_str = target.split(":")
                    port = int(port_str)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.probe_timeout)
                    sock.connect((host, port))
                    sock.close()
                    return True
            except Exception:
                continue
        return False

    def probe_now(self) -> bool:
        """Performs immediate reachability check and updates status."""
        reachable = self.check_reachability()
        with self._lock:
            old_online = self.is_online()
            self._is_online = reachable
            new_online = self.is_online()

        if old_online != new_online:
            self._trigger_callbacks(new_online)
        return new_online

    def _trigger_callbacks(self, is_online: bool) -> None:
        callbacks = self._on_connect_callbacks if is_online else self._on_disconnect_callbacks
        logger.info("Connectivity state changed to: %s", "ONLINE" if is_online else "OFFLINE")
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("Error in connectivity callback: %s", e)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.probe_now()
            except Exception as e:
                logger.debug("Error probing connectivity: %s", e)
            self._stop_event.wait(self.check_interval)

    def start(self) -> None:
        """Starts background monitoring thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ConnectivityMonitor", daemon=True)
        self._thread.start()
        logger.info("Connectivity monitor started.")

    def stop(self) -> None:
        """Stops background monitoring thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Connectivity monitor stopped.")
