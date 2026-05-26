"""Unit tests — ConversationService tool loading and prompt injection.

Verifies that:
1. All tools listed in .initial.config.yaml → tools.enabled_action_tools have a
   corresponding tool.json in the tool registry (i.e. load_all_tools() finds them).
2. _filter_tools_by_config() retains exactly those whitelisted tools and no others.
3. The rendered conversation prompt contains the names of all whitelisted tools
   (i.e. they are actually injected into {{ action_tools }}).
4. Tools NOT in the whitelist are absent from the rendered prompt.

These are fast, dependency-free unit tests — no LLM calls, no subprocesses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths (relative to this file — works regardless of working directory)
# ---------------------------------------------------------------------------
_SRC_ROOT = Path(__file__).resolve().parents[4] / "src" / "openteam" / "server"
_TEMPLATES_DIR = _SRC_ROOT / "resources" / "prompt_templates"
_TOOLS_DIR = _SRC_ROOT / "resources" / "tools"
_CONFIG_FILE = _TEMPLATES_DIR / "conversation" / "main" / ".initial.config.yaml"
_TEMPLATE_FILE = _TEMPLATES_DIR / "conversation" / "main" / "initial.jinja2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_whitelist() -> list[str]:
    """Return enabled_action_tools from .initial.config.yaml (empty list if absent)."""
    data = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8"))
    return data.get("tools", {}).get("enabled_action_tools") or []


def _tool_json_names() -> dict[str, Path]:
    """Return {tool_name: tool.json path} for every tool.json found under _TOOLS_DIR."""
    result = {}
    for tool_json in _TOOLS_DIR.rglob("tool.json"):
        try:
            data = json.loads(tool_json.read_text(encoding="utf-8"))
            name = data.get("name")
            if name:
                result[name] = tool_json
        except Exception:
            pass
    return result


def _render_prompt_with_tools(tool_names: list[str]) -> str:
    """Render initial.jinja2 with a minimal feed that includes the given tool names."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=False,
    )
    template = env.get_template("conversation/main/initial.jinja2")

    # Build a minimal action_tools string the same way ConversationalInferencer would:
    # just list the tool names so we can assert they appear in the output.
    action_tools_str = "\n".join(f"- {n}" for n in tool_names)

    rendered = template.render(
        action_tools=action_tools_str,
        conversation_tools="",
        conversation_history=[],
        current_turn={"role": "manager", "content": "Hello"},
    )
    return rendered


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def whitelist() -> list[str]:
    return _load_whitelist()


@pytest.fixture(scope="module")
def tool_json_map() -> dict[str, Path]:
    return _tool_json_names()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWhitelistConfig:
    """The whitelist config file is well-formed and non-empty."""

    def test_config_file_exists(self):
        assert _CONFIG_FILE.is_file(), f"Config file missing: {_CONFIG_FILE}"

    def test_whitelist_is_non_empty(self, whitelist):
        assert whitelist, (
            "enabled_action_tools in .initial.config.yaml is empty — "
            "no action tools will be injected into the conversation prompt."
        )

    def test_whitelist_items_are_strings(self, whitelist):
        for item in whitelist:
            assert isinstance(item, str) and item.strip(), (
                f"Whitelist entry is not a non-empty string: {item!r}"
            )


class TestToolJsonRegistry:
    """Every whitelisted tool must have a tool.json so load_all_tools() can find it."""

    def test_all_whitelisted_tools_have_tool_json(self, whitelist, tool_json_map):
        missing = [name for name in whitelist if name not in tool_json_map]
        assert not missing, (
            f"Whitelisted tool(s) have no tool.json and will NOT be loaded into the prompt:\n"
            + "\n".join(f"  - {name}  (expected a tool.json under {_TOOLS_DIR}/{name}/)" for name in missing)
        )

    def test_tool_json_names_match_directory(self, whitelist, tool_json_map):
        """The 'name' field inside tool.json should match the directory name."""
        for tool_name in whitelist:
            if tool_name not in tool_json_map:
                continue  # caught by test above
            tool_json_path = tool_json_map[tool_name]
            dir_name = tool_json_path.parent.name
            assert dir_name == tool_name, (
                f"tool.json for '{tool_name}' lives in directory '{dir_name}' — "
                f"directory name should match the tool name for consistent discovery."
            )

    def test_tool_json_has_required_fields(self, whitelist, tool_json_map):
        required_fields = {"name", "description", "parameters", "returns"}
        for tool_name in whitelist:
            if tool_name not in tool_json_map:
                continue  # caught by test above
            data = json.loads(tool_json_map[tool_name].read_text(encoding="utf-8"))
            missing_fields = required_fields - data.keys()
            assert not missing_fields, (
                f"tool.json for '{tool_name}' is missing required fields: {missing_fields}"
            )


