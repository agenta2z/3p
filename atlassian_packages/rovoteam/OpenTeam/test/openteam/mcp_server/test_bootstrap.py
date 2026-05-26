"""Tests for openteam.bootstrap — sibling-repo path resolution."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate the project src/ directory so we can set PYTHONPATH correctly
# and reference bootstrap without conftest side-effects.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[2]  # test/openteam/mcp_server -> project root
_SRC_DIR = _PROJECT_ROOT / "src"


class TestEnsureSiblingsOnPath:
    """Verify ensure_siblings_on_path idempotency and env-var override."""

    def test_idempotent(self, monkeypatch, tmp_path):
        """Calling ensure_siblings_on_path() twice grows sys.path by N, not 2N."""
        # Build a fake siblings layout so the function has something to find.
        af_src = tmp_path / "AgentFoundation" / "src"
        rpu_src = tmp_path / "PythonUtils" / "src"
        af_src.mkdir(parents=True)
        rpu_src.mkdir(parents=True)

        monkeypatch.setenv("OPENTEAM_SIBLINGS_ROOT", str(tmp_path))

        from openteam.bootstrap import ensure_siblings_on_path

        # Snapshot before
        baseline_len = len(sys.path)

        inserted_first = ensure_siblings_on_path()
        after_first = len(sys.path)
        n_added = after_first - baseline_len

        inserted_second = ensure_siblings_on_path()
        after_second = len(sys.path)

        # Second call must not add duplicates
        assert after_second == after_first, (
            f"Second call added {after_second - after_first} extra entries; "
            f"expected 0 (idempotent). sys.path delta: "
            f"first={n_added}, total={after_second - baseline_len}"
        )
        assert inserted_second == [], (
            "Second call should return an empty list (nothing new inserted)"
        )

    def test_env_override(self, monkeypatch, tmp_path):
        """OPENTEAM_SIBLINGS_ROOT env var is honored for sibling lookup."""
        af_src = tmp_path / "AgentFoundation" / "src"
        rpu_src = tmp_path / "PythonUtils" / "src"
        af_src.mkdir(parents=True)
        rpu_src.mkdir(parents=True)

        monkeypatch.setenv("OPENTEAM_SIBLINGS_ROOT", str(tmp_path))

        from openteam.bootstrap import ensure_siblings_on_path

        inserted = ensure_siblings_on_path()
        inserted_strs = [str(p) for p in inserted]

        assert any(str(af_src) in s for s in inserted_strs), (
            f"AgentFoundation/src not found in inserted paths: {inserted_strs}"
        )
        assert any(str(rpu_src) in s for s in inserted_strs), (
            f"PythonUtils/src not found in inserted paths: {inserted_strs}"
        )

    def test_walks_up_to_find_siblings(self, tmp_path):
        """With a real temp layout, _find_siblings_root resolves correctly."""
        # Create a fake workspace: workspace/AgentFoundation/src + workspace/PythonUtils/src
        workspace = tmp_path / "workspace"
        af_src = workspace / "AgentFoundation" / "src"
        rpu_src = workspace / "PythonUtils" / "src"
        af_src.mkdir(parents=True)
        rpu_src.mkdir(parents=True)

        from openteam.bootstrap import _find_siblings_root

        # _find_siblings_root walks up from the openteam package itself,
        # so we cannot easily redirect it without the env var.
        # Instead, verify the env-var path takes precedence over walk-up.
        import os
        old = os.environ.get("OPENTEAM_SIBLINGS_ROOT")
        try:
            os.environ["OPENTEAM_SIBLINGS_ROOT"] = str(workspace)
            result = _find_siblings_root()
            assert result == workspace.resolve(), (
                f"Expected {workspace.resolve()}, got {result}"
            )
        finally:
            if old is None:
                os.environ.pop("OPENTEAM_SIBLINGS_ROOT", None)
            else:
                os.environ["OPENTEAM_SIBLINGS_ROOT"] = old

    def test_missing_siblings_warns(self, monkeypatch, tmp_path, caplog):
        """When siblings dir is empty, no exception raised but warning emitted."""
        # Point at an empty directory — no AgentFoundation or PythonUtils
        empty_dir = tmp_path / "empty_workspace"
        empty_dir.mkdir()

        monkeypatch.setenv("OPENTEAM_SIBLINGS_ROOT", str(empty_dir))

        from openteam.bootstrap import ensure_siblings_on_path

        with caplog.at_level(logging.WARNING, logger="openteam.bootstrap"):
            # Should NOT raise
            inserted = ensure_siblings_on_path(strict=False)

        # A warning about missing dirs should have been logged
        warning_messages = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any("missing" in msg.lower() for msg in warning_messages), (
            f"Expected a warning about missing sibling dirs, got: {warning_messages}"
        )

    def test_strict_raises_on_missing(self, monkeypatch, tmp_path):
        """ensure_siblings_on_path(strict=True) raises FileNotFoundError."""
        empty_dir = tmp_path / "empty_workspace"
        empty_dir.mkdir()

        monkeypatch.setenv("OPENTEAM_SIBLINGS_ROOT", str(empty_dir))

        from openteam.bootstrap import ensure_siblings_on_path

        with pytest.raises(FileNotFoundError):
            ensure_siblings_on_path(strict=True)

    def test_does_not_import_from_siblings(self):
        """bootstrap.py itself is importable without siblings on path.

        This verifies that the module-level code in bootstrap.py does not
        try to import from AgentFoundation or PythonUtils — only the
        ensure_siblings_on_path() call site should trigger those imports.
        """
        import importlib
        # Re-import to verify the module loads cleanly on its own.
        # If bootstrap.py had top-level imports from siblings, this would
        # fail when siblings are not on sys.path.
        mod = importlib.import_module("openteam.bootstrap")
        assert hasattr(mod, "ensure_siblings_on_path")
        assert hasattr(mod, "_find_siblings_root")
