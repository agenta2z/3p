# Migration Plan: Conversation Prompt + Resumable Sessions for OpenTeam

## Context

OpenTeam currently has:
- **SessionStore** (`session_store.py`) — file-based persistent sessions with CRUD
- **ManagerChatView** — displays sessions as chat threads, but **input is disabled** (`"Type a message to your AI team... (demo mode)"`)
- **Prompt templates** (`resources/prompt_templates/`) — generic templates for `plan/`, `deep_research/`, `task_breakdown/`, `create_role/` — but **no conversation template**
- **No conversation service** — no code to render prompts, call an LLM, or append messages to sessions

The goal is to:
1. **Migrate the conversation prompt** from rankevolve (`conversation/main/initial.jinja2`) to OpenTeam
2. **Make sessions conversational** — enable the chat input, send user messages, get AI responses, persist everything
3. **Make sessions resumable** — server restarts preserve full conversation state; the UI reloads seamlessly

---

## Source Analysis: Rankevolve Conversation System

### Prompt Templates (`conversation/main/`)

```
conversation/main/
├── .initial.config.yaml          # XML tag escaping config for WebUI rendering
├── initial.jinja2                # Main system prompt (99 lines)
├── initial.jinja2.old            # Legacy version (deprecated, skip)
└── _variables/
    ├── workflow/
    │   ├── .sop.config.yaml      # SOP directive-to-instruction mapping
    │   └── sop.jinja2            # 5-phase workflow SOP (RankEvolve-specific)
    └── workflow_description/
        └── default.jinja2        # RankEvolve workflow description (skip)
```

### Key Template Variables in `initial.jinja2`

| Variable | Source | OpenTeam Disposition |
|---|---|---|
| `employee` | `.variables.yaml` persona | ✅ Already exists in OpenTeam's `.variables.yaml` |
| `workflow_target_path` | Server runtime | 🟡 Keep in template, provide empty default |
| `session_root_path` | Server runtime | 🟡 Keep in template, provide empty default |
| `workflow_description` | `_variables/workflow_description/default.jinja2` | 🔄 Replace with OpenTeam-specific description |
| `workflow_status` | Server runtime (workflow engine) | 🟡 Keep in template, provide empty default |
| `workflow_nextstep_guidance` | Server runtime (workflow engine) | 🟡 Keep in template, provide empty default |
| `action_tools` | Server runtime (tool registry) | 🟡 Keep in template, initially empty |
| `conversation_tools` | Server runtime (tool registry) | 🟡 Keep in template, initially empty |
| `conversation_history` | Session messages | ✅ Fed from session.messages |
| `current_turn` | Current user message | ✅ Fed from user input |

### Architecture Differences: Rankevolve vs OpenTeam

| Aspect | Rankevolve | OpenTeam (Target) |
|---|---|---|
| **LLM Backend** | Server queue → AgentServiceBridge → poll_responses | Direct LLM API call (ai-gateway or provider) |
| **Session Writer** | Separate server process (sole writer) | SessionStore in-process (read + write) |
| **WebUI Role** | Read-only viewer of server's sessions | Full read/write — owns the session lifecycle |
| **Streaming** | File-based tailer + WebSocket | Phase 1: synchronous; Phase 2: SSE/WebSocket |
| **Workflow Engine** | Full SOP with phases, /task, /research-propose | Not needed initially — conversation-only |
| **Experiment Service** | Manages demo flow steps + animations | Not applicable — real conversations |

---

## Migration Strategy

### Principle: "Copy templates, adapt variables, build a thin conversation service"

The conversation prompt is **domain-agnostic** — its decision procedure, response format, and tool invocation syntax work for any AI assistant. We copy it with minimal edits:

1. **Copy** `initial.jinja2` and `.initial.config.yaml` as-is
2. **Replace** `_variables/workflow_description/default.jinja2` with OpenTeam-specific content
3. **Replace** `_variables/workflow/sop.jinja2` with an OpenTeam-specific SOP (or empty placeholder)
4. **Copy** `.sop.config.yaml` as-is (generic directive mapping)
5. **Skip** `initial.jinja2.old` (deprecated)

Then build a thin **ConversationService** that:
- Renders the prompt template with session history + user input
- Calls an LLM (via `llm_gateway.py` or direct API)
- Parses the `<Response>` from the output
- Appends both user message and assistant response to the session
- Persists via SessionStore's atomic write

---

## Detailed File Changes

### Overview: 11 files (6 new/copied, 5 modified)

