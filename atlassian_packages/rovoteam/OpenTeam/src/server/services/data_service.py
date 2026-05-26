"""DataService — pure data access with no AI logic.

Defines the abstract DataService interface and MockDataService implementation.
MockDataService loads JSON fixtures at startup, builds O(1) lookup indices,
and resolves relationships on-the-fly when returning detail views.

To swap for a real backend, implement LiveDataService(DataService) that
calls your actual database/API — no route changes needed.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _primary_agent_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Use the first assistant message as the session's primary agent (for list grouping)."""
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        agent_id = msg.get("agent_id")
        agent_name = msg.get("agent_name")
        if agent_id is not None or agent_name is not None:
            return {
                "id": agent_id,
                "name": agent_name or (str(agent_id) if agent_id is not None else "Assistant"),
            }
    return {"id": None, "name": "New conversation"}


class DataService(ABC):
    """Abstract interface for data access."""

    # ── Teams ────────────────────────────────────────────────────
    @abstractmethod
    def get_teams(self) -> list[dict]: ...

    @abstractmethod
    def get_team(self, team_id: str, *, resolve: list[str] | None = None) -> dict | None: ...

    # ── Projects ─────────────────────────────────────────────────
    @abstractmethod
    def get_projects(self, *, status: str | None = None, team_id: str | None = None) -> list[dict]: ...

    @abstractmethod
    def get_project(self, project_id: str) -> dict | None: ...

    @abstractmethod
    def get_sprint(self, project_id: str, sprint_number: int | None = None) -> dict | None: ...

    # ── Tasks ────────────────────────────────────────────────────
    @abstractmethod
    def get_tasks(
        self,
        *,
        project_id: str | None = None,
        assignee_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ) -> list[dict]: ...

    @abstractmethod
    def get_task(self, task_id: str) -> dict | None: ...

    # ── Employees ────────────────────────────────────────────────
    @abstractmethod
    def get_employees(
        self,
        *,
        type_filter: str | None = None,
        team_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]: ...

    @abstractmethod
    def get_employee(self, employee_id: str) -> dict | None: ...

    @abstractmethod
    def get_task_queue(self, employee_id: str) -> list[dict]: ...

    # ── Conversations ────────────────────────────────────────────
    @abstractmethod
    def get_conversations(
        self, *, participant_id: str | None = None, project_id: str | None = None
    ) -> list[dict]: ...

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> dict | None: ...

    # ── Role Skills ──────────────────────────────────────────────
    @abstractmethod
    def get_role_skills(self) -> dict: ...

    @abstractmethod
    def get_role_skill_pool(self, role: str) -> dict | None: ...

    # ── Role Configs ──────────────────────────────────────────────
    @abstractmethod
    def get_role_configs(self) -> dict: ...

    @abstractmethod
    def get_role_config(self, role: str) -> dict | None: ...

    # ── Manager Sessions ─────────────────────────────────────────
    @abstractmethod
    def get_sessions(self) -> list[dict]: ...

    @abstractmethod
    def get_session(self, session_id: str) -> dict | None: ...

    # ── Dashboard ────────────────────────────────────────────────
    @abstractmethod
    def get_dashboard_summary(self) -> dict: ...

    # ── Resolution helpers ───────────────────────────────────────
    @abstractmethod
    def resolve_employee_summary(self, employee_id: str) -> dict | None: ...

    @abstractmethod
    def resolve_task_summary(self, task_id: str) -> dict | None: ...


