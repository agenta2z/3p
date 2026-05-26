"""Tests for the ``cross_root_variable_lookup`` flag on TemplateManager.

Refactor 17: when set, variable resolution at render time falls back across
all roots' VariableLoaders in priority order, using ``self.load_variable``
(Refactor 12 cross-root semantics) so that an exact-version match in any
root wins over a default fallback in the origin root.

When the flag is False (default), per-root variable isolation is preserved
exactly as before — these tests also verify the existing isolation
behavior to lock it in as the default.

Test fixtures use TOP-LEVEL ``_variables/`` (matching existing
``test_multi_root_templates.py`` convention; the predefined-variables code
path requires top-level ``_variables/`` to register a per-root
VariableLoader).
"""

from pathlib import Path

import pytest

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
)


# ---------------------------------------------------------------------------
# Two-root fixture: A has specialized variant, B has wrapper + generic
# ---------------------------------------------------------------------------


@pytest.fixture
def two_root_templates(tmp_path: Path) -> tuple[Path, Path]:
    """Build two template roots with TOP-LEVEL ``_variables/``.

    Root A (consumer-specialized) at <tmp>/consumer:
        _variables/task_preamble/role_setup.j2 → "ROLE_SETUP_FROM_A"
        _variables/task_preamble/aggregation.j2 → "AGG_FROM_A_SPECIALIZED"

    Root B (framework-common) at <tmp>/framework:
        main/initial.j2 → wraps {{task_preamble}}
        _variables/task_preamble/aggregation.j2 → "AGG_FROM_B"
        _variables/task_preamble/default.j2 → "DEFAULT_FROM_B"
    """
    consumer = tmp_path / "consumer"
    framework = tmp_path / "framework"

    # Root A — specialized
    a_vars = consumer / "_variables" / "task_preamble"
    a_vars.mkdir(parents=True)
    (a_vars / "role_setup.j2").write_text("ROLE_SETUP_FROM_A", encoding="utf-8")
    (a_vars / "aggregation.j2").write_text(
        "AGG_FROM_A_SPECIALIZED", encoding="utf-8"
    )

    # Root B — wrappers + generic variables
    b_main = framework / "main"
    b_main.mkdir(parents=True)
    (b_main / "initial.j2").write_text(
        "WRAPPER:{{task_preamble}}END",
        encoding="utf-8",
    )
    b_vars = framework / "_variables" / "task_preamble"
    b_vars.mkdir(parents=True)
    (b_vars / "aggregation.j2").write_text("AGG_FROM_B", encoding="utf-8")
    (b_vars / "default.j2").write_text("DEFAULT_FROM_B", encoding="utf-8")

    return consumer, framework


# ---------------------------------------------------------------------------
# Default behavior (cross_root_variable_lookup=False) — preserves isolation
# ---------------------------------------------------------------------------


class TestCrossRootDisabledPreservesIsolation:
    def test_default_flag_is_false(self, two_root_templates):
        consumer, framework = two_root_templates
        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
        )
        assert tm.cross_root_variable_lookup is False

    def test_wrapper_in_B_cannot_see_specialized_variant_in_A(
        self, two_root_templates
    ):
        # Strict per-root isolation: wrapper from B (framework) renders with
        # B's loader only. role_setup.j2 lives in A, never seen.
        consumer, framework = two_root_templates
        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
            template_version="role_setup",
        )
        result = tm("initial")
        assert "ROLE_SETUP_FROM_A" not in result, (
            "isolation violated: A's role_setup variant leaked to B's render"
        )


# ---------------------------------------------------------------------------
# Enabled behavior (cross_root_variable_lookup=True)
# ---------------------------------------------------------------------------


