# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Tests for SOPManager — parsing and guidance rendering.
Evaluation tests use StateGraphTracker from stategraph.py."""

import unittest

from python_utils.common_objects.workflow.stategraph import (
    StateGraphTracker,
)
from python_utils.string_utils.formatting.template_manager.sop_manager import (
    SOP,
    SOPManager,
    SOPPhase,
    SOPSubsection,
)

SAMPLE_SOP_MD = """\
## Phase 0 [initial]: Setup `target_path` and `strategy`

User specifies the target code path and strategy.

**Tools** [__must__]:
- /set-target-path <path>
- /set-strategy <name>

**Rules** [__must__]:
- If path points to a file, suggest parent directory
- Always present commands in code blocks

## Phase 1 [__depends on__ Phase 0]: Codebase Investigation `codebase_understanding`

Analyze the target codebase at `{target_path}`.

**Tools** [__prioritize__]:
- /understand-codebase <path>

## Phase 2 [__depends on__ Phase 1]: Research & Proposal `research_proposals`

Break down the research goal into sub-queries.

**Tools**:
- /research-propose <goal>

## Phase 3 [__depends on__ Phase 2; __for each__ `proposal` __in__ `research_proposals`]: Implementation `experiment_result`

Implement and test the proposed changes.

## Phase 4 [__depends on__ Phase 3; __go to__ Phase 2 __if__ `continue`]: Evaluate and decide to `continue`

Summarize results and decide whether to continue.

## Phase 2a [__depends on__ Phase 0; __if__ `strategy` __is__ `efficiency`]: Efficiency Analysis `efficiency_report`

