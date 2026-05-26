"""TIER-1: CLI bootstrap smoke tests for each tool.

Verifies that every tool's cli module can be imported and its --help runs
in a fresh subprocess with only src/ on PYTHONPATH (no sibling repos).
This catches missing bootstrap calls or accidental hard imports from
AgentFoundation / PythonUtils at module level.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_SRC_DIR = _PROJECT_ROOT / "src"

# The four tool modules under openteam.server.resources.tools
_TOOL_MODULES = [
    "openteam.server.resources.tools.task",
    "openteam.server.resources.tools.create_role",
    "openteam.server.resources.tools.role_setup",
    "openteam.server.resources.tools.project_onboarding",
]


def _clean_env() -> dict[str, str]:
    """Return a subprocess env with PYTHONPATH set to src/ only.

    Strips any sibling-repo paths (AgentFoundation, PythonUtils) from
    the environment to ensure the test exercises the bootstrap path.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC_DIR)
    # Remove OPENTEAM_SIBLINGS_ROOT so bootstrap cannot find siblings
    env.pop("OPENTEAM_SIBLINGS_ROOT", None)
    return env


class TestToolCliImport:
    """Verify each tool's cli module is importable with only src/ on PYTHONPATH."""

    @pytest.mark.parametrize("module", _TOOL_MODULES, ids=[m.split(".")[-1] for m in _TOOL_MODULES])
    def test_each_tool_cli_imports_in_fresh_subprocess(self, module):
        """``python -c 'import {module}.cli'`` must exit 0 in a clean env.

        This proves the cli module's top-level code (including the
        bootstrap call) does not crash when siblings are absent.
        """
        cli_module = f"{module}.cli"
        result = subprocess.run(
            [sys.executable, "-c", f"import {cli_module}"],
            env=_clean_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Importing {cli_module} failed (rc={result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


class TestToolCliHelp:
    """Verify each tool's ``--help`` works in a minimal environment."""

    @pytest.mark.parametrize("module", _TOOL_MODULES, ids=[m.split(".")[-1] for m in _TOOL_MODULES])
    def test_each_tool_cli_help_in_fresh_subprocess(self, module):
        """``python -m {module} --help`` must exit 0 with minimal PYTHONPATH.

        This validates that the __main__.py -> cli.main() chain is wired
        correctly and that --help does not require sibling repos or
        external services to be available.
        """
        result = subprocess.run(
            [sys.executable, "-m", module, "--help"],
            env=_clean_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"``python -m {module} --help`` failed (rc={result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
