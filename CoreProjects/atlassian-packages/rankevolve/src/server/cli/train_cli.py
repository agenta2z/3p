# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""``rankevolve_train`` CLI — shell-spawnable wrapper over :class:`SubmissionRunner`.

A thin (~70 LOC of substance) ``python_binary`` whose only job is to make
the existing async :class:`SubmissionRunner` callable from
:class:`ToolAsInferencer` (or from a debugging shell). Captures the
runner's lifecycle events as marker lines on stdout so the calling
inferencer can pick them up via ``marker_parsers``:

    SUBMISSION_ID:<sid>
    RUN_HOST:<host>
    RUN_LOG_PATH:<abs path>
    FLOW_URI:<url>
    MAST_JOB:<id>

…and a final JSON line on clean exit:

    {"event":"submission_complete","status":"completed|error",
     "runFinishedAt":<ms>,"flowUri":"...","mastJob":"..."}

Plan §1.3 — see ``/home/zgchen/.claude/plans/humming-tinkering-wirth.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

from rankevolve.src.common.streaming.markers import (
    STREAM_DONE_MARKER,
    STREAM_FAIL_MARKER,
)
from rankevolve.src.server.submission_runner import SubmissionRunner


logger: logging.Logger = logging.getLogger(__name__)

# Default codebase-root pattern. The caller may override via
# --codebase-root-pattern; this matches the most common fbsource/fbcode
# layout.
_DEFAULT_CODEBASE_ROOT_PATTERN: str = "**/fbsource/fbcode"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rankevolve_train",
        description=(
            "Run a generated submit_v<n>.py via SubmissionRunner. "
            "Emits stdout markers for the calling inferencer to pick up "
            "(SUBMISSION_ID:, RUN_HOST:, RUN_LOG_PATH:, FLOW_URI:, "
            "MAST_JOB:) plus a final submission_complete JSON line."
        ),
    )
    parser.add_argument("--script-path", required=True, type=Path)
    parser.add_argument("--launch-json", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--experiment-name",
        required=True,
        help="Substituted into ${EXP_NAME} in launch.json script_args",
    )
    parser.add_argument(
        "--enable-flags",
        default="",
        help=(
            "Comma-separated hypothesis IDs (e.g. 'H1,H17,H8'). "
            "Substituted into ${ENABLE_FLAGS}."
        ),
    )
    parser.add_argument(
        "--workflow-target-path",
        default="",
        help=(
            "Path under the codebase root for ${CODEBASE_ROOT} resolution. "
            "Required when launch.json uses ${CODEBASE_ROOT}."
        ),
    )
    parser.add_argument(
        "--codebase-root-pattern",
        default=_DEFAULT_CODEBASE_ROOT_PATTERN,
        help=f"Default: {_DEFAULT_CODEBASE_ROOT_PATTERN!r}",
    )
    parser.add_argument(
        "--app-layer-version",
        default="",
        help=(
            "Pre-built fbpkg version (e.g. 'fire-app:2941a32'). When "
            "empty AND --build-command is set, the runner runs the build "
            "first and parses the version from its stdout."
        ),
    )
    parser.add_argument(
        "--build-command",
        default="",
        help=(
            "Optional build command (e.g. 'cd /…/fbcode && app-layer …'). "
            "Run before spawning the submit script when --app-layer-version "
            "is empty. Allowlist enforced by the runner."
        ),
    )
    parser.add_argument(
        "--submission-id",
        default="",
        help=(
            "Pre-allocated submission id. When empty, a fresh one is "
            "generated and emitted on stdout via SUBMISSION_ID:<sid>."
        ),
    )
    parser.add_argument(
        "--launcher",
        default="",
        choices=("", "buck_run_auto", "fblearner"),
        help=(
            "Override the launcher strategy in launch.json. Empty (default) "
            "means trust launch.json's `launcher` field. 'fblearner' routes "
            "the spawn through the FBLearner SDK launcher (the script "
            "itself does the meta mast.job submit call); 'buck_run_auto' "
            "is the local-buck-run path."
        ),
    )
    return parser.parse_args(argv)


def _emit_marker(channel: str, value: str) -> None:
    """Single-line marker on stdout, immediately flushed so the calling
    ``ToolAsInferencer`` can fire its regex callback in real time."""
    sys.stdout.write(f"{channel}:{value}\n")
    sys.stdout.flush()


