# Migration Plan: RankEvolve Task Subtab System → OpenTeam

**Created:** 2026-04-15  
**Updated:** 2026-04-15 (merged from two plan analyses + deep code investigation)  
**Status:** Final — Ready for implementation  
**Scope:** Port RankEvolve's background task + task subtab system into OpenTeam.
`create_role` and `role_setup` run as background tasks with streaming panels,
task cards in conversation, and session sidebar navigation.

---

## 1. What We're Building

When the manager session executes `create_role` or `role_setup`:

1. **Immediately acknowledge** in conversation: insert a `task_ref` card ("Task: Create Role — Starting...")
2. **Run tool in background** (non-blocking) via `asyncio.create_task()`
3. **Stream tool output** to a separate **task tab** — NOT the main conversation
4. **Update task card** status: Starting → Running → Complete/Error
5. **Switch** between session conversation and task panel via sidebar
6. **Auto-advance**: when task completes, push synthetic message to `input_queue` → conversation continues

---

## 2. Key Design Decisions (Ground Truth from Code Investigation)

### 2.1 Flag Field: `"asynchronous": true` in `tool.json`

**`ToolDefinition` in `agent_foundation` already has this field:**

```python
# agent_foundation/resources/tools/models.py:105
asynchronous: bool = False  # Fire-and-forget: tool runs in background, turn completes immediately
is_bridge: bool = False
```

And `from_dict()` already parses it:
```python
asynchronous=data.get("asynchronous", False),
is_bridge=data.get("is_bridge", False),
```

**Add BOTH flags to the tool.json files:**

```json
// create_role/tool.json and role_setup/tool.json — add:
"asynchronous": true,
"is_bridge": true
```

`is_bridge` marks it as a bridge tool (multi-agent pipeline), `asynchronous` triggers background dispatch.
No new fields invented — both already exist in the shared model.

### 2.2 ToolDispatcher detects async via `tool_def.asynchronous`

`ToolDefinition` objects are already loaded and passed to `ToolDispatcher`.
Check `tool_def.asynchronous` — no need to re-read `tool.json` or maintain a separate set.

### 2.3 `conversation_service.py` must pass `interactive` to ToolDispatcher

`ToolDispatcher` is created in `conversation_service.py` at line 280.
The `interactive` (WebSocketInteractive) instance must be injected there so the dispatcher
can send `task_status` messages and spawn background tasks.

### 2.4 Token routing via `TaskWebSocketInteractive` wrapper

Background tool executors call `WebSocketInteractive.stream_token_batches()` internally.
To include `task_id` in their tokens, we need a wrapper that injects it automatically:

```python
class TaskWebSocketInteractive(WebSocketInteractive):
    """Wrapper for task-scoped streaming — injects task_id into all token messages."""
    def __init__(self, *args, task_id: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._task_id = task_id

    async def stream_token_batches(self, content: str, metadata: dict | None = None) -> None:
        meta = {**(metadata or {}), "task_id": self._task_id}
        await super().stream_token_batches(content, metadata=meta)
```

The background `_exec_async_tool` creates a `TaskWebSocketInteractive` and passes it
as `session_context["interactive"]` to the tool executor.

### 2.5 Auto-advance via `input_queue` (not WS send)

Exactly matching RankEvolve `tool_executor.py:603-612`:
When task completes, push a synthetic message to the session's `input_queue`.
The existing `pending_input` / message handler processes it, resuming the agentic loop.

---

## 3. Server-Side Changes

### Phase 1a — Add flags to `tool.json` (5 min)

**`resources/tools/create_role/tool.json`:**
```json
{
  "name": "create_role",
  "asynchronous": true,
  "is_bridge": true,
  "tool_type": "Action",
  ...
}
```

**`resources/tools/role_setup/tool.json`:**
```json
{
  "name": "role_setup",
  "asynchronous": true,
  "is_bridge": true,
  "tool_type": "Action",
  ...
}
```

### Phase 1b — Add `send_task_status()` to `WebSocketInteractive` (10 min)

**`services/websocket_interactive.py`** — add method:

