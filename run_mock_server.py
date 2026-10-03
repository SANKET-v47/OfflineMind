"""OfflineMind Mock Trusted Source Server Launcher."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from data.mock_server import MockFeedHandler
from http.server import ThreadingHTTPServer

def main():
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

if __name__ == "__main__":
    main()