```
NEW/COPIED FILES:
  1. src/server/resources/prompt_templates/conversation/main/initial.jinja2           — COPY from rankevolve (CRITICAL edits: workflow + tool guards)
  2. src/server/resources/prompt_templates/conversation/main/.initial.config.yaml      — COPY as-is
  3. src/server/resources/prompt_templates/conversation/main/_variables/workflow_description/default.jinja2  — NEW (OpenTeam-specific)
  4. src/server/resources/prompt_templates/conversation/main/_variables/workflow/.sop.config.yaml  — COPY as-is (preserve subsections/directives nesting)
  5. src/server/resources/prompt_templates/conversation/main/_variables/workflow/sop.jinja2  — NEW (OpenTeam placeholder)
  6. src/server/services/conversation_service.py                       — NEW (core conversation engine)

MODIFIED FILES:
  7. src/server/services/session_store.py          — Add append_message() + update_session()
  8. src/server/services/data_service.py           — Add append/update to RealSessionDataService
  9. src/server/routes/session_routes.py           — Add POST /sessions/{id}/messages (send message)
 10. src/server/main.py                            — Wire ConversationService in lifespan
 11. src/ui/src/components/views/ManagerChatView.js — Enable chat input, send messages, optimistic updates
```

**Note:** All paths are relative to `CoreProjects/OpenTeam/`. The `src/` prefix is required — files live under `src/server/` and `src/ui/`, not at the repository root.

---

## File-by-File Specification

### 1. `src/server/resources/prompt_templates/conversation/main/initial.jinja2` — COPY + CRITICAL EDITS

Copy from `rankevolve/src/resources/prompt_templates/conversation/main/initial.jinja2`.

**⚠️ CRITICAL: The original template uses workflow and tool variables unconditionally (lines 6-28). Without the guards below, rendering will crash with Jinja2 `UndefinedError` because `ConversationService.render_prompt()` does not pass these variables. These are NOT optional edits — they are required for the template to function.**

**Changes from rankevolve original:**

1. **Wrap workflow section in conditional (lines 6-19)** — workflow variables are not provided:
```jinja2
{# CHANGED: Guard workflow variables — they may not be provided #}
{% if workflow_target_path is defined and workflow_target_path %}
## Workflow Context
You operate on {{ workflow_target_path }} under repository `{{ session_root_path | default("(not set)") }}`.

<WorkflowDescription>
{{ workflow_description | default("No active workflow.") }}
</WorkflowDescription>

<WorkflowStatus>
{{ workflow_status | default("No workflow active.") }}
</WorkflowStatus>

<WorkflowNextStepGuidance>
{{ workflow_nextstep_guidance | default("No specific guidance — respond to the user's request directly.") }}
</WorkflowNextStepGuidance>
{% endif %}
```

2. **Guard tool sections (lines 22-28)** — tools are not registered yet:
```jinja2
{% if action_tools is defined and action_tools %}
### Action Tools
{{ action_tools }}
{% endif %}

{% if conversation_tools is defined and conversation_tools %}
### Conversation Tools (structured input collection only)
{{ conversation_tools }}
{% endif %}
```

3. **Everything else stays identical** — the Decision Procedure, Response Format, ToolsToInvoke syntax, and Conversation XML structure are domain-agnostic and work perfectly for OpenTeam.

**Why these edits are critical:** Without guards 1 and 2, the template will crash on `{{ workflow_target_path }}`, `{{ action_tools }}`, etc. — Jinja2 raises `UndefinedError` for variables that aren't passed. The `ConversationService.render_prompt()` only passes `conversation_history` and `current_turn`. These guards make the workflow/tool sections activate only when those variables are provided in the future.

### 2. `src/server/resources/prompt_templates/conversation/main/.initial.config.yaml` — COPY AS-IS

```yaml
rendering:
  structural_xml_tags:
    - WorkflowDescription
    - WorkflowStatus
    - WorkflowNextStepGuidance
```

No changes needed. Even without workflow, the config is harmless — tags that don't appear won't be escaped.

### 3. `src/server/resources/prompt_templates/conversation/main/_variables/workflow_description/default.jinja2` — NEW

Replace rankevolve's RankEvolve-specific description with OpenTeam context:

```jinja2
OpenTeam is an AI-powered startup management platform. The Orchestrator coordinates a team of AI agents to manage projects, tasks, employees, and organizational processes.

**Available capabilities:**
- **Team Management** — view and manage team structure, roles, and assignments
- **Project Oversight** — track project status, milestones, and blockers
- **Task Coordination** — create, assign, and prioritize tasks across agents
- **Employee Management** — manage AI employee roles, skills, and performance
- **Sprint Planning** — plan and monitor sprint progress
- **Role Creation** — design and create new AI employee roles with research-backed specifications

The Orchestrator helps the manager make informed decisions by analyzing data, suggesting actions, and coordinating agent activities across the organization.
```

### 4. `src/server/resources/prompt_templates/conversation/main/_variables/workflow/.sop.config.yaml` — COPY AS-IS

Copy the exact file from rankevolve. **Preserve the `subsections` → `directives` nesting structure:**

