"""Tests for the HTTP server bridge (server.py)."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import HTTPServer

import pytest

from openclaw_todo.server import _make_handler_class


@pytest.fixture()
def server_url(tmp_path):
    """Start the HTTP server on an OS-assigned port with a temp DB."""
    db_path = str(tmp_path / "test_todo.db")
    handler_class = _make_handler_class(db_path)
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def _get(url: str) -> tuple[int, dict]:
    """Helper: GET request, return (status, json_body)."""
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url: str, body: bytes | None = None, content_type: str = "application/json") -> tuple[int, dict]:
    """Helper: POST request, return (status, json_body)."""
    req = urllib.request.Request(url, data=body, method="POST")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# --- Health endpoint ---


class TestHealthEndpoint:
    def test_health_ok(self, server_url):
        status, body = _get(f"{server_url}/health")
        assert status == 200
        assert body == {"status": "ok"}

    def test_unknown_get_path_404(self, server_url):
        status, body = _get(f"{server_url}/nonexistent")
        assert status == 404
        assert body["error"] == "not found"


# --- Message endpoint ---


class TestMessageEndpoint:
    def test_todo_add_returns_response(self, server_url):
        payload = json.dumps({"text": "todo: add Buy milk", "sender_id": "U001"}).encode()
        status, body = _post(f"{server_url}/message", payload)
        assert status == 200
        assert body["response"] is not None
        assert "Buy milk" in body["response"]

    def test_non_todo_returns_null(self, server_url):
        payload = json.dumps({"text": "hello world", "sender_id": "U001"}).encode()
        status, body = _post(f"{server_url}/message", payload)
        assert status == 200
        assert body["response"] is None

    def test_todo_usage(self, server_url):
        payload = json.dumps({"text": "todo:", "sender_id": "U001"}).encode()
        status, body = _post(f"{server_url}/message", payload)
        assert status == 200
        assert body["response"] is not None
        assert "📖 OpenClaw TODO" in body["response"]


# --- Error handling ---


class TestErrorHandling:
    def test_empty_body_400(self, server_url):
        status, body = _post(f"{server_url}/message", b"")
        assert status == 400
        assert "empty body" in body["error"]

    def test_invalid_json_400(self, server_url):
        status, body = _post(f"{server_url}/message", b"not json{{{")
        assert status == 400
        assert "invalid JSON" in body["error"]

    def test_missing_fields_422(self, server_url):
        payload = json.dumps({"text": "todo: add test"}).encode()
        status, body = _post(f"{server_url}/message", payload)
        assert status == 422
        assert "missing" in body["error"]

    def test_missing_text_field_422(self, server_url):
        """Missing 'text' field (only sender_id provided) returns 422."""
        payload = json.dumps({"sender_id": "U001"}).encode()
        status, body = _post(f"{server_url}/message", payload)
        assert status == 422
        assert "missing" in body["error"]

    def test_non_dict_json_body_400(self, server_url):
        """JSON array body (not a dict) returns 400."""
        status, body = _post(f"{server_url}/message", b"[1, 2, 3]")
        assert status == 400
        assert "invalid JSON" in body["error"]

    def test_unknown_post_path_404(self, server_url):
        payload = json.dumps({"text": "hi", "sender_id": "U001"}).encode()
        status, _body = _post(f"{server_url}/other", payload)
        assert status == 404

    def test_invalid_content_length_400(self, server_url):
        """Non-numeric Content-Length returns 400."""
        url = f"{server_url}/message"
        req = urllib.request.Request(url, data=b'{"x":1}', method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Content-Length", "not-a-number")
        try:
            resp = urllib.request.urlopen(req)
            status, body = resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            status, body = e.code, json.loads(e.read())
        assert status == 400
        assert "Content-Length" in body["error"]

    def test_oversized_body_413(self, server_url):
        """Content-Length exceeding MAX_BODY_BYTES is rejected with 413."""
        from openclaw_todo.server import MAX_BODY_BYTES

        # Send a small body but claim a huge Content-Length so the server
        # rejects it before reading the full stream.
        url = f"{server_url}/message"
        req = urllib.request.Request(url, data=b'{"x":1}', method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Content-Length", str(MAX_BODY_BYTES + 1))
        try:
            resp = urllib.request.urlopen(req)
            status, body = resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            status, body = e.code, json.loads(e.read())
        assert status == 413
        assert "limit" in body["error"]
