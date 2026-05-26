"""Pydantic models for the OpenTeam AI Company Dashboard."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EmployeeType(str, Enum):
    ai = "ai"
    human = "human"


class EmployeeStatus(str, Enum):
    active = "active"
    idle = "idle"
    blocked = "blocked"
    away = "away"


class ProjectStatus(str, Enum):
    in_progress = "in-progress"
    planning = "planning"
    completed = "completed"
    on_hold = "on-hold"


class TaskStatus(str, Enum):
    backlog = "backlog"
    in_progress = "in-progress"
    in_review = "in-review"
    done = "done"
    blocked = "blocked"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DecisionStatus(str, Enum):
    approved = "approved"
    auto_approved = "auto_approved"
    pending = "pending"
    rejected = "rejected"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ---------------------------------------------------------------------------
# Summary models (lightweight references embedded in other models)
# ---------------------------------------------------------------------------

class EmployeeSummary(BaseModel):
    id: str
    name: str
    type: EmployeeType
    role: str
    status: EmployeeStatus


class TaskSummary(BaseModel):
    id: str
    title: str
    status: TaskStatus
    priority: Priority
    progress_percent: float
    assignee_ids: list[str] = []


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class Employee(BaseModel):
    id: str
    name: str
    type: EmployeeType
    role: str
    status: EmployeeStatus
    avatar_url: str
    team_ids: list[str] = []
    current_task_id: str | None = None
    specializations: list[str] = []
    metrics: dict[str, Any] = {}


class Team(BaseModel):
    id: str
    name: str
    description: str
    member_ids: list[str] = []
    project_ids: list[str] = []
    stats: dict[str, Any] = {}


class AIReport(BaseModel):
    generated_at: datetime
    summary: str
    highlights: list[str] = []
    blockers: list[str] = []
    velocity_trend: str


class AIRecommendation(BaseModel):
    type: str
    message: str
    priority: Severity
    action: dict[str, Any] | None = None


class QuickLink(BaseModel):
    label: str
    url: str
    icon: str


class Project(BaseModel):
    id: str
    name: str
    status: ProjectStatus
    blockers: int
    progress_percent: float
    due_date: datetime
    team_id: str
    sprint: dict[str, Any] = {}
    team_composition: dict[str, Any] = {}
    ai_agent_ids: list[str] = []
    human_member_ids: list[str] = []
    task_ids: list[str] = []
    ai_report: AIReport | None = None
    ai_recommendations: list[AIRecommendation] = []
    quick_links: list[QuickLink] = []


class Task(BaseModel):
    id: str
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    project_id: str
    assignee_ids: list[str] = []
    dependency_ids: list[str] = []
    progress_percent: float
    created_at: datetime
    updated_at: datetime
    due_date: datetime
    estimated_hours: float | None = None
    tags: list[str] = []


class ActivityEntry(BaseModel):
    timestamp: datetime
    type: str
    message: str
    actor_id: str | None = None


class Sprint(BaseModel):
    id: str
    project_id: str
    number: int
    start_date: datetime
    end_date: datetime
    columns: dict[str, Any] = {}
    summary: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Conversation models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    timestamp: datetime
    content: str
    mentions: list[str] = []


class Conversation(BaseModel):
    id: str
    topic: str
    project_id: str | None = None
    related_task_id: str | None = None
    participant_ids: list[str] = []
    started_at: datetime
    last_message_at: datetime
    messages: list[Message] = []


# ---------------------------------------------------------------------------
# Intelligence models
# ---------------------------------------------------------------------------

class SuggestedAction(BaseModel):
    id: str
    severity: Severity
    message: str
    context: str
    actions: list[dict[str, Any]] = []
    related_entity: dict[str, Any] = {}


class Decision(BaseModel):
    id: str
    employee_id: str
    timestamp: datetime
    decision: str
    reasoning: str
    scope: str
    status: DecisionStatus
    approved_by: str | None = None
    actions: list[dict[str, Any]] = []


class ThinkingState(BaseModel):
    employee_id: str
    is_thinking: bool
    current_thought: str | None = None
    thinking_about_task_id: str | None = None
    last_action: ActivityEntry | None = None


class AutonomyConfig(BaseModel):
    employee_id: str
    level: str
    description: str
    recent_autonomous_decisions: list[str] = []
    pending_approvals: list[Decision] = []


class PredictiveTimeline(BaseModel):
    task_id: str
    estimated_completion: datetime
    confidence: str
    confidence_reason: str
    risk_factors: list[str] = []
    margin_hours: float


class WorkloadEntry(BaseModel):
    employee_id: str
    employee_name: str
    utilization_percent: float
    status: str
    current_task: str | None = None
    queue_depth: int


class WorkloadBalance(BaseModel):
    entries: list[WorkloadEntry] = []
    suggestions: list[dict[str, Any]] = []
