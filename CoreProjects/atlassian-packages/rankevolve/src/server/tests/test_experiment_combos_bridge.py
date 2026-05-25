# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Unit tests for ExperimentCombosBridge re-export + pre-flight check."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import asyncio
import shutil
from unittest.mock import MagicMock

from rankevolve.src.server.experiment_bridge import ExperimentBridge
from rankevolve.src.server.experiment_combos_bridge import (
    ExperimentCombosBridge,
    _build_aggregate_only_prompt_builder,
    _flatten_inputs_for_capture,
    aggregate_only_run,
    collect_aggregator_input_from_disk,
    collect_aggregator_input_from_submissions,
    find_latest_experiment_workspace,
    parse_combos_arg,
    preflight_check_flags,
    resolve_active_multi_task_id,
)


class ReexportTest(unittest.TestCase):
    def test_alias_is_experiment_bridge(self) -> None:
        self.assertIs(ExperimentCombosBridge, ExperimentBridge)

    def test_parse_combos_reexport(self) -> None:
        self.assertEqual(
            parse_combos_arg("H1;H17,H8"),
            [["H1"], ["H17", "H8"]],
        )


class PreflightCheckFlagsTest(unittest.TestCase):
    def test_empty_combos_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(preflight_check_flags([], Path(td)), {})

    def test_missing_root_returns_empty(self) -> None:
        self.assertEqual(
            preflight_check_flags([["H1"]], Path("/nonexistent/path/x")),
            {},
        )

    def test_all_flags_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.py").write_text(
                "enable_h1: bool = False\nenable_h17: bool = False\n",
                encoding="utf-8",
            )
            blocked = preflight_check_flags(
                [["H1"], ["H17"]], root
            )
            self.assertEqual(blocked, {})

    def test_missing_flags_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.py").write_text(
                "enable_h1: bool = False\n", encoding="utf-8"
            )
            blocked = preflight_check_flags(
                [["H1", "H99"], ["H1"]], root
            )
            self.assertIn("H1,H99", blocked)
            self.assertEqual(blocked["H1,H99"], ["enable_h99"])
            self.assertNotIn("H1", blocked)

    def test_case_insensitive_flag_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "model.py").write_text(
                "enable_my_feature_v2: bool = False\n", encoding="utf-8"
            )
            blocked = preflight_check_flags([["MY_FEATURE_V2"]], root)
            self.assertEqual(blocked, {})

    def test_only_scans_known_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.bin").write_text(
                "enable_h1: bool = False\n", encoding="utf-8"
            )
            blocked = preflight_check_flags([["H1"]], root)
            self.assertIn("H1", blocked)


class AggregateOnlyPromptBuilderTest(unittest.TestCase):
    """Verifies the Gap-1 fix: when precompute_envelope is supplied,
    the prompt prepends a clearly-labeled section the LLM can fill from."""

    def test_no_envelope_just_per_combo_sections(self) -> None:
        builder = _build_aggregate_only_prompt_builder(precompute_envelope=None)
        out = builder(
            ["combo_h1 body", "combo_h17_h8 body"],
            worker_output_paths=[
                "/abs/combos/combo_h1/analysis/combo_h1.md",
                "/abs/combos/combo_h17_h8/analysis/combo_h17_h8.md",
            ],
        )
        self.assertNotIn("Deterministic learnings_actions precompute envelope", out)
        self.assertIn("### Per-combo analysis 1", out)
        self.assertIn("### Per-combo analysis 2", out)
        self.assertIn("combo_h1 body", out)
        self.assertIn("combo_h17_h8 body", out)
        self.assertIn("/abs/combos/combo_h1/analysis/combo_h1.md", out)

    def test_envelope_prepended_with_explanation(self) -> None:
        envelope = {
            "hypothesisRerank": [
                {
                    "id": "H17", "oldRank": 5, "newRank": 2, "deltaRank": -3,
                    "rationale": "", "evidenceSubmissions": [], "confidence": "high",
                }
            ],
            "newCombos": [
                {
                    "comboId": "REC-1", "title": "", "rationale": "", "risk": "",
                    "selectedItems": ["H17", "H8"], "comboKey": "H17,H8",
                    "expectedNdcg10Lift": 2.5, "confidence": "medium-high",
                    "estimatedComputeHours": 12,
                    "configStatus": "needs_generation",
                    "configPathProposed": "hstu-h17-h8.gin (NEW)",
                    "preconditions": [], "constraintCheck": "PASSED",
                }
            ],
            "openQuestions": [],
        }
        builder = _build_aggregate_only_prompt_builder(precompute_envelope=envelope)
        out = builder(
            ["combo_h17 body"],
            worker_output_paths=["/abs/combos/combo_h17/analysis/combo_h17.md"],
        )
        # Precompute section appears BEFORE per-combo sections.
        envelope_pos = out.find("Deterministic learnings_actions precompute envelope")
        per_combo_pos = out.find("### Per-combo analysis 1")
        self.assertGreaterEqual(envelope_pos, 0)
        self.assertGreater(per_combo_pos, envelope_pos)
        # The deterministic structural fields are embedded as JSON.
        self.assertIn('"id": "H17"', out)
        self.assertIn('"comboId": "REC-1"', out)
        self.assertIn('"selectedItems"', out)
        # Explanation tells the LLM which fields to fill.
        self.assertIn("rationale", out)
        self.assertIn("Pass-through fields", out)
        # Per-combo body still present.
        self.assertIn("combo_h17 body", out)


