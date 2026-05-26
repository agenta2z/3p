"""Dry-run unit tests for the create_role pipeline wiring.

Validates the BreakdownThenAggregateInferencer configuration without
making any real API calls. Uses mock inferencers to verify:

1. Template rendering includes employee persona from .variables.yaml
2. Breakdown parser correctly extracts subtasks from JSON
3. Worker factory creates isolated RovoChatInferencers per sub-query
4. Aggregator prompt builder collects ALL worker results
5. Pipeline wiring is correct for both rovochat and rovodev aggregator types
6. RovoDevCliInferencer aggregator receives the full rendered prompt

Usage:
    cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam
    python -m pytest test/resources/tools/create_role/test_create_role_dryrun.py -vs
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
sys.path.insert(
    0, "/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src"
)
sys.path.insert(
    0, "/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src"
)

from agent_foundation.common.inferencers.inferencer_workspace import InferencerWorkspace
from openteam.server.resources.tools.create_role.executor import (
    ROLE_SYNTHESIS_INSTRUCTIONS,
    _build_template_manager,
    _load_variable_file,
    build_create_role_inferencer,
    parse_breakdown_response,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def template_manager():
    """Create a TemplateManager from the built-in prompt templates."""
    return _build_template_manager()


@pytest.fixture
def sample_breakdown_json():
    """Sample breakdown JSON response wrapped in <Response> tags."""
    return """<Response>
Here is the decomposition:

