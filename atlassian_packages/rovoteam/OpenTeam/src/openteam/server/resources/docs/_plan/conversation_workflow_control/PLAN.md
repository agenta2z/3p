# Conversation Workflow Control — Implementation Plan

> **Goal:** Wire the same SOP-driven workflow state management that RankEvolve uses into OpenTeam's conversation sessions, so every prompt turn receives `workflow_status`, `workflow_description`, `workflow_nextstep_guidance`, and phase-tracking — exactly as in RankEvolve.

---

## 1. Current State Analysis

### 1.1 What RankEvolve Does (the reference pattern)

RankEvolve has a fully wired workflow-controlled conversation system with these key layers:

| Layer | Class / File | Responsibility |
|---|---|---|
| **Workflow state** | `WorkflowContext` (`server/workflow_context.py`) | Tracks phase lifecycle, `to_status_text()`, serialization |
| **Session data** | `RankEvolveSession` (`rankevolve_service/session.py`) | Owns `workflow_context`, computes `session_context` dict each turn |
| **Session info** | `RankEvolveSessionInfo` (`rankevolve_service/session_info.py`) | Extends `SessionInfo` with `workflow_target_path`, `session_root_path` |
| **Message handling** | `RankEvolveMessageHandlers._handle_chat()` | Calls `inferencer.set_prior_context(session.session_context)` before each turn |
| **Inferencer** | `ConversationalInferencer` (AgentFoundation) | Renders prompt with `prior_context`, runs SOP-aware agentic loop |
| **Prompt template** | `conversation/main/initial.jinja2` | Guards on `{% if workflow_target_path is defined %}`, renders status/guidance |
| **SOP** | `_variables/workflow/sop.jinja2` | Phase definitions; parsed by `SOPManager` → `tool_phase_map` |
| **Persistence** | `session_manager.persist_session_state()` | Serializes `WorkflowContext.to_dict()` + `WorkflowPhaseRecord` list |

**Critical flow per turn:**
```
user_message arrives
  → session.session_context computed (reads WorkflowContext.to_status_text() fresh)
  → inferencer.set_prior_context(session.session_context)   ← injects workflow_status etc.
  → inferencer.set_messages(conversation.get_api_messages())
  → inferencer.run_agentic_loop(content)
      → _render_prompt() passes prior_context into Jinja2 feed
          → initial.jinja2 renders WorkflowStatus, WorkflowDescription, WorkflowNextStepGuidance
      → LLM responds; may call action tools (start_phase/complete_phase side-effects)
  → session_manager.persist_session_state()
```

### 1.2 What OpenTeam Has Today

| Layer | Status | Detail |
|---|---|---|
| `initial.jinja2` | ✅ Ready | Full workflow guards in place (`{% if workflow_target_path is defined %}`) |
| `sop.jinja2` | ✅ Ready | 3-phase SOP (Phase 0: Role Spec, Phase 1: Create Role, Phase 2: Role Setup) |
| `workflow_description/default.jinja2` | ✅ Ready | Static description of OpenTeam methodology |
| `.sop.config.yaml` | ✅ Ready | `subsections.Tools.directives` configured |
| `ConversationalInferencer` (AgentFoundation) | ✅ Already used | `conversation_service.py` already builds and uses it for `rovodev` backend |
| `WorkflowContext` | ✅ Migrated to AF | `agent_foundation/server/workflow_context.py` exists (diverges from rankevolve slightly) |
| **Session `workflow_context` field** | ❌ Missing | Session dict has only `id`, `title`, `messages`, timestamps — no workflow state |
| **`session_context` computation** | ❌ Missing | No equivalent of `RankEvolveSession.session_context` property |
| **`set_prior_context()` call** | ❌ Missing | `astream_response()` never calls `inferencer.set_prior_context()` |
| **Phase lifecycle (start/complete/fail)** | ❌ Missing | No `WorkflowContext` object attached to sessions |
| **Persistence of workflow state** | ❌ Missing | `session_state.json` only has messages |
| **Slash command routing** | ❌ Missing | No `/set-session-root`, `/view`, or workflow commands |

