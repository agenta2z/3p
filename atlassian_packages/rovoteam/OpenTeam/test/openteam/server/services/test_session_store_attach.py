"""TIER-1 tests for SessionStore.attach_or_create_session (v6 unified frontend protocol).

Covers Invariants I1 (idempotency), I2 (prefix whitelist + remainder regex),
and I3 (whitelist immutability sentinel — the whitelist itself is type-checked).
"""
from __future__ import annotations

import pytest

from openteam.server.services.session_store import (
    SessionStore,
    _VALID_FRONTEND_PREFIXES,
    validate_external_id,
)


@pytest.fixture
def store(tmp_path):
    """Fresh SessionStore rooted at tmp_path."""
    return SessionStore(tmp_path, resume_server="new")


class TestValidateExternalId:
    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_external_id("")

    def test_rejects_missing_dash(self):
        with pytest.raises(ValueError, match="separator"):
            validate_external_id("rovodevnodash")

    def test_rejects_unknown_prefix(self):
        with pytest.raises(ValueError, match="whitelist"):
            validate_external_id("unknown-abc")

    def test_rejects_unsafe_remainder_slash(self):
        with pytest.raises(ValueError, match="regex"):
            validate_external_id("rovodev-../etc/passwd")

    def test_rejects_unsafe_remainder_dollar(self):
        with pytest.raises(ValueError, match="regex"):
            validate_external_id("rovodev-abc$inject")

    def test_rejects_overly_long_remainder(self):
        with pytest.raises(ValueError, match="regex"):
            validate_external_id("rovodev-" + "x" * 129)

    def test_accepts_uuid_remainder(self):
        prefix, remainder = validate_external_id("rovodev-550e8400-e29b-41d4-a716-446655440000")
        assert prefix == "rovodev"
        assert remainder == "550e8400-e29b-41d4-a716-446655440000"

    def test_accepts_legacy_session_prefix(self):
        prefix, remainder = validate_external_id("session-1700000000-abcdef")
        assert prefix == "session"
        assert remainder == "1700000000-abcdef"

    def test_whitelist_contains_v6_prefixes(self):
        # CI-preflight sentinel: any change to the whitelist requires explicit review.
        # If this set changes, you must also update docs/SERVER_DISCOVERY.md.
        assert _VALID_FRONTEND_PREFIXES == frozenset({
            "rovodev", "webui", "mcp", "session", "slack", "vscode",
        })


class TestAttachOrCreate:
    def test_creates_when_missing(self, store):
        s = store.attach_or_create_session(external_id="rovodev-abc-123")
        assert s["id"] == "rovodev-abc-123"
        assert s["external_id"] == "rovodev-abc-123"
        assert s["frontend_id"] == "rovodev"
        # Re-read from disk confirms it actually persisted under the explicit id.
        again = store.get_session("rovodev-abc-123")
        assert again is not None
        assert again["id"] == "rovodev-abc-123"

    def test_idempotent_returns_same_session(self, store):
        s1 = store.attach_or_create_session(external_id="rovodev-deadbeef")
        s2 = store.attach_or_create_session(external_id="rovodev-deadbeef")
        assert s1["id"] == s2["id"]
        assert s1["created_at"] == s2["created_at"]
        # Same dir on disk, no duplicate
        sessions_dir = store._dir
        matches = [d for d in sessions_dir.iterdir()
                   if d.is_dir() and d.name.startswith("rovodev-deadbeef_")]
        assert len(matches) == 1

    def test_attach_does_not_overwrite_metadata(self, store):
        """Idempotent attach is read-or-create; never read-and-modify."""
        store.attach_or_create_session(
            external_id="rovodev-x1",
            frontend_metadata={"workspace": "/orig"},
        )
        # Second attach with different metadata MUST NOT clobber.
        s = store.attach_or_create_session(
            external_id="rovodev-x1",
            frontend_metadata={"workspace": "/new"},
        )
        assert s["frontend_metadata"] == {"workspace": "/orig"}

    def test_rejects_invalid_prefix(self, store):
        with pytest.raises(ValueError, match="whitelist"):
            store.attach_or_create_session(external_id="badprefix-abc")

    def test_frontend_id_defaults_to_prefix(self, store):
        s = store.attach_or_create_session(external_id="webui-1700000000-abc123")
        assert s["frontend_id"] == "webui"

    def test_frontend_id_explicit_wins(self, store):
        s = store.attach_or_create_session(
            external_id="rovodev-abc",
            frontend_id="rovodev-tui",
        )
        assert s["frontend_id"] == "rovodev-tui"

    def test_title_propagates(self, store):
        s = store.attach_or_create_session(
            external_id="rovodev-titled",
            title="My Task",
        )
        assert s["title"] == "My Task"