class MockDataService(DataService):
    """Loads JSON fixtures at startup, serves queries from memory."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

        self._teams = self._load("teams.json")
        self._projects = self._load("projects.json")
        self._tasks = self._load("tasks.json")
        self._employees = self._load("employees.json")
        self._conversations = self._load("conversations.json")
        self._sprints = self._load("sprints.json")
        self._sessions = self._load("manager_sessions.json")
        self._role_skills = self._load_dict("role_skills.json")
        self._role_configs = self._load_dict("role_configs.json")

        # Build O(1) lookup indices
        self._team_idx: dict[str, dict] = {t["id"]: t for t in self._teams}
        self._project_idx: dict[str, dict] = {p["id"]: p for p in self._projects}
        self._task_idx: dict[str, dict] = {t["id"]: t for t in self._tasks}
        self._employee_idx: dict[str, dict] = {e["id"]: e for e in self._employees}
        self._conversation_idx: dict[str, dict] = {c["id"]: c for c in self._conversations}
        self._sprint_idx: dict[tuple[str, int], dict] = {}
        for s in self._sprints:
            self._sprint_idx[(s["project_id"], s["number"])] = s
        self._session_idx: dict[str, dict] = {s["id"]: s for s in self._sessions}

        logger.info(
            "MockDataService loaded: %d teams, %d projects, %d tasks, %d employees, %d conversations, %d sprints",
            len(self._teams), len(self._projects), len(self._tasks),
            len(self._employees), len(self._conversations), len(self._sprints),
        )

    def _load(self, filename: str) -> list[dict]:
        path = self._fixtures_dir / filename
        if not path.exists():
            logger.warning("Fixture file not found: %s", path)
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def _load_dict(self, filename: str) -> dict:
        path = self._fixtures_dir / filename
        if not path.exists():
            logger.warning("Fixture file not found: %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    # ── Teams ────────────────────────────────────────────────────

    def get_teams(self) -> list[dict]:
        return self._teams

    def get_team(self, team_id: str, *, resolve: list[str] | None = None) -> dict | None:
        team = self._team_idx.get(team_id)
        if not team:
            return None
        result = {**team}
        resolve = resolve or []
        if "members" in resolve:
            result["members"] = [
                self.resolve_employee_summary(eid)
                for eid in team.get("member_ids", [])
                if self.resolve_employee_summary(eid)
            ]
        if "projects" in resolve:
            result["projects"] = [
                {"id": p["id"], "name": p["name"], "status": p["status"], "progress_percent": p["progress_percent"]}
                for pid in team.get("project_ids", [])
                if (p := self._project_idx.get(pid))
            ]
        return result

    # ── Projects ─────────────────────────────────────────────────

    def get_projects(self, *, status: str | None = None, team_id: str | None = None) -> list[dict]:
        result = self._projects
        if status:
            result = [p for p in result if p.get("status") == status]
        if team_id:
            result = [p for p in result if p.get("team_id") == team_id]
        return result

    def get_project(self, project_id: str) -> dict | None:
        raw = self._project_idx.get(project_id)
        if not raw:
            return None
        return {
            **raw,
            "agents": [
                self.resolve_employee_summary(eid)
                for eid in raw.get("ai_agent_ids", [])
                if self.resolve_employee_summary(eid)
            ],
            "humans": [
                self.resolve_employee_summary(eid)
                for eid in raw.get("human_member_ids", [])
                if self.resolve_employee_summary(eid)
            ],
            "tasks_resolved": [
                self.resolve_task_summary(t["id"])
                for t in self._tasks
                if t.get("project_id") == project_id
            ],
        }

    def get_sprint(self, project_id: str, sprint_number: int | None = None) -> dict | None:
        if sprint_number:
            return self._sprint_idx.get((project_id, sprint_number))
        # Return current sprint (highest number for this project)
        proj = self._project_idx.get(project_id)
        if not proj:
            return None
        current = proj.get("sprint", {}).get("current", 1)
        return self._sprint_idx.get((project_id, current))

    # ── Tasks ────────────────────────────────────────────────────

    def get_tasks(
        self,
        *,
        project_id: str | None = None,
        assignee_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ) -> list[dict]:
        result = self._tasks
        if project_id:
            result = [t for t in result if t.get("project_id") == project_id]
        if assignee_id:
            result = [t for t in result if assignee_id in t.get("assignee_ids", [])]
        if status:
            result = [t for t in result if t.get("status") == status]
        if priority:
            result = [t for t in result if t.get("priority") == priority]
        return result

    def get_task(self, task_id: str) -> dict | None:
        raw = self._task_idx.get(task_id)
        if not raw:
            return None
        return {
            **raw,
            "project": {
                "id": p["id"], "name": p["name"]
            } if (p := self._project_idx.get(raw.get("project_id", ""))) else None,
            "assignees": [
                self.resolve_employee_summary(eid)
                for eid in raw.get("assignee_ids", [])
                if self.resolve_employee_summary(eid)
            ],
            "dependencies": [
                {"id": d["id"], "title": d["title"], "status": d["status"]}
                for did in raw.get("dependency_ids", [])
                if (d := self._task_idx.get(did))
            ],
        }

    # ── Employees ────────────────────────────────────────────────

    def get_employees(
        self,
        *,
        type_filter: str | None = None,
        team_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        result = self._employees
        if type_filter:
            result = [e for e in result if e.get("type") == type_filter]
        if team_id:
            result = [e for e in result if team_id in e.get("team_ids", [])]
        if status:
            result = [e for e in result if e.get("status") == status]
        return result

    def get_employee(self, employee_id: str) -> dict | None:
        raw = self._employee_idx.get(employee_id)
        if not raw:
            return None
        # Resolve current task
        current_task = None
        if raw.get("current_task_id"):
            t = self._task_idx.get(raw["current_task_id"])
            if t:
                proj = self._project_idx.get(t.get("project_id", ""))
                current_task = {
                    "id": t["id"],
                    "title": t["title"],
                    "project": {"id": proj["id"], "name": proj["name"]} if proj else None,
                    "progress_percent": t.get("progress_percent", 0),
                    "due_date": t.get("due_date"),
                }
        # Resolve teams
        teams = [
            {"id": tm["id"], "name": tm["name"]}
            for tid in raw.get("team_ids", [])
            if (tm := self._team_idx.get(tid))
        ]
        return {**raw, "current_task": current_task, "teams": teams}

    def get_task_queue(self, employee_id: str) -> list[dict]:
        emp = self._employee_idx.get(employee_id)
        if not emp:
            return []
        return emp.get("task_queue", [])

    # ── Conversations ────────────────────────────────────────────

    def get_conversations(
        self, *, participant_id: str | None = None, project_id: str | None = None
    ) -> list[dict]:
        result = self._conversations
        if participant_id:
            result = [c for c in result if participant_id in c.get("participant_ids", [])]
        if project_id:
            result = [c for c in result if c.get("project_id") == project_id]
        # Return summaries (without full message lists)
        return [
            {
                "id": c["id"],
                "topic": c["topic"],
                "project_id": c.get("project_id"),
                "participant_ids": c.get("participant_ids", []),
                "last_message_at": c.get("last_message_at"),
                "message_count": len(c.get("messages", [])),
            }
            for c in result
        ]

    def get_conversation(self, conversation_id: str) -> dict | None:
        raw = self._conversation_idx.get(conversation_id)
        if not raw:
            return None
        # Resolve participants
        participants = [
            self.resolve_employee_summary(pid)
            for pid in raw.get("participant_ids", [])
            if self.resolve_employee_summary(pid)
        ]
        return {**raw, "participants": participants}

    # ── Role Skills ──────────────────────────────────────────────

    def get_role_skills(self) -> dict:
        return self._role_skills

    def get_role_skill_pool(self, role: str) -> dict | None:
        return self._role_skills.get(role)

    # ── Role Configs ──────────────────────────────────────────────

    def get_role_configs(self) -> dict:
        return self._role_configs

    def get_role_config(self, role: str) -> dict | None:
        return self._role_configs.get(role)

    # ── Manager Sessions ─────────────────────────────────────────

    def get_sessions(self) -> list[dict]:
        out: list[dict] = []
        for s in self._sessions:
            messages = s.get("messages", [])
            out.append(
                {
                    "id": s["id"],
                    "title": s["title"],
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at"),
                    "message_count": len(messages),
                    "primary_agent": _primary_agent_from_messages(messages),
                }
            )
        return out

    def get_session(self, session_id: str) -> dict | None:
        return self._session_idx.get(session_id)

    # ── Dashboard ────────────────────────────────────────────────

    def get_dashboard_summary(self) -> dict:
        ai_count = sum(1 for e in self._employees if e.get("type") == "ai")
        human_count = len(self._employees) - ai_count
        tasks_by_status: dict[str, int] = {}
        for t in self._tasks:
            s = t.get("status", "unknown")
            tasks_by_status[s] = tasks_by_status.get(s, 0) + 1
        blockers = sum(1 for t in self._tasks if t.get("status") == "blocked")

        return {
            "total_teams": len(self._teams),
            "total_projects": len(self._projects),
            "total_tasks": len(self._tasks),
            "total_employees": len(self._employees),
            "ai_agents": ai_count,
            "humans": human_count,
            "tasks_by_status": tasks_by_status,
            "active_blockers": blockers,
            "overall_velocity": sum(t.get("stats", {}).get("sprint_velocity", 0) for t in self._teams),
            "projects_summary": [
                {"id": p["id"], "name": p["name"], "status": p["status"], "progress_percent": p["progress_percent"]}
                for p in self._projects
            ],
            "active_conversations": len(self._conversations),
        }

    # ── Resolution helpers ───────────────────────────────────────

    def resolve_employee_summary(self, employee_id: str) -> dict | None:
        e = self._employee_idx.get(employee_id)
        if not e:
            return None
        return {
            "id": e["id"],
            "name": e["name"],
            "type": e.get("type", "human"),
            "role": e.get("role", ""),
            "status": e.get("status", "active"),
        }

    def resolve_task_summary(self, task_id: str) -> dict | None:
        t = self._task_idx.get(task_id)
        if not t:
            return None
        return {
            "id": t["id"],
            "title": t["title"],
            "status": t.get("status", "backlog"),
            "priority": t.get("priority", "medium"),
            "progress_percent": t.get("progress_percent", 0),
            "assignee_ids": t.get("assignee_ids", []),
        }
