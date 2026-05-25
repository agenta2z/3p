# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Integration test for ``_exec_implement_hypothesis``'s chip lifecycle.

Verifies (Plan: implement-selected-auto-mode-and-hub-nesting.md L0a-d):
* Outer multi-task ``task_status: starting`` emit BEFORE bridge runs.
* One per-batch ``task_status: queued`` emit per batch returned by the
  LLM grouper (via ``on_batches_grouped`` callback).
* Per-batch ``running`` then ``completed`` emit per worker.
* Outer multi-task ``task_status: completed`` emit AFTER bridge returns.
* ``append_hub_implementation`` called once per batch on completion,
  with the right ``sidecar_mid`` (= hub_id when set, else multi_task_id).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from rankevolve.src.server.implement_hypothesis_bridge import Batch


class _FakeInteractive:
    """Captures every _send_response payload for assertion."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def _send_response(self, payload: dict[str, Any], _flag: Any) -> None:
        self.sent.append(payload)


class _FakeSession:
    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_tasks_dir = session_dir / "tasks"
        self.session_tasks_dir.mkdir(exist_ok=True)
        self.info = MagicMock()
        self.info.session_id = "test-session"
        self.info.workflow_target_path = ""
        self.session_context = {}
        self.interactive = _FakeInteractive()

        class _Logger:
            pass

        self.session_logger = _Logger()
        self.session_logger.session_dir = session_dir


def _build_executor(session: _FakeSession) -> Any:
    """Construct a SessionToolExecutor with the minimum stubbed deps so
    ``_exec_implement_hypothesis`` can run end-to-end against a mocked
    bridge."""
    from rankevolve.src.server.tool_executor import SessionToolExecutor

    exe = MagicMock(spec=SessionToolExecutor)
    exe._session = session  # noqa: SLF001
    # Bind the real method to our mock executor.
    exe._exec_implement_hypothesis = (  # noqa: SLF001
        SessionToolExecutor._exec_implement_hypothesis.__get__(exe)
    )

    async def _persist_noop() -> None:
        return None

    exe._persist = _persist_noop  # noqa: SLF001
    return exe


class ExecImplementHypothesisChipLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="exec_implhyp_"))
        self.session = _FakeSession(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def _run_with_stub_bridge(
        self, *, hub_id: str | None, fail_bridge: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (sent_payloads, sidecar_calls). sidecar_calls is the
        list of (kwargs) passed to append_hub_implementation."""
        exe = _build_executor(self.session)
        sidecar_calls: list[dict[str, Any]] = []

        async def _fake_append(**kwargs: Any) -> dict[str, Any]:
            sidecar_calls.append(kwargs)
            return kwargs

        # Patch the bridge to:
        # * Fire on_batches_grouped(batches) with 2 batches.
        # * Fire on_batch_status running/completed for each batch.
        # * Optionally raise to test the error-path.
        class _StubBridge:
            def __init__(self, **kwargs: Any) -> None:
                self.workspace = self.tmp_root = (
                    Path(kwargs["session_tasks_dir"]) / "implhyp-stub"
                )
                self.workspace.mkdir(parents=True, exist_ok=True)

            async def run(
                self, request: str = "", *,
                on_batches_grouped: Any = None,
                on_batch_status: Any = None,
            ) -> str:
                batches = [
                    Batch(batch_id="B1", items=["H1", "H2"]),
                    Batch(batch_id="B2", items=["H3"]),
                ]
                if on_batches_grouped is not None:
                    await on_batches_grouped(batches)
                for b in batches:
                    if on_batch_status is not None:
                        await on_batch_status(b, "running")
                    if fail_bridge and b.batch_id == "B2":
                        if on_batch_status is not None:
                            await on_batch_status(
                                b, "error", error_message="batch boom"
                            )
                        raise RuntimeError("bridge boom")
                    if on_batch_status is not None:
                        await on_batch_status(b, "completed")
                return "completed"

        with patch(
            "rankevolve.src.server.implement_hypothesis_bridge.ImplementHypothesisBridge",
            _StubBridge,
        ), patch(
            "chatbot_demo_react.backend.routes.hub_implementations_store.append_hub_implementation",
            new=_fake_append,
        ):
            args: dict[str, Any] = {"selected_ids": ["H1", "H2", "H3"]}
            if hub_id:
                args["hub_id"] = hub_id
            await exe._exec_implement_hypothesis(args)

        return self.session.interactive.sent, sidecar_calls

    async def test_emits_outer_starting_then_per_batch_queued_running_completed_then_outer_completed(self) -> None:
        sent, sidecar = await self._run_with_stub_bridge(hub_id=None)
        statuses = [(p.get("task_id"), p.get("task_type"), p.get("status")) for p in sent]
        # First emit: outer starting.
        self.assertEqual(statuses[0][1:], ("multi", "starting"))
        outer_id = statuses[0][0]
        self.assertTrue(outer_id.startswith("implhyp-"))
        # Per-batch queued for both batches (right after grouper).
        per_batch_queued = [s for s in statuses if s[1] == "task" and s[2] == "queued"]
        self.assertEqual(len(per_batch_queued), 2)
        self.assertEqual(
            {s[0] for s in per_batch_queued},
            {f"{outer_id}-B1", f"{outer_id}-B2"},
        )
        # Per-batch running + completed for both.
        running = [s for s in statuses if s[1] == "task" and s[2] == "running"]
        self.assertEqual(len(running), 2)
        completed = [s for s in statuses if s[1] == "task" and s[2] == "completed"]
        self.assertEqual(len(completed), 2)
        # Outer terminal completed (last emit).
        self.assertEqual(statuses[-1], (outer_id, "multi", "completed"))

    async def test_sidecar_mid_falls_back_to_multi_task_id_when_no_hub_id(self) -> None:
        _, sidecar = await self._run_with_stub_bridge(hub_id=None)
        # 2 batches → 2 sidecar writes (on completed).
        self.assertEqual(len(sidecar), 2)
        # All writes go to the implhyp-* id (no hub binding).
        ids = {c["multi_task_id"] for c in sidecar}
        self.assertEqual(len(ids), 1)
        self.assertTrue(next(iter(ids)).startswith("implhyp-"))

    async def test_sidecar_mid_uses_hub_id_when_provided(self) -> None:
        _, sidecar = await self._run_with_stub_bridge(hub_id="multi-syn001")
        self.assertEqual(len(sidecar), 2)
        ids = {c["multi_task_id"] for c in sidecar}
        self.assertEqual(ids, {"multi-syn001"})
        # Each row carries the right batch + status.
        statuses = sorted(((c["row"]["batch_id"], c["row"]["status"]) for c in sidecar))
        self.assertEqual(statuses, [("B1", "completed"), ("B2", "completed")])

    async def test_error_path_emits_terminal_error_and_writes_error_sidecar(self) -> None:
        sent, sidecar = await self._run_with_stub_bridge(
            hub_id="multi-test", fail_bridge=True,
        )
        # Outer terminal status is `error`.
        outer_terminals = [
            p for p in sent
            if p.get("task_type") == "multi" and p.get("status") in ("completed", "error")
        ]
        self.assertEqual(outer_terminals[-1]["status"], "error")
        # B2's error transition was recorded.
        b2_rows = [c for c in sidecar if c["row"]["batch_id"] == "B2"]
        self.assertEqual(len(b2_rows), 1)
        self.assertEqual(b2_rows[0]["row"]["status"], "error")
        self.assertEqual(b2_rows[0]["row"]["error_message"], "batch boom")


if __name__ == "__main__":
    unittest.main()
