"""Mock Trusted Source Server for OfflineMind.
Provides controlled endpoints for testing sync, dynamic fact updates,
and simulated network failures.
"""

from __future__ import annotations
import json
import logging
import threading
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

import copy

logger = logging.getLogger(__name__)

DEFAULT_MOCK_FACTS = [
    {
        "entity": "College",
        "attribute": "name",
        "value": "Springfield Technical College",
        "category": "education",
        "source_priority": 85,
        "confidence": 1.0,
    },
    {
        "entity": "College",
        "attribute": "location",
        "value": "Springfield, OR",
        "category": "education",
        "source_priority": 85,
        "confidence": 1.0,
    },
    {
        "entity": "College",
        "attribute": "president",
        "value": "Dr. Eleanor Vance",
        "category": "leadership",
        "source_priority": 85,
        "confidence": 1.0,
    },
]


class MockServerState:
    """Thread-safe state container for mock server facts."""

    def __init__(self):
        self.lock = threading.Lock()
        self.source_name = "Official University Registrar"
        self.reset()

    def reset(self):
        with self.lock:
            self.facts = copy.deepcopy(DEFAULT_MOCK_FACTS)
            self.updated_at = datetime.now(timezone.utc).isoformat()
            self.simulate_hang = False
            self.simulate_corruption = False

    def get_feed(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "source_name": self.source_name,
                "version": "2026.2",
                "timestamp": self.updated_at,
                "facts": [dict(f) for f in self.facts],
            }

    def rename_college(self, new_name: str, reason: str = "Board Charter Amendment") -> None:
        with self.lock:
            for f in self.facts:
                if f["entity"] == "College" and f["attribute"] == "name":
                    f["value"] = new_name
                    f["change_reason"] = reason
            self.updated_at = datetime.now(timezone.utc).isoformat()


_GLOBAL_STATE = MockServerState()


class MockFeedHandler(BaseHTTPRequestHandler):
    """Handles incoming mock HTTP requests."""

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP access logs in test runs
        return

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.flush()
        except Exception:
            pass

    def do_GET(self) -> None:
        if self.path == "/health":
            body = b'{"status": "ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            try:
                self.wfile.flush()
            except Exception:
                pass
            return

        if self.path == "/api/trusted_feed":
            if _GLOBAL_STATE.simulate_hang:
                # Simulate mid-sync connection drop or stall
                time.sleep(2.0)
                self.send_error(504, "Gateway Timeout")
                return

            if _GLOBAL_STATE.simulate_corruption:
                # Return invalid / corrupted payload
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"facts": [{"entity": "Broken", "attribute":')
                return

            data = _GLOBAL_STATE.get_feed()
            payload = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            req_data = {}

        if self.path == "/api/admin/rename_college":
            new_name = req_data.get("name", "Springfield University of Technology")
            reason = req_data.get("reason", "Official University Rebranding")
            _GLOBAL_STATE.rename_college(new_name, reason)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "status": "updated",
                    "new_name": new_name,
                    "updated_at": _GLOBAL_STATE.updated_at,
                }).encode("utf-8")
            )
            return

        if self.path == "/api/admin/simulate_hang":
            _GLOBAL_STATE.simulate_hang = req_data.get("enable", True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"simulate_hang": _GLOBAL_STATE.simulate_hang}).encode("utf-8"))
            return

        if self.path == "/api/admin/simulate_corruption":
            _GLOBAL_STATE.simulate_corruption = req_data.get("enable", True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"simulate_corruption": _GLOBAL_STATE.simulate_corruption}).encode("utf-8"))
            return

        if self.path == "/api/admin/reset":
            _GLOBAL_STATE.reset()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "reset_to_default"}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


class MockServerThread:
    """Threaded wrapper to manage the lifecycle of MockServer in tests/demos."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.url = f"http://{self.host}:{self.port}"
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.server = ThreadingHTTPServer((self.host, self.port), MockFeedHandler)
        self.port = self.server.server_address[1]
        self.url = f"http://{self.host}:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)
        logger.info("MockServer running on %s", self.url)

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        logger.info("MockServer stopped.")

    def reset_state(self) -> None:
        _GLOBAL_STATE.reset()

    def rename_college(self, new_name: str, reason: str = "Official Rebranding") -> None:
        _GLOBAL_STATE.rename_college(new_name, reason)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OfflineMind Mock Trusted Source Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockFeedHandler)
    print(f"Mock Trusted Source Server running at http://{args.host}:{args.port}")
    print(f"  - Feed URL: http://{args.host}:{args.port}/api/trusted_feed")
    print(f"  - Rename endpoint: POST http://{args.host}:{args.port}/api/admin/rename_college")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Mock Server...")
        server.server_close()