```yaml
# SOP config for sop.md — maps subsection directives to instruction text.
# Optional: without this file, subsections render as-is in markdown.

subsections:
  Tools:
    directives:
      __must__: "You MUST use the following tools to complete this phase:"
      __prioritize__: "Prioritize the following tools (you may use alternatives if unavailable):"
```

⚠️ The nesting is important: `subsections:` → `Tools:` → `directives:` → `__must__`/`__prioritize__`. A flat structure would not be parsed correctly by SOPManager.

### 5. `src/server/resources/prompt_templates/conversation/main/_variables/workflow/sop.jinja2` — NEW

```jinja2
## OpenTeam Orchestrator — Standard Operating Procedure

The Orchestrator operates in a flexible, conversation-driven mode. There is no fixed phase sequence — the manager drives the interaction.

**General guidelines:**
- Respond to the manager's requests directly and helpfully
- Use available tools when the manager requests actions (task creation, research, etc.)
- Provide status summaries when asked
- Suggest next steps proactively when appropriate
- Escalate decisions that require human judgment

**When workflow variables are not set**, operate in free-form conversation mode:
- Help the manager with whatever they need
- Draw on available data (teams, projects, tasks, employees) to provide informed responses
- Suggest concrete actions rather than abstract advice
```

### 6. `src/server/services/conversation_service.py` — NEW (Core Engine)

This is the heart of the migration — a thin service that renders the conversation prompt, calls an LLM, parses the response, and persists messages.

```python
class ConversationService:
    """Renders conversation prompts and manages LLM interactions.
    
    Responsibilities:
    1. Render initial.jinja2 with session history + user input
    2. Call LLM via configurable backend (ai-gateway, direct API, or mock)
    3. Parse <Response> tags from LLM output
    4. Return the assistant's response content
    
    Does NOT manage session persistence — that's SessionStore's job.
    The route handler orchestrates: append user msg → call service → append response.
    """
    
    def __init__(self, templates_dir: Path, llm_backend: str = "mock") -> None:
        self._templates_dir = templates_dir
        self._llm_backend = llm_backend
        # Initialize TemplateManager rooted at prompt_templates/
        # with active_template_root_space="conversation"
        self._template_manager = self._build_template_manager()
    
    def _build_template_manager(self) -> TemplateManager:
        """Create TemplateManager for conversation prompt rendering.
        
        Uses the same TemplateManager pattern as create_role/executor.py:
        - Root: prompt_templates/
        - active_template_root_space: "conversation"
        - active_template_type: "main"
        - predefined_variables: True (loads .variables.yaml for {{ employee }})
        """
        from python_utils.string_utils.formatting.template_manager import TemplateManager
        return TemplateManager(
            templates=str(self._templates_dir),
            active_template_type="main",
            predefined_variables=True,
        )
    
    def render_prompt(self, session: dict, user_message: str) -> str:
        """Render the conversation prompt with session history + current turn.
        
        Builds the template feed:
        - conversation_history: list of {role, content} from session.messages
        - current_turn: {role: "manager", content: user_message}
        - workflow_* variables: empty defaults (no workflow active)
        - action_tools / conversation_tools: empty (no tools registered yet)
        - employee: auto-injected from .variables.yaml
        """
        messages = session.get("messages", [])
        
        # Build conversation_history from existing messages
        conversation_history = []
        for msg in messages:
            role = msg.get("role", "manager")
            # Map OpenTeam roles to prompt template roles
            prompt_role = "manager" if role in ("manager", "user") else "assistant"
            conversation_history.append({
                "role": prompt_role,
                "content": msg.get("content", ""),
            })
        
        current_turn = {"role": "manager", "content": user_message}
        
        return self._template_manager(
            "initial",
            active_template_root_space="conversation",
            conversation_history=conversation_history,
            current_turn=current_turn,
            # Workflow variables — empty defaults, template guards with {% if defined %}
            # No need to pass them — Jinja2 "is defined" check handles absence
        )
    
    async def get_response(self, session: dict, user_message: str) -> str:
        """Get an AI response for the user's message.
        
        1. Render prompt with session history
        2. Call LLM backend
        3. Parse <Response> tags from output
        4. Return cleaned response text
        """
        rendered_prompt = self.render_prompt(session, user_message)
        
        if self._llm_backend == "mock":
            raw_response = self._mock_response(user_message)
        else:
            raw_response = await self._call_llm(rendered_prompt)
        
        # Parse <Response>...</Response> tags
        return self._parse_response(raw_response)
    
    def _mock_response(self, user_message: str) -> str:
        """Generate a mock response for testing without an LLM."""
        return (
            f"<Response>\n"
            f"I received your message: \"{user_message}\"\n\n"
            f"As the Orchestrator, I can help you with team management, "
            f"project oversight, task coordination, and more. "
            f"This is currently running in mock mode — connect an LLM backend "
            f"to enable full AI conversations.\n"
            f"</Response>"
        )
    
    async def _call_llm(self, rendered_prompt: str) -> str:
        """Call the configured LLM backend.
        
        Supports:
        - "mock": returns canned response (default, no deps)
        - "ai-gateway": calls Atlassian AI Gateway
        - "anthropic": direct Anthropic API
        - "openai": direct OpenAI API
        
        Future: plug in via llm_gateway.py or agent_foundation inferencers.
        """
        # Phase 1: Simple direct API call
        # Phase 2: Use llm_gateway.py or RovoChatInferencer
        raise NotImplementedError(f"LLM backend '{self._llm_backend}' not yet implemented")
    
    @staticmethod
    def _parse_response(raw_output: str) -> str:
        """Extract content from <Response>...</Response> tags.
        
        Uses the LAST match (not first), matching rankevolve's extract_delimited()
        behavior — handles cases where the LLM outputs multiple attempts.
        Falls back to full output if no tags found (graceful degradation).
        """
        import re
        matches = re.findall(r"<Response>(.*?)</Response>", raw_output, re.DOTALL)
        if matches:
            return matches[-1].strip()  # Last match — final attempt
        # No tags — return full output (may happen with some LLM backends)
        return raw_output.strip()
```

