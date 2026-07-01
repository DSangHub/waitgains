#!/usr/bin/env python3
"""Minimal zero-dependency dev server for the waitgains / HoldPay landing page.

The site's markup lives inside ``README.md`` (prefixed with a ``# waitgains``
markdown heading). This server reads that file on every request, strips any
content before ``<!DOCTYPE``, and serves the result as ``text/html`` so the
page renders in a browser. Reading on each request means edits to ``README.md``
show up on refresh, which is convenient for development.

Usage:
    python3 serve.py [--host HOST] [--port PORT]
"""

from __future__ import annotations

import argparse
import http.server
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "README.md"


def render_html() -> bytes:
    text = SOURCE.read_text(encoding="utf-8")
    idx = text.find("<!DOCTYPE")
    if idx == -1:
        idx = text.find("<html")
    if idx != -1:
        text = text[idx:]
    return text.encode("utf-8")


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        body = render_html()
        self._send(body)
        self.wfile.write(body)

    def do_HEAD(self) -> None:  # noqa: N802
        self._send(render_html())

    def log_message(self, fmt: str, *args) -> None:
        print("[serve.py] " + (fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the landing page.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving HoldPay landing page on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
