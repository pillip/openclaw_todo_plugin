"""HTTP server bridge for the OpenClaw JS/TS gateway.

Wraps ``handle_message`` in a minimal HTTP server so that a thin JS bridge
plugin can call it via ``fetch``.  Uses only the Python stdlib
(``http.server``) — zero runtime dependencies.

Environment variables
---------------------
OPENCLAW_TODO_PORT      Server port (default 8200)
OPENCLAW_TODO_DB_PATH   SQLite database path (default: plugin default)
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from openclaw_todo.plugin import handle_message

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8200
DEFAULT_HOST = "127.0.0.1"


def _get_config() -> tuple[str, int, str | None]:
    """Return (host, port, db_path) from environment."""
    host = DEFAULT_HOST
    port = int(os.environ.get("OPENCLAW_TODO_PORT", str(DEFAULT_PORT)))
    db_path = os.environ.get("OPENCLAW_TODO_DB_PATH") or None
    return host, port, db_path


def _json_response(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    """Write a JSON response."""
    payload = json.dumps(body).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _make_handler_class(db_path: str | None) -> type[BaseHTTPRequestHandler]:
    """Create a request handler class with the given *db_path* baked in."""

    class TodoHTTPHandler(BaseHTTPRequestHandler):
        """Handle /health and /message endpoints."""

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                _json_response(self, HTTPStatus.OK, {"status": "ok"})
            else:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/message":
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "not found"})
                return

            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "empty body"})
                return

            raw = self.rfile.read(content_length)

            # Parse JSON
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                return

            # Validate fields
            if not isinstance(data, dict):
                _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                return

            text = data.get("text")
            sender_id = data.get("sender_id")
            if text is None or sender_id is None:
                _json_response(
                    self,
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"error": "missing required fields: text, sender_id"},
                )
                return

            # Dispatch
            response = handle_message(str(text), {"sender_id": str(sender_id)}, db_path=db_path)
            _json_response(self, HTTPStatus.OK, {"response": response})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Route request logs through the Python logger."""
            logger.info(format, *args)

    return TodoHTTPHandler


def run(host: str | None = None, port: int | None = None, db_path: str | None = None) -> None:
    """Start the HTTP server (blocking)."""
    env_host, env_port, env_db_path = _get_config()
    host = host or env_host
    port = port if port is not None else env_port
    db_path = db_path or env_db_path

    handler_class = _make_handler_class(db_path)
    server = HTTPServer((host, port), handler_class)

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d, shutting down...", signum)
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    actual_port = server.server_address[1]
    logger.info("openclaw-todo-server listening on %s:%d", host, actual_port)
    print(f"openclaw-todo-server listening on {host}:{actual_port}", file=sys.stderr)

    server.serve_forever()
    server.server_close()
    logger.info("Server stopped.")
