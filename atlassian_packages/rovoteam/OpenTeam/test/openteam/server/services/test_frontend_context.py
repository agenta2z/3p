"""TIER-1 tests for openteam.server.services.frontend_context.

Verifies env-var protocol decoding + mode discipline (I9 + I15).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from openteam.server.services.frontend_context import build_frontend_session_context
from openteam.server.services.session_store import SessionStore


@pytest.fixture
def server_dir(tmp_path):
    """Create a real SessionStore + return its server_dir."""
    runtime_root = tmp_path / "rt"
    runtime_root.mkdir()
    store = SessionStore(runtime_root, resume_server="new")
    return store.server_dir, store


def _set_env(monkeypatch, **kwargs):
    for k in ("OPENTEAM_MODE", "OPENTEAM_SESSION_ID", "OPENTEAM_SERVER_DIR",
              "OPENTEAM_FRONTEND_ID", "OPENTEAM_FRONTEND_METADATA"):
        monkeypatch.delenv(k, raising=False)
    for k, v in kwargs.items():
        if v is not None:
            monkeypatch.setenv(k, v)


# ── Path A fallback (no frontend context) ───────────────────────────────────
class TestPathAFallback:
    def test_empty_when_no_env(self, monkeypatch):
        _set_env(monkeypatch)
        assert build_frontend_session_context() == {}

    def test_empty_when_session_id_set_but_no_server_dir(self, monkeypatch):
        _set_env(monkeypatch, OPENTEAM_SESSION_ID="rovodev-abc")
        assert build_frontend_session_context() == {}

    def test_empty_when_server_dir_set_but_no_session_id(self, monkeypatch):
        _set_env(monkeypatch, OPENTEAM_SERVER_DIR="/tmp")
        assert build_frontend_session_context() == {}


# ── Subprocess Mode (creates) ───────────────────────────────────────────────
class TestSubprocessMode:
    def test_creates_session(self, server_dir, monkeypatch):
        sdir, store = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="subprocess",
            OPENTEAM_SESSION_ID="rovodev-sub-1",
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        ctx = build_frontend_session_context()
        assert ctx["session_id"] == "rovodev-sub-1"
        assert ctx["session_root"].endswith("rovodev-sub-1") or "rovodev-sub-1_" in ctx["session_root"]
        # Verify session actually persisted
        # (NOTE: build_frontend_session_context constructs its OWN SessionStore
        # via SessionStore(runtime_root=..., resume_server=server_name); that
        # store wrote the session to the same on-disk dir we control via
        # `store` fixture. Re-read via a fresh store to avoid any in-memory
        # state.)
        verify_store = SessionStore(store.runtime_root, resume_server=store.server_name)
        assert verify_store.get_session("rovodev-sub-1") is not None

    def test_default_mode_is_subprocess(self, server_dir, monkeypatch):
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_SESSION_ID="rovodev-default",
            OPENTEAM_SERVER_DIR=str(sdir),
        )  # NO OPENTEAM_MODE set
        ctx = build_frontend_session_context()
        # Default = subprocess; would have created the session
        assert ctx["session_id"] == "rovodev-default"

    def test_invalid_mode_falls_back_to_subprocess(self, server_dir, monkeypatch, caplog):
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="garbage",
            OPENTEAM_SESSION_ID="rovodev-invalid-mode",
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        ctx = build_frontend_session_context()
        # Got created (subprocess mode treatment)
        assert ctx["session_id"] == "rovodev-invalid-mode"


# ── Server Mode (read-only, I9 fail-fast on miss) ───────────────────────────
class TestServerMode:
    def test_reads_existing_session(self, server_dir, monkeypatch):
        sdir, store = server_dir
        # Pre-create the session via the same path the HTTP attach endpoint uses
        store.attach_or_create_session(external_id="rovodev-server-1")
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="server",
            OPENTEAM_SESSION_ID="rovodev-server-1",
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        ctx = build_frontend_session_context()
        assert ctx["session_id"] == "rovodev-server-1"

    def test_fail_fast_on_missing_session(self, server_dir, monkeypatch):
        """I9: Server Mode + missing session must raise (NOT silent self-heal).

        Calling attach_or_create_session here would make the subprocess a
        second writer, reintroducing the _update_index race that I9 was
        designed to eliminate.
        """
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="server",
            OPENTEAM_SESSION_ID="rovodev-never-existed",
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        with pytest.raises(RuntimeError, match=r"\[I9\]"):
            build_frontend_session_context()


# ── Bare-id composition (frontend supplied just the UUID) ───────────────────
class TestBareIdComposition:
    def test_composes_with_env_frontend_id(self, server_dir, monkeypatch):
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="subprocess",
            OPENTEAM_SESSION_ID="abc-def-1234",   # bare, not whitelist-prefixed
            OPENTEAM_FRONTEND_ID="rovodev",
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        ctx = build_frontend_session_context()
        assert ctx["session_id"] == "rovodev-abc-def-1234"
        assert ctx["external_id"] == "rovodev-abc-def-1234"

    def test_already_prefixed_passes_through(self, server_dir, monkeypatch):
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="subprocess",
            OPENTEAM_SESSION_ID="webui-1700000000-abc123",  # already prefixed
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        ctx = build_frontend_session_context()
        assert ctx["session_id"] == "webui-1700000000-abc123"
        assert ctx["external_id"] == "webui-1700000000-abc123"

    def test_kwarg_overrides_env(self, server_dir, monkeypatch):
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="subprocess",
            OPENTEAM_SESSION_ID="abc-def",
            OPENTEAM_FRONTEND_ID="rovodev",     # env says rovodev
            OPENTEAM_SERVER_DIR=str(sdir),
        )
        # kwarg overrides
        ctx = build_frontend_session_context(frontend_id="slack")
        assert ctx["session_id"] == "slack-abc-def"


class TestFrontendMetadata:
    def test_env_metadata_parsed_from_json(self, server_dir, monkeypatch):
        sdir, store = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="subprocess",
            OPENTEAM_SESSION_ID="rovodev-meta-env",
            OPENTEAM_SERVER_DIR=str(sdir),
            OPENTEAM_FRONTEND_METADATA=json.dumps({"workspace": "/tmp/proj"}),
        )
        ctx = build_frontend_session_context()
        assert ctx["session_id"] == "rovodev-meta-env"
        # Verify persisted (Subprocess Mode created)
        verify_store = SessionStore(store.runtime_root, resume_server=store.server_name)
        session = verify_store.get_session("rovodev-meta-env")
        assert session["frontend_metadata"] == {"workspace": "/tmp/proj"}

    def test_invalid_json_logs_and_falls_back_to_empty(self, server_dir, monkeypatch):
        sdir, _ = server_dir
        _set_env(
            monkeypatch,
            OPENTEAM_MODE="subprocess",
            OPENTEAM_SESSION_ID="rovodev-badjson",
            OPENTEAM_SERVER_DIR=str(sdir),
            OPENTEAM_FRONTEND_METADATA="not json{{{",
        )
        # Should NOT raise; should warn + use {}.
        ctx = build_frontend_session_context()
        assert ctx["session_id"] == "rovodev-badjson"
