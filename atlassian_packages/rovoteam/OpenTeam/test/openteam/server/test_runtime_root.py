"""TIER-1 tests for openteam.server.runtime_root (Round-8 / I21)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from openteam.server.runtime_root import (
    RuntimeRoot,
    apply_runtime_root,
    resolve_runtime_root,
)


class TestResolveEnum:
    def test_auto_uses_find_runtime_root(self, monkeypatch, tmp_path):
        # Force tier 1 (env var) so the result is deterministic
        monkeypatch.setenv("OPENTEAM_RUNTIME_DIR", str(tmp_path / "rt"))
        assert resolve_runtime_root(RuntimeRoot.AUTO) == (tmp_path / "rt").resolve()
        assert resolve_runtime_root("auto") == (tmp_path / "rt").resolve()
        assert resolve_runtime_root(None) == (tmp_path / "rt").resolve()

    def test_user_home(self, monkeypatch):
        # Should NOT touch env var
        monkeypatch.delenv("OPENTEAM_RUNTIME_DIR", raising=False)
        assert resolve_runtime_root(RuntimeRoot.USER_HOME) == (
            Path.home() / ".openteam" / "_runtime"
        )
        assert resolve_runtime_root("user-home") == (
            Path.home() / ".openteam" / "_runtime"
        )

    def test_explicit_path_absolute(self, tmp_path):
        assert resolve_runtime_root(str(tmp_path / "rt")) == (tmp_path / "rt").resolve()

    def test_explicit_path_relative_resolves_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert resolve_runtime_root("subdir/rt") == (tmp_path / "subdir" / "rt").resolve()

    def test_tilde_expands(self):
        assert resolve_runtime_root("~/custom") == (Path.home() / "custom").resolve()


class TestRepoRoot:
    def test_repo_root_resolves_when_src_ancestor_exists(self):
        # The runtime_root.py module itself lives under src/, so REPO_ROOT
        # should resolve to <repo>/_runtime.
        resolved = resolve_runtime_root(RuntimeRoot.REPO_ROOT)
        assert resolved.name == "_runtime"
        assert resolved.parent.is_dir()

    def test_repo_root_fail_loud(self, tmp_path, monkeypatch):
        """Pip-installed user runs --runtime-root repo-root → ValueError, not silent fallback."""
        # Move CWD somewhere with no src/ ancestor
        outside = tmp_path / "outside_repo"
        outside.mkdir()
        monkeypatch.chdir(outside)
        # Also need to fake out the __file__ walk-up; we can't really do that
        # since __file__ for runtime_root.py is inside src/. So we test the
        # CWD walk-up branch by patching __file__ resolution.
        from openteam.server import runtime_root as rr

        # Replace the file path used by REPO_ROOT walk-up
        fake_file = outside / "not_under_src.py"
        monkeypatch.setattr(rr, "__file__", str(fake_file))

        with pytest.raises(ValueError, match="no src/ ancestor"):
            resolve_runtime_root(RuntimeRoot.REPO_ROOT)


class TestApplyRuntimeRoot:
    def test_sets_env_var(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENTEAM_RUNTIME_DIR", raising=False)
        resolved = apply_runtime_root(str(tmp_path / "rt"))
        assert os.environ["OPENTEAM_RUNTIME_DIR"] == str(resolved)
        # I21 single source: subsequent find_runtime_root() returns same
        from openteam.server.runtime_root import find_runtime_root
        assert find_runtime_root() == resolved

    def test_user_home_sets_env_var(self, monkeypatch):
        monkeypatch.delenv("OPENTEAM_RUNTIME_DIR", raising=False)
        resolved = apply_runtime_root(RuntimeRoot.USER_HOME)
        assert os.environ["OPENTEAM_RUNTIME_DIR"] == str(resolved)
        assert resolved == Path.home() / ".openteam" / "_runtime"