```python
async def send_task_status(
    self,
    task_id: str,
    status: str,              # "starting" | "running" | "completed" | "error"
    request: str = "",
    tool_name: str = "",
    error: str = "",
) -> None:
    """Notify UI of task lifecycle events — creates/updates task subtab."""
    msg = {
        "type": "task_status",
        "task_id": task_id,
        "status": status,
        "session_id": self._session_id,
    }
    if request:
        msg["request"] = request
    if tool_name:
        msg["tool_name"] = tool_name
    if error:
        msg["error"] = error
    await self._send(msg)
```

Also add `TaskWebSocketInteractive` subclass in the same file:

```python
class TaskWebSocketInteractive(WebSocketInteractive):
    """Wraps WebSocketInteractive for task-scoped streaming — injects task_id into tokens."""

    def __init__(self, *args: Any, task_id: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._task_id = task_id

    async def stream_token_batches(
        self, content: str, metadata: dict | None = None
    ) -> None:
        meta = {**(metadata or {}), "task_id": self._task_id}
        await super().stream_token_batches(content, metadata=meta)
```

### Phase 1c — Update `ToolDispatcher` — Background Task Spawning (30 min)

**`services/tool_dispatcher.py`** — key changes:

**Constructor:** Add `interactive` and `input_queue` parameters:

```python
def __init__(
    self,
    tool_registry: dict[str, ToolDefinition],
    integration_executor: Any,
    session_context: dict[str, Any],
    interactive: Any = None,        # ← NEW: WebSocketInteractive instance
    input_queue: Any = None,        # ← NEW: asyncio.Queue for auto-advance
) -> None:
    self._integration_executor = integration_executor
    self._session_context = session_context
    self._interactive = interactive
    self._input_queue = input_queue
    self._executor_map: dict[str, Callable] = {}
    self._tool_registry = tool_registry     # ← keep reference for tool_def lookup
    self._load_executors(tool_registry)
```

**`__call__` — detect async tools via `tool_def.asynchronous`:**

```python
async def __call__(self, tool_name: str, arguments: dict[str, Any]) -> Any:
    tool_def = self._tool_registry.get(tool_name)

    if tool_def and tool_def.asynchronous and self._interactive:
        return await self._exec_async_tool(tool_name, arguments, tool_def)

    # ... existing synchronous dispatch (unchanged)
```

**New `_exec_async_tool` method:**

```python
async def _exec_async_tool(
    self, tool_name: str, arguments: dict[str, Any], tool_def: ToolDefinition
) -> Any:
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
        ToolExecutionResult,
    )
    import uuid

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    request = (
        arguments.get("role_description")
        or arguments.get("role_document_path")
        or tool_name
    )[:80]
    session_id = self._session_context.get("session_id", "")

    # 1. Notify UI: task starting
    await self._interactive.send_task_status(
        task_id=task_id, status="starting",
        request=request, tool_name=tool_name,
    )

    async def _run() -> None:
        from openteam.server.services.websocket_interactive import TaskWebSocketInteractive

        # Create task-scoped interactive that injects task_id into all tokens
        task_interactive = TaskWebSocketInteractive(
            websocket=self._interactive._websocket,
            session_id=self._interactive._session_id,
            task_id=task_id,
        )

        try:
            await self._interactive.send_task_status(
                task_id=task_id, status="running",
            )
            result = await self._executor_map[tool_name](
                arguments,
                {**self._session_context, "task_id": task_id, "interactive": task_interactive},
            )
            await self._interactive.send_task_status(
                task_id=task_id, status="completed",
            )
            # Auto-advance: push synthetic message to input_queue (RankEvolve pattern)
            if self._input_queue is not None:
                summary = (result.result[:200] if result and result.result else "")
                await self._input_queue.put({
                    "type": "message",
                    "content": (
                        f"[System: Task '{tool_name}' (task_id={task_id}) completed successfully. "
                        f"{summary}. Please review results and continue workflow.]"
                    ),
                    "session_id": session_id,
                    "auto_advance": True,
                })
        except Exception as e:
            logger.error("[ToolDispatcher] Task %s error: %s", task_id, e)
            await self._interactive.send_task_status(
                task_id=task_id, status="error", error=str(e)[:200],
            )

    asyncio.create_task(_run())

    # Return immediately — agentic loop continues, background task streams to task panel
    return ToolExecutionResult(
        result=f"[Task {task_id} started — running '{tool_name}' in background]",
        metadata={"task_id": task_id, "is_background_task": True},
    )
```

### Phase 1d — Update `conversation_service.py` — Pass `interactive` + `input_queue` (15 min)