class TestCrossRootEnabled:
    def test_wrapper_in_B_finds_specialized_variant_in_A(
        self, two_root_templates
    ):
        # With cross-root: wrapper from B uses B's loader as primary, then
        # the cross-root override re-resolves via load_variable (which finds
        # role_setup.j2 in A first).
        consumer, framework = two_root_templates
        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
            template_version="role_setup",
        )
        result = tm("initial")
        assert "ROLE_SETUP_FROM_A" in result, (
            f"cross-root fallback failed: got {result!r}"
        )

    def test_origin_root_wins_among_others_for_same_key_via_priority(
        self, two_root_templates
    ):
        # Both A and B have task_preamble/aggregation.j2. With version=
        # aggregation: load_variable iterates [A, B] in priority order.
        # A is first → A's value wins. (This is "highest priority root
        # for that variable wins" — the cross-root semantic.)
        consumer, framework = two_root_templates
        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
            template_version="aggregation",
        )
        result = tm("initial")
        # A is first in templates list → load_variable Pass 1 finds A's first.
        assert "AGG_FROM_A_SPECIALIZED" in result, (
            f"priority order broken: {result!r}"
        )
        assert "AGG_FROM_B" not in result

    def test_origin_no_loader_falls_through_then_cross_root(self, tmp_path):
        # Wrapper from a root with no _variables/. No per-root loader for it.
        # Cross-root delegates to load_variable across all roots.
        primary = tmp_path / "primary"
        secondary = tmp_path / "secondary"
        wrapper = tmp_path / "wrapper"

        # Primary has 'var' / version 'v'
        p_vars = primary / "_variables" / "var"
        p_vars.mkdir(parents=True)
        (p_vars / "v.j2").write_text("PRIMARY", encoding="utf-8")
        # Secondary has 'var2' / version 'v'
        s_vars = secondary / "_variables" / "var2"
        s_vars.mkdir(parents=True)
        (s_vars / "v.j2").write_text("SECONDARY_VAR2", encoding="utf-8")
        # Wrapper root has no _variables/
        w_main = wrapper / "main"
        w_main.mkdir(parents=True)
        (w_main / "initial.j2").write_text(
            "{{var}}|{{var2}}", encoding="utf-8"
        )

        tm = TemplateManager(
            templates=[str(primary), str(secondary), str(wrapper)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
            template_version="v",
        )
        result = tm("initial")
        assert "PRIMARY" in result
        assert "SECONDARY_VAR2" in result


# ---------------------------------------------------------------------------
# Invariants and edge cases
# ---------------------------------------------------------------------------


class TestCrossRootInvariants:
    def test_cross_root_irrelevant_when_predefined_variables_false(
        self, two_root_templates
    ):
        # With predefined_variables=False, the per-root loader code path is
        # not entered at all — cross_root_variable_lookup has no effect.
        consumer, framework = two_root_templates
        tm_off = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=False,
            cross_root_variable_lookup=False,
        )
        tm_on = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=False,
            cross_root_variable_lookup=True,
        )
        result_off = tm_off("initial", task_preamble="X")
        result_on = tm_on("initial", task_preamble="X")
        assert result_off == result_on
        assert "X" in result_off

    def test_switch_preserves_cross_root_flag(self, two_root_templates):
        consumer, framework = two_root_templates
        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
        )
        switched = tm.switch(template_version="role_setup")
        assert switched.cross_root_variable_lookup is True

    def test_add_template_root_preserves_cross_root_flag(
        self, two_root_templates, tmp_path
    ):
        consumer, framework = two_root_templates
        third = tmp_path / "third"
        (third / "main").mkdir(parents=True)
        (third / "main" / "extra.j2").write_text("EXTRA", encoding="utf-8")

        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
        )
        tm.add_template_root(str(third))
        assert tm.cross_root_variable_lookup is True

    def test_static_predefined_vars_unaffected_by_flag(self, tmp_path):
        # When predefined_variables is a Mapping, _static_predefined_vars
        # path is used, not per-root loaders. Cross-root flag is irrelevant.
        a = tmp_path / "a"
        a_main = a / "main"
        a_main.mkdir(parents=True)
        (a_main / "initial.j2").write_text("{{x}}", encoding="utf-8")

        tm = TemplateManager(
            templates=str(a),
            active_template_type="main",
            predefined_variables={"x": "STATIC_X"},
            cross_root_variable_lookup=True,
        )
        result = tm("initial")
        assert result == "STATIC_X"


# ---------------------------------------------------------------------------
# Default fallback within origin still works (Refactor 12 Pass 2 inside loader)
# ---------------------------------------------------------------------------


