"""TIER-1 tests for openteam.client.attach — HTTP POST helper.

Tests the wrapper in isolation by spinning up a minimal HTTPServer in a
background thread. Avoids the FastAPI dep here so the client package's
test surface stays as stdlib-only as the package itself.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import threading
from contextlib import contextmanager

import pytest

from openteam.client.attach import AttachFailed, AttachResult, attach_session_via_http
from openteam.client.discovery import ServerHandle


# ── Minimal HTTP test server ────────────────────────────────────────────────
class _AttachHandler(http.server.BaseHTTPRequestHandler):
    # Class-level config knobs set by individual tests
    response_status: int = 200
    response_body: bytes = b'{"session_id":"x","session_root":"/tmp/x","created":true}'
    received_body: dict = {}

    def log_message(self, *args):
        pass  # silence test output

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            type(self).received_body = json.loads(raw)
        except json.JSONDecodeError:
            type(self).received_body = {"_raw": raw.decode("utf-8", "replace")}
        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.response_body)))
        self.end_headers()
        self.wfile.write(self.response_body)


@contextmanager
def _running_server():
    """Spawn the test HTTP server on a free port, yield (port, handler_cls)."""
    handler_cls = type("H", (_AttachHandler,), {})
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler_cls)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, handler_cls
    finally:
        httpd.shutdown()
        httpd.server_close()


def _handle(port: int) -> ServerHandle:
    return ServerHandle(
        server_id="server_test", pid=1, host="127.0.0.1", port=port,
        runtime_root="/tmp", server_dir_name="x",
        started_at="2026-05-18T00:00:00.000Z", version="0.1.0",
    )


class TestAttachSuccess:
    def test_returns_attach_result_on_200(self):
        with _running_server() as (port, H):
            H.response_status = 200
            H.response_body = json.dumps({
                "session_id": "rovodev-abc",
                "session_root": "/tmp/srv/sessions/rovodev-abc_20260518",
                "created": True,
            }).encode()
            result = attach_session_via_http(
                _handle(port),
                external_id="rovodev-abc",
                frontend_id="rovodev",
            )
            assert isinstance(result, AttachResult)
            assert result.session_id == "rovodev-abc"
            assert result.session_root == "/tmp/srv/sessions/rovodev-abc_20260518"
            assert result.created is True

    def test_sends_body_with_expected_shape(self):
        with _running_server() as (port, H):
            H.response_status = 200
            H.response_body = b'{"session_id":"x","session_root":"/x","created":false}'
            attach_session_via_http(
                _handle(port),
                external_id="rovodev-xyz",
                frontend_id="rovodev",
                frontend_metadata={"k": "v"},
                title="Hi",
            )
            assert H.received_body == {
                "external_id": "rovodev-xyz",
                "frontend_id": "rovodev",
                "frontend_metadata": {"k": "v"},
                "title": "Hi",
            }

    def test_omits_title_when_none(self):
        with _running_server() as (port, H):
            H.response_status = 200
            H.response_body = b'{"session_id":"x","session_root":"/x","created":false}'
            attach_session_via_http(
                _handle(port), external_id="rovodev-x", frontend_id="rovodev",
            )
            assert "title" not in H.received_body


class TestAttachFailures:
    def test_raises_on_4xx(self):
        with _running_server() as (port, H):
            H.response_status = 400
            H.response_body = b'{"detail":"bad prefix"}'
            with pytest.raises(AttachFailed, match="failed"):
                attach_session_via_http(
                    _handle(port), external_id="x-y", frontend_id="x",
                )

    def test_raises_on_connection_refused(self):
        # Port 1 is unlikely to have a listener
        with pytest.raises(AttachFailed):
            attach_session_via_http(
                _handle(1),
                external_id="rovodev-x", frontend_id="rovodev",
                timeout_s=0.5,
            )

    def test_raises_on_invalid_json(self):
        with _running_server() as (port, H):
            H.response_status = 200
            H.response_body = b'not json{{{'
            with pytest.raises(AttachFailed, match="invalid JSON"):
                attach_session_via_http(
                    _handle(port), external_id="rovodev-x", frontend_id="rovodev",
                )

    def test_raises_on_missing_required_field(self):
        with _running_server() as (port, H):
            H.response_status = 200
            H.response_body = b'{"session_id":"x"}'  # missing session_root, created
            with pytest.raises(AttachFailed, match="missing required field"):
                attach_session_via_http(
                    _handle(port), external_id="rovodev-x", frontend_id="rovodev",
                )
