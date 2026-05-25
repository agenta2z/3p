# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Tests for the rankevolve_monitor CLI's PATCH-back integration.

The deterministic plumbing (_build_terminal_payload, arg parsing, no-op
when --submission-id missing) is unit-tested. The actual HTTP PATCH is
mocked — real WebUI integration is covered by chat-driven smoke tests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

from rankevolve.src.server.cli.monitor_cli import (
    _build_terminal_payload,
    _MonitorState,
    _parse_args,
    _patch_submission_row,
)


class ParseArgsTest(unittest.TestCase):
    def test_patchback_flags_present(self) -> None:
        args = _parse_args(
            [
                "--workspace", "/tmp/ws",
                "--submission-id", "sub-abc",
                "--multi-task-id", "multi-foo",
                "--session-id", "ses-xyz",
                "--webui-url", "http://127.0.0.1:8087",
                "--analysis-file", "/tmp/ws/analysis/combo_x.md",
            ]
        )
        self.assertEqual(args.submission_id, "sub-abc")
        self.assertEqual(args.multi_task_id, "multi-foo")
        self.assertEqual(args.session_id, "ses-xyz")
        self.assertEqual(args.webui_url, "http://127.0.0.1:8087")
        self.assertEqual(args.analysis_file, "/tmp/ws/analysis/combo_x.md")

    def test_patchback_flags_default_empty(self) -> None:
        args = _parse_args(["--workspace", "/tmp/ws"])
        self.assertEqual(args.submission_id, "")
        self.assertEqual(args.webui_url, "")
        self.assertEqual(args.analysis_file, "")


class BuildTerminalPayloadTest(unittest.TestCase):
    def test_empty_trajectory(self) -> None:
        state = _MonitorState()
        payload = _build_terminal_payload(state, "completed", 1234567890)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["epochsCompleted"], 0)
        self.assertEqual(payload["finalMetrics"], {})
        self.assertEqual(payload["epochTrajectory"], [])
        self.assertEqual(payload["runFinishedAt"], 1234567890)

    def test_with_trajectory(self) -> None:
        state = _MonitorState()
        state.trajectory = [
            {"epoch": 0.0, "ndcg10": 0.10, "hr10": 0.20, "mrr": 0.05},
            {"epoch": 5.0, "ndcg10": 0.15, "hr10": 0.25, "mrr": 0.10},
        ]
        payload = _build_terminal_payload(state, "completed", 999)
        self.assertEqual(payload["epochsCompleted"], 5)
        # ndcg10 → ndcg_10 backend-naming convention.
        self.assertEqual(payload["finalMetrics"]["ndcg_10"], 0.15)
        self.assertEqual(payload["finalMetrics"]["hr_10"], 0.25)
        self.assertEqual(payload["finalMetrics"]["mrr"], 0.10)


class PatchSubmissionRowTest(unittest.IsolatedAsyncioTestCase):
    async def _ns(self, **overrides: Any) -> argparse.Namespace:
        defaults: dict[str, Any] = {
            "submission_id": "sub-x",
            "multi_task_id": "multi-foo",
            "session_id": "ses-y",
            "webui_url": "http://localhost:8087",
            "analysis_file": "",
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    async def test_skipped_when_submission_id_missing(self) -> None:
        args = await self._ns(submission_id="")
        # No mock → if the function tries to PATCH, the test will fail
        # at network call time. Reaching return-None-cleanly = pass.
        await _patch_submission_row(args, _MonitorState(), "completed", 0)

    async def test_skipped_when_webui_url_missing(self) -> None:
        args = await self._ns(webui_url="")
        await _patch_submission_row(args, _MonitorState(), "completed", 0)

    async def test_skipped_when_session_id_missing(self) -> None:
        args = await self._ns(session_id="")
        await _patch_submission_row(args, _MonitorState(), "completed", 0)

    async def test_patch_called_with_correct_url_and_payload(self) -> None:
        args = await self._ns(analysis_file="/tmp/x/analysis.md")
        state = _MonitorState()
        state.trajectory = [{"epoch": 1.0, "ndcg10": 0.18}]

        # Mock aiohttp at the import site inside _patch_submission_row.
        captured: dict[str, Any] = {}

        class _FakeResp:
            status = 200
            async def text(self) -> str:
                return ""
            async def __aenter__(self):  # noqa: ANN204
                return self
            async def __aexit__(self, *a: Any) -> None:
                return None

        class _FakeSession:
            async def __aenter__(self):  # noqa: ANN204
                return self
            async def __aexit__(self, *a: Any) -> None:
                return None
            def patch(self, url: str, json: dict[str, Any], timeout: Any) -> _FakeResp:
                captured["url"] = url
                captured["json"] = json
                return _FakeResp()

        class _FakeAiohttp:
            ClientSession = _FakeSession
            class ClientTimeout:  # noqa: D106
                def __init__(self, total: float) -> None:
                    self.total = total

        with patch.dict("sys.modules", {"aiohttp": _FakeAiohttp}):
            await _patch_submission_row(args, state, "completed", 1234)

        self.assertIn(
            "/api/hubs/multi-foo/submissions/sub-x?session_id=ses-y",
            captured["url"],
        )
        body = captured["json"]
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["runFinishedAt"], 1234)
        self.assertEqual(body["finalMetrics"]["ndcg_10"], 0.18)
        self.assertEqual(body["analysisFile"], "/tmp/x/analysis.md")

    async def test_patch_failure_does_not_raise(self) -> None:
        args = await self._ns()

        class _BoomSession:
            async def __aenter__(self):  # noqa: ANN204
                return self
            async def __aexit__(self, *a: Any) -> None:
                return None
            def patch(self, *a: Any, **k: Any) -> Any:
                raise RuntimeError("network down")

        class _FakeAiohttp:
            ClientSession = _BoomSession
            class ClientTimeout:  # noqa: D106
                def __init__(self, total: float) -> None:
                    pass

        with patch.dict("sys.modules", {"aiohttp": _FakeAiohttp}):
            # Should NOT raise — best-effort PATCH-back swallows errors.
            await _patch_submission_row(args, _MonitorState(), "error", 0)
