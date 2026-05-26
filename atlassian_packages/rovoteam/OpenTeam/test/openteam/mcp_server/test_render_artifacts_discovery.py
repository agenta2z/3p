"""TIER-1: render_result surfaces _path/_dir keys as Artifacts and ignores others."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from openteam.mcp_server._helpers import render_result

# Representative context_updates per tool, using known _path / _dir suffixes.
_TOOL_CONTEXTS: dict[str, dict[str, str]] = {
    "task": {
        "workspace_path": "/tmp/ws",
        "plan_path": "/tmp/plan.md",
        "impl_path": "/tmp/impl.md",
        "cache_dir": "/tmp/cache",
        # non-artifact keys
        "status": "complete",
        "elapsed": "42s",
    },
    "create_role": {
        "output_path": "/tmp/role.md",
        "working_dir": "/tmp/work",
        "run_id": "abc123",
    },
    "role_setup": {
        "report_path": "/tmp/report.md",
        "skills_dir": "/tmp/skills",
        "agent_name": "orchestrator",
    },
    "project_onboarding": {
        "onboarding_path": "/tmp/onboarding.md",
        "artifacts_dir": "/tmp/artifacts",
        "session_id": "xyz",
    },
}


@pytest.mark.parametrize("tool_name", list(_TOOL_CONTEXTS.keys()))
class TestRenderArtifactsDiscovery:
    def test_artifact_keys_surfaced(self, tool_name: str):
        ctx = _TOOL_CONTEXTS[tool_name]
        obj = SimpleNamespace(result="done", context_updates=ctx)
        text = render_result(obj)

        for key, value in ctx.items():
            if (key.endswith("_path") or key.endswith("_dir")) and isinstance(value, str) and value:
                assert f"{key}: {value}" in text, (
                    f"Expected artifact '{key}: {value}' in rendered output "
                    f"for tool '{tool_name}'"
                )

    def test_non_artifact_keys_absent(self, tool_name: str):
        ctx = _TOOL_CONTEXTS[tool_name]
        obj = SimpleNamespace(result="done", context_updates=ctx)
        text = render_result(obj)

        for key in ctx:
            if not (key.endswith("_path") or key.endswith("_dir")):
                # The key itself may coincidentally appear in "done" or "Artifacts:",
                # so check for the "key: value" formatted line specifically.
                assert f"  {key}: {ctx[key]}" not in text, (
                    f"Non-artifact key '{key}' should not appear as an artifact "
                    f"line for tool '{tool_name}'"
                )