**Key design decisions:**

1. **Separation of concerns** — ConversationService renders prompts and calls LLMs. SessionStore persists. Routes orchestrate the flow. No God object.

2. **TemplateManager reuse** — Uses the exact same `TemplateManager` pattern as `create_role/executor.py`. The root `.variables.yaml` auto-injects the `{{ employee }}` persona. `active_template_root_space="conversation"` selects the conversation templates.

3. **Mock backend by default** — Works out of the box without LLM credentials. Real backends plugged in later.

4. **`<Response>` parsing** — Extracts the user-facing content, stripping the thinking/reasoning section. Same pattern as rankevolve's `extract_delimited()`.

### 7. `src/server/services/session_store.py` — MODIFY (Add message operations)

Add methods for appending messages and updating session state:

```python
# Add to SessionStore class:

def append_message(self, session_id: str, message: dict[str, Any]) -> dict[str, Any] | None:
    """Append a message to a session and persist. Returns updated session or None."""
    session = self.get_session(session_id)
    if session is None:
        return None
    
    session["messages"].append(message)
    session["updated_at"] = _iso_now()
    
    # Persist — try flat file first, fall back to directory
    flat_file = self._session_path(session_id)
    if flat_file.is_file():
        self._atomic_write(flat_file, session)
    else:
        session_dir = self._find_session_dir(session_id)
        if session_dir:
            self._atomic_write(session_dir / "session_state.json", session)
        else:
            # Fallback: create flat file
            self._atomic_write(flat_file, session)
    
    return session

def update_session(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update session fields (title, etc.) and persist. Returns updated session or None."""
    session = self.get_session(session_id)
    if session is None:
        return None
    
    for key, value in updates.items():
        if key != "id":  # Never overwrite ID
            session[key] = value
    session["updated_at"] = _iso_now()
    
    flat_file = self._session_path(session_id)
    if flat_file.is_file():
        self._atomic_write(flat_file, session)
    else:
        session_dir = self._find_session_dir(session_id)
        if session_dir:
            self._atomic_write(session_dir / "session_state.json", session)
        else:
            self._atomic_write(flat_file, session)
    
    return session
```

**Why these go on SessionStore (not ConversationService):**
- SessionStore owns persistence — it knows the storage layout (flat vs directory)
- ConversationService is stateless — it renders prompts and calls LLMs
- Routes orchestrate: `store.append_message(user_msg)` → `service.get_response()` → `store.append_message(response_msg)`

### 8. `src/server/services/data_service.py` — MODIFY

Add message operations to RealSessionDataService:

```python
# Add to RealSessionDataService class:

def append_message(self, session_id: str, message: dict) -> dict | None:
    return self._session_store.append_message(session_id, message)

def update_session(self, session_id: str, updates: dict) -> dict | None:
    return self._session_store.update_session(session_id, updates)
```

### 9. `src/server/routes/session_routes.py` — MODIFY (Add send message endpoint)

Add the conversation endpoint that ties everything together:

