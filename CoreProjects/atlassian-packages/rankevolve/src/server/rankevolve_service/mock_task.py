# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Mock task runner for UI testing.

Creates a realistic task workspace and simulates phased progress
(planning -> implementation) with delays. Writes streaming content to
_runtime/inferencer_cache/ files so the WorkspaceStreamTailer delivers
tokens to the UI through the normal file-based streaming path.

Usage: /task --mock <request>
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_foundation.ui.interactive_base import (
    InteractionFlags,
)
from rankevolve.src.common.streaming.markers import STREAM_DONE_MARKER
from rankevolve.src.server.rankevolve_service import message_protocol as proto
from rankevolve.src.server.workflow_context import WorkflowPhaseRecord

logger = logging.getLogger(__name__)

# Phase delays (seconds)
_PLAN_ROUND_DELAY = 5.0
_IMPL_STEP_DELAY = 5.0
_STREAM_CHUNK_DELAY = 0.5


async def run_mock_task(
    session: Any,
    session_id: str,
    task_id: str,
    request: str,
    tasks_dir: Path | None,
) -> None:
    """Simulate a full task lifecycle for UI testing.

    Writes streaming content to inferencer_cache/ files which the
    WorkspaceStreamTailer in the bridge tails and delivers to the UI.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Round 9: per-session layout — caller MUST pass tasks_dir derived from
    # session.session_tasks_dir. The legacy global fallback was removed when
    # the flat <server>/tasks/ directory was retired.
    if tasks_dir is None:
        raise ValueError(
            "mock_task.run_mock_task requires an explicit tasks_dir "
            "(per-session: session.session_tasks_dir). The legacy global "
            "rankevolve/_runtime/tasks/ fallback has been removed."
        )
    base_dir = tasks_dir
    workspace = base_dir / f"task_{timestamp}"

    # Create directory structure
    for subdir in [
        "outputs",
        "results",
        "analysis",
        "checkpoints/pti",
        "logs/session",
        "_runtime/inferencer_cache",
        "_runtime/tmp_output_files",
    ]:
        (workspace / subdir).mkdir(parents=True, exist_ok=True)

    # Write request
    (workspace / "request.txt").write_text(request + "\n", encoding="utf-8")

    # Update workflow context
    session.workflow_context.current_phase = "3"
    session.workflow_context.phase_status = "running"
    session.workflow_context.active_task_summary = f"[mock] {request[:60]}"
    session.workflow_context.active_workspace = str(workspace)

    # Send starting status — this triggers the WorkspaceStreamTailer in the bridge.
    # Use _send_response directly to bypass iter_() which breaks dicts into keys.
    await asyncio.to_thread(
        session.interactive._send_response,
        {
            "type": proto.TASK_STATUS,
            "session_id": session_id,
            "task_id": task_id,
            "status": "starting",
            "request": request[:80],
            "workspace": str(workspace),
        },
        InteractionFlags.MessageOnly,
    )

    cache_dir = workspace / "_runtime" / "inferencer_cache"

    # Phase 1: Planning (~20s)
    await _mock_planning_phase(session, session_id, workspace, cache_dir, request)

    # Phase 2: Implementation (~20s)
    await _mock_implementation_phase(session, session_id, workspace, cache_dir, request)

    # Completion
    session.workflow_context.phase_status = "completed"
    session.workflow_context.completed_phases.append(
        WorkflowPhaseRecord(
            phase="3",
            status="completed",
            summary=f"[mock] {request[:60]}",
            workspace_path=str(workspace),
            task_id=task_id,
        )
    )
    session.workflow_context.active_task_summary = ""

    await asyncio.to_thread(
        session.interactive._send_response,
        {
            "type": proto.TASK_STATUS,
            "session_id": session_id,
            "task_id": task_id,
            "status": "completed",
            "workspace": str(workspace),
        },
        InteractionFlags.TurnCompleted,
    )
    session.info.active_task_id = None
    logger.info("Mock task %s completed (workspace: %s)", task_id, workspace)


async def _write_stream_chunks(
    stream_file: Path,
    chunks: list[str],
    delay: float = _STREAM_CHUNK_DELAY,
) -> None:
    """Write text chunks incrementally to a stream file for the tailer to pick up.

    The WorkspaceStreamTailer polls for file growth, so we append chunks
    with delays to simulate real-time streaming. Finally writes the
    STREAM_DONE_MARKER so the tailer knows this file is complete.
    """
    with open(stream_file, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk)
            f.flush()
            await asyncio.sleep(delay)
        f.write("\n" + STREAM_DONE_MARKER + "\n")
        f.flush()


async def _mock_planning_phase(
    session: Any,
    session_id: str,
    workspace: Path,
    cache_dir: Path,
    request: str,
) -> None:
    """Simulate the planning phase with iterative rounds."""
    plan_texts = [
        _mock_plan_round_0(request),
        _mock_plan_round_1(request),
        _mock_plan_round_2(request),
        _mock_plan_round_3(request),
    ]

    # Create cache subdirectory for planning phase
    # Directory name must contain "_plan_" and "_base_" for the tailer to
    # assign phase="plan" and role="base" metadata.
    plan_cache_dir = cache_dir / "mock_base_plan_phase"
    plan_cache_dir.mkdir(parents=True, exist_ok=True)

    # Stream planning content to cache file
    plan_stream_file = plan_cache_dir / "stream_plan.txt"

    plan_stream_chunks = [
        f"## [MOCK] Planning Phase\n\nAnalyzing request: {request}\n\n",
        "Starting iterative planning with consensus...\n\n",
    ]

    for i, plan_text in enumerate(plan_texts):
        # Write round plan to outputs
        (workspace / "outputs" / f"round{i}_plan.md").write_text(
            plan_text, encoding="utf-8"
        )

        # Write iteration artifacts to results
        proposal = f"Proposal for iteration {i + 1}:\n\n{plan_text[:500]}"
        (workspace / "results" / f"plan_attempt_1_iter_{i + 1}_proposal.txt").write_text(
            proposal, encoding="utf-8"
        )
        review = {
            "iteration": i + 1,
            "verdict": "needs_revision" if i < 3 else "approved",
            "issues": [
                {"severity": "MINOR", "description": f"Mock issue {j + 1}"}
                for j in range(max(0, 3 - i))
            ],
        }
        (workspace / "results" / f"plan_attempt_1_iter_{i + 1}_review.json").write_text(
            json.dumps(review, indent=2) + "\n", encoding="utf-8"
        )
        if i < 3:
            feedback = {
                "iteration": i + 1,
                "feedback": f"Address the {3 - i} remaining issue(s) in the next revision.",
            }
            (
                workspace / "results" / f"plan_attempt_1_iter_{i + 1}_counter_feedback.json"
            ).write_text(json.dumps(feedback, indent=2) + "\n", encoding="utf-8")

        verdict = "needs revision" if i < 3 else "APPROVED - consensus reached"
        plan_stream_chunks.append(
            f"### Round {i + 1}/4\n\n"
            f"Review: {verdict}\n\n"
        )

    plan_stream_chunks.append(
        "Planning phase complete. Consensus achieved after 4 iterations.\n\n"
    )

    # Write all chunks with delays — tailer picks them up in real time
    await _write_stream_chunks(plan_stream_file, plan_stream_chunks, _PLAN_ROUND_DELAY)

    # Write final plan artifacts
    final_plan = plan_texts[-1]
    (workspace / "results" / "plan_final_output.txt").write_text(
        final_plan, encoding="utf-8"
    )
    (workspace / "results" / "plan_consensus_summary.json").write_text(
        json.dumps(
            {"phase": "plan", "consensus_achieved": True, "total_iterations": 4},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "results" / "plan_consensus_history.json").write_text(
        json.dumps(
            {
                "history": [
                    {"round": i + 1, "verdict": "needs_revision" if i < 3 else "approved"}
                    for i in range(4)
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "outputs" / ".plan_completed").write_text(
        json.dumps(
            {
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "step": "plan",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


async def _mock_implementation_phase(
    session: Any,
    session_id: str,
    workspace: Path,
    cache_dir: Path,
    request: str,
) -> None:
    """Simulate the implementation phase."""
    # Create cache subdirectory for implementation phase
    # "_implementation_" and "_base_" in name for tailer metadata
    impl_cache_dir = cache_dir / "mock_base_implementation_phase"
    impl_cache_dir.mkdir(parents=True, exist_ok=True)

    impl_stream_file = impl_cache_dir / "stream_impl.txt"

    impl_text = _mock_implementation(request)
    impl_chunks = [
        "## [MOCK] Implementation Phase\n\n",
        "Generating implementation based on approved plan...\n\n",
        "### Step 1: Code Generation\n\n",
        f"```python\n{impl_text[:400]}\n```\n\n",
        "### Step 2: Code Review\n\n",
        "Reviewing generated code for correctness and style...\n\n"
        "- Syntax: PASS\n"
        "- Logic: PASS\n"
        "- Style: PASS (minor formatting suggestions)\n\n",
        "### Step 3: Finalization\n\n",
        "Implementation complete. All checks passed.\n\n"
        f"Workspace: {workspace}\n\n",
    ]

    await _write_stream_chunks(impl_stream_file, impl_chunks, _IMPL_STEP_DELAY)


# ── Mock content generators ──────────────────────────────────────


def _mock_plan_round_0(request: str) -> str:
    return f"""## Context

