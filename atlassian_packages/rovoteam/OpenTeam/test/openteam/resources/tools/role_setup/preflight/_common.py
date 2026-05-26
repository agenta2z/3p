"""Shared helpers for ``role_setup`` preflight tests.

Mirrors the pattern used by ``create_role/preflight/`` and
``task/preflight/`` — each preflight test is in its own file (one concern
per file), but common path discovery, skip markers, and YAML path
constants live here to avoid duplication.

role_setup has a nested-BTA topology (outer BTA → inner BTA per skill/tool),
so we expose paths for BOTH the outer YAML and the inner imported YAML.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Paths and discovery
# ---------------------------------------------------------------------------

# This file lives at:
#   .../OpenTeam/test/openteam/resources/tools/role_setup/preflight/_common.py
_HERE = Path(__file__).resolve().parent
# parents[0]=preflight, [1]=role_setup, [2]=tools, [3]=resources,
# [4]=openteam, [5]=test, [6]=OpenTeam
OPENSTARTUP_ROOT = _HERE.parents[5]
COREPROJECTS_ROOT = OPENSTARTUP_ROOT.parent

# Outer YAML — the entry-point invoked by the CLI / dispatcher.
OUTER_YAML_PATH = (
    OPENSTARTUP_ROOT
    / "src" / "openteam" / "server" / "resources" / "tools"
    / "role_setup" / "role_setup.yaml"
)

# Inner YAML — imported by outer's worker_factory.skill_tool_creation slot.
INNER_YAML_PATH = (
    OPENSTARTUP_ROOT
    / "src" / "openteam" / "server" / "resources" / "tools"
    / "role_setup" / "role_setup_skill_tool_creation.yaml"
)

AF_TEMPLATES_DIR = (
    COREPROJECTS_ROOT
    / "AgentFoundation" / "src" / "agent_foundation"
    / "resources" / "prompt_templates"
)

OPENSTARTUP_TEMPLATES_DIR = (
    OPENSTARTUP_ROOT
    / "src" / "openteam" / "server" / "resources" / "prompt_templates"
)


# ---------------------------------------------------------------------------
# Skip markers (shared with the real-CLI integration test)
# ---------------------------------------------------------------------------

def _cli_available(command: str) -> bool:
    try:
        result = subprocess.run(
            f"{command} --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


ACLI_AVAILABLE = _cli_available("acli")

ROVOCHAT_CREDS_AVAILABLE = bool(
    (os.environ.get("ROVOCHAT_EMAIL") or os.environ.get("JIRA_EMAIL"))
    and (
        os.environ.get("ROVOCHAT_API_TOKEN")
        or os.environ.get("JIRA_API_TOKEN")
    )
)

skip_no_acli = pytest.mark.skipif(
    not ACLI_AVAILABLE,
    reason="acli (Rovo Dev CLI) not available on PATH",
)
skip_no_rovochat_creds = pytest.mark.skipif(
    not ROVOCHAT_CREDS_AVAILABLE,
    reason=(
        "RovoChat credentials not set (need ROVOCHAT_EMAIL/JIRA_EMAIL and "
        "ROVOCHAT_API_TOKEN/JIRA_API_TOKEN)"
    ),
)


def set_template_root_env(monkeypatch):
    """Helper: configure PROMPT_TEMPLATES_ROOT for tests that load the YAML.

    Sets the dual-root convention (AgentFoundation first, OpenTeam second)
    so that all referenced templates resolve correctly.
    """
    monkeypatch.setenv(
        "PROMPT_TEMPLATES_ROOT",
        f"{AF_TEMPLATES_DIR}:{OPENSTARTUP_TEMPLATES_DIR}",
    )