class FlattenInputsForCaptureTest(unittest.TestCase):
    """The pure helper used to mirror BTA._build_aggregator_only_input's
    path-dict flattening so the bridge can capture the exact prompt."""

    def test_path_dict_flattens_to_summary_plus_path(self) -> None:
        flattened, paths = _flatten_inputs_for_capture([
            {"path": "/abs/x.md", "summary": "x body"},
            {"path": "/abs/y.md", "summary": ""},
            {"path": "/abs/z.md"},
        ])
        self.assertEqual(flattened, ["x body", "/abs/y.md", "/abs/z.md"])
        self.assertEqual(paths, ["/abs/x.md", "/abs/y.md", "/abs/z.md"])

    def test_plain_string_passes_through(self) -> None:
        flattened, paths = _flatten_inputs_for_capture(["just text"])
        self.assertEqual(flattened, ["just text"])
        self.assertEqual(paths, [None])


class AggregateOnlyRunWorkspaceCaptureTest(unittest.TestCase):
    """Verifies that when task_workspace is supplied, aggregate_only_run
    writes llm_input.md (the prompt) and llm_response.md (the LLM body)
    into it. When not supplied, no capture happens (existing behavior)."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        # Lay out a fake experiment workspace with one combo analysis.
        self.exp_workspace = self.tmpdir / "exp"
        analysis = self.exp_workspace / "combos" / "combo_h1" / "analysis"
        analysis.mkdir(parents=True)
        (analysis / "combo_h1.md").write_text(
            "# combo_h1 analysis\n\nNDCG@10 = 0.1872\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_aggregator(self, response_text: str = "MOCKED LLM RESPONSE"):
        """A mock aggregator inferencer that returns a constant response.
        Plain class (not MagicMock) so the `ainfer` coroutine is treated
        as a coroutine, not as a wrapped attribute. Mirrors the bits of
        the DualInferencer interface aggregate_only_run / BTA expects.
        """
        class _MockAgg:
            has_local_access = False  # production devmate default

            def __init__(self) -> None:
                self.last_prompt: str | None = None

            async def ainfer(self, prompt, inference_config=None, **kw):
                self.last_prompt = prompt
                return response_text

        return _MockAgg()

    def test_workspace_capture_writes_input_and_response(self) -> None:
        task_workspace = self.tmpdir / "task_agg_x"
        agg = self._make_aggregator(response_text="LLM SAID HELLO")
        result = asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            task_workspace=task_workspace,
        ))
        self.assertEqual(result, "LLM SAID HELLO")
        # llm_input.md captured the prompt — should include the per-combo body.
        input_md = (task_workspace / "llm_input.md").read_text()
        self.assertIn("Per-combo analysis 1", input_md)
        self.assertIn("combo_h1 analysis", input_md)
        # llm_response.md captured the LLM body verbatim.
        response_md = (task_workspace / "llm_response.md").read_text()
        self.assertEqual(response_md, "LLM SAID HELLO")

    def test_workspace_capture_includes_precompute_envelope(self) -> None:
        task_workspace = self.tmpdir / "task_agg_y"
        envelope = {
            "hypothesisRerank": [{"id": "H17", "rationale": ""}],
            "newCombos": [],
            "openQuestions": [],
        }
        agg = self._make_aggregator()
        asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            precompute_envelope=envelope,
            task_workspace=task_workspace,
        ))
        input_md = (task_workspace / "llm_input.md").read_text()
        self.assertIn("Deterministic learnings_actions precompute envelope", input_md)
        self.assertIn('"id": "H17"', input_md)
        # Envelope appears BEFORE per-combo section (same ordering as the prompt).
        env_pos = input_md.find("Deterministic learnings_actions precompute envelope")
        per_pos = input_md.find("### Per-combo analysis 1")
        self.assertGreater(per_pos, env_pos)

    def test_no_workspace_skips_capture(self) -> None:
        """Existing callers that don't supply task_workspace still work;
        no llm_input.md / llm_response.md is written anywhere."""
        agg = self._make_aggregator()
        result = asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            # task_workspace omitted
        ))
        self.assertEqual(result, "MOCKED LLM RESPONSE")
        # No artifacts in tmpdir from capture.
        for child in self.tmpdir.rglob("llm_input.md"):
            self.fail(f"unexpected llm_input.md at {child}")
        for child in self.tmpdir.rglob("llm_response.md"):
            self.fail(f"unexpected llm_response.md at {child}")

    def test_bypass_calls_agg_directly_with_built_prompt(self) -> None:
        """Streaming-gap-fix L1: aggregate_only_run bypasses BTA and calls
        agg_inf.ainfer(prompt_str) DIRECTLY. The captured llm_input.md
        contents must be byte-identical to what's passed to ainfer (no BTA
        layer to second-guess the prompt build). This is the property that
        makes llm_input.md `definitionally accurate` after the bypass."""
        task_workspace = self.tmpdir / "task_agg_z"
        agg = self._make_aggregator(response_text="OK")
        asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            task_workspace=task_workspace,
        ))
        # The mock captured the prompt arg passed to ainfer.
        captured = (task_workspace / "llm_input.md").read_text()
        self.assertEqual(
            agg.last_prompt, captured,
            "ainfer() must be called with the same string captured to "
            "llm_input.md — proves the bypass: no BTA layer between "
            "the builder and the inferencer.",
        )
        # No `children/aggregator/` subdir created (BTA reroute is gone).
        self.assertFalse(
            (task_workspace / "children" / "aggregator").exists(),
            "BTA bypass must not create children/aggregator/ subdir.",
        )

    def test_bypass_skips_workspace_wiring_when_agg_lacks_workspace_attr(self) -> None:
        """Streaming-gap-fix L1: the workspace-wiring branch is gated on
        `hasattr(agg_inf, '_workspace')`. Mock aggs (used in tests) lack
        the attr, so the gate skips InferencerWorkspace setup gracefully."""
        task_workspace = self.tmpdir / "task_agg_no_ws"
        agg = self._make_aggregator(response_text="NO WIRING")
        # Should not raise even though agg has no _workspace attribute.
        result = asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            task_workspace=task_workspace,
        ))
        self.assertEqual(result, "NO WIRING")


class FindLatestExperimentWorkspaceTest(unittest.TestCase):
    """Picker shape check: only `exp_*` dirs containing per-combo
    analyses (`combos/*/analysis/combo_*.md`) qualify. Bare `exp_`
    prefix is necessary but NOT sufficient — synth's per-hypothesis
    analysis tasks (e.g. `exp_<ts>_H56_rerun/outputs/analysis.md`)
    must NOT be returned even if they're the most recent."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.tasks = self.tmp / "tasks"
        self.tasks.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_combos_workspace(self, name: str) -> Path:
        ws = self.tasks / name
        (ws / "combos" / "H1" / "analysis").mkdir(parents=True)
        (ws / "combos" / "H1" / "analysis" / "combo_H1.md").write_text(
            "# H1 analysis\n", encoding="utf-8",
        )
        return ws

    def _make_per_hypothesis_task(self, name: str) -> Path:
        # Mirrors synth's per-H analysis tasks: outputs/analysis.md, NO combos/
        ws = self.tasks / name
        (ws / "outputs").mkdir(parents=True)
        (ws / "outputs" / "analysis.md").write_text(
            "# per-H analysis\n", encoding="utf-8",
        )
        return ws

    def test_returns_none_when_no_dir(self) -> None:
        self.assertIsNone(
            find_latest_experiment_workspace(self.tmp / "nonexistent"),
        )

    def test_returns_none_when_no_qualifying_workspace(self) -> None:
        self._make_per_hypothesis_task("exp_20260101_000000_H1")
        self._make_per_hypothesis_task("exp_20260102_000000_H56_rerun")
        self.assertIsNone(find_latest_experiment_workspace(self.tasks))

    def test_returns_qualifying_workspace_when_alone(self) -> None:
        ws = self._make_combos_workspace("exp_20260101_000000_combos")
        result = find_latest_experiment_workspace(self.tasks)
        self.assertEqual(result, ws)

    def test_skips_more_recent_non_combos_in_favor_of_qualifying(self) -> None:
        """The bug shape: a more-recent per-hypothesis task gets picked
        unless the picker requires combos/ substructure."""
        older_combos = self._make_combos_workspace("exp_aaaa_combos")
        newer_per_h = self._make_per_hypothesis_task("exp_zzzz_H56_rerun")
        # Force newer mtime on the per-H one.
        import os
        old_t = older_combos.stat().st_mtime
        os.utime(newer_per_h, (old_t + 1000, old_t + 1000))
        result = find_latest_experiment_workspace(self.tasks)
        self.assertEqual(
            result, older_combos,
            "Picker must skip non-combos `exp_*` even when more recent",
        )