**`services/conversation_service.py`** — update ToolDispatcher construction (around line 280):

```python
# Before:
dispatcher = ToolDispatcher(
    tool_registry=tool_registry,
    integration_executor=integration_executor,
    session_context=session_context,
)

# After:
dispatcher = ToolDispatcher(
    tool_registry=tool_registry,
    integration_executor=integration_executor,
    session_context={**session_context, "session_id": session_id},
    interactive=interactive,       # ← WebSocketInteractive instance
    input_queue=input_queue,       # ← asyncio.Queue for auto-advance
)
```

The `interactive` and `input_queue` are already available in `run_agentic_loop()` scope —
they just need to be passed through.

---

## 4. Client-Side Changes

### Phase 2a — Update `useManagerChat.js` — Task State + Handlers (30 min)

Add task-related state and handlers:

```js
// New state
const [tasks, setTasks] = useState({});          // { task_id: { id, label, status, streamContent, isStreaming } }
const [activeTabType, setActiveTabType] = useState('session');
const [activeTabId, setActiveTabId] = useState(null);

// switchTab helper
const switchTab = useCallback((tabId, tabType) => {
  setActiveTabType(tabType || 'session');
  setActiveTabId(tabType === 'task' ? tabId : null);
}, []);

// In handleServerMessage switch:

case 'task_status': {
  const { task_id, status, request, tool_name } = data;
  if (status === 'starting') {
    // Create task entry + task_ref card in conversation
    setTasks(prev => ({
      ...prev,
      [task_id]: {
        id: task_id,
        label: request || tool_name || 'Task',
        status: 'starting',
        streamContent: '',
        isStreaming: false,
        createdAt: Date.now(),
      },
    }));
    setMessages(prev => [...prev, {
      id: `task-ref-${task_id}`,
      role: 'task_ref',
      taskId: task_id,
      label: request || tool_name || 'Task',
      status: 'starting',
      timestamp: new Date().toISOString(),
    }]);
  } else {
    // Update task status + task_ref card
    setTasks(prev => prev[task_id]
      ? { ...prev, [task_id]: { ...prev[task_id], status } }
      : prev
    );
    setMessages(prev => prev.map(msg =>
      msg.role === 'task_ref' && msg.taskId === task_id
        ? { ...msg, status }
        : msg
    ));
  }
  break;
}

case 'token': {
  const task_id = data.task_id || data.metadata?.task_id;
  if (task_id) {
    // Route to task streaming — do NOT touch conversation streaming
    setTasks(prev => {
      const task = prev[task_id];
      if (!task) return prev;
      return {
        ...prev,
        [task_id]: {
          ...task,
          isStreaming: true,
          streamContent: (task.streamContent || '') + data.content,
        },
      };
    });
    return; // Don't fall through
  }
  // Existing conversation streaming (unchanged)...
  break;
}
```

Also update `message_end` to mark task as no longer streaming:
```js
// In message_end: reset isStreaming for any active task
if (data.task_id || data.metadata?.task_id) {
  const tid = data.task_id || data.metadata?.task_id;
  setTasks(prev => prev[tid]
    ? { ...prev, [tid]: { ...prev[tid], isStreaming: false } }
    : prev
  );
}
```

Return `tasks`, `activeTabType`, `activeTabId`, `switchTab` from the hook.

### Phase 2b — Create `TaskCard.js` (15 min)

**`components/chat/TaskCard.js`** — adapted from RankEvolve `TaskCard.js` (nearly identical):