```python
from datetime import datetime, timezone
from uuid import uuid4

class SendMessageRequest(BaseModel):
    message: str

def _make_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp (avoids importing private _iso_now)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@router.post("/{session_id}/messages")
async def send_message(request: Request, session_id: str, body: SendMessageRequest):
    """Send a user message to a session and get an AI response.
    
    Flow:
    1. Validate session exists
    2. Append user message to session
    3. Call ConversationService.get_response()
    4. Append assistant response to session
    5. Return both messages
    
    This is synchronous (request-response) for Phase 1.
    Phase 2 adds SSE streaming for real-time token delivery.
    """
    svc = request.app.state.data_service
    conversation_svc = getattr(request.app.state, "conversation_service", None)
    
    # Check capabilities
    if not hasattr(svc, "append_message"):
        raise HTTPException(400, "Messaging not available in mock mode")
    if not conversation_svc:
        raise HTTPException(503, "Conversation service not initialized")
    
    # 1. Get current session
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")
    
    # 2. Build and append user message
    user_msg = {
        "id": f"msg-{uuid4().hex[:8]}",
        "role": "manager",
        "content": body.message,
        "timestamp": _make_timestamp(),
    }
    session = svc.append_message(session_id, user_msg)
    
    # 3. Get AI response
    try:
        response_text = await conversation_svc.get_response(session, body.message)
    except Exception as e:
        # Still saved the user message — append error as system message
        error_msg = {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "agent_name": "Orchestrator",
            "agent_id": "orchestrator",
            "content": f"I encountered an error processing your request: {str(e)}",
            "timestamp": _make_timestamp(),
            "error": True,
        }
        svc.append_message(session_id, error_msg)
        return {"data": {"user_message": user_msg, "assistant_message": error_msg, "error": True}}
    
    # 4. Append assistant response
    assistant_msg = {
        "id": f"msg-{uuid4().hex[:8]}",
        "role": "assistant",
        "agent_name": "Orchestrator",
        "agent_id": "orchestrator",
        "content": response_text,
        "timestamp": _make_timestamp(),
    }
    svc.append_message(session_id, assistant_msg)
    
    # 5. Return both messages
    return {"data": {"user_message": user_msg, "assistant_message": assistant_msg}}
```

**Changes from original plan:**
- **`_make_timestamp()`** replaces `from server.services.session_store import _iso_now` — avoids importing a private function cross-module (Issue 6)
- **`"error": True`** field added to error responses — allows clients to distinguish LLM failures from successful responses without parsing content (Issue 9)

**Critical design: User message is persisted BEFORE calling LLM.** If the LLM call fails, the user's message is still saved (conversation is resumable), and an error message is appended so the user knows what happened.

### 10. `src/server/main.py` — MODIFY (Wire ConversationService)

In the lifespan, after creating RealSessionDataService:

```python
if real_sessions_dir:
    from server.services.session_store import SessionStore
    from server.services.data_service import RealSessionDataService
    from server.services.conversation_service import ConversationService
    
    session_store = SessionStore(real_sessions_dir)
    data_svc = RealSessionDataService(fixtures_dir, session_store)
    
    # Initialize conversation service
    templates_dir = Path(__file__).parent / "resources" / "prompt_templates"
    llm_backend = getattr(app.state, "llm_backend", "mock")
    conversation_svc = ConversationService(templates_dir, llm_backend=llm_backend)
    app.state.conversation_service = conversation_svc
    
    logger.info("Real sessions enabled: %s", real_sessions_dir)
    logger.info("Conversation service: backend=%s", llm_backend)
else:
    data_svc = MockDataService(fixtures_dir)
    app.state.conversation_service = None
```

### 11. `src/ui/src/components/views/ManagerChatView.js` — MODIFY (Enable chat input)

> **⚡ Skip-ahead option:** If you plan to implement Phase 2 streaming (`plan_chat_streaming.md`) immediately after this plan, **skip this section entirely**. The Phase 1 frontend below (HTTP POST, optimistic UI, `refetch()`) gets **fully replaced** by Phase 2's WebSocket-based `useManagerChat` hook + `StreamingMessage` + `ChatInput` components. No Phase 1 frontend code survives into Phase 2. The backend work (Sections 1–10 above) is required by both phases — only this frontend section is throwaway.
>
> If you want a quick working chat before tackling WebSocket streaming, proceed below.

Transform the disabled chat input into a working message sender with optimistic UI updates.

> **🆕 Enriched from rankevolve webui investigation (2026-04-06):** The rankevolve `AgentChatPanel.js` + `useAgentChat.js` pattern has been deeply studied. The Phase 1 design below uses HTTP POST (simpler, no infra change). **Phase 2 WebSocket streaming** is fully designed in `plan_chat_streaming.md` — read that plan for the richer UX path (token streaming, blinking cursor, thinking indicator, phase badges, cancellation, auto-reconnect).

**Import changes** — modify the existing import line, don't create duplicates:
```javascript
// BEFORE:
import React, { useEffect, useRef } from 'react';
// AFTER:
import React, { useEffect, useRef, useState, useCallback } from 'react';

// ADD these new imports:
import CircularProgress from '@mui/material/CircularProgress';
import { postJson } from '../../utils/api';
```

