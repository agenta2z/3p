# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Tests for :mod:`rankevolve.src.server.experiment_bridge`.

Focuses on the deterministic plumbing: argv parsing, combo resolution,
workspace layout, and the summary/plan files written before the BTA
runs. The BTA execution itself is mocked — real subprocess spawning of
``rankevolve_train`` / ``rankevolve_monitor`` is covered by the Phase-1
integration test (``test_train_cli_e2e``) and by chat-driven smoke tests
(documented in plan §2.5).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rankevolve.src.server.experiment_bridge import (
    Combo,
    ExperimentBridge,
    parse_combos_arg,
    parse_experiment_options,
    parse_hypothesis_ids,
)


class ParseHypothesisIdsTest(unittest.TestCase):
    def test_extracts_h_headings(self) -> None:
        # CommonMark headings are start-of-line; we deliberately do NOT
        # match indented `#` (preserves the common case where prose
        # mentions an "## H42" inside a code fence as documentation).
        text = (
            "# H1: increase sequence length\n"
            "\n"
            "## H17 — input compression\n"
            "\n"
            "Some prose about H42 (NOT a heading; should be ignored).\n"
            "\n"
            "### H4_BROKEN\n"
        )
        self.assertEqual(parse_hypothesis_ids(text), ["H1", "H17", "H4_BROKEN"])

    def test_dedupes_repeats(self) -> None:
        text = "# H1\n## H1\n### H1_VARIANT\n"
        self.assertEqual(parse_hypothesis_ids(text), ["H1", "H1_VARIANT"])

    def test_no_hypotheses(self) -> None:
        self.assertEqual(parse_hypothesis_ids("just prose, no headings"), [])

    def test_empty(self) -> None:
        self.assertEqual(parse_hypothesis_ids(""), [])


