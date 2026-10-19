"""Tiny TCP ping/pong health-check server for the Unity bridge.

Usage:
    python bridge_ping_server.py
    python bridge_ping_server.py --host 127.0.0.1 --port 5000

The protocol is one newline-terminated command per connection:
    PING
    -> PONG
"""

from __future__ import annotations

import argparse
import socketserver


class PingHandler(socketserver.StreamRequestHandler):
    """Handle one line-based health-check request."""

    def handle(self) -> None:
        request = self.rfile.readline(1024).decode("ascii", errors="replace").strip()
        if request == "PING":
            response = "PONG\n"
        else:
            response = "ERROR unknown_command\n"
        self.wfile.write(response.encode("ascii"))
        self.wfile.flush()
        print(f"{self.client_address[0]}:{self.client_address[1]} {request!r} -> {response.strip()}", flush=True)


class PingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Interface to listen on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="TCP port to listen on (default: 5000)")
    args = parser.parse_args()

    with PingServer((args.host, args.port), PingHandler) as server:
        print(f"Ping server listening on {args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nPing server stopped.", flush=True)


if __name__ == "__main__":
    main()
