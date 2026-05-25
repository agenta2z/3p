# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Tests for :mod:`rankevolve.src.server.implement_hypothesis_bridge`.

Focuses on the deterministic plumbing: option parsing, batch JSON parsing,
soft validation/repair, fallback singletons, workspace layout, and the
artifacts written before/after the BTA runs. The BTA execution itself
is mocked — real PTI workers (which actually edit the model codebase)
are covered by chat-driven smoke tests, not unit tests.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from rankevolve.src.server.implement_hypothesis_bridge import (
    Batch,
    ImplementHypothesisBridge,
    parse_batches_response,
    parse_implement_hypothesis_options,
    validate_and_repair_batches,
)


class ParseImplementHypothesisOptionsTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        request, opts = parse_implement_hypothesis_options(
            "do the thing --select H1,H17 --plan /tmp/p.md "
            "--max-batch-size 7 --max-parallel 3 --reuse-task implhyp_old"
        )
        self.assertEqual(request, "do the thing")
        self.assertEqual(opts["select"], "H1,H17")
        self.assertEqual(opts["plan"], "/tmp/p.md")
        self.assertEqual(opts["max_batch_size"], "7")
        self.assertEqual(opts["max_parallel"], "3")
        self.assertEqual(opts["reuse_task"], "implhyp_old")

    def test_passthrough_request(self) -> None:
        request, opts = parse_implement_hypothesis_options("some free text --select H1")
        self.assertEqual(request, "some free text")
        self.assertEqual(opts["select"], "H1")

    def test_empty(self) -> None:
        request, opts = parse_implement_hypothesis_options("")
        self.assertEqual(request, "")
        self.assertEqual(opts, {})


class ParseBatchesResponseTest(unittest.TestCase):
    def _wrap(self, json_blob: str, *, in_response: bool = True, fenced: bool = True) -> str:
        body = json_blob
        if fenced:
            body = f"```json\n{body}\n```"
        if in_response:
            return f"<Response>\n{body}\n</Response>"
        return body

    def test_basic_response(self) -> None:
        text = self._wrap(json.dumps({
            "batches": [
                {"batch_id": "B1", "items": ["H1", "H17"], "rationale": "shared masking"},
                {"batch_id": "B2", "items": ["H4"], "rationale": "scoring head"},
            ]
        }))
        batches = parse_batches_response(text, valid_ids={"H1", "H17", "H4"})
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0].batch_id, "B1")
        self.assertEqual(batches[0].items, ["H1", "H17"])
        self.assertEqual(batches[1].items, ["H4"])

    def test_drops_unknown_ids(self) -> None:
        text = self._wrap(json.dumps({
            "batches": [
                {"batch_id": "B1", "items": ["H1", "HBOGUS"], "rationale": "x"},
            ]
        }))
        batches = parse_batches_response(text, valid_ids={"H1"})
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].items, ["H1"])

    def test_no_response_tags_still_works(self) -> None:
        text = self._wrap(
            json.dumps({"batches": [{"batch_id": "B1", "items": ["H1"]}]}),
            in_response=False,
        )
        batches = parse_batches_response(text, valid_ids={"H1"})
        self.assertEqual(len(batches), 1)

    def test_no_fence_still_works(self) -> None:
        text = self._wrap(
            json.dumps({"batches": [{"batch_id": "B1", "items": ["H1"]}]}),
            fenced=False,
        )
        batches = parse_batches_response(text, valid_ids={"H1"})
        self.assertEqual(len(batches), 1)

    def test_unparseable_returns_empty(self) -> None:
        self.assertEqual(parse_batches_response("not json at all", {"H1"}), [])

    def test_missing_batches_key(self) -> None:
        text = self._wrap(json.dumps({"items": ["H1"]}))
        self.assertEqual(parse_batches_response(text, {"H1"}), [])

    def test_empty_batch_dropped(self) -> None:
        text = self._wrap(json.dumps({
            "batches": [
                {"batch_id": "", "items": ["H1"]},  # empty id
                {"batch_id": "B2", "items": []},  # empty items
                {"batch_id": "B3", "items": ["H1"]},  # ok
            ]
        }))
        batches = parse_batches_response(text, {"H1"})
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].batch_id, "B3")


