"""Example-based tests for BackendRegistry — no LLM cost."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

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

from openteam.server.backends.registry import (
    BackendBuildContext,
    BackendDescriptor,
    BackendRegistry,
)


def _ctx() -> BackendBuildContext:
    return BackendBuildContext(
        templates_dir=Path("/tmp/templates"),
        working_dir="/tmp/work",
    )


def _desc(name: str = "x") -> BackendDescriptor:
    return BackendDescriptor(name=name, display_name=name, description="")


class RegistryTests(unittest.TestCase):
    def test_register_and_create_round_trip(self):
        reg = BackendRegistry()
        sentinel = object()
        reg.register("alpha", lambda ctx: sentinel, _desc("alpha"))
        self.assertIs(reg.create("alpha", _ctx()), sentinel)

    def test_list_backends_returns_descriptors(self):
        reg = BackendRegistry()
        reg.register("alpha", lambda ctx: None, _desc("alpha"))
        reg.register("beta", lambda ctx: None, _desc("beta"))
        names = reg.list_backends()
        self.assertEqual(set(names), {"alpha", "beta"})
        self.assertEqual(names["alpha"].name, "alpha")

    def test_last_write_wins_on_duplicate_register(self):
        reg = BackendRegistry()
        reg.register("dup", lambda ctx: "first", _desc("dup"))
        reg.register("dup", lambda ctx: "second", _desc("dup"))
        self.assertEqual(reg.create("dup", _ctx()), "second")
        # list_backends shows one entry only
        self.assertEqual(list(reg.list_backends()), ["dup"])

    def test_create_unknown_raises_keyerror_with_available_list(self):
        reg = BackendRegistry()
        reg.register("alpha", lambda ctx: None, _desc("alpha"))
        with self.assertRaises(KeyError) as cm:
            reg.create("missing", _ctx())
        msg = str(cm.exception)
        self.assertIn("missing", msg)
        self.assertIn("alpha", msg)  # available list included

    def test_get_descriptor_unknown_raises_keyerror(self):
        reg = BackendRegistry()
        with self.assertRaises(KeyError):
            reg.get_descriptor("nope")

    def test_decorator_registers(self):
        reg = BackendRegistry()

        @reg.register_backend("decorated", _desc("decorated"))
        def factory(ctx):
            return "decorated-result"

        self.assertEqual(reg.create("decorated", _ctx()), "decorated-result")
        # Decorator returns the original factory so it remains callable.
        self.assertEqual(factory(_ctx()), "decorated-result")

    def test_module_singleton_has_builtins(self):
        # Importing the package should auto-register mock/rovodev/claude_cli.
        from openteam.server.backends import get_registry

        names = set(get_registry().list_backends())
        self.assertIn("mock", names)
        self.assertIn("rovodev", names)
        self.assertIn("claude_cli", names)


if __name__ == "__main__":
    unittest.main()
