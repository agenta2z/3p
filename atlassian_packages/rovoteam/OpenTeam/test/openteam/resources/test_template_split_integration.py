"""Integration tests for the prompt-template split (Task 8).

Verifies that the 2-root TemplateManager wiring (OpenTeam first,
AgentFoundation second) correctly:
  - Resolves wrapper templates from AgentFoundation with variables from
    OpenTeam's ``_variables/`` (fallback path).
  - Resolves specialized variable variants (e.g., ``role_setup_report``)
    when the wrapper template comes from AgentFoundation.
  - Returns the OpenTeam (higher-priority) version when a template
    exists in BOTH roots.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
)
from python_utils.string_utils.formatting.template_manager.template_manager import (
    _OriginTaggedStr,
)

# ---------------------------------------------------------------------------
# Resolve the two template roots from installed packages
# ---------------------------------------------------------------------------

import agent_foundation.resources as _af_res
import openteam.server.resources as _os_res

OS_TEMPLATES_ROOT = str(Path(_os_res.__file__).parent / "prompt_templates")
AF_TEMPLATES_ROOT = str(Path(_af_res.__file__).parent / "prompt_templates")


def _make_2root_tm(**kwargs) -> TemplateManager:
    """Construct a TemplateManager with the canonical 2-root list.

    OpenTeam first (override + all ``_variables/``),
    AgentFoundation second (fallback wrappers only, no ``_variables/``).
    """
    defaults = dict(
        templates=[OS_TEMPLATES_ROOT, AF_TEMPLATES_ROOT],
        active_template_type="main",
        predefined_variables=True,
        default_template_key="initial",
        enable_templated_feed=True,
    )
    defaults.update(kwargs)
    return TemplateManager(**defaults)


# ===========================================================================
# 8.1 — Wrapper template in AgentFoundation resolves variables from
#        OpenTeam's _variables/ (fallback path)
# ===========================================================================


class TestWrapperResolvesVariablesFromOpenTeam:
    """AgentFoundation has NO ``_variables/``, so ``_variable_loader`` falls
    back to OpenTeam's loader.  Wrapper templates that reference
    ``{{ task_preamble }}`` or ``{{ task_instructions }}`` must still render
    with real variable content."""

    def test_plan_initial_resolves_task_preamble(self):
        """plan/main/initial.jinja2 lives in AgentFoundation.
        Its ``{{ task_preamble }}`` must resolve from OpenTeam's
        ``plan/main/_variables/task_preamble/default.jinja2``."""
        tm = _make_2root_tm()

        # The raw template should come from AgentFoundation (it was moved there)
        raw = tm.get_raw_template(
            "initial",
            active_template_root_space="plan",
            active_template_type="main",
        )
        assert raw is not None, "plan/main/initial template not found"
        # Verify it's the wrapper (contains the characteristic markers)
        assert "task_preamble" in raw, "wrapper template must reference task_preamble"

        # Verify the origin is AgentFoundation (template was moved there)
        origin = getattr(raw, "_origin_root", None)
        assert origin == AF_TEMPLATES_ROOT, (
            f"plan/main/initial should come from AgentFoundation; got origin={origin!r}"
        )

    def test_plan_initial_variable_resolution_produces_content(self):
        """Render plan/main/initial with the 2-root TM and verify that
        predefined variables (task_preamble, task_instructions) are resolved
        to non-empty content from OpenTeam's _variables/."""
        tm = _make_2root_tm()

        # load_variables should find the default task_preamble from OpenTeam
        result = tm.load_variables(
            {"task_preamble": "default"}, root_space="plan"
        )
        preamble = result["task_preamble"]
        assert len(preamble.strip()) > 0, "task_preamble/default should not be empty"

    def test_implementation_initial_resolves_variables(self):
        """implementation/main/initial.jinja2 lives in AgentFoundation.
        Variables must resolve from OpenTeam."""
        tm = _make_2root_tm()

        raw = tm.get_raw_template(
            "initial",
            active_template_root_space="implementation",
            active_template_type="main",
        )
        assert raw is not None
        origin = getattr(raw, "_origin_root", None)
        assert origin == AF_TEMPLATES_ROOT, (
            f"implementation/main/initial should come from AgentFoundation; "
            f"got origin={origin!r}"
        )

        # Verify variable resolution works
        result = tm.load_variables(
            {"task_preamble": "default"}, root_space="implementation"
        )
        assert len(result["task_preamble"].strip()) > 0, (
            "implementation task_preamble/default should resolve from OpenTeam"
        )

    def test_both_roots_have_variable_loaders(self):
        """Both roots should have VariableLoaders — OpenTeam has
        ``_variables/task_preamble/``, AgentFoundation has
        ``_variables/notes/`` (shared cross-template variables)."""
        tm = _make_2root_tm()
        assert OS_TEMPLATES_ROOT in tm._variable_loaders_by_root, (
            "OpenTeam root should have a VariableLoader"
        )
        assert AF_TEMPLATES_ROOT in tm._variable_loaders_by_root, (
            "AgentFoundation root should have a VariableLoader "
            "(it now has _variables/notes/ for shared variables)"
        )

    def test_variable_loader_fallback_is_openstartup(self):
        """The backward-compat ``_variable_loader`` should point to
        OpenTeam's loader (the first root with ``_variables/``)."""
        tm = _make_2root_tm()
        assert tm._variable_loader is not None, (
            "_variable_loader should be set (backward compat)"
        )
        assert tm._variable_loader is tm._variable_loaders_by_root[OS_TEMPLATES_ROOT], (
            "_variable_loader should be OpenTeam's loader"
        )