```jsx
import React from 'react';
import { Box, Paper, Typography, Chip, Button, Tooltip } from '@mui/material';
import { OpenInNew as OpenIcon } from '@mui/icons-material';

const STATUS_CONFIG = {
  starting: { label: 'Starting...', color: 'warning' },
  running:  { label: 'Running',     color: 'info' },
  completed:{ label: 'Complete',    color: 'success' },
  error:    { label: 'Error',       color: 'error' },
};

export function TaskCard({ taskId, label, status, onOpenTask }) {
  const statusInfo = STATUS_CONFIG[status] || STATUS_CONFIG.running;
  const displayLabel = label?.length > 50 ? label.slice(0, 50) + '...' : label;

  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
      <Paper elevation={0} sx={{
        p: 2, maxWidth: '95%',
        backgroundColor: 'rgba(74, 144, 217, 0.08)',
        borderRadius: 2, border: '1px solid', borderColor: 'primary.dark',
        display: 'flex', alignItems: 'center', gap: 2,
      }}>
        <Tooltip title={label || ''} placement="top" arrow>
          <Typography variant="body2" sx={{ fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 400 }}>
            Task: {displayLabel}
          </Typography>
        </Tooltip>
        <Chip label={statusInfo.label} size="small" color={statusInfo.color} variant="outlined" sx={{ height: 22, fontSize: '0.7rem' }} />
        <Button size="small" endIcon={<OpenIcon sx={{ fontSize: 14 }} />}
          onClick={() => onOpenTask?.(taskId)} sx={{ fontSize: '0.75rem', textTransform: 'none', ml: 'auto' }}>
          Open Task
        </Button>
      </Paper>
    </Box>
  );
}
export default TaskCard;
```

### Phase 2c — Create `TaskPanel.js` (20 min)

**`components/chat/TaskPanel.js`** — adapted from RankEvolve `TaskPanel.js` (stripped to essentials):

```jsx
import React, { useRef, useEffect } from 'react';
import { Box, Typography, Button, Chip } from '@mui/material';
import { ArrowBack as BackIcon } from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';

const STATUS_CONFIG = {
  starting: { label: 'Starting...', color: 'warning' },
  running:  { label: 'Running',     color: 'info' },
  completed:{ label: 'Complete',    color: 'success' },
  error:    { label: 'Error',       color: 'error' },
};

export function TaskPanel({ task, onBack }) {
  const bottomRef = useRef(null);
  const statusInfo = STATUS_CONFIG[task?.status] || STATUS_CONFIG.running;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [task?.streamContent]);

  if (!task) {
    return (
      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography color="text.secondary">No task selected</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button startIcon={<BackIcon />} onClick={onBack} size="small" sx={{ textTransform: 'none' }}>
          Back to conversation
        </Button>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {task.label}
        </Typography>
        <Chip label={statusInfo.label} color={statusInfo.color} size="small" variant="outlined" />
      </Box>

      {/* Streaming content */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
        {task.streamContent ? (
          <ReactMarkdown>{task.streamContent}</ReactMarkdown>
        ) : (
          <Typography color="text.secondary" sx={{ fontStyle: 'italic' }}>
            {task.status === 'starting' ? 'Initializing task...' : 'Waiting for output...'}
          </Typography>
        )}
        {task.isStreaming && (
          <Box sx={{ display: 'inline-block', width: 8, height: 16, backgroundColor: 'primary.main', ml: 0.5, animation: 'blink 1s step-end infinite', '@keyframes blink': { '50%': { opacity: 0 } } }} />
        )}
        <div ref={bottomRef} />
      </Box>
    </Box>
  );
}
export default TaskPanel;
```

### Phase 2d — Update `ManagerChatView.js` — Tab Routing + task_ref (15 min)

```jsx
import { TaskCard } from '../chat/TaskCard';
import { TaskPanel } from '../chat/TaskPanel';

export default function ManagerChatView({ sessionId }) {
  const {
    messages, tasks, activeTabType, activeTabId, switchTab,
    // ...existing
  } = useManagerChat(sessionId);

  // If a task tab is active, show TaskPanel instead of conversation
  if (activeTabType === 'task' && activeTabId) {
    return (
      <TaskPanel
        task={tasks[activeTabId]}
        onBack={() => switchTab(null, 'session')}
      />
    );
  }

  // Existing conversation view — add task_ref rendering in messages.map:
  // if (msg.role === 'task_ref') {
  //   return (
  //     <TaskCard key={msg.id} taskId={msg.taskId} label={msg.label}
  //       status={msg.status} onOpenTask={(id) => switchTab(id, 'task')} />
  //   );
  // }
}
```

### Phase 3 (Optional) — Session Sidebar with Task Tree

Copy RankEvolve `SessionSidebar.js` → `components/layout/SessionSidebar.js`.
Adapt to use `tasks`, `sessionList`, `activeTabType`, `activeTabId`, `switchTab` from `useManagerChat`.
Shows sessions with nested task children, status chips, click-to-switch.

---

## 5. File Summary

### Server — Files to Modify

