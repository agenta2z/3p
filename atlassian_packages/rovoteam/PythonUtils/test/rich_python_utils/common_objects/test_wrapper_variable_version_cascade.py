"""Locks in: wrapper variables MUST resolve nested references against the
caller's ``version`` argument (not the global/default).

Context
-------
Wrapper variables (e.g. ``context.user_request_with_task_preamble``) contain
nested ``{{ X }}`` references that must cascade the version into their own
resolution. Without this, an aggregator inferencer (``version="aggregation"``)
would receive the default ``task_preamble`` instead of the aggregation-
specific one — silently producing the wrong prompt.

These tests pin the behaviour empirically observed on 2026-05-21 in
PythonUtils after the consolidation of ``_set_nested_key`` helpers.
"""

from pathlib import Path

import pytest

from python_utils.common_objects.variable_manager import (
    FileBasedVariableManager,
    VariableManagerConfig,
)


@pytest.fixture
def template_root(tmp_path: Path) -> Path:
    """Build a minimal template root that mirrors the production layout
    used by ``plan/main`` (aggregation-capable space).

    Layout::

        <tmp>/
          _variables/
            context/
              user_request_with_task_preamble.jinja2   # WRAPPER
            task_preamble/
              default.jinja2                           # generic
              aggregation.jinja2                       # version-specific
    """
    root = tmp_path
    var_root = root / "_variables"
    var_root.mkdir()

    # Wrapper variable references both nested vars
    ctx = var_root / "context"
    ctx.mkdir()
    (ctx / "user_request_with_task_preamble.jinja2").write_text(
        "{{ task_preamble }}\n\n## Original User Request\n{{ input }}",
        encoding="utf-8",
    )

    # Versioned task_preamble folder (production convention)
    tp = var_root / "task_preamble"
    tp.mkdir()
    (tp / "default.jinja2").write_text(
        "DEFAULT_PREAMBLE_MARKER", encoding="utf-8"
    )
    (tp / "aggregation.jinja2").write_text(
        "AGGREGATION_PREAMBLE_MARKER", encoding="utf-8"
    )

    return root


@pytest.fixture
def loader(template_root: Path) -> FileBasedVariableManager:
    # Use production-aligned config: variables live under ``_variables/``
    # (matching the OpenTeam / AgentFoundation template trees).
    config = VariableManagerConfig(variables_folder_name="_variables")
    return FileBasedVariableManager(
        base_path=str(template_root), config=config
    )


# ---------------------------------------------------------------------------
# Direct lookup: file resolution honours ``version``
# ---------------------------------------------------------------------------


class TestDirectVersionLookup:
    """Sanity: direct ``_find_variable_file`` call already respects version."""

    def test_default_when_no_version(self, loader, template_root):
        path, _ = loader._find_variable_file(
            "task_preamble", [template_root / "_variables"], version=""
        )
        assert path is not None
        assert "DEFAULT_PREAMBLE_MARKER" in path.read_text()

    def test_aggregation_when_version_set(self, loader, template_root):
        path, _ = loader._find_variable_file(
            "task_preamble",
            [template_root / "_variables"],
            version="aggregation",
        )
        assert path is not None
        assert "AGGREGATION_PREAMBLE_MARKER" in path.read_text()


# ---------------------------------------------------------------------------
# Wrapper-variable resolution: the real regression test
# ---------------------------------------------------------------------------


class TestWrapperVariableVersionCascade:
    """When a template references a *wrapper* variable that itself contains
    nested ``{{ X }}`` references, the caller's ``version`` MUST cascade into
    the wrapper's body resolution. Otherwise an aggregator would see the
    default preamble instead of the aggregation-specific one.
    """

    def test_wrapper_with_no_version_yields_default_nested(self, loader):
        """No version -> wrapper's nested ``task_preamble`` resolves to default."""
        content = "{{ context.user_request_with_task_preamble }}"
        resolved = loader.resolve_from_content(content, version="")
        wrapper = resolved.get("context.user_request_with_task_preamble", "")
        assert "DEFAULT_PREAMBLE_MARKER" in wrapper, (
            "Wrapper should embed DEFAULT preamble when no version. Got:\n"
            + wrapper[:300]
        )
        # The nested ``{{ input }}`` is left for the template_manager layer
        # to substitute; here we only verify the variable-resolution cascade.
        assert "{{ input }}" in wrapper

    def test_wrapper_with_aggregation_version_yields_aggregation_nested(
        self, loader
    ):
        """The regression test: version="aggregation" MUST cascade into the
        wrapper body so the nested ``task_preamble`` resolves to
        ``aggregation.jinja2`` (NOT the default).
        """
        content = "{{ context.user_request_with_task_preamble }}"
        resolved = loader.resolve_from_content(
            content, version="aggregation"
        )
        wrapper = resolved.get("context.user_request_with_task_preamble", "")
        assert "AGGREGATION_PREAMBLE_MARKER" in wrapper, (
            "Wrapper should embed AGGREGATION preamble when version='aggregation'. "
            "Bug: version did NOT cascade into the wrapper body. Got:\n"
            + wrapper[:300]
        )
        # Sanity: DEFAULT must NOT leak through
        assert "DEFAULT_PREAMBLE_MARKER" not in wrapper, (
            "BUG: default preamble leaked into aggregation context. Got:\n"
            + wrapper[:300]
        )

    def test_direct_reference_independently_resolves(self, loader):
        """Sanity: a direct ``{{ task_preamble }}`` reference (no wrapper)
        also resolves to the aggregation version. Confirms the wrapper layer
        is the only differentiator — the underlying mechanism is sound.
        """
        content = "{{ task_preamble }}"
        resolved = loader.resolve_from_content(
            content, version="aggregation"
        )
        direct = resolved.get("task_preamble", "")
        assert "AGGREGATION_PREAMBLE_MARKER" in direct
        assert "DEFAULT_PREAMBLE_MARKER" not in direct


# ---------------------------------------------------------------------------
# Negative test: an unknown version falls back to default (graceful degradation)
# ---------------------------------------------------------------------------


class TestUnknownVersionFallback:
    def test_unknown_version_falls_back_to_default(self, loader):
        """An unrecognised version should fall through to default (Pass 2 in
        ``_find_variable_file``). The wrapper body should embed default.
        """
        content = "{{ context.user_request_with_task_preamble }}"
        resolved = loader.resolve_from_content(
            content, version="nonexistent_version_xyz"
        )
        wrapper = resolved.get("context.user_request_with_task_preamble", "")
        assert "DEFAULT_PREAMBLE_MARKER" in wrapper, (
            "Unknown version should fall through to default. Got:\n"
            + wrapper[:300]
        )