class ValidateAndRepairBatchesTest(unittest.TestCase):
    def test_dedup_across_batches(self) -> None:
        batches = [
            Batch("B1", ["H1", "H17"]),
            Batch("B2", ["H17", "H4"]),  # H17 duplicated
        ]
        out, warnings = validate_and_repair_batches(batches, ["H1", "H17", "H4"], 5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].items, ["H1", "H17"])
        self.assertEqual(out[1].items, ["H4"])  # H17 dropped from B2
        self.assertTrue(any("multiple batches" in w for w in warnings))

    def test_hard_cap_split(self) -> None:
        # max_batch_size=3 → hard cap 6. A batch of 7 splits.
        batches = [Batch("BIG", [f"H{i}" for i in range(7)])]
        selected = [f"H{i}" for i in range(7)]
        out, warnings = validate_and_repair_batches(batches, selected, 3)
        # 7 items, max=3 → ceil(7/3) = 3 batches
        self.assertEqual(len(out), 3)
        self.assertEqual(len(out[0].items), 3)
        self.assertEqual(len(out[1].items), 3)
        self.assertEqual(len(out[2].items), 1)
        self.assertTrue(any("auto-split" in w for w in warnings))

    def test_missing_id_added_as_singleton(self) -> None:
        batches = [Batch("B1", ["H1"])]
        out, warnings = validate_and_repair_batches(batches, ["H1", "H17"], 5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].items, ["H1"])
        self.assertEqual(out[1].items, ["H17"])
        self.assertTrue(any("not covered" in w for w in warnings))

    def test_clean_input_no_warnings(self) -> None:
        batches = [Batch("B1", ["H1", "H17"]), Batch("B2", ["H4"])]
        out, warnings = validate_and_repair_batches(batches, ["H1", "H17", "H4"], 5)
        self.assertEqual(len(out), 2)
        self.assertEqual(warnings, [])

    def test_empty_batch_after_dedup_dropped(self) -> None:
        batches = [
            Batch("B1", ["H1"]),
            Batch("B2", ["H1"]),  # all dup → empty after dedup
            Batch("B3", ["H17"]),
        ]
        out, _ = validate_and_repair_batches(batches, ["H1", "H17"], 5)
        # B2 dropped; B1 and B3 survive
        self.assertEqual(len(out), 2)
        self.assertEqual({b.batch_id for b in out}, {"B1", "B3"})


class WorkspaceLayoutTest(unittest.TestCase):
    def test_workspace_subdirs_created(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_ws_"))
        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="# H1",
            selected_ids=["H1"],
        )
        ws = b.workspace
        self.assertTrue(ws.is_dir())
        self.assertTrue(str(ws.name).startswith("implhyp_"))
        for sub in ("outputs", "results", "logs", "batches"):
            self.assertTrue((ws / sub).is_dir(), f"{sub} not created")
        self.assertTrue((ws / "_runtime" / "inferencer_cache").is_dir())

    def test_reuse_task_resumes_workspace(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_resume_"))
        existing = tmp / "implhyp_existing"
        existing.mkdir(parents=True)
        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="# H1",
            selected_ids=["H1"],
            reuse_task="implhyp_existing",
        )
        self.assertEqual(b.workspace, existing)

    def test_max_parallel_clamps_to_5(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_clamp_"))
        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="",
            selected_ids=["H1"],
            max_parallel=99,
        )
        self.assertEqual(b._max_parallel, 5)

    def test_max_batch_size_minimum_1(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_min_"))
        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="",
            selected_ids=["H1"],
            max_batch_size=0,
        )
        self.assertEqual(b._max_batch_size, 1)


