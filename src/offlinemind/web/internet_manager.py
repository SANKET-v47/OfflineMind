"""Internet connectivity manager with robust state machine and non-blocking probes."""

from __future__ import annotations
import enum
import logging
import socket
import threading
import time
from typing import Callable, List, Optional
import requests

logger = logging.getLogger(__name__)


class InternetState(enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    DEGRADED = "DEGRADED"


class InternetManager:
    """Manages internet detection, status events, and safe graceful degradation."""

    def __init__(
        self,
        check_interval: float = 3.0,
        probe_timeout: float = 1.5,
        probe_endpoints: Optional[List[str]] = None,
    ):
        self.check_interval = check_interval
        self.probe_timeout = probe_timeout
        self.probe_endpoints = probe_endpoints or [
            "1.1.1.1:53",
            "8.8.8.8:53",
            "http://www.google.com",
            "http://www.cloudflare.com",
        ]
        self._state = InternetState.CONNECTING
        self._simulated_offline = False
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._on_online_cbs: List[Callable[[], None]] = []
        self._on_offline_cbs: List[Callable[[], None]] = []
        self._on_change_cbs: List[Callable[[InternetState, InternetState], None]] = []

    @property
    def state(self) -> InternetState:
        with self._lock:
            if self._simulated_offline:
                return InternetState.OFFLINE
            return self._state

    def is_online(self) -> bool:
        return self.state == InternetState.ONLINE

    def set_force_offline(self, force: bool) -> None:
        """User-controlled killswitch to guarantee complete local privacy."""
        with self._lock:
            old_state = self.state
            self._simulated_offline = force
            new_state = self.state
            logger.info("Force offline toggled: %s (State: %s)", force, new_state.value)
            if old_state != new_state:
                self._dispatch_state_change(old_state, new_state)

    def is_force_offline(self) -> bool:
        with self._lock:
            return self._simulated_offline

    def on_online(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._on_online_cbs.append(callback)

    def on_offline(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._on_offline_cbs.append(callback)

    def on_state_change(self, callback: Callable[[InternetState, InternetState], None]) -> None:
        with self._lock:
            self._on_change_cbs.append(callback)

    def start(self) -> None:
        """Starts background non-blocking polling daemon."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="InternetPoller")
            self._thread.start()
            logger.debug("InternetManager daemon started.")

    def stop(self) -> None:
        """Stops background polling."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def probe_now(self) -> InternetState:
        """Executes a synchronous probe and updates state immediately."""
        with self._lock:
            if self._simulated_offline:
                return InternetState.OFFLINE

            detected = self._execute_probe()
            old_state = self._state
            self._state = detected
            if old_state != self._state:
                self._dispatch_state_change(old_state, self._state)
            return self.state

    def _execute_probe(self) -> InternetState:
        """Probes socket endpoints first (fastest), then HTTP endpoints."""
        successes = 0
        total_attempted = 0

        for ep in self.probe_endpoints:
            total_attempted += 1
            if ":" in ep and not ep.startswith("http"):
                # DNS / Socket Probe
                host, port_str = ep.split(":")
                try:
                    with socket.create_connection((host, int(port_str)), timeout=self.probe_timeout):
                        successes += 1
                        break  # Fast exit on first successful socket connection
                except Exception:
                    pass
            elif ep.startswith("http"):
                # HTTP Probe
                try:
                    resp = requests.head(ep, timeout=self.probe_timeout, allow_redirects=True)
                    if resp.status_code < 400:
                        successes += 1
                        break
                except Exception:
                    pass

        if successes > 0:
            return InternetState.ONLINE
        return InternetState.OFFLINE

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.probe_now()
            except Exception as e:
                logger.error("Error in internet probe loop: %s", e)
            self._stop_event.wait(self.check_interval)

    def _dispatch_state_change(self, old_state: InternetState, new_state: InternetState) -> None:
        for cb in self._on_change_cbs:
            try:
                cb(old_state, new_state)
            except Exception as e:
                logger.error("Error in state change callback: %s", e)

        if new_state == InternetState.ONLINE:
            for cb in self._on_online_cbs:
                try:
                    cb()
                except Exception as e:
                    logger.error("Error in online callback: %s", e)
        elif new_state == InternetState.OFFLINE:
            for cb in self._on_offline_cbs:
                try:
                    cb()
                except Exception as e:
                    logger.error("Error in offline callback: %s", e)