# ===========================================================================
# 8.2 — Specialized variable variant resolved for AgentFoundation templates
# ===========================================================================


class TestSpecializedVariantResolution:
    """Specialized variable variants (e.g., ``role_setup_report``,
    ``aggregation``) must resolve correctly even when the wrapper template
    comes from AgentFoundation."""

    def test_role_setup_report_task_instructions(self):
        """``task_instructions/role_setup_report`` variant must resolve
        from OpenTeam's ``plan/main/_variables/``."""
        tm = _make_2root_tm()

        result = tm.load_variables(
            {"task_instructions": "role_setup_report"}, root_space="plan"
        )
        content = result["task_instructions"]
        assert "Role Setup Report" in content, (
            "role_setup_report variant should contain 'Role Setup Report'"
        )

    def test_aggregation_task_preamble(self):
        """``task_preamble/aggregation`` variant must resolve from
        OpenTeam's ``plan/main/_variables/``."""
        tm = _make_2root_tm()

        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert len(result["task_preamble"].strip()) > 0, (
            "task_preamble/aggregation should resolve from OpenTeam"
        )

    def test_skill_tool_creation_task_instructions(self):
        """``task_instructions/skill_tool_creation`` variant must resolve
        from OpenTeam's ``plan/main/_variables/``."""
        tm = _make_2root_tm()

        result = tm.load_variables(
            {"task_instructions": "skill_tool_creation"}, root_space="plan"
        )
        assert len(result["task_instructions"].strip()) > 0, (
            "task_instructions/skill_tool_creation should resolve from OpenTeam"
        )

    def test_implementation_aggregation_task_instructions(self):
        """``task_instructions/aggregation`` variant must resolve from
        OpenTeam's ``implementation/main/_variables/``."""
        tm = _make_2root_tm()

        result = tm.load_variables(
            {"task_instructions": "aggregation"}, root_space="implementation"
        )
        content = result["task_instructions"]
        assert "aggregat" in content.lower(), (
            "aggregation variant should contain aggregation-related content"
        )


# ===========================================================================
# 8.3 — Template in BOTH roots returns OpenTeam (higher-priority) version
# ===========================================================================


class TestHigherPriorityRootWins:
    """When a template exists in both OpenTeam and AgentFoundation,
    the OpenTeam version (first in the list) must win."""

    def test_override_with_synthetic_duplicate(self, tmp_path):
        """Create a synthetic scenario where both roots have the same
        template key, and verify the first root wins."""
        # Create two roots with the same template
        override = tmp_path / "override"
        base = tmp_path / "base"

        # Write the same template key in both roots
        (override / "plan" / "main").mkdir(parents=True)
        (override / "plan" / "main" / "initial.jinja2").write_text(
            "OVERRIDE: {{ input }}", encoding="utf-8"
        )
        (base / "plan" / "main").mkdir(parents=True)
        (base / "plan" / "main" / "initial.jinja2").write_text(
            "BASE: {{ input }}", encoding="utf-8"
        )

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
            default_template_key="initial",
        )

        raw = tm.get_raw_template(
            "initial",
            active_template_root_space="plan",
            active_template_type="main",
        )
        assert raw is not None
        assert "OVERRIDE" in raw, (
            "First root (override) should win over second root (base)"
        )
        assert "BASE" not in raw

    def test_real_roots_plan_initial_comes_from_af(self):
        """With the real 2-root setup, plan/main/initial.jinja2 should come
        from AgentFoundation (since it was MOVED there — it no longer exists
        in OpenTeam)."""
        tm = _make_2root_tm()

        raw = tm.get_raw_template(
            "initial",
            active_template_root_space="plan",
            active_template_type="main",
        )
        origin = getattr(raw, "_origin_root", None)
        # After the split, the wrapper template only exists in AgentFoundation
        assert origin == AF_TEMPLATES_ROOT, (
            f"plan/main/initial should come from AgentFoundation after the split; "
            f"got origin={origin!r}"
        )

    def test_variables_yaml_persona_comes_from_openstartup(self):
        """The ``.variables.yaml`` persona (employee) should come from
        OpenTeam (it was NOT moved to AgentFoundation)."""
        tm = _make_2root_tm()

        # The .variables.yaml sidecar is loaded by the VariableLoader
        # for the OpenTeam root. Verify the employee persona is available.
        loader = tm._variable_loaders_by_root.get(OS_TEMPLATES_ROOT)
        assert loader is not None

        # The YAML sidecar variables should include the employee persona
        yaml_vars = loader.get_all_variables(
            variable_root_space="plan",
            variable_type="main",
        )
        assert "employee" in yaml_vars, (
            ".variables.yaml persona (employee) should be available from OpenTeam"
        )
        employee = yaml_vars["employee"]
        assert "name" in employee, "employee should have a name field"
        assert employee["name"] == "OpenTeam", (
            "employee.name should be 'OpenTeam' from the .variables.yaml"
        )
