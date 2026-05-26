"""Unit tests for ToolDispatcher — registry-driven generic tool dispatch."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_tool_def(name: str, source_path: str | None = None):
    """Create a minimal ToolDefinition-like object."""
    td = MagicMock()
    td.name = name
    td.source_path = source_path or ""
    return td


def _make_integration_executor(handles_names: list[str]):
    """Create a mock IntegrationToolExecutor."""
    executor = MagicMock()
    executor.handles = lambda name: name in handles_names
    executor.__call__ = AsyncMock(
        return_value=MagicMock(result="integration_result", context_updates={})
    )
    return executor


def _make_tool_json(tmp_path: Path, name: str, executor_ref: str | None = None) -> Path:
    """Write a minimal tool.json and return its path."""
    data = {"name": name, "tool_type": "Action"}
    if executor_ref:
        data["executor"] = executor_ref
    tool_dir = tmp_path / name
    tool_dir.mkdir()
    tool_json = tool_dir / "tool.json"
    tool_json.write_text(json.dumps(data))
    return tool_json


# ---------------------------------------------------------------------------
# Import ToolDispatcher
# ---------------------------------------------------------------------------

from openteam.server.services.tool_dispatcher import ToolDispatcher


# ---------------------------------------------------------------------------
# Tests: _load_executors
# ---------------------------------------------------------------------------

class TestLoadExecutors:

    def test_loads_executor_from_tool_json(self, tmp_path):
        """ToolDispatcher discovers and imports executor from tool.json."""
        # Write a real tool.json pointing to a real module:execute function
        tool_json = _make_tool_json(
            tmp_path, "create_role",
            executor_ref="openteam.server.resources.tools.create_role.executor:execute"
        )
        tool_def = _make_tool_def("create_role", source_path=str(tool_json))
        integration = _make_integration_executor([])

        dispatcher = ToolDispatcher(
            tool_registry={"create_role": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert "create_role" in dispatcher._executor_map
        assert callable(dispatcher._executor_map["create_role"])

    def test_loads_role_setup_executor(self, tmp_path):
        """ToolDispatcher discovers executor for role_setup."""
        tool_json = _make_tool_json(
            tmp_path, "role_setup",
            executor_ref="openteam.server.resources.tools.role_setup.executor:execute"
        )
        tool_def = _make_tool_def("role_setup", source_path=str(tool_json))
        integration = _make_integration_executor([])

        dispatcher = ToolDispatcher(
            tool_registry={"role_setup": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert "role_setup" in dispatcher._executor_map

    def test_skips_tool_without_source_path(self, tmp_path):
        """Tools with empty source_path are skipped."""
        tool_def = _make_tool_def("create_role", source_path="")
        integration = _make_integration_executor([])

        dispatcher = ToolDispatcher(
            tool_registry={"create_role": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert "create_role" not in dispatcher._executor_map

    def test_skips_tool_json_without_executor_field(self, tmp_path):
        """tool.json without 'executor' field is skipped gracefully."""
        tool_json = _make_tool_json(tmp_path, "no_executor", executor_ref=None)
        tool_def = _make_tool_def("no_executor", source_path=str(tool_json))
        integration = _make_integration_executor([])

        dispatcher = ToolDispatcher(
            tool_registry={"no_executor": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert "no_executor" not in dispatcher._executor_map

    def test_handles_import_error_gracefully(self, tmp_path):
        """Bad executor ref logs warning and skips — no crash."""
        tool_json = _make_tool_json(
            tmp_path, "bad_tool",
            executor_ref="nonexistent.module.path:execute"
        )
        tool_def = _make_tool_def("bad_tool", source_path=str(tool_json))
        integration = _make_integration_executor([])

        # Should not raise
        dispatcher = ToolDispatcher(
            tool_registry={"bad_tool": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert "bad_tool" not in dispatcher._executor_map

    def test_handles_missing_tool_json_gracefully(self, tmp_path):
        """Non-existent source_path is skipped gracefully."""
        tool_def = _make_tool_def("ghost_tool", source_path=str(tmp_path / "ghost" / "tool.json"))
        integration = _make_integration_executor([])

        dispatcher = ToolDispatcher(
            tool_registry={"ghost_tool": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert "ghost_tool" not in dispatcher._executor_map


# ---------------------------------------------------------------------------
# Tests: handles()
# ---------------------------------------------------------------------------

class TestHandles:

    def test_handles_registry_tool(self, tmp_path):
        """handles() returns True for tools with executor in registry."""
        tool_json = _make_tool_json(
            tmp_path, "create_role",
            executor_ref="openteam.server.resources.tools.create_role.executor:execute"
        )
        tool_def = _make_tool_def("create_role", source_path=str(tool_json))
        integration = _make_integration_executor([])

        dispatcher = ToolDispatcher(
            tool_registry={"create_role": tool_def},
            integration_executor=integration,
            session_context={},
        )

        assert dispatcher.handles("create_role") is True

    def test_handles_integration_tool(self):
        """handles() returns True for integration tools (Slack/TWG)."""
        integration = _make_integration_executor(["slack_send_message"])
        dispatcher = ToolDispatcher(
            tool_registry={},
            integration_executor=integration,
            session_context={},
        )

        assert dispatcher.handles("slack_send_message") is True

    def test_does_not_handle_unknown(self):
        """handles() returns False for unknown tools."""
        integration = _make_integration_executor([])
        dispatcher = ToolDispatcher(
            tool_registry={},
            integration_executor=integration,
            session_context={},
        )

        assert dispatcher.handles("nonexistent_tool") is False


# ---------------------------------------------------------------------------
# Tests: __call__ dispatch priority
# ---------------------------------------------------------------------------

class TestDispatch:

    @pytest.mark.asyncio
    async def test_dispatches_to_registry_executor(self, tmp_path):
        """__call__ dispatches to registry executor for known tools."""
        mock_execute = AsyncMock(
            return_value=MagicMock(result="role_created", context_updates={})
        )

        tool_json = _make_tool_json(
            tmp_path, "create_role",
            executor_ref="some.module:execute"
        )
        tool_def = _make_tool_def("create_role", source_path=str(tool_json))
        integration = _make_integration_executor(["create_role"])  # also handles it

        dispatcher = ToolDispatcher(
            tool_registry={"create_role": tool_def},
            integration_executor=integration,
            session_context={"cloud_id": "test"},
        )
        # Manually override the executor map with our mock
        dispatcher._executor_map["create_role"] = mock_execute

        result = await dispatcher("create_role", {"role_description": "PM role"})

        # Registry executor takes priority over integration executor
        mock_execute.assert_called_once_with(
            {"role_description": "PM role"}, {"cloud_id": "test"}
        )
        assert result.result == "role_created"

    @pytest.mark.asyncio
    async def test_dispatches_to_integration_executor_fallback(self):
        """__call__ falls back to integration executor for integration tools."""
        mock_result = MagicMock(result="slack_ok", context_updates={})
        integration = MagicMock()
        integration.handles = lambda name: name == "slack_send_message"
        integration = AsyncMock(return_value=mock_result)
        integration.handles = lambda name: name == "slack_send_message"

        dispatcher = ToolDispatcher(
            tool_registry={},
            integration_executor=integration,
            session_context={},
        )

        result = await dispatcher("slack_send_message", {"channel": "#general"})

        integration.assert_called_once_with("slack_send_message", {"channel": "#general"})
        assert result.result == "slack_ok"

    @pytest.mark.asyncio
    async def test_returns_unknown_tool_for_unrecognized(self):
        """__call__ returns 'Unknown tool' for tools with no executor."""
        integration = _make_integration_executor([])
        dispatcher = ToolDispatcher(
            tool_registry={},
            integration_executor=integration,
            session_context={},
        )

        result = await dispatcher("nonexistent_tool", {})

        assert "Unknown tool" in result.result
        assert "nonexistent_tool" in result.result

    @pytest.mark.asyncio
    async def test_session_context_passed_to_executor(self, tmp_path):
        """session_context is passed to registry executor as second argument."""
        received_context = {}

        async def mock_execute(arguments, session_context):
            received_context.update(session_context)
            from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import ToolExecutionResult
            return ToolExecutionResult(result="ok")

        tool_json = _make_tool_json(tmp_path, "my_tool", executor_ref="mod:fn")
        tool_def = _make_tool_def("my_tool", source_path=str(tool_json))
        integration = _make_integration_executor([])

        ctx = {"working_dir": "/tmp", "cloud_id": "abc", "uct_token": "tok"}
        dispatcher = ToolDispatcher(
            tool_registry={"my_tool": tool_def},
            integration_executor=integration,
            session_context=ctx,
        )
        dispatcher._executor_map["my_tool"] = mock_execute

        await dispatcher("my_tool", {})

        assert received_context["cloud_id"] == "abc"
        assert received_context["working_dir"] == "/tmp"


# ---------------------------------------------------------------------------
# Tests: _import_callable
# ---------------------------------------------------------------------------

class TestImportCallable:

    def test_imports_real_function(self):
        """_import_callable can import a real function from a real module."""
        fn = ToolDispatcher._import_callable(
            "openteam.server.resources.tools.create_role.executor:execute"
        )
        assert callable(fn)
        import asyncio
        assert asyncio.iscoroutinefunction(fn)

    def test_imports_role_setup_execute(self):
        """_import_callable can import role_setup execute function."""
        fn = ToolDispatcher._import_callable(
            "openteam.server.resources.tools.role_setup.executor:execute"
        )
        assert callable(fn)

    def test_raises_on_missing_colon(self):
        """_import_callable raises ValueError for invalid ref format."""
        with pytest.raises(ValueError, match="Invalid executor reference"):
            ToolDispatcher._import_callable("no_colon_here")

    def test_raises_on_nonexistent_module(self):
        """_import_callable raises ImportError for unknown module."""
        with pytest.raises(ImportError):
            ToolDispatcher._import_callable("nonexistent.module.xyz:execute")

    def test_raises_on_nonexistent_callable(self):
        """_import_callable raises AttributeError for unknown callable."""
        with pytest.raises(AttributeError):
            ToolDispatcher._import_callable(
                "openteam.server.resources.tools.create_role.executor:nonexistent_fn"
            )


# ---------------------------------------------------------------------------
# Integration: tool.json files have executor field
# ---------------------------------------------------------------------------

class TestToolJsonExecutorField:

    def _read_tool_json(self, tool_name: str) -> dict:
        tools_dir = (
            Path(__file__).parent.parent.parent.parent.parent
            / "src" / "openteam" / "server" / "resources" / "tools"
        )
        tool_json = tools_dir / tool_name / "tool.json"
        assert tool_json.exists(), f"{tool_json} does not exist"
        return json.loads(tool_json.read_text())

    def test_create_role_has_executor(self):
        """create_role/tool.json has 'executor' field."""
        data = self._read_tool_json("create_role")
        assert "executor" in data
        assert "create_role.executor:execute" in data["executor"]

    def test_role_setup_has_executor(self):
        """role_setup/tool.json has 'executor' field."""
        data = self._read_tool_json("role_setup")
        assert "executor" in data
        assert "role_setup.executor:execute" in data["executor"]

    def test_create_role_executor_is_importable(self):
        """create_role executor ref can be imported successfully."""
        data = self._read_tool_json("create_role")
        fn = ToolDispatcher._import_callable(data["executor"])
        assert callable(fn)

    def test_role_setup_executor_is_importable(self):
        """role_setup executor ref can be imported successfully."""
        data = self._read_tool_json("role_setup")
        fn = ToolDispatcher._import_callable(data["executor"])
        assert callable(fn)