{request}

## Initial Analysis

This is a mock planning output (round 0) for UI testing purposes.
The task involves understanding the requirements, identifying affected components,
and proposing an implementation strategy.

### Components Identified

1. **Core module** — Primary logic changes needed
2. **Test suite** — Unit and integration tests to add
3. **Configuration** — Config schema updates if any

### Approach

- Phase 1: Analyze existing code and dependencies
- Phase 2: Implement core changes
- Phase 3: Add tests and documentation

### Risks

- Backward compatibility with existing consumers
- Performance impact on hot paths
"""


def _mock_plan_round_1(request: str) -> str:
    return f"""## Context

{request}

## Revised Plan (Round 1)

Incorporating reviewer feedback on the initial proposal.

### Key Changes from Round 0

1. Added error handling strategy for edge cases
2. Refined the testing approach to include property-based tests
3. Added rollback mechanism for safe deployment

### Detailed Implementation Steps

1. Create new module `core/handler.py` with the primary logic
2. Add configuration schema validation
3. Implement the main processing pipeline
4. Add comprehensive test coverage (unit + integration)
5. Update documentation and changelog

### Dependencies

- No new external dependencies required
- Internal dependency on `utils.validation` module
"""


def _mock_plan_round_2(request: str) -> str:
    return f"""## Context