Run efficiency-focused analysis.
"""

SAMPLE_SOP_YAML = {
    "phases": [
        {
            "id": "0", "name": "Setup", "directives": ["initial"],
            "outputs": ["target_path", "strategy"],
            "description": "User specifies the target code path.",
            "subsections": [{"name": "Tools", "directive": "must", "content": "- /set-target-path"}],
        },
        {
            "id": "1", "name": "Codebase Investigation",
            "depends_on": ["0"], "outputs": ["codebase_understanding"],
            "description": "Analyze the target codebase.",
        },
    ],
}


class TestMarkdownParser(unittest.TestCase):

    def setUp(self):
        self.sop = SOPManager.parse_markdown(SAMPLE_SOP_MD)

    def test_phase_count(self):
        self.assertEqual(len(self.sop.phases), 6)

    def test_phase_ids(self):
        self.assertEqual(self.sop.phase_ids, ["0", "1", "2", "3", "4", "2a"])

    def test_phase_0_outputs(self):
        p = self.sop.get_phase("0")
        self.assertEqual(p.outputs, ["target_path", "strategy"])

    def test_phase_0_initial(self):
        p = self.sop.get_phase("0")
        self.assertIn("initial", p.directives)

    def test_depends_on(self):
        self.assertEqual(self.sop.get_phase("1").depends_on, ["0"])

    def test_for_each(self):
        p = self.sop.get_phase("3")
        self.assertEqual(p.foreach_item_var, "proposal")
        self.assertEqual(p.foreach_collection_var, "research_proposals")

    def test_goto(self):
        p = self.sop.get_phase("4")
        self.assertEqual(p.goto_target, "2")
        self.assertEqual(p.goto_condition_var, "continue")

    def test_if_is_gate(self):
        p = self.sop.get_phase("2a")
        self.assertEqual(p.gate_var, "strategy")
        self.assertEqual(p.gate_value, "efficiency")

    def test_subsections(self):
        p = self.sop.get_phase("0")
        self.assertEqual(len(p.subsections), 2)
        self.assertEqual(p.subsections[0].name, "Tools")
        self.assertEqual(p.subsections[0].directive, "must")

    def test_description_before_subsections(self):
        p = self.sop.get_phase("0")
        self.assertIn("User specifies", p.description)
        self.assertNotIn("Tools", p.description)

    def test_node_links(self):
        """StateGraph should have linked Node.next from depends_on."""
        phase0 = self.sop.get_phase("0")
        next_ids = [n.id for n in (phase0.get_next() or [])]
        self.assertIn("1", next_ids)


class TestYAMLParser(unittest.TestCase):

    def test_phase_count(self):
        sop = SOPManager.parse_yaml(SAMPLE_SOP_YAML)
        self.assertEqual(len(sop.phases), 2)

    def test_subsections(self):
        sop = SOPManager.parse_yaml(SAMPLE_SOP_YAML)
        self.assertEqual(sop.get_phase("0").subsections[0].directive, "must")


class TestEvaluationViaTracker(unittest.TestCase):
    """Evaluation tests use StateGraphTracker instead of SOPManager.evaluate()."""

    def setUp(self):
        self.sop = SOPManager.parse_markdown(SAMPLE_SOP_MD)

    def _tracker(self, **kwargs):
        return StateGraphTracker(graph=self.sop, **kwargs)

    def test_idle_shows_phase_0(self):
        t = self._tracker()
        self.assertIn("0", [n.id for n in t.get_available_next()])

    def test_phase_incomplete_without_outputs(self):
        t = self._tracker(completed_states=["0"])
        self.assertNotIn("1", [n.id for n in t.get_available_next()])
        self.assertIn("0", t.get_missing_outputs())

    def test_phase_complete_with_outputs(self):
        t = self._tracker(completed_states=["0"],
                          state_outputs={"target_path": "/fbcode", "strategy": "default"})
        ids = [n.id for n in t.get_available_next()]
        self.assertIn("1", ids)
        self.assertNotIn("0", ids)

    def test_gate_allows(self):
        t = self._tracker(completed_states=["0"],
                          state_outputs={"target_path": "/fbcode", "strategy": "efficiency"})
        self.assertIn("2a", [n.id for n in t.get_available_next()])

    def test_gate_blocks(self):
        t = self._tracker(completed_states=["0"],
                          state_outputs={"target_path": "/fbcode", "strategy": "exploratory"})
        self.assertNotIn("2a", [n.id for n in t.get_available_next()])

    def test_foreach_needs_collection(self):
        t = self._tracker(
            completed_states=["0", "1", "2"],
            state_outputs={"target_path": "/fbcode", "strategy": "default", "codebase_understanding": "done"},
        )
        self.assertNotIn("3", [n.id for n in t.get_available_next()])

    def test_foreach_with_collection(self):
        t = self._tracker(
            completed_states=["0", "1", "2"],
            state_outputs={
                "target_path": "/fbcode", "strategy": "default",
                "codebase_understanding": "done", "research_proposals": ["a", "b"],
            },
        )
        self.assertIn("3", [n.id for n in t.get_available_next()])

    def test_goto_reenables(self):
        t = self._tracker(
            completed_states=["0", "1", "2", "3", "4"],
            state_outputs={
                "target_path": "/fbcode", "strategy": "default",
                "codebase_understanding": "done", "research_proposals": ["a"],
                "experiment_result": "done", "continue": True,
            },
        )
        self.assertIn("2", [n.id for n in t.get_available_next()])

    def test_goto_blocked_when_false(self):
        t = self._tracker(
            completed_states=["0", "1", "2", "3", "4"],
            state_outputs={
                "target_path": "/fbcode", "strategy": "default",
                "codebase_understanding": "done", "research_proposals": ["a"],
                "experiment_result": "done", "continue": False,
            },
        )
        self.assertNotIn("2", [n.id for n in t.get_available_next()])

    def test_running_status(self):
        t = self._tracker(completed_states=["0"],
                          state_outputs={"target_path": "/fbcode", "strategy": "default"})
        t.start("1")
        self.assertEqual(t.status, "running")

    def test_error_status(self):
        t = self._tracker(completed_states=["0", "1"],
                          state_outputs={"target_path": "/fbcode", "strategy": "default",
                                         "codebase_understanding": "done"})
        t.start("2")
        t.fail("2", "some error")
        self.assertEqual(t.status, "error")


class TestGuidanceRenderer(unittest.TestCase):

    def setUp(self):
        self.sop = SOPManager.parse_markdown(SAMPLE_SOP_MD)
        self.config = {
            "subsections": {
                "Tools": {"directives": {"__must__": "You MUST use the following tools:"}},
            }
        }

    def test_idle_guidance(self):
        t = StateGraphTracker(graph=self.sop)
        text = SOPManager.render_guidance(t, self.sop)
        self.assertIn("### Nextstep Guidance:", text)
        self.assertIn("Setup", text)

    def test_running_guidance(self):
        t = StateGraphTracker(graph=self.sop, completed_states=["0"],
                              state_outputs={"target_path": "/fbcode", "strategy": "default"})
        t.start("1")
        text = SOPManager.render_guidance(t, self.sop)
        self.assertIn("In progress", text)

    def test_missing_outputs_guidance(self):
        t = StateGraphTracker(graph=self.sop, completed_states=["0"])
        text = SOPManager.render_guidance(t, self.sop)
        self.assertIn("incomplete", text)
        self.assertIn("`target_path`", text)

    def test_directive_injection(self):
        t = StateGraphTracker(graph=self.sop)
        text = SOPManager.render_guidance(t, self.sop, sop_config=self.config)
        self.assertIn("You MUST use the following tools:", text)

    def test_no_config_renders_content(self):
        t = StateGraphTracker(graph=self.sop)
        text = SOPManager.render_guidance(t, self.sop)
        self.assertIn("/set-target-path", text)


class TestForEachSequential(unittest.TestCase):

    def test_sequential_flag(self):
        md = "## Phase 0 [initial]: Start `items`\nStart.\n## Phase 1 [__depends on__ Phase 0; __for each__ `item` __in__ `items` __sequentially__]: Process\nWork.\n"
        sop = SOPManager.parse_markdown(md)
        p = sop.get_phase("1")
        self.assertTrue(p.foreach_sequential)
        self.assertEqual(p.foreach_item_var, "item")
        self.assertEqual(p.foreach_collection_var, "items")


class TestDashNameHeadingFormat(unittest.TestCase):
    """Test headings with '-- Name' between phase ID and directives."""

    SAMPLE_WITH_NAMES = """\