class CollectFromSubmissionsTest(unittest.TestCase):
    """Hub-driven aggregator-input collector: terminal-status filter +
    analysisFile read + analysisSummary fallback + size caps + the
    Layer 4 filter matrix (min_epochs / include_incomparable / include_errored)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_analysis(self, rel: str, body: str) -> str:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return str(p)

    def test_empty_submissions(self) -> None:
        self.assertEqual(
            collect_aggregator_input_from_submissions([], self.tmp), [],
        )

    def test_skips_non_terminal(self) -> None:
        subs = [
            {"comboKey": "H1", "status": "queued", "analysisFile": "x.md"},
            {"comboKey": "H2", "status": "running", "analysisFile": "y.md"},
        ]
        self.assertEqual(
            collect_aggregator_input_from_submissions(subs, self.tmp), [],
        )

    def test_reads_analysis_file_when_present(self) -> None:
        path = self._write_analysis(
            "tasks/exp_h1/outputs/analysis.md", "# H1 body content",
        )
        subs = [{"comboKey": "H1", "status": "completed", "analysisFile": path}]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["combo_id"], "H1")
        self.assertEqual(out[0]["path"], path)
        self.assertIn("H1 body content", out[0]["summary"])

    def test_relative_analysis_file_resolved_against_session_dir(self) -> None:
        self._write_analysis("tasks/exp_h1/outputs/analysis.md", "rel body")
        subs = [{
            "comboKey": "H1", "status": "completed",
            "analysisFile": "tasks/exp_h1/outputs/analysis.md",
        }]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertEqual(len(out), 1)
        self.assertIn("rel body", out[0]["summary"])

    def test_falls_back_to_summary_when_file_missing(self) -> None:
        subs = [{
            "comboKey": "H1", "status": "completed",
            "analysisFile": "/nonexistent/path.md",
            "analysisSummary": "summary fallback content",
        }]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertEqual(len(out), 1)
        self.assertIn("summary fallback content", out[0]["summary"])

    def test_falls_back_to_stub_when_both_missing(self) -> None:
        subs = [{"comboKey": "H1", "status": "completed"}]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertEqual(len(out), 1)
        self.assertIn("[H1] no analysis content available", out[0]["summary"])

    def test_uses_id_when_combokey_missing(self) -> None:
        subs = [{"id": "sub-x", "status": "completed", "analysisSummary": "x"}]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertEqual(out[0]["combo_id"], "sub-x")

    def test_skips_when_no_combo_id(self) -> None:
        subs = [{"status": "completed", "analysisSummary": "x"}]
        self.assertEqual(
            collect_aggregator_input_from_submissions(subs, self.tmp), [],
        )

    def test_per_doc_size_cap(self) -> None:
        big = "x" * (200 * 1024)
        path = self._write_analysis("tasks/exp_h1/outputs/analysis.md", big)
        subs = [{"comboKey": "H1", "status": "completed", "analysisFile": path}]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertIn("[truncated: per-combo cap]", out[0]["summary"])

    # --- Layer 4 filter matrix -------------------------------------------

    def test_min_epochs_default_excludes_nothing(self) -> None:
        subs = [
            {"comboKey": "H1", "status": "completed",
             "epochsCompleted": 0, "analysisSummary": "x"},
            {"comboKey": "H2", "status": "completed",
             "epochsCompleted": 100, "analysisSummary": "y"},
        ]
        out = collect_aggregator_input_from_submissions(subs, self.tmp)
        self.assertEqual({e["combo_id"] for e in out}, {"H1", "H2"})

    def test_min_epochs_filters_below_threshold(self) -> None:
        subs = [
            {"comboKey": "H_BELOW", "status": "completed",
             "epochsCompleted": 4, "analysisSummary": "x"},
            {"comboKey": "H_AT", "status": "completed",
             "epochsCompleted": 10, "analysisSummary": "y"},
            {"comboKey": "H_OVER", "status": "completed",
             "epochsCompleted": 100, "analysisSummary": "z"},
            {"comboKey": "H_MISSING", "status": "completed",
             "analysisSummary": "w"},  # no epochsCompleted → treated as 0
        ]
        out = collect_aggregator_input_from_submissions(
            subs, self.tmp, min_epochs=10,
        )
        self.assertEqual(
            {e["combo_id"] for e in out}, {"H_AT", "H_OVER"},
        )

    def test_exclude_incomparable(self) -> None:
        subs = [
            {"comboKey": "H1", "status": "completed",
             "verdict": "win", "analysisSummary": "x"},
            {"comboKey": "H2", "status": "completed",
             "verdict": "incomparable", "analysisSummary": "y"},
        ]
        out = collect_aggregator_input_from_submissions(
            subs, self.tmp, include_incomparable=False,
        )
        self.assertEqual({e["combo_id"] for e in out}, {"H1"})

    def test_exclude_errored(self) -> None:
        subs = [
            {"comboKey": "H1", "status": "completed", "analysisSummary": "x"},
            {"comboKey": "H_ERR", "status": "error", "analysisSummary": "y"},
            {"comboKey": "H_FAIL", "status": "failed", "analysisSummary": "z"},
            {"comboKey": "H_CANCEL",
             "status": "cancelled", "analysisSummary": "w"},
        ]
        out = collect_aggregator_input_from_submissions(
            subs, self.tmp, include_errored=False,
        )
        self.assertEqual({e["combo_id"] for e in out}, {"H1"})

    def test_filters_compose(self) -> None:
        subs = [
            # passes all
            {"comboKey": "OK", "status": "completed",
             "epochsCompleted": 50, "verdict": "win",
             "analysisSummary": "x"},
            # filtered: incomparable
            {"comboKey": "INC", "status": "completed",
             "epochsCompleted": 50, "verdict": "incomparable",
             "analysisSummary": "x"},
            # filtered: error
            {"comboKey": "ERR", "status": "error",
             "epochsCompleted": 50, "analysisSummary": "x"},
            # filtered: too few epochs
            {"comboKey": "EARLY", "status": "completed",
             "epochsCompleted": 4, "verdict": "win",
             "analysisSummary": "x"},
        ]
        out = collect_aggregator_input_from_submissions(
            subs, self.tmp,
            min_epochs=10,
            include_incomparable=False,
            include_errored=False,
        )
        self.assertEqual({e["combo_id"] for e in out}, {"OK"})


class ResolveActiveMultiTaskIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_hub(self, mid: str) -> None:
        (self.tmp / f"hub_{mid}_submissions.json").write_text(
            "{}", encoding="utf-8",
        )

    def test_explicit_takes_precedence(self) -> None:
        self._make_hub("multi-A")
        self._make_hub("multi-B")
        mid, err = resolve_active_multi_task_id(
            self.tmp, explicit="multi-A", workflow_context_active="multi-B",
        )
        self.assertEqual(mid, "multi-A")
        self.assertIsNone(err)

    def test_explicit_missing_hub_errors(self) -> None:
        mid, err = resolve_active_multi_task_id(self.tmp, explicit="missing")
        self.assertIsNone(mid)
        self.assertIn("missing", err)

    def test_workflow_context_fallback(self) -> None:
        self._make_hub("multi-A")
        self._make_hub("multi-B")
        mid, err = resolve_active_multi_task_id(
            self.tmp, workflow_context_active="multi-B",
        )
        self.assertEqual(mid, "multi-B")
        self.assertIsNone(err)

    def test_exactly_one_hub_heuristic(self) -> None:
        self._make_hub("multi-only")
        mid, err = resolve_active_multi_task_id(self.tmp)
        self.assertEqual(mid, "multi-only")
        self.assertIsNone(err)

    def test_no_hubs_errors(self) -> None:
        mid, err = resolve_active_multi_task_id(self.tmp)
        self.assertIsNone(mid)
        self.assertIn("No hub submissions", err)

    def test_multiple_hubs_no_explicit_errors(self) -> None:
        self._make_hub("multi-A")
        self._make_hub("multi-B")
        mid, err = resolve_active_multi_task_id(self.tmp)
        self.assertIsNone(mid)
        self.assertIn("Multiple hubs", err)
        self.assertIn("--reuse-hub", err)


class ParseAggregationFlagsTest(unittest.TestCase):
    """Layer 4 — verifies the 3 new aggregation-settings flags parse
    correctly alongside the existing aggregate-only flag set."""

    def _parse(self, args_str: str) -> dict:
        from rankevolve.src.server.command_router import (  # @manual
            _parse_experiment_combos_args,
        )
        return _parse_experiment_combos_args(args_str)

    def test_min_epochs_parses_as_int(self) -> None:
        out = self._parse("--aggregate-only --min-epochs 15")
        self.assertEqual(out.get("min_epochs"), 15)

    def test_min_epochs_invalid_value_silently_dropped(self) -> None:
        out = self._parse("--aggregate-only --min-epochs notanumber")
        self.assertNotIn("min_epochs", out)

    def test_exclude_incomparable_presence_only(self) -> None:
        out = self._parse("--aggregate-only --exclude-incomparable")
        self.assertIs(out.get("exclude_incomparable"), True)

    def test_exclude_errored_presence_only(self) -> None:
        out = self._parse("--aggregate-only --exclude-errored")
        self.assertIs(out.get("exclude_errored"), True)

    def test_no_flags_means_no_filter(self) -> None:
        out = self._parse("--aggregate-only")
        self.assertNotIn("min_epochs", out)
        self.assertNotIn("exclude_incomparable", out)
        self.assertNotIn("exclude_errored", out)

    def test_composes_with_existing_flags(self) -> None:
        out = self._parse(
            "--aggregate-only --min-epochs 10 --exclude-incomparable "
            "--archive-keep 5 --force-refresh"
        )
        self.assertEqual(out.get("min_epochs"), 10)
        self.assertIs(out.get("exclude_incomparable"), True)
        self.assertEqual(out.get("archive_keep"), 5)
        self.assertIs(out.get("force_refresh"), True)
        self.assertIs(out.get("aggregate_only"), True)


class AggregateOnlyRunOutputPathWiringTest(unittest.TestCase):
    """Regression: aggregate_only_run must thread `output_path` into the
    aggregator's `inference_config` so DualInferencer's per-round file-
    reference substitution can fire (dual_inferencer.py:1292+ legacy mode).
    Without this, multi-round consensus loops re-embed the full proposal
    body inline every round — wasted tokens that compound with
    max_iterations."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.exp_workspace = self.tmpdir / "exp"
        analysis = self.exp_workspace / "combos" / "combo_h1" / "analysis"
        analysis.mkdir(parents=True)
        (analysis / "combo_h1.md").write_text(
            "# combo_h1\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_capturing_agg(self):
        class _Agg:
            has_local_access = False

            def __init__(self) -> None:
                self.last_inference_config: dict | None = None

            async def ainfer(self, prompt, inference_config=None, **kw):
                self.last_inference_config = inference_config
                return "OK"

        return _Agg()

    def test_passes_output_path_when_task_workspace_supplied(self) -> None:
        task_workspace = self.tmpdir / "task_agg"
        agg = self._make_capturing_agg()
        asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            task_workspace=task_workspace,
        ))
        cfg = agg.last_inference_config
        self.assertIsNotNone(cfg)
        # Path must be inside task_workspace/artifacts/ and use the
        # `{{ round_index }}` template substitution that DualInferencer's
        # _maybe_replace_with_file_reference expects.
        out_path = cfg.get("output_path", "")
        self.assertTrue(
            out_path.startswith(str(task_workspace / "artifacts")),
            f"output_path must be under artifacts/, got {out_path!r}",
        )
        self.assertIn("{{ round_index }}", out_path)
        self.assertTrue(out_path.endswith("_aggregation.md"))

    def test_creates_artifacts_dir(self) -> None:
        task_workspace = self.tmpdir / "task_agg"
        agg = self._make_capturing_agg()
        asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
            task_workspace=task_workspace,
        ))
        self.assertTrue((task_workspace / "artifacts").is_dir())

    def test_no_output_path_when_no_task_workspace(self) -> None:
        """Existing callers that don't supply task_workspace get an empty
        inference_config (back-compat: no surprise key injection)."""
        agg = self._make_capturing_agg()
        asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: agg,
        ))
        self.assertEqual(agg.last_inference_config, {})

    def test_recovers_final_artifact_when_dual_returns_file_reference(self) -> None:
        """Regression: when `output_path` is wired, the dual's final
        return value is the per-round file-reference substitution string
        (`"The complete output has been written to: <path>..."`) rather
        than the proposal body — by design (dual_inferencer.py:700,
        :930-931). aggregate_only_run must recover the real content from
        the highest-numbered round artifact, otherwise the downstream
        validator rejects the 2-line file-reference message as "body
        lacks any `## ` heading"."""
        task_workspace = self.tmpdir / "task_agg"

        class _DualLikeAgg:
            """Mimics DualInferencer's post-replacement behavior: the
            real proposal is on disk; ainfer() returns only the file ref."""
            has_local_access = False

            async def ainfer(self, prompt, inference_config=None, **kw):
                # Simulate: 4 rounds of fix steps wrote progressively
                # refined artifacts; the 4th got approved by review;
                # ainfer returns the file-ref to round3.
                output_path = inference_config["output_path"]
                # `{{ round_index }}` substitution mirrors
                # dual_inferencer.py:1295-1297.
                for i in range(4):
                    p = Path(output_path.replace("{{ round_index }}", str(i)))
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(
                        f"# Round {i} aggregation\n\n## Headline\nbody body body\n",
                        encoding="utf-8",
                    )
                last = Path(output_path.replace("{{ round_index }}", "3"))
                return (
                    f"The complete output has been written to: `{last}`.\n"
                    f"Read that file for the full details."
                )

        result = asyncio.run(aggregate_only_run(
            self.exp_workspace,
            self.tmpdir / "live.md",
            aggregator_factory=lambda: _DualLikeAgg(),
            task_workspace=task_workspace,
        ))
        # Must NOT be the 2-line file-ref message; must be the real body
        # from round3_aggregation.md.
        self.assertIn("# Round 3 aggregation", result)
        self.assertIn("## Headline", result)
        self.assertNotIn("Read that file for the full details", result)
        # llm_response.md captures the recovered (full) content too,
        # so the workspace tab shows what the validator actually saw.
        captured = (task_workspace / "llm_response.md").read_text()
        self.assertIn("# Round 3 aggregation", captured)


class BuildDualPlaceholderProposalTest(unittest.TestCase):
    """Regression: ExperimentBridge._build_dual must override the
    DualInferencer default `placeholder_proposal="proposal"` to
    `"main_response"` — matching the convention used by every aggregation/
    plan/implementation/proposal template (`{{ main_response }}`) and
    the reference dual_inferencer_bridge.py:528,544. Without this
    override, review.jinja2 + followup.jinja2 render an EMPTY
    `<ProposedAggregation>` slot because the framework default keys the
    feed against a name no template references."""

    def test_aggregation_role_uses_main_response_placeholder(self) -> None:
        from rankevolve.src.server.experiment_bridge import ExperimentBridge
        tmp = Path(tempfile.mkdtemp(prefix="exp_bridge_dual_"))
        try:
            b = ExperimentBridge(session_tasks_dir=tmp, plan_text="# H1")
            dual = b._build_dual(
                role="accumulated_learnings",
                template_space="aggregation",
                template_version="accumulated_learnings",
            )
            self.assertEqual(
                dual.placeholder_proposal, "main_response",
                "Aggregation review/followup templates use {{ main_response }}; "
                "the framework default 'proposal' would render an empty slot.",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
