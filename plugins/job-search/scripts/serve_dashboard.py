#!/usr/bin/env python3
"""Serve the job-search home folder read-only on 127.0.0.1 so the dashboard has a local URL.

Usage:
  serve_dashboard.py [--home H] [--port 8765]          # serve until stopped (Ctrl+C)
  serve_dashboard.py [--home H] [--port 8765] --check  # exit 0 if something already listens

Binds to localhost only. Only GET and HEAD are answered, directory listings are off, and only
dashboard.html, jobs/<id>/{resume.html,resume.pdf,answers.md,jd.md} and the career radar reports
radar/radar-<YYYY-MM-DD>.md are served.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import re
import socket
import urllib.parse
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jslib  # noqa: E402

HOST = "127.0.0.1"
# Only the dashboard and the per-job files it links to are served. Profile, memory and
# raw JSON stay private even to other pages running on this machine.
ALLOWED = re.compile(r"^/(dashboard\.html|jobs/[A-Za-z0-9._-]+/(resume\.html|resume\.pdf|answers\.md|jd\.md)"
                     r"|radar/radar-\d{4}-\d{2}-\d{2}\.md)$")
DEFAULT_PORT = 8765


def port_in_use(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


class ReadOnlyHandler(http.server.SimpleHTTPRequestHandler):
    """Static files only. No listings, no writes, no caching of stale dashboards."""

    def send_head(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/dashboard.html")
            self.end_headers()
            return None
        if ".." in path or not ALLOWED.match(path):
            self.send_error(404, "Not found")
            return None
        return super().send_head()

    def list_directory(self, path):  # noqa: D401 - stdlib override
        self.send_error(403, "Directory listing is off")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _deny(self):
        self.send_error(405, "Read-only server")

    do_POST = do_PUT = do_DELETE = do_PATCH = _deny

    def log_message(self, fmt, *args):
        sys.stderr.write("[dashboard] %s\n" % (fmt % args))


ReadOnlyHandler.extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map)
ReadOnlyHandler.extensions_map.update({".md": "text/plain; charset=utf-8", ".json": "application/json",
                                       ".jsonl": "text/plain; charset=utf-8"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Serve the dashboard on http://127.0.0.1:PORT (read-only).")
    ap.add_argument("--home")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--check", action="store_true", help="exit 0 if the port is already in use, 1 if free")
    args = ap.parse_args(argv)

    url = "http://%s:%d/dashboard.html" % (HOST, args.port)
    if args.check:
        if port_in_use(args.port):
            print("Something is already listening on %s:%d. Try %s" % (HOST, args.port, url))
            return 0
        print("Nothing is listening on %s:%d." % (HOST, args.port))
        return 1

    home = jslib.require_home(args.home)
    if not (home / "dashboard.html").exists():
        print("Note: %s has no dashboard.html yet. Run build_dashboard.py first." % home, file=sys.stderr)
    if port_in_use(args.port):
        print("Port %d is already in use. If the dashboard server is running, open %s" % (args.port, url))
        print("Otherwise pick another port with --port.")
        return 1

    handler = functools.partial(ReadOnlyHandler, directory=str(home))
    httpd = http.server.ThreadingHTTPServer((HOST, args.port), handler)
    print("Serving %s (read-only, localhost only)." % home)
    print(url, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