def _make_emit_event(submission_id: str) -> Any:
    """Build the ``emit_event`` callback the runner invokes on lifecycle
    events. We translate each event into the stdout marker contract.

    Mutates the ``last_seen`` dict so the caller can read the final state
    after the runner completes (used to build the final JSON line).
    """
    last_seen: dict[str, Any] = {}

    async def emit(event: dict[str, Any]) -> None:
        last_seen.update(event)
        # Live emit: surface URIs / job IDs as soon as they appear so the
        # monitor inferencer can attach within seconds, not at exit.
        flow_uri = event.get("flowUri")
        if flow_uri:
            _emit_marker("FLOW_URI", str(flow_uri))
        mast_job = event.get("mastJob")
        if mast_job:
            _emit_marker("MAST_JOB", str(mast_job))

    return emit, last_seen


def _emit_final_summary(
    status: str, last_seen: dict[str, Any], submission_id: str
) -> None:
    payload = {
        "event": "submission_complete",
        "submissionId": submission_id,
        "status": status,
        "runFinishedAt": last_seen.get("runFinishedAt"),
        "flowUri": last_seen.get("flowUri"),
        "mastJob": last_seen.get("mastJob"),
        "experimentId": last_seen.get("experimentId"),
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


async def _amain(args: argparse.Namespace) -> int:
    submission_id = args.submission_id or f"sub-{uuid.uuid4().hex[:8]}"
    _emit_marker("SUBMISSION_ID", submission_id)
    _emit_marker("RUN_HOST", socket.gethostname())

    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    # Mirror the canonical stream path the WebUI's WorkspaceStreamTailer
    # discovers automatically.
    stream_path = (
        workspace / "_runtime" / "inferencer_cache" / "submission" / "stream_run.txt"
    )
    _emit_marker("RUN_LOG_PATH", str(stream_path))

    enable_flags = [f for f in args.enable_flags.split(",") if f.strip()]
    emit_event, last_seen = _make_emit_event(submission_id)

    # Round 11: when --launcher is set, edit launch.json on the fly to
    # override its `launcher` field. Keeps the launcher selection a
    # single point (the registry); the runner reads launch.json verbatim.
    launch_json_path = args.launch_json.resolve()
    if args.launcher:
        try:
            launch_doc = json.loads(launch_json_path.read_text(encoding="utf-8"))
            if launch_doc.get("launcher") != args.launcher:
                launch_doc["launcher"] = args.launcher
                # Write to a sibling "_runtime" copy so the original
                # launch_v<n>.json stays unmodified (audit trail).
                runtime_dir = workspace / "_runtime"
                runtime_dir.mkdir(parents=True, exist_ok=True)
                override_path = runtime_dir / launch_json_path.name
                override_path.write_text(json.dumps(launch_doc), encoding="utf-8")
                launch_json_path = override_path
        except (OSError, ValueError) as e:
            logger.warning(
                "rankevolve_train: --launcher override failed (%s); "
                "falling back to launch.json's declared launcher.",
                e,
            )

    runner = SubmissionRunner(
        workspace=workspace,
        script_path=args.script_path.resolve(),
        enable_flags=enable_flags,
        experiment_name=args.experiment_name,
        launch_path=launch_json_path,
        emit_event=emit_event,
        workflow_target_path=args.workflow_target_path,
        codebase_root_pattern=args.codebase_root_pattern,
        app_layer_version=args.app_layer_version,
        build_command=args.build_command,
    )

    try:
        await runner.run()
        _emit_final_summary("completed", last_seen, submission_id)
        return 0
    except Exception as e:
        logger.exception(
            "rankevolve_train: SubmissionRunner.run failed: %s", e
        )
        # Surface failure as a parsable line — the caller sees both this
        # and the cache-file STREAM_FAIL_MARKER from the runner itself.
        _emit_marker("RUN_ERROR", str(e)[:500])
        _emit_final_summary("error", last_seen, submission_id)
        return 1


def main() -> None:
    """``python_binary`` entry point.

    Configures logging once, parses argv, runs the async lifecycle. Exit
    code surfaces to the calling shell / ``ToolAsInferencer.success_check``.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )
    args = _parse_args(sys.argv[1:])
    rc = asyncio.run(_amain(args))
    sys.exit(rc)


# Touch the marker constants so accidental refactors of the canonical
# names (in src/common/streaming/markers.py) surface as an import error
# at CLI startup rather than as silent drift in the cache file.
_MARKERS_USED: tuple[str, str] = (STREAM_DONE_MARKER, STREAM_FAIL_MARKER)
_ = os  # noqa: F841 — kept for potential future env-overrides