class ParseCombosArgTest(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(
            parse_combos_arg("H1;H17,H8;H56_BASELINE"),
            [["H1"], ["H17", "H8"], ["H56_BASELINE"]],
        )

    def test_whitespace_tolerated(self) -> None:
        self.assertEqual(
            parse_combos_arg(" H1 ; H17 , H8 "),
            [["H1"], ["H17", "H8"]],
        )

    def test_empty(self) -> None:
        self.assertEqual(parse_combos_arg(""), [])

    def test_ignores_empty_segments(self) -> None:
        self.assertEqual(parse_combos_arg("H1;;H2;"), [["H1"], ["H2"]])


class ParseExperimentOptionsTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        request, opts = parse_experiment_options(
            "do the thing --plan /tmp/p.md --select H1,H2 "
            "--combos H1;H1,H2 --max-concurrency 4 --rounds 2"
        )
        self.assertEqual(request, "do the thing")
        self.assertEqual(opts["plan"], "/tmp/p.md")
        self.assertEqual(opts["select"], "H1,H2")
        self.assertEqual(opts["combos"], "H1;H1,H2")
        self.assertEqual(opts["max_concurrency"], "4")
        self.assertEqual(opts["rounds"], "2")

    def test_boolean_flags(self) -> None:
        _, opts = parse_experiment_options(
            "--workspace-keep-only-final --implement-default"
        )
        self.assertTrue(opts["workspace_keep_only_final"])
        self.assertTrue(opts["implement_default"])


class ResolveCombosTest(unittest.TestCase):
    def _bridge(self, **kwargs: Any) -> ExperimentBridge:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_test_"))
        return ExperimentBridge(session_tasks_dir=tmp, **kwargs)

    def test_explicit_combos_win(self) -> None:
        b = self._bridge(
            plan_text="# H1\n# H17",
            selected_ids=["H42"],
            combos=[["H8"], ["H1", "H17"]],
        )
        combos = b.resolve_combos()
        self.assertEqual([(c.combo_id, c.items) for c in combos], [
            ("H8", ["H8"]),
            ("H1_H17", ["H1", "H17"]),
        ])

    def test_selected_ids_used_when_no_explicit(self) -> None:
        b = self._bridge(
            plan_text="# H1\n# H17",
            selected_ids=["H1", "H17"],
            combos=[],
        )
        combos = b.resolve_combos()
        self.assertEqual([c.items for c in combos], [["H1"], ["H17"]])

    def test_plan_text_fallback(self) -> None:
        b = self._bridge(
            plan_text="# H1: foo\n## H17: bar\n### H4_BROKEN: baz",
            selected_ids=[],
            combos=[],
        )
        combos = b.resolve_combos()
        self.assertEqual([c.items for c in combos], [["H1"], ["H17"], ["H4_BROKEN"]])

    def test_empty_input_returns_empty(self) -> None:
        b = self._bridge(plan_text="no hypotheses here", selected_ids=[], combos=[])
        self.assertEqual(b.resolve_combos(), [])


class WorkspaceLayoutTest(unittest.TestCase):
    def test_workspace_subdirs_created(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_ws_"))
        b = ExperimentBridge(session_tasks_dir=tmp, plan_text="# H1")
        ws = b.workspace
        self.assertTrue(ws.is_dir())
        self.assertTrue(str(ws.name).startswith("exp_"))
        for sub in ("outputs", "results", "logs", "combos"):
            self.assertTrue((ws / sub).is_dir(), f"{sub} not created")
        self.assertTrue((ws / "_runtime" / "inferencer_cache").is_dir())

    def test_workspace_path_override(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_ws_"))
        custom = tmp / "custom_loc"
        b = ExperimentBridge(
            session_tasks_dir=tmp, plan_text="# H1", workspace_path=custom
        )
        self.assertEqual(b.workspace, custom)
        self.assertTrue(custom.is_dir())


class RunWritesArtifactsTest(unittest.IsolatedAsyncioTestCase):
    """End-to-end of the deterministic plumbing — BTA execution mocked to
    no-op so we can validate workspace writes without spawning subprocesses
    or making LLM calls."""

    async def test_run_writes_plan_and_summary(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_run_"))
        b = ExperimentBridge(
            session_tasks_dir=tmp,
            plan_text="# H1\n# H17",
            combos=[["H1"], ["H17", "H8"]],
        )
        # Patch the BTA construction to a no-op so .ainfer succeeds without
        # invoking the inner workers or spawning subprocesses.
        with patch.object(b, "_build_outer_bta") as mock_build:
            mock_bta = mock_build.return_value
            async def _noop_ainfer(*args: Any, **kwargs: Any) -> str:
                return "ok"
            mock_bta.ainfer = _noop_ainfer
            summary = await b.run("test request")

        # Plan file has both combos.
        plan_path = b.workspace / "results" / "combo_plan.json"
        self.assertTrue(plan_path.is_file())
        plan = json.loads(plan_path.read_text())
        self.assertEqual(len(plan["combos"]), 2)
        self.assertEqual(plan["combos"][0]["combo_id"], "H1")
        self.assertEqual(plan["combos"][1]["combo_id"], "H17_H8")

        # Summary file has status=completed.
        summary_path = b.workspace / "results" / "experiment_summary.json"
        self.assertTrue(summary_path.is_file())
        summary_doc = json.loads(summary_path.read_text())
        self.assertEqual(summary_doc["status"], "completed")
        self.assertEqual(len(summary_doc["combos"]), 2)

        # Human-readable summary text mentions both combos.
        self.assertIn("/experiment completed", summary)
        self.assertIn("H1", summary)
        self.assertIn("H17_H8", summary)

        # Pre-cached breakdown_result.json so BTA can resume without an
        # LLM call (matches the deterministic-breakdown invariant).
        breakdown_cache = b.workspace / "checkpoints" / "bta" / "breakdown_result.json"
        self.assertTrue(breakdown_cache.is_file())

    async def test_run_with_no_combos_returns_actionable_error(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_empty_"))
        b = ExperimentBridge(
            session_tasks_dir=tmp,
            plan_text="just prose, no headings",
            selected_ids=[],
            combos=[],
        )
        result = await b.run("")
        self.assertIn("no combos resolved", result)
        # Did NOT write a summary file (we bailed before run).
        self.assertFalse((b.workspace / "results" / "experiment_summary.json").is_file())


class AggregatorWiringTest(unittest.TestCase):
    """Phase 3 — verify the inner aggregator BTA is wired only when
    enable_aggregator=True (default off so Phase 2 deployments don't
    accidentally trigger Phase 3 LLM cost).

    The BTA's ``__attrs_post_init__`` reads ``_workspace`` on each child
    inferencer to propagate workspace context, so mocks must duck-type
    that attribute.
    """

    @staticmethod
    def _patched_dual_factory():  # noqa: ANN202
        from unittest.mock import MagicMock
        # MagicMock auto-vivifies any attribute access, so `_workspace`
        # access during BTA's post_init is harmless. Returns a fresh
        # mock per call so the call_count assertion stays accurate.
        return MagicMock(_workspace=None, _for_each_child_inferencer=lambda *a, **k: ())

    def test_aggregator_disabled_by_default(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_agg_"))
        b = ExperimentBridge(session_tasks_dir=tmp, plan_text="# H1")
        with patch(
            "rankevolve.src.server.experiment_bridge.ExperimentBridge._build_dual",
            side_effect=lambda *args, **kwargs: self._patched_dual_factory(),
        ) as mock_dual:
            outer = b._build_outer_bta()
            self.assertEqual(mock_dual.call_count, 0)
        self.assertIsNone(outer.aggregator_inferencer)

    def test_aggregator_enabled_constructs_inner_bta(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_agg_on_"))
        b = ExperimentBridge(
            session_tasks_dir=tmp, plan_text="# H1", enable_aggregator=True
        )
        with patch(
            "rankevolve.src.server.experiment_bridge.ExperimentBridge._build_dual",
            side_effect=lambda *args, **kwargs: self._patched_dual_factory(),
        ) as mock_dual:
            outer = b._build_outer_bta()
            # Inner BTA constructs 2 DualInferencers (breakdown + final).
            # Workers are factory-built lazily — not at construction time.
            self.assertEqual(mock_dual.call_count, 2)
        self.assertIsNotNone(outer.aggregator_inferencer)


class MultiRoundLwiTest(unittest.TestCase):
    """Phase 4 — verify the rounds knob wraps the BTA in a one-step LWI
    when rounds > 1, and no-ops when rounds == 1."""

    def test_single_round_returns_bta_unchanged(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_round_"))
        b = ExperimentBridge(session_tasks_dir=tmp, plan_text="# H1", rounds=1)
        sentinel = object()
        # _wrap_in_outer_lwi returns the BTA verbatim when rounds=1.
        result = b._wrap_in_outer_lwi(sentinel)  # type: ignore[arg-type]
        self.assertIs(result, sentinel)

    def test_multi_round_wraps_in_lwi(self) -> None:
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.linear_workflow_inferencer import (
            LinearWorkflowInferencer,
        )
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_round_n_"))
        b = ExperimentBridge(session_tasks_dir=tmp, plan_text="# H1", rounds=3)
        bta = b._build_outer_bta()  # aggregator off → no LLM construction
        wrapped = b._wrap_in_outer_lwi(bta)
        self.assertIsInstance(wrapped, LinearWorkflowInferencer)
        # Single step that loops back to itself with max_loop_iterations
        # = rounds - 1 (so total rounds == rounds).
        self.assertEqual(len(wrapped.step_configs), 1)
        cfg = wrapped.step_configs[0]
        self.assertEqual(cfg.name, "outer_round")
        self.assertEqual(cfg.loop_back_to, "outer_round")
        self.assertEqual(cfg.max_loop_iterations, 2)  # 3 - 1

    def test_loop_condition_reads_recommendations_file(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_loop_cond_"))
        b = ExperimentBridge(session_tasks_dir=tmp, plan_text="# H1", rounds=2)
        bta = b._build_outer_bta()
        wrapped = b._wrap_in_outer_lwi(bta)
        # `loop_condition` reads next_round_recommendations.json from the
        # round_<n+1> workspace; absence ⇒ stop.
        cond = wrapped.step_configs[0].loop_condition
        assert cond is not None  # pyre narrowing
        self.assertFalse(cond({"iteration": 0}, None))
        # Write a recommendations file with promoted_combos → continue.
        recs_dir = b.workspace / "round_1" / "results"
        recs_dir.mkdir(parents=True, exist_ok=True)
        (recs_dir / "next_round_recommendations.json").write_text(
            json.dumps({"promoted_combos": [{"items": ["H1"]}]}),
            encoding="utf-8",
        )
        self.assertTrue(cond({"iteration": 0}, None))
        # Empty promoted_combos → stop.
        (recs_dir / "next_round_recommendations.json").write_text(
            json.dumps({"promoted_combos": []}), encoding="utf-8"
        )
        self.assertFalse(cond({"iteration": 0}, None))


class ComboTest(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        c = Combo(combo_id="H1_H17", items=["H1", "H17"], config_name="L=400 + compression")
        d = c.to_dict()
        self.assertEqual(d["combo_id"], "H1_H17")
        self.assertEqual(d["items"], ["H1", "H17"])
        self.assertEqual(d["config_name"], "L=400 + compression")

    def test_default_config_name_from_items(self) -> None:
        c = Combo(combo_id="x", items=["H1", "H17"])
        self.assertEqual(c.config_name, "H1_H17")