### 1.3 AgentFoundation Migration Status

`WorkflowContext` **has been migrated** to AgentFoundation:
- Location: `agent_foundation/server/workflow_context.py`
- Differences from rankevolve version: slightly leaner (no `task_queue`, no `max_parallel_tasks`, no `enqueue_task` methods — those are rankevolve-specific). Core fields (`strategy`, `workflow_description`, `current_phase`, `phase_status`, `completed_phases`, `phase_outputs`, `to_status_text()`) are all present and compatible.

`ConversationalInferencer` **has been migrated** to AgentFoundation:
- Location: `agent_foundation/common/inferencers/agentic_inferencers/conversational/conversational_inferencer.py`
- Already references `agent_foundation.server.workflow_context._WORKFLOW_DESC_PHASE_RE` and `WorkflowPhaseRecord` — full SOP-awareness is in AF version.
- `set_prior_context()` / `update_prior_context()` exist.
- Already used by `ConversationService._build_rovodev_inferencer()`.

**Key conclusion:** The AF `ConversationalInferencer` is already SOP-aware. It reads `prior_context` keys (`workflow_description`, `workflow_status`, `current_phase`, `phase_status`, `completed_phases`, `phase_outputs`, `tool_phase_map`) every turn from `set_prior_context()`. We just need to **supply** those values.

---

## 2. Implementation Plan

The plan is structured into **5 steps** in dependency order. Steps 1–3 are the core wiring; Steps 4–5 are persistence and slash commands.

---

### Step 1 — Extend Session Data Model to Carry `WorkflowContext`

**Files affected:** `src/openteam/server/services/session_store.py`

`SessionStore.create_session()` currently produces a minimal dict (`id`, `title`, `messages`, timestamps). We need to add a `workflow_context` field holding a serialized `WorkflowContext` dict.

```python
# In create_session():
from agent_foundation.server.workflow_context import WorkflowContext

desc = self._load_workflow_description()  # reads default.jinja2 from templates_dir
wc = WorkflowContext(workflow_description=desc)
session = {
    "id": session_id,
    "title": title or "Orchestrator Session",
    "created_at": timestamp,
    "updated_at": timestamp,
    "server": self._server_dir.name,
    "workflow_context": wc.to_dict(),   # ← NEW
    "messages": [...],
}
```

**Critical: `load_workflow_description()` path resolution.** AF's `WorkflowContext.__post_init__` calls `load_workflow_description("default")` which tries `importlib.resources` for `agent_foundation.src.resources.prompt_templates` — this will NOT find OpenTeam's templates. Always bypass `__post_init__` by passing `workflow_description=desc` explicitly at construction time, loading the description from `self._templates_dir / "conversation/main/_variables/workflow_description/default.jinja2"`.

**Backward compatibility:** Old sessions on disk won't have `workflow_context`. In `get_session()`, backfill:
```python
if "workflow_context" not in session:
    session["workflow_context"] = WorkflowContext(workflow_description=desc).to_dict()
```

**New method to add:**
```python
def update_workflow_context(self, session_id: str, wc_dict: dict) -> dict | None:
    """Persist updated WorkflowContext dict back into session."""
    return self.update_session(session_id, {"workflow_context": wc_dict})
```

---

### Step 2 — Add `_compute_session_context()` to `ConversationService`

**Files affected:** `src/openteam/server/services/conversation_service.py`

Add the equivalent of `RankEvolveSession.session_context` — a method that takes a session dict and builds the `prior_context` dict for prompt injection:

```python
def _compute_session_context(self, session: dict) -> dict:
    """Build prior_context dict from session state — called once per turn."""
    from agent_foundation.server.workflow_context import WorkflowContext

    wc_dict = session.get("workflow_context", {})
    wc = WorkflowContext.from_dict(wc_dict) if wc_dict else WorkflowContext(
        workflow_description=self._load_workflow_description()
    )

    ctx: dict = {}

    # Only inject target path if set (gates the Workflow Context section in template)
    # After template guard is relaxed (Step 3b), workflow_description gates instead.
    workflow_target_path = session.get("workflow_target_path", "")
    if workflow_target_path:
        ctx["workflow_target_path"] = workflow_target_path
        ctx["session_root_path"] = session.get("session_root_path", "not set")

    # Always inject workflow state (AF inferencer uses these for SOP tracking)
    ctx["workflow_status"] = wc.to_status_text()
    ctx["workflow_description"] = wc.workflow_description
    ctx["strategy"] = wc.strategy
    ctx["current_phase"] = wc.current_phase
    ctx["phase_status"] = wc.phase_status
    ctx["completed_phases"] = wc.completed_phases
    ctx["phase_outputs"] = wc.phase_outputs

    return ctx

def _load_workflow_description(self) -> str:
    desc_file = (
        self._templates_dir
        / "conversation" / "main"
        / "_variables" / "workflow_description" / "default.jinja2"
    )
    return desc_file.read_text(encoding="utf-8") if desc_file.is_file() else ""
```

**Note on `workflow_nextstep_guidance`:** This variable does NOT need to be computed here. The AF `ConversationalInferencer._render_prompt()` computes it internally from `prior_context["workflow_description"]`, `current_phase`, `phase_status`, and the SOP file — via the `StateGraphTracker`. We only supply the raw state; the inferencer does the nextstep derivation.

---

### Step 3a — Call `set_prior_context()` in `astream_response()`

**Files affected:** `src/openteam/server/services/conversation_service.py`

```python
elif self._llm_backend == "rovodev":
    inferencer = self._get_session_inferencer(session["id"])  # see Step 3c

    # ← NEW: inject workflow state as prior_context before each turn
    session_ctx = self._compute_session_context(session)
    inferencer.set_prior_context(session_ctx)

    # Sync conversation history (existing)
    messages = session.get("messages", [])
    conv_messages = [
        {"role": "user" if m.get("role") in ("manager", "user") else "assistant",
         "content": m.get("content", "")}
        for m in messages
    ]
    inferencer.set_messages(conv_messages)

    # Stream
    full_response = ""
    async for chunk in inferencer.ainfer_streaming(user_message):
        chunk_str = str(chunk) if not isinstance(chunk, str) else chunk
        if chunk_str:
            full_response += chunk_str
            yield chunk_str

    # ← NEW: persist context_updates back to session (see Step 4)
    if data_service:
        updated_wc = self._extract_updated_workflow_context(
            session, inferencer.prior_context
        )
        data_service.update_workflow_context(session["id"], updated_wc)
```

---

### Step 3b — Relax `workflow_target_path` Guard in `initial.jinja2`

**File:** `src/openteam/server/resources/prompt_templates/conversation/main/initial.jinja2`

**Current (line 6):**
```jinja2
{% if workflow_target_path is defined and workflow_target_path %}
## Workflow Context
...
{% endif %}
```

**Change to:**
```jinja2
{% if workflow_description is defined and workflow_description %}
## Workflow Context
{% if workflow_target_path is defined and workflow_target_path %}
You operate on {{ workflow_target_path }} under repository `{{ session_root_path | default("(not set)") }}`.
{% endif %}
...
{% endif %}
```

This ensures the SOP/status/guidance are shown from the first turn (workflow_description is always loaded), while the target-path line is still conditionally shown only when relevant.

---

### Step 3c — Per-Session `ConversationalInferencer` (Critical Bug Fix)

**Files affected:** `src/openteam/server/services/conversation_service.py`

**Current bug:** One shared `ConversationalInferencer` instance across all sessions. `set_prior_context()` and `set_messages()` write per-session state to a shared object — multi-session races will cause cross-session contamination.

**Fix:** Replace `self._inferencer: CI` with `self._inferencers: dict[str, CI]`:

```python
class ConversationService:
    def __init__(self, ...):
        ...
        self._inferencers: dict[str, Any] = {}  # session_id → ConversationalInferencer

    def _get_session_inferencer(self, session_id: str):
        if session_id not in self._inferencers and self._llm_backend == "rovodev":
            self._inferencers[session_id] = self._build_rovodev_inferencer()
        return self._inferencers.get(session_id)

    def evict_session_inferencer(self, session_id: str) -> None:
        """Call when session is deleted to free memory."""
        self._inferencers.pop(session_id, None)
```

This matches `RankEvolveSession.conversation_inferencer` — one inferencer per session.

---

### Step 4 — Post-Turn WorkflowContext Persistence

**Files affected:** `src/openteam/server/services/conversation_service.py`, `session_store.py`, `manager_websocket_routes.py`

After `ainfer_streaming()` completes, the inferencer's `prior_context` may have been updated by `context_updates` from tool calls. Extract and persist:

```python
def _extract_updated_workflow_context(self, session: dict, prior_context: dict) -> dict:
    """Build updated WorkflowContext dict from inferencer's post-turn prior_context."""
    from agent_foundation.server.workflow_context import WorkflowContext

    # Start from current session state
    wc_dict = session.get("workflow_context", {})
    wc = WorkflowContext.from_dict(wc_dict) if wc_dict else WorkflowContext()

    # Apply any updates written by tools via context_updates
    if "current_phase" in prior_context:
        wc.current_phase = prior_context["current_phase"]
    if "phase_status" in prior_context:
        wc.phase_status = prior_context["phase_status"]
    if "phase_outputs" in prior_context:
        wc.phase_outputs = prior_context.get("phase_outputs", {})

    # Handle _completed_gate_phases (confirmation-gate pattern from AF inferencer)
    for gate_phase in prior_context.get("_completed_gate_phases", []):
        wc.complete_phase(gate_phase, "User confirmed")

    return wc.to_dict()
```

Pass `data_service` into `astream_response()`:
```python
async def astream_response(self, session: dict, user_message: str, data_service=None):
```

Update call site in `manager_websocket_routes.py`:
```python
async for chunk in conv_svc.astream_response(session, text, data_service=data_svc):
```

---

### Step 5 — Slash Command Routing

**New file:** `src/openteam/server/command_router.py`

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class CommandResult:
    action: str
    message: str
    session_updates: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)

def route_command(text: str, session: dict) -> CommandResult:
    parts = text.strip().split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/set-session-root":
        return _handle_set_session_root(args)
    elif cmd == "/set-workflow-target":
        return _handle_set_workflow_target(args)
    elif cmd == "/workflow-status":
        return _handle_workflow_status(session)
    elif cmd == "/reset-workflow":
        return _handle_reset_workflow()
    else:
        return CommandResult(action="unknown", message=f"Unknown command: {cmd}")
```

**Wire into `manager_websocket_routes.py` → `process_message()`:**
```python
async def process_message(sid: str, text: str) -> None:
    if text.strip().startswith("/"):
        session = data_svc.get_session(sid)
        from openteam.server.command_router import route_command
        result = route_command(text, session)
        if result.session_updates:
            data_svc.update_session(sid, result.session_updates)
        await send_safe({"type": "command_response", "message": result.message, "data": result.data})
        return
    # ... existing LLM flow