def _patched_dual_factory() -> Any:
    """Duck-typed mock for DualInferencer/PTI children. The BTA's
    `__attrs_post_init__` walks `_workspace` + `_for_each_child_inferencer`
    on every child; both must exist."""
    return MagicMock(
        _workspace=None,
        _for_each_child_inferencer=lambda *a, **k: (),
    )


class FallbackSingletonsTest(unittest.IsolatedAsyncioTestCase):
    """When the breakdown LLM fails or returns garbage, the bridge falls
    back to one batch per hypothesis. Always-correct, just expensive."""

    async def test_fallback_when_breakdown_returns_garbage(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_fb_"))

        class _GarbageInferencer:
            async def ainfer(self, *args: Any, **kwargs: Any) -> str:
                return "complete nonsense, not even json"

        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="",
            selected_ids=["H1", "H17"],
            breakdown_factory=lambda: _GarbageInferencer(),
        )
        batches = await b._resolve_batches()
        self.assertEqual(len(batches), 2)
        self.assertEqual({b.items[0] for b in batches}, {"H1", "H17"})
        self.assertTrue(all(len(b.items) == 1 for b in batches))


class RunWritesArtifactsTest(unittest.IsolatedAsyncioTestCase):
    """End-to-end of deterministic plumbing — BTA.ainfer mocked to no-op
    so we validate workspace writes without spawning real PTI workers."""

    async def test_run_writes_plan_and_summary(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_run_"))

        class _OkBreakdown:
            async def ainfer(self, *args: Any, **kwargs: Any) -> str:
                return (
                    "<Response>\n```json\n"
                    + json.dumps({
                        "batches": [
                            {"batch_id": "B1", "items": ["H1", "H17"], "rationale": "shared"},
                            {"batch_id": "B2", "items": ["H4"], "rationale": "isolated"},
                        ]
                    })
                    + "\n```\n</Response>"
                )

        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="",
            selected_ids=["H1", "H17", "H4"],
            breakdown_factory=lambda: _OkBreakdown(),
            worker_factory_override=lambda batch: _patched_dual_factory(),
            aggregator_factory=lambda: _patched_dual_factory(),
        )

        with patch.object(b, "_build_outer_bta") as mock_build:
            mock_bta = mock_build.return_value
            async def _noop_ainfer(*args: Any, **kwargs: Any) -> str:
                return "ok"
            mock_bta.ainfer = _noop_ainfer
            summary = await b.run("test request")

        plan_path = b.workspace / "results" / "batch_plan.json"
        self.assertTrue(plan_path.is_file())
        plan = json.loads(plan_path.read_text())
        self.assertEqual(len(plan["batches"]), 2)
        self.assertEqual(plan["batches"][0]["batch_id"], "B1")

        summary_path = b.workspace / "results" / "implementation_summary.json"
        self.assertTrue(summary_path.is_file())
        summary_doc = json.loads(summary_path.read_text())
        self.assertEqual(summary_doc["status"], "completed")
        self.assertEqual(summary_doc["selected_ids"], ["H1", "H17", "H4"])

        self.assertIn("/implement-hypothesis completed", summary)
        self.assertIn("B1", summary)

        # BTA's deterministic-breakdown cache also written.
        breakdown_cache = b.workspace / "checkpoints" / "bta" / "breakdown_result.json"
        self.assertTrue(breakdown_cache.is_file())

    async def test_run_with_no_selection_returns_actionable_error(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="impl_hyp_empty_"))
        b = ImplementHypothesisBridge(
            session_tasks_dir=tmp,
            plan_text="",
            selected_ids=[],
        )
        result = await b.run("")
        self.assertIn("no hypotheses selected", result)
        self.assertFalse((b.workspace / "results" / "implementation_summary.json").is_file())


class BatchTest(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        b = Batch(batch_id="B1", items=["H1", "H17"], rationale="shared")
        d = b.to_dict()
        self.assertEqual(d["batch_id"], "B1")
        self.assertEqual(d["items"], ["H1", "H17"])
        self.assertEqual(d["rationale"], "shared")