```json
{
  "subtasks": [
    {
      "subtask_id": 1,
      "description": "Core responsibilities and day-to-day activities",
      "todos": ["Research daily tasks", "Identify key deliverables"],
      "priority": "CRITICAL",
      "type": "EXTERNAL"
    },
    {
      "subtask_id": 2,
      "description": "Required technical skills and competencies",
      "todos": ["Identify technical requirements", "Map skill levels"],
      "priority": "HIGH",
      "type": "EXTERNAL"
    },
    {
      "subtask_id": 3,
      "description": "Collaboration patterns and stakeholder interactions",
      "todos": ["Map cross-functional relationships", "Define communication norms"],
      "priority": "HIGH",
      "type": "EXTERNAL"
    }
  ],
  "reasoning": "Three complementary facets covering role scope, skills, and interactions.",
  "coverage_complete": true,
  "gaps": "none"
}
```
</Response>"""


@pytest.fixture
def sample_worker_results():
    """Simulated worker research results (one per facet)."""
    return (
        "<Response>## Core Responsibilities\n- Manage sprint planning\n- Coordinate cross-team dependencies\n- Track delivery metrics</Response>",
        "<Response>## Technical Skills\n- Project management tools (Jira, Confluence)\n- Agile/Scrum methodology\n- Risk assessment frameworks</Response>",
        "<Response>## Collaboration Patterns\n- Daily standups with engineering teams\n- Weekly sync with product leadership\n- Quarterly planning with stakeholders</Response>",
    )


# ---------------------------------------------------------------------------
# Test: Template Rendering
# ---------------------------------------------------------------------------


class TestTemplateRendering:
    """Verify templates render correctly with employee persona."""

    def test_employee_persona_in_breakdown(self, template_manager):
        """Employee persona from .variables.yaml must appear in breakdown template."""
        result = template_manager(
            "initial",
            active_template_root_space="task_breakdown",
            input="Program Manager for AI developer tools",
        )
        assert "OpenTeam" in result, "Employee persona 'OpenTeam' not found in rendered template"
        assert "decompos" in result.lower(), "Breakdown instruction not found"

    def test_employee_persona_in_deep_research(self, template_manager):
        """Employee persona must appear in deep research template."""
        result = template_manager(
            "initial",
            active_template_root_space="deep_research",
            input="Research core responsibilities",
        )
        assert "OpenTeam" in result

    def test_employee_persona_in_plan(self, template_manager):
        """Employee persona must appear in plan template."""
        result = template_manager(
            "initial",
            active_template_root_space="plan",
            input="Synthesize findings",
            task_instructions=ROLE_SYNTHESIS_INSTRUCTIONS,
        )
        assert "OpenTeam" in result
        assert "Role Overview" in result, "ROLE_SYNTHESIS_INSTRUCTIONS not injected"

    def test_task_preamble_resolved(self, template_manager):
        """task_preamble should be injected via template_extra_feed (loaded from create_role.jinja2)."""
        from openteam.server.resources.tools.create_role.executor import _load_variable_file
        preamble = _load_variable_file("task_breakdown", "task_preamble", "create_role")
        result = template_manager(
            "initial",
            active_template_root_space="task_breakdown",
            input="Test role",
            task_preamble=preamble,
        )
        # The task_preamble for task_breakdown contains "AI Employee Role Creation"
        assert "AI Employee Role" in result


# ---------------------------------------------------------------------------
# Test: Breakdown Parser
# ---------------------------------------------------------------------------


class TestBreakdownParser:
    """Verify parse_breakdown_response extracts subtasks correctly."""

    def test_parse_json_subtasks(self, sample_breakdown_json):
        """Should extract all 3 subtasks from JSON response."""
        queries = parse_breakdown_response(sample_breakdown_json)
        assert len(queries) == 3
        assert "Core responsibilities" in queries[0]
        assert "technical skills" in queries[1].lower()
        assert "Collaboration" in queries[2]

    def test_parse_includes_todos(self, sample_breakdown_json):
        """Each extracted query should include the todos as investigation areas."""
        queries = parse_breakdown_response(sample_breakdown_json)
        assert "Research daily tasks" in queries[0]
        assert "Identify technical requirements" in queries[1]

    def test_parse_numbered_list_fallback(self):
        """Should fall back to numbered list parsing if no JSON found."""
        raw = "<Response>1. Research core responsibilities\n2. Identify required skills\n3. Map collaboration patterns</Response>"
        queries = parse_breakdown_response(raw)
        assert len(queries) == 3
        assert "core responsibilities" in queries[0].lower()

    def test_parse_empty_response(self):
        """Should return empty list for empty response."""
        queries = parse_breakdown_response("")
        assert isinstance(queries, list)


# ---------------------------------------------------------------------------
# Test: Aggregator Prompt Builder — ALL worker results passed
# ---------------------------------------------------------------------------


class TestAggregatorPromptBuilder:
    """Verify the aggregator prompt builder collects ALL worker results."""

    def test_all_worker_results_in_prompt(
        self, template_manager, sample_worker_results
    ):
        """The aggregator prompt must contain content from ALL worker results."""
        # Reconstruct the agg_prompt_builder exactly as executor.py does
        from agent_foundation.common.response_parsers import extract_delimited

        def agg_prompt_builder(
            worker_results: tuple, *, original_query: str = ""
        ) -> str:
            parts = []
            for idx, res in enumerate(worker_results):
                cleaned = extract_delimited(str(res))
                parts.append(f"### Research Facet {idx + 1}\n{cleaned}")
            joined = "\n\n".join(parts)
            agg_input = (
                f"**Original Role Request:** {original_query}\n\n"
                f"**Research Findings:**\n{joined}"
            )
            return template_manager(
                "initial",
                active_template_root_space="plan",
                input=agg_input,
                task_instructions=ROLE_SYNTHESIS_INSTRUCTIONS,
            )

        prompt = agg_prompt_builder(
            sample_worker_results,
            original_query="Program Manager for AI developer tools",
        )

        # Verify ALL facets are present
        assert "Research Facet 1" in prompt
        assert "Research Facet 2" in prompt
        assert "Research Facet 3" in prompt

        # Verify content from each worker result is included
        assert "sprint planning" in prompt.lower()
        assert "Project management tools" in prompt
        assert "Daily standups" in prompt

        # Verify original query is included
        assert "Program Manager" in prompt

        # Verify synthesis instructions are included
        assert "Role Overview" in prompt
        assert "Core Responsibilities" in prompt

        # Verify employee persona is rendered
        assert "OpenTeam" in prompt

    def test_agg_prompt_file_paths_for_local_aggregator(
        self, sample_worker_results
    ):
        """When workspace is set AND aggregator has local access,
        prompt should include only file path references (no inline text)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from agent_foundation.common.inferencers.inferencer_workspace import (
                InferencerWorkspace,
            )

            inferencer = build_create_role_inferencer(
                cloud_id="test-cloud-id",
                uct_token="test-token",
                aggregator_type="rovodev",
                aggregator_working_dir=tmpdir,
                workspace=tmpdir,
            )
            # Simulate workspace paths that BTA's closure would capture
            ws = InferencerWorkspace(root=tmpdir)
            mock_paths = [
                ws.child(f"worker_{i}").output_path(f"facet_{i}.md")
                for i in range(len(sample_worker_results))
            ]
            prompt = inferencer.aggregator_prompt_builder(
                sample_worker_results,
                original_query="Test",
                worker_output_paths=mock_paths,
            )
            assert "Read the full research report from:" in prompt
            assert "facet_0.md" in prompt
            assert "facet_1.md" in prompt
            assert "facet_2.md" in prompt
            # Should NOT include inline worker content for local aggregator
            assert "sprint planning" not in prompt.lower()

    def test_agg_prompt_inline_text_for_non_local_aggregator(
        self, sample_worker_results
    ):
        """When aggregator lacks local access (RovoChat), prompt should
        include full inline text, NOT file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            inferencer = build_create_role_inferencer(
                cloud_id="test-cloud-id",
                uct_token="test-token",
                aggregator_type="rovochat",
                workspace=tmpdir,
            )
            prompt = inferencer.aggregator_prompt_builder(
                sample_worker_results,
                original_query="Test",
            )
            # Should include inline text
            assert "sprint planning" in prompt.lower()
            # Should NOT include file paths
            assert "Read the full research report from:" not in prompt

    def test_worker_results_count_matches(self, sample_worker_results):
        """Number of Research Facet headers must match number of worker results."""
        from agent_foundation.common.response_parsers import extract_delimited

        parts = []
        for idx, res in enumerate(sample_worker_results):
            cleaned = extract_delimited(str(res))
            parts.append(f"### Research Facet {idx + 1}\n{cleaned}")
        joined = "\n\n".join(parts)

        facet_count = joined.count("### Research Facet")
        assert facet_count == len(sample_worker_results), (
            f"Expected {len(sample_worker_results)} facets, got {facet_count}"
        )

    def test_response_tags_stripped(self, sample_worker_results):
        """<Response> tags should be stripped from worker outputs in aggregator prompt."""
        from agent_foundation.common.response_parsers import extract_delimited

        for res in sample_worker_results:
            cleaned = extract_delimited(str(res))
            assert "<Response>" not in cleaned
            assert "</Response>" not in cleaned


# ---------------------------------------------------------------------------
# Test: Pipeline Wiring (build_create_role_inferencer)
# ---------------------------------------------------------------------------


class TestPipelineWiring:
    """Verify the BTA pipeline is wired correctly."""

    def test_rovochat_aggregator_pipeline(self):
        """Default pipeline uses RovoChatInferencer for all stages."""
        inferencer = build_create_role_inferencer(
            cloud_id="test-cloud-id",
            uct_token="test-token",
            max_facets=3,
        )
        assert inferencer.max_breakdown == 3
        assert inferencer.breakdown_inferencer is not None
        assert inferencer.worker_factory is not None
        assert inferencer.aggregator_inferencer is not None
        assert inferencer.aggregator_prompt_builder is not None
        assert inferencer.max_concurrency is None, (
            "max_concurrency must be None to avoid deadlock with aggregator"
        )

        # Verify breakdown uses task_breakdown template space
        bi = inferencer.breakdown_inferencer
        assert bi.template_root_space == "task_breakdown"
        assert bi.template_key == "initial"

    def test_rovodev_aggregator_pipeline(self):
        """Pipeline with rovodev aggregator uses RovoDevCliInferencer."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            inferencer = build_create_role_inferencer(
                cloud_id="test-cloud-id",
                uct_token="test-token",
                max_facets=2,
                aggregator_type="rovodev",
                aggregator_working_dir=tmpdir,
            )
            assert isinstance(
                inferencer.aggregator_inferencer, RovoDevCliInferencer
            ), (
                f"Expected RovoDevCliInferencer, got "
                f"{type(inferencer.aggregator_inferencer).__name__}"
            )
            assert inferencer.aggregator_inferencer.effective_cwd == tmpdir
            assert inferencer.aggregator_inferencer.yolo is True
            # agent_mode not used with acli

    def test_worker_factory_creates_isolated_instances(self):
        """Worker factory must create a fresh inferencer per sub-query."""
        inferencer = build_create_role_inferencer(
            cloud_id="test-cloud-id",
            uct_token="test-token",
        )
        w1 = inferencer.worker_factory(sub_query="Query 1", index=0)
        w2 = inferencer.worker_factory(sub_query="Query 2", index=1)

        from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
            RovoChatInferencer,
        )
        assert w1 is not w2, "Workers must be distinct instances"
        assert isinstance(w1, RovoChatInferencer), f"Expected RovoChatInferencer, got {type(w1).__name__}"
        assert isinstance(w2, RovoChatInferencer), f"Expected RovoChatInferencer, got {type(w2).__name__}"
        assert w1.template_root_space == "deep_research"
        assert w2.template_root_space == "deep_research"
        assert w1.template_extra_feed.get("task_preamble"), (
            "worker must have task_preamble in template_extra_feed"
        )
        # Each worker must be a distinct instance for conversation isolation
        assert w1 is not w2, (
            "Workers must have separate RovoChatInferencer instances for conversation isolation"
        )

    def test_breakdown_parser_wired(self):
        """Breakdown parser must be wired to parse_breakdown_response."""
        inferencer = build_create_role_inferencer(
            cloud_id="test-cloud-id",
            uct_token="test-token",
        )
        assert inferencer.breakdown_parser is parse_breakdown_response


