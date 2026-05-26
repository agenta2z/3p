"""TIER-1 tests for openteam.mcp_server.context."""
from __future__ import annotations

from openteam.mcp_server.context import build_session_context


class TestBuildSessionContext:
    def test_unique_task_id(self):
        ctx1 = build_session_context()
        ctx2 = build_session_context()
        assert ctx1["task_id"] != ctx2["task_id"]

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENTEAM_WORKING_DIR", "/custom/dir")
        ctx = build_session_context()
        assert ctx["working_dir"] == "/custom/dir"

    def test_empty_env_minimal(self, monkeypatch):
        """With no OPENTEAM_* env vars, ctx has task_id and interactive=None."""
        for key in (
            "OPENTEAM_WORKING_DIR",
            "OPENTEAM_SERVER_DIR",
            "OPENTEAM_CLOUD_ID",
            "OPENTEAM_UCT_TOKEN",
            "OPENTEAM_EMAIL",
        ):
            monkeypatch.delenv(key, raising=False)

        ctx = build_session_context()
        assert "task_id" in ctx
        assert ctx["interactive"] is None
        # None of the env-mapped keys should be present
        for mapped_key in ("working_dir", "server_dir", "cloud_id", "uct_token", "email"):
            assert mapped_key not in ctx