| File | Phase | Change |
|---|---|---|
| `resources/tools/create_role/tool.json` | 1a | Add `"asynchronous": true, "is_bridge": true` |
| `resources/tools/role_setup/tool.json` | 1a | Add `"asynchronous": true, "is_bridge": true` |
| `services/websocket_interactive.py` | 1b | Add `send_task_status()`; add `TaskWebSocketInteractive` subclass |
| `services/tool_dispatcher.py` | 1c | Add `interactive`+`input_queue` params; add `_exec_async_tool()`; check `tool_def.asynchronous` |
| `services/conversation_service.py` | 1d | Pass `interactive`, `input_queue`, `session_id` to ToolDispatcher |

### Client — Files to Create

| File | Source | Phase |
|---|---|---|
| `components/chat/TaskCard.js` | RankEvolve `TaskCard.js` | 2b |
| `components/chat/TaskPanel.js` | RankEvolve `TaskPanel.js` | 2c |
| `components/layout/SessionSidebar.js` | RankEvolve `SessionSidebar.js` | 3 |

### Client — Files to Modify

| File | Phase | Change |
|---|---|---|
| `hooks/useManagerChat.js` | 2a | Add `tasks`, `activeTabType`, `activeTabId`, `switchTab`; handle `task_status` + task `token` routing |
| `components/views/ManagerChatView.js` | 2d | Tab routing → TaskPanel; task_ref → TaskCard in messages |

---

## 6. Implementation Order

```
Step 1  (5 min)  tool.json — add "asynchronous": true, "is_bridge": true
Step 2  (15 min) websocket_interactive.py — send_task_status() + TaskWebSocketInteractive
Step 3  (30 min) tool_dispatcher.py — _exec_async_tool() + tool_def.asynchronous check
Step 4  (15 min) conversation_service.py — pass interactive + input_queue + session_id
Step 5  (30 min) useManagerChat.js — task state + task_status handler + token routing
Step 6  (15 min) TaskCard.js — create (copy from RankEvolve)
Step 7  (20 min) TaskPanel.js — create (copy from RankEvolve, strip multi-agent)
Step 8  (15 min) ManagerChatView.js — tab routing + task_ref rendering
Step 9  (20 min) SessionSidebar.js — create (copy from RankEvolve) [optional]
Step 10 (20 min) Manual test
```

---

## 7. Wire Protocol

### New WS Messages (Server → Client)

```json
// Task starting — triggers task_ref card in conversation
{"type": "task_status", "task_id": "task-a3f9c21b", "status": "starting",
 "request": "Senior Backend Engineer", "tool_name": "create_role", "session_id": "..."}

// Task running
{"type": "task_status", "task_id": "task-a3f9c21b", "status": "running", "session_id": "..."}

// Token for task — routed to TaskPanel, NOT conversation
{"type": "token", "content": "Researching responsibilities...",
 "metadata": {"task_id": "task-a3f9c21b"}, "session_id": "..."}

// Task completed
{"type": "task_status", "task_id": "task-a3f9c21b", "status": "completed", "session_id": "..."}

// Task error
{"type": "task_status", "task_id": "task-a3f9c21b", "status": "error",
 "error": "Connection failed: timeout after 300s", "session_id": "..."}
```

### Auto-advance (via input_queue, not WS)

```python
# Pushed to input_queue on task completion — triggers next agentic loop turn
{
    "type": "message",
    "content": "[System: Task 'create_role' (task_id=task-a3f9c21b) completed. Output: ... Please review and continue workflow.]",
    "session_id": "...",
    "auto_advance": True,
}
```

---

## 8. Verification Checklist

- [ ] Manager invokes `create_role` → task card appears in conversation "Task: [label] — Starting..."
- [ ] Task card status updates to "Running" (blue chip)
- [ ] Click "Open Task" → TaskPanel opens with task header and status chip
- [ ] Task output streams into TaskPanel (not conversation)
- [ ] Conversation chat input remains enabled while task runs
- [ ] Back button returns to conversation view
- [ ] Task card updates to "Complete" (green chip) when done
- [ ] Auto-advance: conversation continues after task completes (synthetic message triggers next turn)
- [ ] Task error → task card shows "Error" (red chip); error message shown
- [ ] `role_setup` tool works identically
- [ ] Non-async tools (Slack, TWG) unaffected — still run synchronously
- [ ] Sidebar shows session with task nested below (Phase 3)