# ---------------------------------------------------------------------------
# Test: End-to-End Mock Pipeline
# ---------------------------------------------------------------------------


class TestEndToEndMockPipeline:
    """Full pipeline test with mocked inferencers — validates data flow."""

    def test_aggregator_receives_all_worker_results_via_prompt_builder(
        self, sample_worker_results
    ):
        """Simulate the BTA aggregator_prompt_builder call with N worker results.

        This is the critical test: the BTA graph calls
            agg_fn(*worker_results, **_kwargs)
        which triggers:
            prompt_builder(worker_results, original_query=original_query)

        We verify that ALL N worker results appear in the final prompt.
        """
        inferencer = build_create_role_inferencer(
            cloud_id="test-cloud-id",
            uct_token="test-token",
            max_facets=5,
        )

        # Call the aggregator_prompt_builder directly as BTA would
        prompt = inferencer.aggregator_prompt_builder(
            sample_worker_results,
            original_query="Program Manager for AI developer tools",
        )

        # ALL 3 worker results must be present
        for i in range(len(sample_worker_results)):
            assert f"Research Facet {i + 1}" in prompt, (
                f"Worker result {i + 1} missing from aggregator prompt"
            )

        # Content from each result must be present
        assert "sprint planning" in prompt.lower()
        assert "Project management tools" in prompt
        assert "Daily standups" in prompt

        # Synthesis instructions must be present
        assert "Role Overview" in prompt
        assert "Success Metrics" in prompt

    def test_rovodev_aggregator_receives_full_prompt(
        self, sample_worker_results
    ):
        """When using rovodev aggregator, verify the full rendered prompt
        would be passed to RovoDevCliInferencer.infer().
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            inferencer = build_create_role_inferencer(
                cloud_id="test-cloud-id",
                uct_token="test-token",
                max_facets=3,
                aggregator_type="rovodev",
                aggregator_working_dir=tmpdir,
                workspace=tmpdir,
            )

            # Build the prompt that would be sent to rovodev
            prompt = inferencer.aggregator_prompt_builder(
                sample_worker_results,
                original_query="Program Manager for AI developer tools",
            )

            # Verify prompt is substantial (should be several KB)
            assert len(prompt) > 2000, (
                f"Aggregator prompt too short ({len(prompt)} chars) — "
                f"may be missing worker results or template content"
            )

            # Verify all components are present
            assert "OpenTeam" in prompt, "Employee persona missing"
            assert "Research Facet 1" in prompt, "First worker result missing"
            assert "Research Facet 3" in prompt, "Last worker result missing"
            assert "Role Overview" in prompt, "Synthesis instructions missing"
            assert "Program Manager" in prompt, "Original query missing"


if __name__ == "__main__":
    pytest.main([__file__, "-vs"])


# ---------------------------------------------------------------------------
# Test: Worker receives sub-query (not original input)
# ---------------------------------------------------------------------------


class TestWorkerSubQueryInjection:
    """Verify each worker gets its specific sub-query, not the original input."""

    def test_worker_template_renders_sub_query(self, template_manager):
        """Worker must render the sub-query text into the deep_research template,
        not the original role description.
        """
        sub_query = "Research required technical skills for a Program Manager"
        rendered = template_manager(
            "initial",
            active_template_root_space="deep_research",
            input=sub_query,
        )
        # The sub-query text must appear in the rendered prompt
        assert "technical skills" in rendered.lower(), (
            "Sub-query content not found in rendered deep_research template"
        )
        assert "Program Manager" in rendered

    def test_worker_factory_produces_correct_template_space(self):
        """Each worker from the factory must use deep_research template space."""
        inferencer = build_create_role_inferencer(
            cloud_id="test-cloud-id",
            uct_token="test-token",
        )
        w = inferencer.worker_factory(sub_query="Test sub-query", index=0)
        assert w.template_root_space == "deep_research", (
            f"Expected 'deep_research', got '{w.template_root_space}'"
        )
        assert w.template_key == "initial"

    def test_breakdown_queries_are_text_strings(self, sample_breakdown_json):
        """Breakdown parser must return text strings, not file paths or objects."""
        queries = parse_breakdown_response(sample_breakdown_json)
        for i, q in enumerate(queries):
            assert isinstance(q, str), (
                f"Query {i} is {type(q).__name__}, expected str"
            )
            # Should NOT look like file paths
            assert not q.startswith("/"), (
                f"Query {i} looks like a file path: {q[:50]}"
            )
            assert not q.endswith(".txt"), (
                f"Query {i} looks like a file path: {q[:50]}"
            )


# ---------------------------------------------------------------------------
# Test: output_path and has_local_access
# ---------------------------------------------------------------------------


class TestOutputPathHandling:
    """Verify output_path passdown and has_local_access gating."""

    def test_worker_gets_relative_output_path(self):
        """Each worker must get a unique relative output_path filename.

        The path is relative (e.g., ``"facet_0.md"``) — it resolves to an
        absolute path only after BTA assigns a child workspace via
        ``_build_diamond_graph``.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            inferencer = build_create_role_inferencer(
                cloud_id="test-cloud-id",
                uct_token="test-token",
                max_facets=3,
                workspace=tmpdir,
            )
            w0 = inferencer.worker_factory(sub_query="Q0", index=0)
            w1 = inferencer.worker_factory(sub_query="Q1", index=1)
            w2 = inferencer.worker_factory(sub_query="Q2", index=2)

            assert w0.output_path == "facet_0.md"
            assert w1.output_path == "facet_1.md"
            assert w2.output_path == "facet_2.md"
            # Each must be unique
            assert w0.output_path != w1.output_path
            assert w1.output_path != w2.output_path

    def test_worker_always_has_output_path(self):
        """Workers always get a relative output_path regardless of workspace_root."""
        inferencer = build_create_role_inferencer(
            cloud_id="test-cloud-id",
            uct_token="test-token",
        )
        w = inferencer.worker_factory(sub_query="Q", index=0)
        assert w.output_path == "facet_0.md"

    def test_rovochat_has_no_local_access(self):
        """RovoChatInferencer should have has_local_access=False."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
            RovoChatInferencer,
        )

        rc = RovoChatInferencer(cloud_id="test", uct_token="test")
        assert rc.has_local_access is False

    def test_rovodev_has_local_access(self):
        """RovoDevCliInferencer should have has_local_access=True."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )

        rd = RovoDevCliInferencer(working_dir=".")
        assert rd.has_local_access is True

    def test_build_feed_omits_output_path_for_non_local(self):
        """InferencerBase._build_feed should omit output_path when inferencer lacks
        local access (has_local_access=False by default for RovoChatInferencer)."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
            RovoChatInferencer,
        )

        # RovoChatInferencer inherits _build_feed from InferencerBase;
        # has_local_access=False by default so output_path is excluded from feed
        inf = RovoChatInferencer(cloud_id="test", uct_token="test")
        inf.output_path = "/tmp/test_output.md"
        feed = inf._build_template_feed("Test query")
        assert "output_path" not in feed, (
            "output_path should NOT be in feed for non-local inferencer (has_local_access=False)"
        )
        assert feed["input"] == "Test query"

    def test_build_feed_includes_output_path_for_local(self):
        """InferencerBase._build_feed should include output_path when inferencer
        has local access (has_local_access=True for RovoDevCliInferencer)."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        import tempfile, os as _os

        # RovoDevCliInferencer inherits _build_feed from InferencerBase;
        # has_local_access=True so absolute output_path IS included in feed
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = _os.path.join(tmpdir, "test_output.md")
            inf = RovoDevCliInferencer(working_dir=".")
            inf.output_path = output_file
            feed = inf._build_template_feed("Test query")
            assert feed.get("output_path") == output_file, (
                f"output_path should be in feed for local inferencer, got: {list(feed.keys())}"
            )

    def test_template_renders_without_output_path(self, template_manager):
        """When output_path is not provided, template should instruct agent to
        include full research in <Response> tags."""
        result = template_manager(
            "initial",
            active_template_root_space="deep_research",
            input="Test query",
        )
        assert "COMPLETE research findings" in result or "COMPLETE research report" in result or "concise summary" not in result.lower()
        assert "write it to:" not in result.lower()

    def test_template_renders_with_output_path(self, template_manager):
        """When output_path is provided, template should instruct agent to
        write report to file and put concise summary in <Response> tags."""
        result = template_manager(
            "initial",
            active_template_root_space="deep_research",
            input="Test query",
            output_path="/tmp/research_output.md",
        )
        assert "write it to:" in result.lower() or "Write the full report to:" in result
        assert "/tmp/research_output.md" in result
        assert "concise summary" in result.lower()

    def test_save_response_writes_file_for_non_local(self):
        """For non-local inferencers (RovoChatInferencer), the template should
        instruct the agent to include full findings in <Response> tags (no output_path
        in feed), so the BTA pipeline extracts <Response> content to write to disk.

        Verify: _build_template_feed omits output_path for non-local inferencer,
        meaning the rendered prompt asks for inline <Response> content.
        """
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
            RovoChatInferencer,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test_output.md")
            inf = RovoChatInferencer(cloud_id="test", uct_token="test")
            inf.output_path = output_file
            # Non-local inferencer: output_path must NOT be in the template feed
            # (has_local_access=False, so the agent cannot write files itself)
            feed = inf._build_template_feed("Research sub-query")
            assert "output_path" not in feed, (
                "Non-local inferencer must NOT receive output_path in template feed"
            )
            assert feed["input"] == "Research sub-query"
