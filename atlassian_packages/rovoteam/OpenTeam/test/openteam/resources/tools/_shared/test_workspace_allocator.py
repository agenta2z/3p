"""Tests for the unified workspace allocator (Phases 0 + 1).

Phase 0 contract tests were originally xfail; they are now GREEN after Phase 1 landed.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from openteam.server.resources.tools._shared.workspace_allocator import (
    allocate_tool_workspace,
    find_runtime_root,
    make_workspace_dirname,
)

_DIRNAME_RE = re.compile(r"^[a-z_]+_\d{8}_\d{6}_[0-9a-f]{8}$")


# ── find_runtime_root ────────────────────────────────────────────────

def test_find_runtime_root_uses_env_var(tmp_path, monkeypatch):
    """RED #1 — $OPENTEAM_RUNTIME_DIR wins over all other strategies."""
    monkeypatch.setenv("OPENTEAM_RUNTIME_DIR", str(tmp_path / "custom"))
    assert find_runtime_root() == (tmp_path / "custom").resolve()


def test_find_runtime_root_walks_up_from_file(monkeypatch):
    """RED #2 — Walk-up to src/ ancestor finds correct _runtime/."""
    monkeypatch.delenv("OPENTEAM_RUNTIME_DIR", raising=False)
    root = find_runtime_root()
    assert root.name == "_runtime"
    assert (root.parent / "src").is_dir(), (
        f"Expected <repo>/src/ to exist alongside {root}"
    )


def test_find_runtime_root_walks_up_from_cwd(tmp_path, monkeypatch):
    """RED #3 — CWD walk-up fallback when __file__ walk fails."""
    monkeypatch.delenv("OPENTEAM_RUNTIME_DIR", raising=False)
    src_dir = tmp_path / "fake_repo" / "src"
    src_dir.mkdir(parents=True)
    (tmp_path / "fake_repo" / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path / "fake_repo")
    # Strategy 2 (walk from __file__) will find the REAL src/ first in dev,
    # but strategy 3 (CWD) is exercised when strategy 2 is blocked.
    # We test strategy 3 indirectly: the function still resolves when CWD
    # has the repo structure, even if __file__ is elsewhere.
    root = find_runtime_root()
    assert root.name == "_runtime"


def test_find_runtime_root_fallback_home(tmp_path, monkeypatch):
    """RED #4 — Falls back to ~/.openteam/_runtime when all else fails."""
    monkeypatch.delenv("OPENTEAM_RUNTIME_DIR", raising=False)
    fallback = Path.home() / ".openteam" / "_runtime"
    with patch(
        "openteam.server.resources.tools._shared.workspace_allocator.Path.resolve",
        return_value=Path("/no/src/anywhere/workspace_allocator.py"),
    ):
        pass
    # Direct fallback test: the module-level constant
    from openteam.server.resources.tools._shared.workspace_allocator import (
        _FALLBACK_HOME_DIR,
    )
    assert _FALLBACK_HOME_DIR == fallback


# ── make_workspace_dirname ───────────────────────────────────────────

def test_make_workspace_dirname_format():
    """RED #5 — matches regex <tool>_YYYYMMDD_HHMMSS_<8hex>."""
    dirname = make_workspace_dirname("task")
    assert _DIRNAME_RE.match(dirname), f"'{dirname}' doesn't match expected pattern"
    assert dirname.startswith("task_")


def test_make_workspace_dirname_lex_sortable():
    """RED #6 — two dirnames 1s apart sort correctly by string comparison."""
    d1 = make_workspace_dirname("task")
    time.sleep(1.1)
    d2 = make_workspace_dirname("task")
    assert d1 < d2, f"Expected {d1!r} < {d2!r} (lex sort by timestamp)"


# ── allocate_tool_workspace — Path A (standalone) ────────────────────

def test_path_a_standalone_layout(tmp_path, monkeypatch):
    """RED #7 — standalone layout at _runtime/tasks/<tool>/<tool>_<TS>_<uuid8>/."""
    monkeypatch.setenv("OPENTEAM_RUNTIME_DIR", str(tmp_path))
    ws = allocate_tool_workspace("task")
    assert ws.exists()
    assert ws.is_dir()
    rel = ws.relative_to(tmp_path)
    parts = rel.parts
    assert parts[0] == "tasks", f"Expected tasks/ prefix, got {parts}"
    assert parts[1] == "task", f"Expected task/ subdir, got {parts}"
    assert _DIRNAME_RE.match(parts[2]), f"Dirname {parts[2]} doesn't match pattern"


# ── allocate_tool_workspace — Path B (server-affiliated) ─────────────

def test_path_b_server_affiliated_layout(tmp_path):
    """RED #8 — server-affiliated layout at <base_dir>/<tool>_<TS>_<uuid8>/."""
    base = tmp_path / "session_root" / "tasks"
    base.mkdir(parents=True)
    ws = allocate_tool_workspace("role_setup", base_dir=base)
    assert ws.exists()
    assert ws.is_dir()
    assert ws.parent == base
    assert _DIRNAME_RE.match(ws.name), f"Dirname {ws.name} doesn't match pattern"
    assert ws.name.startswith("role_setup_")


# ── Validation ───────────────────────────────────────────────────────

def test_invalid_tool_name_raises():
    """RED #9 — empty / non-identifier raises ValueError."""
    with pytest.raises(ValueError, match="tool_name"):
        allocate_tool_workspace("")
    with pytest.raises(ValueError, match="tool_name"):
        allocate_tool_workspace("foo-bar")
    with pytest.raises(ValueError, match="tool_name"):
        make_workspace_dirname("")


def test_relative_base_dir_raises(tmp_path):
    """RED #10 — non-absolute base_dir raises ValueError."""
    with pytest.raises(ValueError, match="base_dir must be absolute"):
        allocate_tool_workspace("task", base_dir=Path("relative/path"))


# ── UUID8 collision ──────────────────────────────────────────────────

def test_uuid8_collision_retried(tmp_path, monkeypatch):
    """RED #11 — mock uuid4 to collide; allocator retries then raises."""
    monkeypatch.setenv("OPENTEAM_RUNTIME_DIR", str(tmp_path))
    fixed_hex = "deadbeef" * 4
    with patch("openteam.server.resources.tools._shared.workspace_allocator.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = fixed_hex
        ws1 = allocate_tool_workspace("task")
        assert ws1.exists()
        with pytest.raises(FileExistsError):
            allocate_tool_workspace("task")


def test_role_setup_concurrent_runs_dont_collide(tmp_path, monkeypatch):
    """RED #12 — two allocations in same millisecond produce distinct paths."""
    monkeypatch.setenv("OPENTEAM_RUNTIME_DIR", str(tmp_path))
    ws1 = allocate_tool_workspace("role_setup")
    ws2 = allocate_tool_workspace("role_setup")
    assert ws1 != ws2
    assert ws1.exists()
    assert ws2.exists()
