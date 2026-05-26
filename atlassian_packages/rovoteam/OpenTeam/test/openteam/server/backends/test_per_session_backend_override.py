"""Per-session backend override + cache eviction behavior."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

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

from openteam.server.services.conversation_service import ConversationService


_TEMPLATES_DIR = (
    _OPENSTARTUP / "src" / "openteam" / "server" / "resources" / "prompt_templates"
)


def _service(backend: str = "claude_cli") -> ConversationService:
    fake_store = MagicMock()
    fake_store.update_session = MagicMock(
        return_value={"id": "s1", "llm_backend": backend}
    )
    return ConversationService(
        templates_dir=_TEMPLATES_DIR,
        llm_backend=backend,
        working_dir=str(Path.cwd()),
        session_store=fake_store,
    )


class PerSessionOverrideTests(unittest.TestCase):
    def test_mock_backend_short_circuits_to_none(self):
        svc = _service(backend="mock")
        # Should NOT consult the registry — mock fast-path returns None.
        self.assertIsNone(svc._get_session_inferencer("s1"))

    def test_session_override_wins_over_server_default(self):
        """Per-session llm_backend in session dict trumps self._llm_backend."""
        svc = _service(backend="claude_cli")
        sentinel_a = object()
        sentinel_b = object()
        with patch(
            "openteam.server.backends.get_registry"
        ) as fake_get_registry:
            reg = MagicMock()
            # First create() call returns sentinel_a, second sentinel_b.
            reg.create.side_effect = [sentinel_a, sentinel_b]
            reg.list_backends.return_value = {
                "claude_cli": MagicMock(),
                "rovodev": MagicMock(),
            }
            fake_get_registry.return_value = reg

            # Server default = claude_cli; first call uses default
            r1 = svc._get_session_inferencer("s1")
            # Per-session override forces rovodev
            r2 = svc._get_session_inferencer(
                "s1", session={"id": "s1", "llm_backend": "rovodev"}
            )

        # Same session_id → cached; second call returns cached value
        # (override doesn't auto-evict; set_session_backend does).
        self.assertIs(r1, sentinel_a)
        self.assertIs(r2, sentinel_a)  # cached, not rebuilt

    def test_set_session_backend_evicts_cache(self):
        svc = _service(backend="claude_cli")
        sentinel_a = object()
        sentinel_b = object()
        with patch(
            "openteam.server.backends.get_registry"
        ) as fake_get_registry:
            reg = MagicMock()
            reg.create.side_effect = [sentinel_a, sentinel_b]
            reg.list_backends.return_value = {
                "claude_cli": MagicMock(),
                "rovodev": MagicMock(),
                "mock": MagicMock(),
            }
            fake_get_registry.return_value = reg

            r1 = svc._get_session_inferencer("s1")
            self.assertIs(r1, sentinel_a)

            svc.set_session_backend("s1", "rovodev")
            # session_store.update_session should have been called
            svc._session_store.update_session.assert_called_once_with(
                "s1", {"llm_backend": "rovodev", "llm_model": None}
            )

            # Cache evicted; next call rebuilds
            r2 = svc._get_session_inferencer(
                "s1", session={"llm_backend": "rovodev"}
            )
            self.assertIs(r2, sentinel_b)

    def test_set_session_backend_unknown_raises(self):
        svc = _service(backend="claude_cli")
        with patch(
            "openteam.server.backends.get_registry"
        ) as fake_get_registry:
            reg = MagicMock()
            reg.list_backends.return_value = {
                "claude_cli": MagicMock(),
                "mock": MagicMock(),
            }
            fake_get_registry.return_value = reg
            with self.assertRaises(KeyError) as cm:
                svc.set_session_backend("s1", "totally-fake")
        self.assertIn("totally-fake", str(cm.exception))
        self.assertIn("claude_cli", str(cm.exception))

    def test_available_backends_reflects_registry(self):
        names = ConversationService.AVAILABLE_BACKENDS()
        self.assertIn("mock", names)
        self.assertIn("claude_cli", names)
        self.assertIn("rovodev", names)


if __name__ == "__main__":
    unittest.main()