**Component state and handlers:**
```javascript
// Inside ManagerChatView component:
const [inputValue, setInputValue] = useState('');
const [sending, setSending] = useState(false);
const [optimisticMessages, setOptimisticMessages] = useState([]);
const { data: session, loading, error, refetch } = useApiData(
    sessionId ? `/sessions/${sessionId}` : null
);

// Merge server messages with optimistic ones for display
const displayMessages = session?.messages 
    ? [...session.messages, ...optimisticMessages]
    : optimisticMessages;

const handleSend = useCallback(async () => {
    const message = inputValue.trim();
    if (!message || sending) return;
    
    setSending(true);
    setInputValue('');
    
    // Optimistic UI: show user message immediately
    const optimisticMsg = {
        id: `optimistic-${Date.now()}`,
        role: 'manager',
        content: message,
        timestamp: new Date().toISOString(),
    };
    setOptimisticMessages(prev => [...prev, optimisticMsg]);
    
    try {
        await postJson(`/sessions/${sessionId}/messages`, { message });
        setOptimisticMessages([]);  // clear — server data now has everything
        refetch();  // reload session with server-persisted messages
    } catch (err) {
        console.error('Failed to send message:', err);
        setOptimisticMessages([]);  // clear optimistic — server may have saved
        refetch();  // reload anyway to check what was persisted
    } finally {
        setSending(false);
    }
}, [inputValue, sending, sessionId, refetch]);

const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
};
```

**Replace the disabled TextField:**
```jsx
<TextField
    fullWidth
    placeholder={serverInfo?.real_sessions 
        ? "Type a message to your AI team..." 
        : "Type a message to your AI team... (demo mode)"}
    disabled={!serverInfo?.real_sessions || sending}
    value={inputValue}
    onChange={(e) => setInputValue(e.target.value)}
    onKeyDown={handleKeyDown}
    size="small"
    multiline
    maxRows={4}
    InputProps={{
        endAdornment: (
            <InputAdornment position="end">
                <IconButton 
                    size="small"
                    onClick={handleSend}
                    disabled={!inputValue.trim() || sending}
                    sx={{ color: inputValue.trim() ? 'primary.main' : 'text.disabled' }}
                >
                    {sending ? <CircularProgress size={18} /> : <SendIcon fontSize="small" />}
                </IconButton>
            </InputAdornment>
        ),
    }}
/>
```

**Use `displayMessages` instead of `session?.messages`** in the messages rendering loop.

**Key UX decisions:**
- **Optimistic UI** — user message appears in chat instantly via `optimisticMessages` state, cleared when `refetch()` returns server data. No blank wait during LLM round-trip.
- **Input enabled only in real-sessions mode** — mock mode stays read-only (backward compatible)
- **`onKeyDown`** (not deprecated `onKeyPress`) — Enter sends, Shift+Enter for newline. Matches existing codebase convention (`QuickChatBox.js`, `RoleControlPopover.js`).
- **`useState` + `useCallback` added to existing React import** — not separate import lines
- **`CircularProgress` imported from MUI** — needed for the sending spinner
- **Error resilience** — refetch even on error, since user message may have been saved server-side
- **⚠️ This is Phase 1 (HTTP POST, no streaming).** For real-time token streaming with blinking cursor, "Thinking..." indicator, and phase badges (as rankevolve does), see `plan_chat_streaming.md`.

---

## Resumability Design

### How Sessions Survive Server Restarts

The system is designed to be fully resumable:

```
SERVER STARTS
  └─► SessionStore.__init__(sessions_dir)
        ├─► Scans existing session files (flat + directory)
        ├─► If files exist: loads them (no default session created)
        └─► If empty: creates default Orchestrator session

USER OPENS UI
  └─► Sidebar fetches GET /api/sessions
        └─► Returns all persisted sessions with summaries
  └─► User clicks a session
        └─► ManagerChatView fetches GET /api/sessions/{id}
              └─► Returns full session with all messages
              └─► Chat input is enabled (real-sessions mode)
              └─► User continues conversation from where they left off

USER SENDS MESSAGE
  └─► POST /sessions/{id}/messages
        ├─► 1. User message appended to session file (atomic write)
        ├─► 2. ConversationService renders prompt with FULL history
        ├─► 3. LLM sees all previous messages in <PreviousTurns>
        ├─► 4. LLM response appended to session file (atomic write)
        └─► 5. Response returned to UI

SERVER CRASHES MID-CONVERSATION
  └─► User message already persisted (step 1 happens BEFORE LLM call)
  └─► On restart: SessionStore loads session with user message intact
  └─► User sees their last message; can resend or continue
  └─► LLM response lost only if crash happened during step 3-4
  └─► No orphan partial writes (atomic tmp + os.replace)
```

### Key Resumability Properties

