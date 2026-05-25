# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""``rankevolve_monitor`` CLI — watch a submission workspace until terminal.

Tail :class:`WorkspaceStreamTailer` over ``<workspace>/_runtime/inferencer_cache/``
and parse epoch metrics out of stdout. On terminal (``STREAM_DONE_MARKER`` or
``STREAM_FAIL_MARKER`` observed), emit a final JSON line that the calling
inferencer can ingest as the per-combo result:

    {"event":"monitor_complete","status":"completed|error",
     "epochsCompleted":N,
     "finalMetrics":{"ndcg_10":...,"hr_10":...,"mrr":...},
     "epochTrajectory":[{"epoch":..,"ndcg10":..,...}, ...]}

While running, also emits live markers (``EPOCH:n NDCG10:v``, ``STATUS:s``,
``RUN_FINISHED_AT:ms``) so a calling ``ToolAsInferencer`` can fire its
``marker_parsers`` callbacks in real time.

Plan §1.4 — see ``/home/zgchen/.claude/plans/humming-tinkering-wirth.md``.

FBLearner polling (when ``--flow-uri`` / ``--mast-job`` are passed) is a
follow-up; this v1 covers the local-subprocess case end-to-end.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

from rankevolve.src.common.streaming.file_tailer import WorkspaceStreamTailer
from rankevolve.src.common.streaming.markers import (
    STREAM_DONE_MARKER,
    STREAM_FAIL_MARKER,
)


logger: logging.Logger = logging.getLogger(__name__)


# Default per-line metric regex. Matches lines like:
#   EPOCH:42 NDCG10:0.1872 HR10:0.3239 MRR:0.1614
# Caller may override via --metric-regex if the training script uses a
# different convention.
_DEFAULT_METRIC_REGEX: str = (
    r"^EPOCH:(?P<epoch>\d+)"
    r"(?:\s+NDCG10:(?P<ndcg10>[\d.]+))?"
    r"(?:\s+HR10:(?P<hr10>[\d.]+))?"
    r"(?:\s+MRR:(?P<mrr>[\d.]+))?"
)


class _MonitorState:
    """Mutable state accumulated as tailing progresses."""

    def __init__(self) -> None:
        self.trajectory: list[dict[str, float]] = []
        self.terminal: str | None = None  # "completed" | "error" | None

    def record_metric(self, m: re.Match[str]) -> None:
        """Capture an epoch sample. Subsequent samples for the same epoch
        overwrite the prior value (training scripts sometimes re-emit
        a final sample after early-killed signal handling)."""
        try:
            epoch = int(m.group("epoch"))
        except (TypeError, ValueError):
            return
        sample: dict[str, float] = {"epoch": float(epoch)}
        for field in ("ndcg10", "hr10", "mrr"):
            raw = m.groupdict().get(field)
            if raw is None:
                continue
            try:
                sample[field] = float(raw)
            except ValueError:
                continue
        # Replace existing entry for the same epoch if present; else append.
        for i, existing in enumerate(self.trajectory):
            if existing.get("epoch") == sample["epoch"]:
                self.trajectory[i] = sample
                return
        self.trajectory.append(sample)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rankevolve_monitor",
        description=(
            "Tail a submission workspace's stream files until terminal, "
            "parse epoch metrics, and emit a structured JSON summary on exit."
        ),
    )
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--metric-regex",
        default=_DEFAULT_METRIC_REGEX,
        help=(
            "Per-line regex with named groups (epoch, ndcg10, hr10, mrr). "
            f"Default matches 'EPOCH:n NDCG10:v ...': {_DEFAULT_METRIC_REGEX!r}"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Seconds between cache-dir scans.",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=21600.0,
        help=(
            "Seconds to wait for terminal marker before exiting with "
            "status='timeout'. Default: 6 hours."
        ),
    )
    parser.add_argument(
        "--flow-uri",
        default="",
        help="(reserved for FBLearner integration; not yet wired)",
    )
    parser.add_argument(
        "--mast-job",
        default="",
        help="(reserved for FBLearner integration; not yet wired)",
    )
    # Round 11: PATCH-back integration. When --submission-id + --webui-url
    # are set, the monitor PATCHes the row in hub_<mid>_submissions.json
    # on terminal so the WebUI sees the run complete without waiting for
    # the next FBLearnerPoller tick.
    parser.add_argument(
        "--submission-id",
        default="",
        help=(
            "Submission row id to PATCH on terminal (in hub_<mid>_submissions.json)."
        ),
    )
    parser.add_argument(
        "--multi-task-id",
        default="",
        help="Hub multi_task_id for the PATCH endpoint URL.",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Session id for the PATCH endpoint query string.",
    )
    parser.add_argument(
        "--webui-url",
        default="",
        help=(
            "Base URL of the WebUI backend (e.g. https://localhost:8087). "
            "If unset OR --submission-id is unset, PATCH-back is skipped."
        ),
    )
    parser.add_argument(
        "--analysis-file",
        default="",
        help="Optional path to a per-combo analysis.md to record on the row.",
    )
    return parser.parse_args(argv)


def _emit_marker(channel: str, value: str) -> None:
    sys.stdout.write(f"{channel}:{value}\n")
    sys.stdout.flush()