{request}

## Refined Plan (Round 2)

Further refinements based on iteration 2 review.

### Improvements

1. Simplified the processing pipeline to reduce complexity
2. Added caching layer for repeated operations
3. Improved error messages for better debugging

### Final Architecture

```
request -> validate -> process -> cache -> respond
                          |
                          v
                      [fallback]
```

### Test Plan

- 15 unit tests covering core logic
- 3 integration tests for end-to-end flow
- 2 performance benchmarks
"""


def _mock_plan_round_3(request: str) -> str:
    return f"""## Context

{request}

## Final Plan (Round 3 — Approved)

This plan has achieved consensus after addressing all reviewer concerns.

### Summary

The implementation adds a new processing pipeline that handles the request
efficiently with proper error handling, caching, and comprehensive tests.

### Implementation Checklist

- [x] Core module implementation
- [x] Configuration schema
- [x] Error handling strategy
- [x] Caching layer
- [x] Unit tests (15 cases)
- [x] Integration tests (3 cases)
- [x] Performance benchmarks (2 cases)
- [x] Documentation updates

### Estimated Impact

- ~200 lines of new code
- ~150 lines of test code
- No breaking changes to public API
"""


def _mock_implementation(request: str) -> str:
    return f'''# Auto-generated implementation for: {request}
# [MOCK] This is simulated code for UI testing

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MockProcessor:
    """Processes requests based on the approved plan."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {{}}
        self._cache: dict[str, Any] = {{}}

    def process(self, request: str) -> dict[str, Any]:
        """Process a request and return results."""
        if request in self._cache:
            logger.info("Cache hit for request")
            return self._cache[request]

        result = self._do_process(request)
        self._cache[request] = result
        return result

    def _do_process(self, request: str) -> dict[str, Any]:
        """Core processing logic."""
        return {{
            "status": "success",
            "request": request,
            "output": "Mock processing complete",
        }}
'''