| Property | How It's Achieved |
|---|---|
| **Session state survives restart** | JSON files on disk, scanned on init |
| **Conversation history preserved** | All messages in session file's `messages` array |
| **LLM sees full context on resume** | `render_prompt()` builds `conversation_history` from ALL messages |
| **No duplicate default sessions** | `has_sessions` check: `any(glob("session-*.json"))` |
| **Atomic writes prevent corruption** | `_atomic_write()`: tempfile + `os.replace()` |
| **User message saved before LLM call** | `append_message(user_msg)` runs before `get_response()` |
| **Graceful LLM failure** | Error message appended as assistant response, conversation continues |

### Conversation History in the Prompt

The prompt template's `<Conversation>` section ensures the LLM sees the full context:

```xml
<Conversation>
  <PreviousTurns>
    <!-- ALL previous messages from session.messages -->
    <manager>What's the status of Project Alpha?</manager>
    <assistant>Project Alpha is on track. Here's the summary...</assistant>
    <manager>Can you assign the auth migration task to Agent-Delta?</manager>
    <assistant>Done. I've assigned task TSK-042 to Agent-Delta...</assistant>
  </PreviousTurns>
  <CurrentTurn>
    <!-- The new user message being processed -->
    <manager>What about the sprint deadline?</manager>
  </CurrentTurn>
</Conversation>
```

After a server restart, the UI reloads the session, and the next `POST /sessions/{id}/messages` call rebuilds the full `<PreviousTurns>` from the persisted messages — the LLM continues as if nothing happened.

---

## Critical Analysis: Risks & Mitigations

### 🟡 Risk 1: TemplateManager dependency + no dependency manifest

The `ConversationService` imports `TemplateManager` from `python_utils`. If this package is not installed in the OpenTeam environment, it will fail.

**Current state:** OpenTeam has **no `requirements.txt`, `pyproject.toml`, or `setup.py`**. Dependencies are managed via the parent workspace or system-wide installs. The existing `create_role/executor.py` already imports `TemplateManager`, so it must be available in the runtime environment.

**Mitigation:** Add a try/except with fallback to raw Jinja2 rendering:
```python
try:
    from python_utils.string_utils.formatting.template_manager import TemplateManager
except ImportError:
    # Fallback: direct Jinja2 rendering
    from jinja2 import Environment, FileSystemLoader
    # ... simpler rendering without predefined_variables
```

**Recommendation:** Verify `python_utils` is importable before implementation. Consider adding a `requirements.txt` to OpenTeam to document dependencies explicitly.

### 🟡 Risk 2: Growing message history → prompt too long

As conversations grow, the `conversation_history` section grows unboundedly. After ~50 messages, the prompt may exceed LLM context limits.

**Mitigation (Phase 2):** Add a `max_history_messages` parameter to `render_prompt()` that truncates to the last N messages, preserving the system context + recent conversation.

**For Phase 1:** Not a problem — mock backend doesn't have token limits, and real LLM backends will be added with truncation support.

### 🟡 Risk 3: Concurrent writes to same session

If two browser tabs send messages to the same session simultaneously, the read-modify-write cycle in `append_message()` could lose a message (TOCTTOU race).

**Mitigation:** For Phase 1, this is acceptable — single-user tool. For Phase 2, implement a proper lock around the full read-modify-write cycle:
```python
import threading
_session_locks: dict[str, threading.Lock] = {}

def _get_lock(session_id: str) -> threading.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = threading.Lock()
    return _session_locks[session_id]

# In append_message:
with self._get_lock(session_id):
    session = self.get_session(session_id)  # read
    session["messages"].append(message)      # modify
    self._atomic_write(path, session)        # write
```

Note: `fcntl` file locking alone is insufficient — the lock must cover the full read-modify-write cycle, not just the write. A threading lock is simpler and works cross-platform.

### 🟢 Risk 4: Mock mode backward compatibility

The plan adds new routes (`POST /sessions/{id}/messages`) and enables chat input — but only when `serverInfo.real_sessions` is true. Mock mode behavior is unchanged:
- GET endpoints return mock data as before
- POST `/sessions` returns 400 (existing)
- POST `/sessions/{id}/messages` returns 400 ("Messaging not available in mock mode")
- Chat input stays disabled in mock mode

### 🟢 Risk 5: Session schema evolution

The existing session schema (`id`, `title`, `created_at`, `updated_at`, `messages[]`) is sufficient for conversations. No schema migration needed. The `messages` array already supports both `manager` and `assistant` roles with `agent_name`/`agent_id` for assistant messages.

---

## Implementation Order