def _build_terminal_payload(
    state: _MonitorState, status: str, run_finished_at: int
) -> dict[str, Any]:
    """Construct the structured terminal payload (used by both stdout
    emission AND the PATCH-back to the WebUI hub-submissions row)."""
    final_metrics: dict[str, float] = {}
    epochs_completed = 0
    if state.trajectory:
        last = state.trajectory[-1]
        epochs_completed = int(last.get("epoch", 0))
        for field in ("ndcg10", "hr10", "mrr"):
            if field in last:
                # Backend uses "ndcg_10" / "hr_10" naming on submission
                # rows; mirror it here for downstream consumers.
                key = field.replace("ndcg10", "ndcg_10").replace("hr10", "hr_10")
                final_metrics[key] = last[field]
    return {
        "status": status,
        "epochsCompleted": epochs_completed,
        "finalMetrics": final_metrics,
        "epochTrajectory": state.trajectory,
        "runFinishedAt": run_finished_at,
    }


def _emit_final(state: _MonitorState, status: str, run_finished_at: int) -> None:
    payload = _build_terminal_payload(state, status, run_finished_at)
    payload["event"] = "monitor_complete"
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


async def _patch_submission_row(
    args: argparse.Namespace,
    state: _MonitorState,
    status: str,
    run_finished_at: int,
) -> None:
    """PATCH the hub-submissions row with the terminal state.

    Best-effort: failures are logged at WARNING and never propagate. The
    stdout terminal payload + cache-file STREAM_DONE_MARKER stay as the
    source of truth; this just lets the WebUI react sooner than the
    FBLearnerPoller's 30s tick.

    Activated only when ALL of --submission-id, --multi-task-id,
    --session-id, --webui-url are set (otherwise: silent no-op).
    """
    if not (
        args.submission_id
        and args.multi_task_id
        and args.session_id
        and args.webui_url
    ):
        return
    payload = _build_terminal_payload(state, status, run_finished_at)
    if args.analysis_file:
        payload["analysisFile"] = args.analysis_file
    url = (
        args.webui_url.rstrip("/")
        + f"/api/hubs/{args.multi_task_id}/submissions/{args.submission_id}"
        + f"?session_id={args.session_id}"
    )
    try:
        # Lazy-import: aiohttp is not in the monitor's normal deps; if
        # absent we fall back to urllib in a thread.
        try:
            import aiohttp  # @manual

            async with aiohttp.ClientSession() as sess:
                async with sess.patch(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        logger.warning(
                            "PATCH %s returned %s: %s", url, resp.status, body[:200]
                        )
        except ImportError:
            import urllib.request

            def _do_patch() -> None:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="PATCH",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                    if resp.status >= 400:
                        logger.warning(
                            "PATCH %s returned %s", url, resp.status
                        )

            await asyncio.to_thread(_do_patch)
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning(
            "PATCH-back to %s failed: %s; stdout terminal payload is "
            "still authoritative",
            url,
            e,
        )


async def _amain(args: argparse.Namespace) -> int:
    workspace = args.workspace.resolve()
    cache_dir = workspace / "_runtime" / "inferencer_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(args.metric_regex)
    state = _MonitorState()
    deadline = time.monotonic() + args.max_wait

    tailer = WorkspaceStreamTailer(
        cache_dir=str(cache_dir),
        poll_interval=args.poll_interval,
        replay_existing=True,  # monitor may attach mid-stream; replay catches up
    )

    async def on_chunk(content: str, _meta: dict[str, Any]) -> None:
        for line in content.splitlines():
            if STREAM_DONE_MARKER in line:
                state.terminal = "completed"
                _emit_marker("STATUS", "completed")
                tailer.stop()
                continue
            if STREAM_FAIL_MARKER in line:
                state.terminal = "error"
                _emit_marker("STATUS", "error")
                tailer.stop()
                continue
            m = pattern.search(line)
            if m is None:
                continue
            state.record_metric(m)
            # Live emit so a caller's marker_parsers can update progress.
            ndcg = m.groupdict().get("ndcg10")
            if ndcg is not None:
                _emit_marker("EPOCH", f"{m.group('epoch')} NDCG10:{ndcg}")
            else:
                _emit_marker("EPOCH", m.group("epoch"))

    async def deadline_watchdog() -> None:
        while tailer._running:  # pyre-ignore[16] — internal flag, fine for CLI
            if time.monotonic() >= deadline:
                logger.warning(
                    "rankevolve_monitor: max-wait %.0fs elapsed without "
                    "terminal marker; exiting with status='timeout'",
                    args.max_wait,
                )
                if state.terminal is None:
                    state.terminal = "error"  # treat timeout as failure
                tailer.stop()
                return
            await asyncio.sleep(min(5.0, args.max_wait / 10.0))

    watchdog = asyncio.create_task(deadline_watchdog())
    try:
        await tailer.tail(on_chunk)
    finally:
        watchdog.cancel()
        try:
            await watchdog
        except asyncio.CancelledError:
            pass

    finished_at = int(time.time() * 1000)
    _emit_marker("RUN_FINISHED_AT", str(finished_at))
    final_status = state.terminal or "error"
    # PATCH-back to hub_*_submissions.json BEFORE the final stdout payload
    # so the WebUI sees the terminal state in the row by the time the
    # caller (typically a ToolAsInferencer) processes the JSON line.
    await _patch_submission_row(args, state, final_status, finished_at)
    _emit_final(state, final_status, finished_at)
    return 0 if final_status == "completed" else 1


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )
    args = _parse_args(sys.argv[1:])
    rc = asyncio.run(_amain(args))
    sys.exit(rc)
