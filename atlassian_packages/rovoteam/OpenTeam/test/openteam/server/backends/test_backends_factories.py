"""Factory smoke tests — mostly contract-level, mock the underlying CLIs.

We avoid spawning real claude/acli processes — testing here is about the
factory wiring, not the inferencer's runtime.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

# Bootstrap sys.path
_HERE = Path(__file__).resolve()
_OPENSTARTUP = _HERE.parents[4]
_REPO_ROOT = _OPENSTARTUP.parent
for _dep in [
    _OPENSTARTUP / "src",
    _REPO_ROOT / "AgentFoundation" / "src",
    _REPO_ROOT / "PythonUtils" / "src",
]:
    p = str(_dep)
    if p not in sys.path:
        sys.path.insert(0, p)

from openteam.server.backends import factories as factories_mod
from openteam.server.backends.registry import BackendBuildContext


def _real_templates_dir() -> Path:
    """Use the actual templates dir so JinjaPromptRenderer wiring works."""
    return _OPENSTARTUP / "src" / "openteam" / "server" / "resources" / "prompt_templates"


class MockGuardTests(unittest.TestCase):
    def test_mock_factory_raises_if_invoked(self):
        """The mock entry exists for descriptor listing but must never be invoked."""
        ctx = BackendBuildContext(templates_dir=Path("/tmp"), working_dir="/tmp")
        with self.assertRaises(RuntimeError) as cm:
            factories_mod._mock_guard_factory(ctx)
        self.assertIn("mock is service-handled", str(cm.exception))


class RovodevModelWarningTests(unittest.TestCase):
    def setUp(self):
        # Reset the module-level "warned once" flag between tests.
        factories_mod._rovodev_model_warning_logged = False

    def test_rovodev_factory_logs_when_model_provided(self):
        """rovodev has no model_name attr — operator should know it's a no-op."""
        ctx = BackendBuildContext(
            templates_dir=_real_templates_dir(),
            working_dir=str(Path.cwd()),
            model_name="opus[1m]",
        )
        # Mock RovoDevCliInferencer + the conversational wrap so we don't spawn acli.
        with patch.object(
            factories_mod, "_wrap_in_conversational", return_value="WRAPPED"
        ), patch(
            "agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.RovoDevCliInferencer"
        ) as fake_base:
            fake_base.return_value.acli_path = "/fake/acli"
            with self.assertLogs(factories_mod.logger, level="INFO") as cap:
                result = factories_mod._rovodev_factory(ctx)
        self.assertEqual(result, "WRAPPED")
        # First call emits the warning; second call should NOT (warned-once guard).
        self.assertTrue(any("ignores model_name" in m for m in cap.output))

        with patch.object(
            factories_mod, "_wrap_in_conversational", return_value="WRAPPED"
        ), patch(
            "agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.RovoDevCliInferencer"
        ) as fake_base:
            fake_base.return_value.acli_path = "/fake/acli"
            with self.assertLogs(factories_mod.logger, level="INFO") as cap2:
                factories_mod._rovodev_factory(ctx)
        # Second call: only the "RovoDev initialized" log, no "ignores model_name".
        self.assertFalse(any("ignores model_name" in m for m in cap2.output))


class ClaudeCliFactoryTests(unittest.TestCase):
    def test_claude_cli_factory_constructs_inferencer(self):
        """Factory wires ClaudeCodeCliInferencer with the expected kwargs."""
        ctx = BackendBuildContext(
            templates_dir=_real_templates_dir(),
            working_dir=str(Path.cwd()),
            cache_dir="/tmp/cache",
            model_name="haiku",
        )
        with patch.object(
            factories_mod, "_wrap_in_conversational", return_value="WRAPPED"
        ), patch(
            "agent_foundation.common.inferencers.agentic_inferencers.external."
            "claude_code.claude_code_cli_inferencer.ClaudeCodeCliInferencer"
        ) as fake_base:
            fake_base.return_value.model_name = "haiku"
            result = factories_mod._claude_cli_factory(ctx)
        self.assertEqual(result, "WRAPPED")
        kwargs = fake_base.call_args.kwargs
        self.assertEqual(kwargs["target_path"], str(Path.cwd()))
        self.assertEqual(kwargs["model_name"], "haiku")
        self.assertEqual(kwargs["idle_timeout_seconds"], 1800)
        self.assertEqual(kwargs["permission_mode"], "bypassPermissions")
        self.assertEqual(kwargs["cache_folder"], "/tmp/cache")

    def test_claude_cli_factory_default_model(self):
        """When ctx.model_name is None, falls back to the descriptor default 'opus[1m]'."""
        ctx = BackendBuildContext(
            templates_dir=_real_templates_dir(),
            working_dir=str(Path.cwd()),
        )
        with patch.object(
            factories_mod, "_wrap_in_conversational", return_value="W"
        ), patch(
            "agent_foundation.common.inferencers.agentic_inferencers.external."
            "claude_code.claude_code_cli_inferencer.ClaudeCodeCliInferencer"
        ) as fake_base:
            factories_mod._claude_cli_factory(ctx)
        self.assertEqual(fake_base.call_args.kwargs["model_name"], "opus[1m]")


class AvailabilityProbeTests(unittest.TestCase):
    def test_claude_cli_available_when_which_returns_path(self):
        with patch("openteam.server.backends.factories.shutil.which",
                   return_value="/path/to/claude"):
            self.assertIn(
                "claude found at /path/to/claude",
                factories_mod._claude_cli_status_message(),
            )

    def test_claude_cli_unavailable_when_which_returns_none(self):
        with patch("openteam.server.backends.factories.shutil.which",
                   return_value=None):
            self.assertIn(
                "claude binary not found",
                factories_mod._claude_cli_status_message(),
            )

    def test_rovodev_unavailable_when_which_returns_none(self):
        with patch("openteam.server.backends.factories.shutil.which",
                   return_value=None):
            self.assertIn(
                "acli binary not found",
                factories_mod._rovodev_status_message(),
            )


if __name__ == "__main__":
    unittest.main()
