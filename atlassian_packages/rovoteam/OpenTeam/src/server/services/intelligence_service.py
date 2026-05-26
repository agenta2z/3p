"""IntelligenceService — AI-native features: suggestions, thinking, decisions.

Separated from DataService because these map to an AI reasoning engine
in the future, not a database. MockIntelligenceService loads from
fixtures; LiveIntelligenceService will call an LLM/orchestrator.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class IntelligenceService(ABC):
    """Abstract interface for AI-native features."""

    @abstractmethod
    def get_suggested_actions(self, context: str) -> list[dict]: ...

    @abstractmethod
    def get_thinking_state(self, employee_id: str) -> dict | None: ...

    @abstractmethod
    def get_decisions(self, employee_id: str) -> list[dict]: ...

    @abstractmethod
    def get_autonomy(self, employee_id: str) -> dict | None: ...

    @abstractmethod
    def get_workload_balance(self) -> dict: ...

    @abstractmethod
    def get_predictive_timeline(self, task_id: str) -> dict | None: ...


class MockIntelligenceService(IntelligenceService):
    """Loads AI-native fixtures from JSON files."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

        self._suggested_actions = self._load_dict("suggested_actions.json")
        self._decisions = self._load_dict("decisions.json")
        self._agent_states = self._load_dict("agent_states.json")

        logger.info(
            "MockIntelligenceService loaded: %d action contexts, %d agent states, %d decision sets",
            len(self._suggested_actions),
            len(self._agent_states),
            len(self._decisions),
        )

    def _load_dict(self, filename: str) -> dict:
        path = self._fixtures_dir / filename
        if not path.exists():
            logger.warning("Intelligence fixture not found: %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def get_suggested_actions(self, context: str) -> list[dict]:
        return self._suggested_actions.get(context, [])

    def get_thinking_state(self, employee_id: str) -> dict | None:
        agent = self._agent_states.get(employee_id)
        if not agent:
            return None
        return agent.get("thinking")

    def get_decisions(self, employee_id: str) -> list[dict]:
        return self._decisions.get(employee_id, [])

    def get_autonomy(self, employee_id: str) -> dict | None:
        agent = self._agent_states.get(employee_id)
        if not agent:
            return None
        return agent.get("autonomy")

    def get_workload_balance(self) -> dict:
        entries = []
        for emp_id, state in self._agent_states.items():
            if "workload" in state:
                entries.append(state["workload"])
        return {
            "entries": entries,
            "suggestions": self._suggested_actions.get("workload_suggestions", []),
        }

    def get_predictive_timeline(self, task_id: str) -> dict | None:
        for state in self._agent_states.values():
            predictions = state.get("predictions", {})
            if task_id in predictions:
                return predictions[task_id]
        return None
