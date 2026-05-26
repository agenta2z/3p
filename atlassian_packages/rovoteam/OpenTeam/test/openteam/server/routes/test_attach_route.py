"""TIER-1 tests for POST /api/sessions/attach (v6 unified frontend protocol).

Tests the route in isolation by mounting it on a fresh FastAPI app with a
real :class:`SessionStore` + :class:`RealSessionDataService` wired in. This
avoids dragging in the full server bootstrap (which loads fixtures, LLM
backends, etc.) while still exercising the actual code path the production
server uses.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openteam.server.routes.session_routes import router as session_router
from openteam.server.services.data_service import RealSessionDataService
from openteam.server.services.session_store import SessionStore


@pytest.fixture
def app_with_real_sessions(tmp_path):
    """FastAPI app with a real SessionStore mounted, no fixtures needed."""
    runtime_root = tmp_path / "rt"
    runtime_root.mkdir()
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    # MockDataService.__init__ loads JSON fixtures from this dir; empty dir
    # is fine — it just leaves all the mock dicts empty.

    store = SessionStore(runtime_root, resume_server="new")
    svc = RealSessionDataService(fixtures_dir, store)

    app = FastAPI()
    app.state.data_service = svc
    app.include_router(session_router, prefix="/api/sessions")
    return app, store


@pytest.fixture
def client(app_with_real_sessions):
    app, _ = app_with_real_sessions
    return TestClient(app)


@pytest.fixture
def mock_only_app(tmp_path):
    """FastAPI app with a MockDataService — used to exercise mock-mode 400."""
    from openteam.server.services.data_service import MockDataService

    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    svc = MockDataService(fixtures_dir)
    app = FastAPI()
    app.state.data_service = svc
    app.include_router(session_router, prefix="/api/sessions")
    return app


class TestAttachCreates:
    def test_creates_new_returns_created_true(self, client):
        r = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-abc-123",
            "frontend_id": "rovodev",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "rovodev-abc-123"
        assert body["created"] is True
        assert body["session_root"]  # absolute path

    def test_idempotent_returns_created_false_second_time(self, client):
        first = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-deadbeef",
            "frontend_id": "rovodev",
        })
        assert first.status_code == 200
        assert first.json()["created"] is True

        second = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-deadbeef",
            "frontend_id": "rovodev",
        })
        assert second.status_code == 200
        assert second.json()["created"] is False
        assert second.json()["session_id"] == first.json()["session_id"]
        assert second.json()["session_root"] == first.json()["session_root"]

    def test_metadata_persisted(self, app_with_real_sessions, client):
        _, store = app_with_real_sessions
        r = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-meta-1",
            "frontend_id": "rovodev",
            "frontend_metadata": {"workspace": "/tmp/proj", "tui_version": "1.0"},
        })
        assert r.status_code == 200
        # Verify metadata was persisted on disk
        session = store.get_session("rovodev-meta-1")
        assert session is not None
        assert session["frontend_metadata"] == {
            "workspace": "/tmp/proj",
            "tui_version": "1.0",
        }

    def test_frontend_id_defaults_to_prefix(self, app_with_real_sessions, client):
        _, store = app_with_real_sessions
        r = client.post("/api/sessions/attach", json={
            "external_id": "webui-1700000000-abc",
        })
        assert r.status_code == 200
        session = store.get_session("webui-1700000000-abc")
        assert session["frontend_id"] == "webui"

    def test_title_propagates(self, app_with_real_sessions, client):
        _, store = app_with_real_sessions
        r = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-titled",
            "title": "My Workspace",
        })
        assert r.status_code == 200
        session = store.get_session("rovodev-titled")
        assert session["title"] == "My Workspace"


class TestAttachValidation:
    def test_invalid_prefix_returns_400(self, client):
        r = client.post("/api/sessions/attach", json={
            "external_id": "evil-prefix-abc",
            "frontend_id": "evil",
        })
        assert r.status_code == 400
        assert "whitelist" in r.text.lower()

    def test_unsafe_remainder_returns_400(self, client):
        r = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-../etc/passwd",
        })
        assert r.status_code == 400
        assert "regex" in r.text.lower()

    def test_missing_external_id_returns_422(self, client):
        # Pydantic validation fires before our handler
        r = client.post("/api/sessions/attach", json={})
        assert r.status_code == 422


class TestAttachMockMode:
    """I18: mock-mode safety — endpoint returns 400 when data_service is mock."""

    def test_mock_mode_returns_400(self, mock_only_app):
        client = TestClient(mock_only_app)
        r = client.post("/api/sessions/attach", json={
            "external_id": "rovodev-x",
        })
        assert r.status_code == 400
        assert "mock mode" in r.text.lower()


class TestAttachOrderingVsCreate:
    """Sanity check that POST /api/sessions/attach doesn't collide with POST /api/sessions.

    Adding /attach AFTER POST "" / POST "/" must not change behavior of the
    create_session route.
    """

    def test_legacy_create_still_works(self, client):
        r = client.post("/api/sessions", json={"title": "Legacy"})
        assert r.status_code == 200
        sid = r.json()["data"]["id"]
        # Legacy sessions get server-minted ids with "session-" prefix
        assert sid.startswith("session-")