class TestMultiLevelVariantSelection:
    """Verify that ``template_version`` supports slash-separated multi-level
    variant selection (e.g., ``understand_codebase/meta_mrs_rankevolve``)
    AND that the single-file-per-folder cross-root convention works for
    consumer-specialized variants (e.g., AgentFoundation provides
    ``generic.jinja2``; a consumer provides
    ``meta_mrs_rankevolve.jinja2`` in its own root; cross-root priority
    picks the consumer's variant).
    """

    def test_consumer_specialized_variant_wins_via_cross_root_priority(
        self, tmp_path
    ):
        """Single-file-per-folder pattern across two roots.

        AgentFoundation root: ``implementation/main/_variables/task_preamble/
        understand_codebase/generic.jinja2``

        Consumer root: ``plan/main/_variables/task_preamble/
        understand_codebase/meta_mrs_rankevolve.jinja2``

        With ``templates=[consumer, agentfoundation]`` and
        ``cross_root_variable_lookup=True``, the consumer's variant wins
        for namespace=plan; framework's generic is used for namespace=
        implementation.
        """
        af = tmp_path / "agentfoundation"
        consumer = tmp_path / "consumer"

        # AgentFoundation: framework-level generic for implementation namespace
        af_var = af / "implementation" / "main" / "_variables" / "task_preamble" / "understand_codebase"
        af_var.mkdir(parents=True)
        (af_var / "generic.j2").write_text("GENERIC_FRAMEWORK", encoding="utf-8")
        (af / "implementation" / "main" / "initial.j2").write_text(
            "IMPL:{{task_preamble}}", encoding="utf-8"
        )
        # Top-level _variables/ for the per-root loader to register
        (af / "_variables").mkdir()
        (af / "_variables" / "_marker.j2").write_text("x", encoding="utf-8")

        # Consumer: project-specialized variant for plan namespace
        c_var = consumer / "plan" / "main" / "_variables" / "task_preamble" / "understand_codebase"
        c_var.mkdir(parents=True)
        (c_var / "meta_mrs_rankevolve.j2").write_text(
            "RANKEVOLVE_PROJECT", encoding="utf-8"
        )
        (consumer / "plan" / "main" / "initial.j2").write_text(
            "PLAN:{{task_preamble}}", encoding="utf-8"
        )
        (consumer / "_variables").mkdir()
        (consumer / "_variables" / "_marker.j2").write_text("x", encoding="utf-8")

        tm = TemplateManager(
            templates=[str(consumer), str(af)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
            template_version="understand_codebase",
        )
        # plan namespace: consumer's specialized variant wins
        plan_result = tm("initial", active_template_root_space="plan")
        assert "RANKEVOLVE_PROJECT" in plan_result
        # implementation namespace: framework's generic is used (consumer
        # has no implementation/...).
        impl_result = tm("initial", active_template_root_space="implementation")
        assert "GENERIC_FRAMEWORK" in impl_result

    def test_slash_separated_version_selects_specific_variant(self, tmp_path):
        """When a folder has MULTIPLE variants, slash-separated version
        selects a specific one explicitly.
        """
        # Nested production layout: <root>/<space>/<type>/_variables/<var>/<version>/<variant>.<ext>
        p = tmp_path / "plan" / "main" / "_variables" / "task_preamble" / "understand_codebase"
        p.mkdir(parents=True)
        (p / "generic.j2").write_text("GENERIC", encoding="utf-8")
        (p / "meta_mrs_rankevolve.j2").write_text(
            "RANKEVOLVE", encoding="utf-8"
        )
        (p / "meta_mrs_attention.j2").write_text(
            "ATTENTION", encoding="utf-8"
        )

        tm = TemplateManager(
            templates=str(tmp_path),
            active_template_type="main",
            active_template_root_space="plan",
            predefined_variables=False,
        )
        result = tm.load_variables(
            {"task_preamble": "understand_codebase/meta_mrs_rankevolve"},
            root_space="plan",
        )
        assert result["task_preamble"] == "RANKEVOLVE"

        result = tm.load_variables(
            {"task_preamble": "understand_codebase/meta_mrs_attention"},
            root_space="plan",
        )
        assert result["task_preamble"] == "ATTENTION"

        result = tm.load_variables(
            {"task_preamble": "understand_codebase/generic"},
            root_space="plan",
        )
        assert result["task_preamble"] == "GENERIC"

        # Plain version with multiple files + no default → falls back to literal
        result = tm.load_variables(
            {"task_preamble": "understand_codebase"},
            root_space="plan",
        )
        assert result["task_preamble"] == "understand_codebase"


class TestCrossRootWithMissingVersion:
    def test_unknown_version_falls_back_to_origin_default(
        self, two_root_templates
    ):
        # template_version='nonexistent' — no root has that version.
        # load_variable Pass 1: iterates [A, B] → no role_setup-equivalent
        # found anywhere. Pass 2 across roots: iterates [A, B] looking for
        # default; A has none, B has default.j2 → returns DEFAULT_FROM_B.
        consumer, framework = two_root_templates
        tm = TemplateManager(
            templates=[str(consumer), str(framework)],
            active_template_type="main",
            predefined_variables=True,
            cross_root_variable_lookup=True,
            template_version="nonexistent_anywhere",
        )
        result = tm("initial")
        assert "DEFAULT_FROM_B" in result, (
            f"default fallback didn't trigger: {result!r}"
        )