## Phase 0 -- Setup [initial]: `target_path` and `strategy`

User specifies the target code path and strategy.

**Tools** [__must__]:
- /set-target-path <path>

## Phase 1 -- Codebase Investigation [__depends on__ Phase 0; __requires confirmation__]: `codebase_understanding`

Analyze the target codebase.

## Phase 2 -- Research & Proposal [__depends on__ Phase 1]: `research_proposals`

Break down the research goal.
"""

    def setUp(self):
        self.sop = SOPManager.parse_markdown(self.SAMPLE_WITH_NAMES)

    def test_phase_count(self):
        self.assertEqual(len(self.sop.phases), 3)

    def test_phase_ids(self):
        self.assertEqual(self.sop.phase_ids, ["0", "1", "2"])

    def test_phase_names_from_heading(self):
        self.assertEqual(self.sop.get_phase("0").name, "Setup")
        self.assertEqual(self.sop.get_phase("1").name, "Codebase Investigation")
        self.assertEqual(self.sop.get_phase("2").name, "Research & Proposal")

    def test_outputs(self):
        self.assertEqual(self.sop.get_phase("0").outputs, ["target_path", "strategy"])
        self.assertEqual(self.sop.get_phase("1").outputs, ["codebase_understanding"])

    def test_depends_on(self):
        self.assertEqual(self.sop.get_phase("1").depends_on, ["0"])

    def test_idle_guidance_shows_phase_details(self):
        t = StateGraphTracker(graph=self.sop)
        text = SOPManager.render_guidance(t, self.sop)
        self.assertIn("Setup", text)
        self.assertNotIn("Begin with the first available phase", text)


if __name__ == "__main__":
    unittest.main()
