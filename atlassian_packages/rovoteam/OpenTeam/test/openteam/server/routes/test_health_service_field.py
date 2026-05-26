"""CI preflight (I11): GET /api/health response includes ``service: "openteam"``.

This is the defensive marker that lets ``openteam.client.discovery.health_check``
distinguish a real OpenTeam server from an impostor process listening on
port 8000 (R5 mitigation). Dropping the field would silently break the
client-side service-match check.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openteam.client.discovery import SERVICE_NAME
from openteam.server.routes.health_routes import SERVICE_MARKER, router as health_router


def test_marker_constants_agree():
    """Server-side SERVICE_MARKER must match client-side SERVICE_NAME literal.

    Both modules independently hard-code "openteam"; this test fails if a
    refactor drifts them apart.
    """
    assert SERVICE_MARKER == SERVICE_NAME == "openteam"


def test_health_response_includes_service_field():
    app = FastAPI()
    app.include_router(health_router, prefix="/api")
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("service") == "openteam", (
        "I11 defensive marker missing from /api/health response. "
        "Without this, openteam.client cannot distinguish a real OpenTeam "
        "server from an impostor process on port 8000."
    )


def test_health_response_other_fields_unchanged():
    """Smoke check that adding `service` didn't break existing fields."""
    app = FastAPI()
    app.include_router(health_router, prefix="/api")
    client = TestClient(app)
    r = client.get("/api/health")
    body = r.json()
    assert body["status"] == "ok"
    assert "mode" in body
    assert "real_sessions" in body
    assert "version" in body
    assert "server_name" in body