class TestFilterToolsByConfig:
    """ConversationService._filter_tools_by_config() behaves correctly."""

    def _make_mock_registry(self, names: list[str]) -> dict:
        """Build a minimal mock tool registry with the given tool names."""
        class _MockTool:
            def __init__(self, name):
                self.name = name
                self.aliases = []
        return {name: _MockTool(name) for name in names}

    def _make_mock_renderer(self, whitelist: list[str]):
        """Build a mock prompt renderer whose template_config returns the given whitelist."""
        class _MockRenderer:
            @property
            def template_config(self):
                return {"tools": {"enabled_action_tools": whitelist}}
        return _MockRenderer()

    def test_whitelisted_tools_are_kept(self, whitelist):
        from openteam.server.services.conversation_service import ConversationService

        all_names = whitelist + ["slack_send_message", "twg", "some_other_tool"]
        registry = self._make_mock_registry(all_names)
        renderer = self._make_mock_renderer(whitelist)

        filtered = ConversationService._filter_tools_by_config(registry, renderer)

        for name in whitelist:
            assert name in filtered, (
                f"Whitelisted tool '{name}' was dropped by _filter_tools_by_config()"
            )

    def test_non_whitelisted_tools_are_excluded(self, whitelist):
        from openteam.server.services.conversation_service import ConversationService

        non_whitelisted = ["slack_send_message", "twg", "some_other_tool"]
        all_names = whitelist + non_whitelisted
        registry = self._make_mock_registry(all_names)
        renderer = self._make_mock_renderer(whitelist)

        filtered = ConversationService._filter_tools_by_config(registry, renderer)

        for name in non_whitelisted:
            assert name not in filtered, (
                f"Non-whitelisted tool '{name}' was unexpectedly kept by _filter_tools_by_config()"
            )

    def test_empty_whitelist_returns_all_tools(self):
        from openteam.server.services.conversation_service import ConversationService

        all_names = ["tool_a", "tool_b", "tool_c"]
        registry = self._make_mock_registry(all_names)
        renderer = self._make_mock_renderer([])  # empty whitelist → pass all through

        filtered = ConversationService._filter_tools_by_config(registry, renderer)

        assert filtered == registry, (
            "Empty whitelist should return the full registry unchanged"
        )

    def test_absent_whitelist_returns_all_tools(self):
        from openteam.server.services.conversation_service import ConversationService

        class _NoConfigRenderer:
            @property
            def template_config(self):
                return {}  # no 'tools' key at all

        all_names = ["tool_a", "tool_b"]
        registry = self._make_mock_registry(all_names)

        filtered = ConversationService._filter_tools_by_config(registry, _NoConfigRenderer())

        assert filtered == registry, (
            "Absent whitelist config should return the full registry unchanged"
        )

    def test_filter_count_matches_whitelist(self, whitelist):
        from openteam.server.services.conversation_service import ConversationService

        # Registry contains exactly the whitelisted tools + extras
        extra = ["extra_tool_1", "extra_tool_2"]
        registry = self._make_mock_registry(whitelist + extra)
        renderer = self._make_mock_renderer(whitelist)

        filtered = ConversationService._filter_tools_by_config(registry, renderer)

        assert len(filtered) == len(whitelist), (
            f"Expected {len(whitelist)} tools after filtering, got {len(filtered)}"
        )


class TestPromptInjection:
    """Whitelisted tool names must appear in the rendered conversation prompt."""

    def test_whitelisted_tools_appear_in_prompt(self, whitelist):
        rendered = _render_prompt_with_tools(whitelist)
        for tool_name in whitelist:
            assert tool_name in rendered, (
                f"Tool '{tool_name}' is whitelisted but does NOT appear in the "
                f"rendered conversation prompt (initial.jinja2)."
            )

    def test_non_whitelisted_tool_absent_from_prompt(self, whitelist):
        non_whitelisted = "__definitely_not_a_real_tool__"
        rendered = _render_prompt_with_tools(whitelist)
        assert non_whitelisted not in rendered, (
            f"Sentinel non-whitelisted tool unexpectedly appeared in the prompt."
        )

    def test_action_tools_section_present_when_tools_provided(self, whitelist):
        rendered = _render_prompt_with_tools(whitelist)
        assert "### Action Tools" in rendered, (
            "The '### Action Tools' section header is missing from the rendered prompt."
        )

    def test_action_tools_section_absent_when_no_tools(self):
        rendered = _render_prompt_with_tools([])
        assert "### Action Tools" not in rendered, (
            "The '### Action Tools' section should not appear when no tools are provided."
        )
