# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Tests for the bridge's callback DI (Layer 0b/c).

Verifies:
* ``run(on_batches_grouped=…, on_batch_status=…)`` invokes both
  callbacks at the right hook points.
* The per-batch wrapper fires ``running`` then ``completed`` on success
  and ``running`` then ``error`` on failure.
* When no callbacks are passed (back-compat), the bridge runs identically
  to before.

Plan: /home/zgchen/.claude/plans/implement-selected-auto-mode-and-hub-nesting.md
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rankevolve.src.server.implement_hypothesis_bridge import (
    Batch,
    ImplementHypothesisBridge,
)


class _FakeWorker:
    """Minimal worker that quacks like enough of an InferencerBase for
    the wrapper's `inner.ainfer = ...` swap. We avoid pulling in real
    BTA execution; the wrapper logic is what's under test."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.ainfer_called = 0

    async def ainfer(self, *args: Any, **kwargs: Any) -> str:
        self.ainfer_called += 1
        if self.fail:
            raise RuntimeError("boom")
        return "ok"


def _bridge_with_fake_worker(
    *, fail_worker: bool = False, hub_id: str | None = None,
) -> tuple[ImplementHypothesisBridge, Path, _FakeWorker]:
    tmp = Path(tempfile.mkdtemp(prefix="implhyp_cb_"))
    fake = _FakeWorker(fail=fail_worker)
    bridge = ImplementHypothesisBridge(
        session_tasks_dir=tmp,
        plan_text="",
        selected_ids=["H1", "H2"],
        worker_factory_override=lambda batch: fake,  # type: ignore[arg-type]
        hub_id=hub_id,
    )
    return bridge, tmp, fake


class WorkerFactoryWrapperTest(unittest.TestCase):
    """Ensure the per-batch worker wrapper fires running → completed/error."""

    def tearDown(self) -> None:
        # Best-effort cleanup of temp workspaces created by helper.
        pass

    def test_no_callback_returns_inner_unchanged(self) -> None:
        bridge, tmp, fake = _bridge_with_fake_worker()
        try:
            self.assertIsNone(bridge._on_batch_status)
            batch = Batch(batch_id="B1", items=["H1"])
            inner = bridge._worker_factory(batch, 0)
            self.assertIs(inner, fake)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_callback_wraps_inner_and_fires_running_then_completed(self) -> None:
        events: list[tuple[str, str]] = []

        async def cb(batch: Any, status: str, **kw: Any) -> None:
            events.append((batch.batch_id, status))

        bridge, tmp, fake = _bridge_with_fake_worker()
        try:
            bridge._on_batch_status = cb
            batch = Batch(batch_id="B1", items=["H1"])
            wrapped = bridge._worker_factory(batch, 0)
            asyncio.run(wrapped.ainfer())
            self.assertEqual(events, [("B1", "running"), ("B1", "completed")])
            self.assertEqual(fake.ainfer_called, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_callback_fires_error_on_worker_exception(self) -> None:
        events: list[tuple[str, str, str | None]] = []

        async def cb(batch: Any, status: str, **kw: Any) -> None:
            events.append((batch.batch_id, status, kw.get("error_message")))

        bridge, tmp, fake = _bridge_with_fake_worker(fail_worker=True)
        try:
            bridge._on_batch_status = cb
            batch = Batch(batch_id="B2", items=["H2"])
            wrapped = bridge._worker_factory(batch, 0)
            with self.assertRaises(RuntimeError):
                asyncio.run(wrapped.ainfer())
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0], ("B2", "running", None))
            self.assertEqual(events[1][:2], ("B2", "error"))
            self.assertEqual(events[1][2], "boom")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class HubIdConstructorTest(unittest.TestCase):
    def test_hub_id_stored_when_provided(self) -> None:
        bridge, tmp, _ = _bridge_with_fake_worker(hub_id="multi-syn001")
        try:
            self.assertEqual(bridge._hub_id, "multi-syn001")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hub_id_defaults_to_none(self) -> None:
        bridge, tmp, _ = _bridge_with_fake_worker()
        try:
            self.assertIsNone(bridge._hub_id)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RunCallbackInvocationTest(unittest.TestCase):
    """End-to-end: stub `_resolve_batches` + the BTA's `ainfer` so we can
    drive `run()` without any real LLM calls and assert the callbacks
    fire in the expected order."""

    def test_on_batches_grouped_called_after_resolve(self) -> None:
        bridge, tmp, _ = _bridge_with_fake_worker()
        try:
            seen: list[list[str]] = []

            async def on_grouped(batches: list[Batch]) -> None:
                seen.append([b.batch_id for b in batches])

            stub_batches = [
                Batch(batch_id="B1", items=["H1"]),
                Batch(batch_id="B2", items=["H2"]),
            ]

            async def fake_resolve() -> list[Batch]:
                return stub_batches

            class _StubBTA:
                async def ainfer(self, *_a: Any, **_kw: Any) -> str:
                    return "bta-ok"

            with patch.object(
                bridge, "_resolve_batches", side_effect=fake_resolve
            ), patch.object(
                bridge, "_build_outer_bta", return_value=_StubBTA()
            ):
                summary = asyncio.run(bridge.run(
                    "",
                    on_batches_grouped=on_grouped,
                ))
            self.assertEqual(seen, [["B1", "B2"]])
            self.assertIn("completed", summary)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_run_back_compat_no_callbacks(self) -> None:
        """Existing call sites that don't pass callbacks still work."""
        bridge, tmp, _ = _bridge_with_fake_worker()
        try:
            stub_batches = [Batch(batch_id="B1", items=["H1"])]

            async def fake_resolve() -> list[Batch]:
                return stub_batches

            class _StubBTA:
                async def ainfer(self, *_a: Any, **_kw: Any) -> str:
                    return "bta-ok"

            with patch.object(
                bridge, "_resolve_batches", side_effect=fake_resolve
            ), patch.object(
                bridge, "_build_outer_bta", return_value=_StubBTA()
            ):
                summary = asyncio.run(bridge.run(""))
            self.assertIn("completed", summary)
            # Confirms instance fields were populated to None.
            self.assertIsNone(bridge._on_batch_status)
            self.assertIsNone(bridge._on_batches_grouped)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
