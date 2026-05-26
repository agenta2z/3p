"""Lightweight JSON persistence for resumability.

Persists:
- The set of (task_type, primary_key) currently in flight
- A mapping issue_key -> {pr_url, pr_id} once a PR is opened
- A set of (issue_key) that have been fully completed (PR merged)

The orchestrator persists on every queue mutation. On startup, it can re-hydrate
the queue from this state file.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, Set

logger = logging.getLogger(__name__)


@dataclass
class PRRecord:
    workspace: str
    repo: str
    pr_id: int
    pr_url: str


@dataclass
class OrchestratorState:
    in_flight: Set[str] = field(default_factory=set)         # "task_type:primary_key"
    issue_to_pr: Dict[str, PRRecord] = field(default_factory=dict)
    completed: Set[str] = field(default_factory=set)         # issue keys
    stuck: Set[str] = field(default_factory=set)             # issue keys whose
    # rescue failed; we won't retry these — they need human intervention.

    def to_json(self) -> str:
        return json.dumps({
            "in_flight": sorted(self.in_flight),
            "issue_to_pr": {k: asdict(v) for k, v in self.issue_to_pr.items()},
            "completed": sorted(self.completed),
            "stuck": sorted(self.stuck),
        }, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "OrchestratorState":
        d = json.loads(text)
        return cls(
            in_flight=set(d.get("in_flight", [])),
            issue_to_pr={
                k: PRRecord(**v) for k, v in d.get("issue_to_pr", {}).items()
            },
            completed=set(d.get("completed", [])),
            stuck=set(d.get("stuck", [])),
        )


_ONE_SHOT_TASK_TYPES = ("CreatePR", "RescueIssue")


def purge_stale_one_shot_markers(state: OrchestratorState) -> list[str]:
    """Drop in-flight markers for one-shot task types (CreatePR, RescueIssue).

    Rationale:
      One-shot tasks complete or fail within a single orchestrator run. If
      they're still in `in_flight` after a process restart, they're orphans —
      the worker that owned them died. Carrying them forward causes false
      idempotency hits in `MonitorEpic` (the issue is mistakenly thought to be
      under active work, so the curator skips it forever).

    Round-based markers (`MonitorEpic:*`, `MonitorPR:*`) are preserved because
    the orchestrator's seeding logic re-enqueues them; the in_flight set is
    used to de-dup the re-enqueue.

    Returns the list of purged markers (for logging).
    """
    purged: list[str] = []
    keep: set[str] = set()
    for marker in state.in_flight:
        task_type = marker.split(":", 1)[0] if ":" in marker else marker
        if task_type in _ONE_SHOT_TASK_TYPES:
            purged.append(marker)
        else:
            keep.add(marker)
    state.in_flight = keep
    return purged


def load_state(state_path: str) -> OrchestratorState:
    if not os.path.exists(state_path):
        return OrchestratorState()
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = OrchestratorState.from_json(f.read())
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Could not parse state %s, starting fresh: %s", state_path, e)
        return OrchestratorState()

    # Self-healing: purge orphaned one-shot tasks left over from prior runs.
    purged = purge_stale_one_shot_markers(state)
    if purged:
        logger.warning(
            "Purged %d stale one-shot in_flight marker(s) from prior run: %s",
            len(purged), sorted(purged),
        )
    return state


def save_state(state: OrchestratorState, state_path: str) -> None:
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    tmp_path = state_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(state.to_json())
    os.replace(tmp_path, state_path)
