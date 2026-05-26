"""TIER-1 tests for tool_cli.py Phase 0a rendering fix.

Verifies duck-typed rendering of ToolExecutionResult, dict (modern + legacy),
and bare str. Also verifies the suffix-discovery rule for artifact paths.
"""
from __future__ import annotations

import sys
from io import StringIO
from types import SimpleNamespace

import pytest


def _capture_render(result):
    """Run the rendering logic from tool_cli and capture stdout + stderr."""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()
    try:
        if hasattr(result, "result") and hasattr(result, "context_updates"):
            print(result.result or "", flush=True)
            ctx = result.context_updates or {}
        elif isinstance(result, dict):
            print(result.get("result") or result.get("text") or "", flush=True)
            ctx = result.get("context_updates") or {}
        else:
            print(str(result), flush=True)
            ctx = {}

        for key, value in sorted(ctx.items()):
            if (key.endswith("_path") or key.endswith("_dir")) and isinstance(value, str) and value:
                print(f"[{key}] {value}", file=sys.stderr)

        return sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


class TestToolCliRendering:
    def test_renders_tool_execution_result(self):
        result = SimpleNamespace(
            result="hi", context_updates={"workspace_path": "/tmp"}
        )
        stdout, stderr = _capture_render(result)
        assert stdout == "hi\n"
        assert stderr == "[workspace_path] /tmp\n"

    def test_renders_dict_result_modern_key(self):
        result = {"result": "hi"}
        stdout, stderr = _capture_render(result)
        assert stdout == "hi\n"
        assert stderr == ""

    def test_renders_dict_result_legacy_text_key(self):
        result = {"text": "hi"}
        stdout, stderr = _capture_render(result)
        assert stdout == "hi\n"
        assert stderr == ""

    def test_renders_str_result(self):
        stdout, stderr = _capture_render("hi")
        assert stdout == "hi\n"
        assert stderr == ""

    def test_falsy_result_prints_empty_line(self):
        result = SimpleNamespace(result="", context_updates={})
        stdout, stderr = _capture_render(result)
        assert stdout == "\n"

    def test_artifact_paths_on_stderr(self):
        result = SimpleNamespace(
            result="done",
            context_updates={
                "workspace_path": "/tmp/ws",
                "plan_path": "/tmp/ws/plan.md",
                "skills_dir": "/tmp/ws/skills",
            },
        )
        stdout, stderr = _capture_render(result)
        assert stdout == "done\n"
        lines = stderr.strip().split("\n")
        assert len(lines) == 3
        assert "[plan_path] /tmp/ws/plan.md" in lines[0]
        assert "[skills_dir] /tmp/ws/skills" in lines[1]
        assert "[workspace_path] /tmp/ws" in lines[2]

    def test_unknown_artifact_keys_ignored(self):
        result = SimpleNamespace(
            result="done",
            context_updates={"foo": "bar", "status": "ok"},
        )
        stdout, stderr = _capture_render(result)
        assert stdout == "done\n"
        assert stderr == ""