```

---

## 3. Critical-Thinking Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| **Shared inferencer multi-session race** | 🔴 High | Step 3c — per-session inferencer dict (required before any workflow control is meaningful) |
| **`load_workflow_description()` finds wrong templates** | 🔴 High | Always pass `workflow_description=` at construction; never rely on AF's importlib path |
| **`workflow_nextstep_guidance` not injected** | 🟡 Medium | AF inferencer computes it internally from `prior_context` — no manual injection needed |
| **Old sessions lack `workflow_context`** | 🟡 Medium | `get_session()` backfill with fresh `WorkflowContext` |
| **Tool executors don't return `context_updates`** | 🟡 Medium | Requires executor changes (Step 4); without this, phase transitions don't update session |
| **`JinjaPromptRenderer.find_sop_file()` missing in AF** | 🟡 Medium | Verify; if missing, pass SOP path explicitly at CI construction |
| **`workflow_target_path` guard hides SOP from day 1** | 🟡 Medium | Step 3b template change — relax guard to `workflow_description` |
| **`context_updates` not persisted between sessions restart** | 🟠 Low-Med | Step 4 persistence ensures `workflow_context` is written to `session_state.json` after each turn |
| **`_dynamic_context` (completed actions) lost on server restart** | 🟠 Low | Out of scope for this plan; `AgenticDynamicContext.to_dict()/from_dict()` can be added later |

---

## 4. File-by-File Summary

### Files to create:
- [ ] `src/openteam/server/command_router.py`
- [ ] `test/openteam/server/services/test_workflow_context_integration.py`

### Files to modify:
- [ ] `src/openteam/server/services/session_store.py` — `create_session`, `get_session`, add `update_workflow_context`
- [ ] `src/openteam/server/services/conversation_service.py` — `_compute_session_context`, `_load_workflow_description`, `_extract_updated_workflow_context`, `_get_session_inferencer`, per-session inferencer dict, `astream_response` with `set_prior_context` + `data_service` param
- [ ] `src/openteam/server/routes/manager_websocket_routes.py` — slash command detection, pass `data_svc` to `astream_response`
- [ ] `src/openteam/server/resources/prompt_templates/conversation/main/initial.jinja2` — relax guard
- [ ] `src/openteam/server/resources/tools/create_role/executor.py` — return `context_updates`
- [ ] `src/openteam/server/resources/tools/role_setup/executor.py` — return `context_updates`

### Already correct — no changes:
- ✅ `conversation/main/_variables/workflow/sop.jinja2`
- ✅ `conversation/main/_variables/workflow/.sop.config.yaml`
- ✅ `conversation/main/_variables/workflow_description/default.jinja2`
- ✅ `conversation/main/.initial.config.yaml` (create_role + role_setup whitelist)
- ✅ `resources/tools/role_setup/tool.json` (just created)

---

## 5. Implementation Order (Dependency-Sorted)

```
1. session_store.py          — workflow_context field in session data model
        ↓
2. conversation_service.py   — _compute_session_context(), _load_workflow_description()
        ↓
3. conversation_service.py   — per-session inferencer dict (critical bug fix)
        ↓
4. conversation_service.py   — set_prior_context() call in astream_response()
        |
        ↓ (parallel)
   initial.jinja2             — relax workflow_target_path guard
        ↓
5. conversation_service.py   — post-turn persistence (_extract_updated_workflow_context)
   session_store.py           — update_workflow_context()
   manager_websocket_routes   — pass data_service to astream_response()
        ↓
6. command_router.py         — slash commands
   manager_websocket_routes   — slash command detection
        ↓
7. tool executors            — context_updates from create_role, role_setup
```

---

## 6. Comparison: RankEvolve vs OpenTeam (After This Plan)

| Aspect | RankEvolve | OpenTeam (target state) |
|---|---|---|
| Session object | `RankEvolveSession` attrs class with typed `WorkflowContext` field | Plain dict with `"workflow_context": wc.to_dict()` |
| `session_context` computation | `@property` on `RankEvolveSession` | `ConversationService._compute_session_context(session_dict)` |
| `set_prior_context()` call site | `RankEvolveMessageHandlers._handle_chat()` | `ConversationService.astream_response()` |
| Per-session inferencer | `RankEvolveSession.conversation_inferencer` | `ConversationService._inferencers[session_id]` |
| Persistence mechanism | `SessionManager.persist_session_state()` (full dump) | `SessionStore.update_workflow_context()` (partial update) |
| Phase lifecycle callers | Message handler (explicit commands) + tool `context_updates` | Tool `context_updates` only + slash commands |
| Transport | Queue-based `QueueInteractive` | WebSocket `send_safe()` |
| `WorkflowContext` class | `rankevolve.src.server.workflow_context` (has task_queue) | `agent_foundation.server.workflow_context` (leaner, already migrated) |