| Step | File | Type | Description | Dependencies |
|---|---|---|---|---|
| 1 | `src/server/resources/prompt_templates/conversation/main/initial.jinja2` | COPY+EDIT | Copy from rankevolve, add workflow+tool guards (CRITICAL) | None |
| 2 | `src/server/resources/prompt_templates/conversation/main/.initial.config.yaml` | COPY | XML tag escaping config | None |
| 3 | `src/.../conversation/main/_variables/workflow_description/default.jinja2` | NEW | OpenTeam workflow description | None |
| 4 | `src/.../conversation/main/_variables/workflow/.sop.config.yaml` | COPY | SOP directive mapping (preserve nesting!) | None |
| 5 | `src/.../conversation/main/_variables/workflow/sop.jinja2` | NEW | OpenTeam SOP placeholder | None |
| 6 | `src/server/services/session_store.py` | MODIFY | Add `append_message()`, `update_session()` | None |
| 7 | `src/server/services/data_service.py` | MODIFY | Add message ops to `RealSessionDataService` | Step 6 |
| 8 | `src/server/services/conversation_service.py` | NEW | Core conversation engine (last-match parsing) | Steps 1-5 |
| 9 | `src/server/routes/session_routes.py` | MODIFY | Add `POST /{id}/messages` (own timestamp util) | Steps 7, 8 |
| 10 | `src/server/main.py` | MODIFY | Wire `ConversationService` in lifespan | Step 8 |
| 11 | `src/ui/src/components/views/ManagerChatView.js` | MODIFY | Enable chat input, optimistic UI, onKeyDown | Step 9 |

Steps 1-5 can run in parallel (no dependencies). Steps 6-7 in parallel. Then 8, then 9-10, then 11.

---

## Verification Plan

### Backend Tests

1. **Template rendering**: Create ConversationService, render prompt with empty session → verify `{{ employee }}` injected, workflow section absent, conversation section empty
2. **Template with history**: Render with 3-message session → verify `<PreviousTurns>` contains all 3 messages in correct order
3. **Mock response**: `get_response()` with mock backend → verify `<Response>` tags parsed correctly
4. **append_message**: Create session, append user message → verify session file updated atomically, message count increased
5. **Full flow**: Create session → POST /sessions/{id}/messages → verify user message + assistant response in session
6. **Resumability**: Create session, add messages, create new SessionStore on same dir → verify all messages loaded
7. **Error handling**: Mock LLM failure → verify user message persisted, error message appended

### Frontend Tests

8. **Mock mode**: Chat input disabled, placeholder shows "(demo mode)"
9. **Real-sessions mode**: Chat input enabled, placeholder shows "Type a message..."
10. **Send message**: Type message, press Enter → message sent, input clears, session refreshes with new messages
11. **Loading state**: While sending, input disabled, send button shows spinner
12. **Error resilience**: Network error on send → console error logged, session refetches

### Integration Tests

13. **End-to-end**: `./run.sh --real-sessions /tmp/test` → create session → send message → see response → restart server → reopen session → all messages present → send another message → conversation continues
14. **curl test**: `curl -X POST localhost:8000/api/sessions/{id}/messages -d '{"message":"Hello"}' -H 'Content-Type: application/json'` → returns user + assistant messages

---

## Summary

> **🆕 Updated 2026-04-06** after deep investigation of rankevolve webui (`src/webui/src/` + `react/src/`). Key findings:
> - `ManagerChatView.js` chat input is **hardcoded `disabled`** — not conditional on any state. Must be explicitly unlocked.
> - Rankevolve uses **two chat systems**: HTTP POST + progress WebSocket (experiment flow) and full-duplex WebSocket streaming (agent flow). Both are production-quality and directly learnable from.
> - `MarkdownRenderer.js` (react-markdown + remark-gfm + Prism syntax highlighting) is **vastly superior** to OpenTeam's hand-rolled `dangerouslySetInnerHTML` markdown — should be adopted.
> - `useAgentChat.js` WebSocket hook + `agent_websocket_routes.py` are **directly copy-adaptable** for Phase 2 streaming. See `plan_chat_streaming.md`.
> - `StreamingMessage.js` blinking cursor + phase/agent `<Chip>` badges are **directly reusable** UI patterns.
> - `RovoDevCliInferencer` is **not suitable** for chat: blocking subprocess, no streaming, output format mismatch. Use `RovoChatInferencer` (streaming HTTP) or the Phase 2 WebSocket path instead.

This migration brings three things to OpenTeam:

1. **Conversation prompts** — The proven rankevolve conversation template (decision procedure, response format, tool invocation syntax) adapted for OpenTeam with optional workflow support
2. **Working chat** — Users can actually talk to the Orchestrator through the chat input, with messages persisted to disk
3. **Full resumability** — Server restarts, browser refreshes, and crashes all handled gracefully through atomic file persistence and prompt reconstruction from history

The architecture is intentionally simple for Phase 1 (synchronous request-response, mock LLM). Phase 2 extensions (SSE streaming, real LLM backends, tool execution, workflow engine) plug into well-defined interfaces without refactoring.
