# Plan: Generic Tool Invocation — Registry-Driven ToolDispatcher

**Date:** 2026-04-14
**Status:** Final (merged from two plans)
**Problem:** OpenTeam's `conversation_service.py` has a hardcoded `tool_executor` closure that
only dispatches to integration tools (Slack, TWG). Registered action tools like `create_role` and
`role_setup` appear in the LLM prompt but return `"Unknown tool: {tool_name}"` at runtime —
they have no executor wired up.

---

## Current Architecture (Gap Analysis)

| Layer | What it does | File |
|---|---|---|
| Tool Registry | Scans `tool.json` → `{name: ToolDefinition}` with `source_path` set | AF `resources/tools/registry.py` |
| Tool Filtering | Whitelist via `.initial.config.yaml` → `enabled_action_tools` | `conversation_service.py:_filter_tools_by_config` |
| Prompt Rendering | Injects tool schemas into `{{ action_tools }}` | `conversational_inferencer.py:_render_prompt` |
| **Tool Execution** | **Hardcoded closure — only Slack/TWG** | **`conversation_service.py:270-288`** |

**The gap:** `ToolDefinition` has `source_path` but no executor reference. Registry is used for
prompt injection only. `create_role` and `role_setup` appear in the LLM prompt but the
`tool_executor` closure returns `"Unknown tool"` for them — **they are broken at runtime**.

**RankEvolve has the same problem** — its `SessionToolExecutor.__call__()` is a hardcoded
`if/elif` chain (task, understand_codebase, research_propose, etc.). Neither project had generic
dispatch before this plan.

---

## Proposed Solution: Explicit Executor Declaration in `tool.json`

### Design Principles

1. **Explicit > Implicit** — `tool.json` declares its executor via Python entry-point syntax
2. **No AF changes** — `executor` field in `tool.json` is silently ignored by `ToolDefinition.from_dict()` (verified: it uses explicit `data.get()` per field, no catch-all)
3. **Protocol-compatible** — `__call__(tool_name, arguments)` matches `ToolExecutorCallable` exactly; session context captured at construction
4. **Backward compatible** — integration tools (Slack, TWG) use `IntegrationToolExecutor` fallback unchanged

### Architecture

```
tool.json
  "executor": "openteam.server.resources.tools.create_role.executor:execute"
        ↓
ToolDispatcher.__call__(tool_name, arguments)
        ├── executor_map[tool_name](arguments, session_context)   ← registry tools
        ├── integration_executor(tool_name, arguments)             ← Slack/TWG fallback
        └── ToolExecutionResult("Unknown tool: ...")               ← unknown
        ↓
tool_executor closure in conversation_service.py
        └── SOP phase-tracking wrapper (auto context_updates)
```

---

## Implementation Steps

### Step 1 — Add `executor` field to `tool.json` files

Standard Python entry-point format: `module.path:callable_name`

**`create_role/tool.json`:**
```json
{
  "name": "create_role",
  "executor": "openteam.server.resources.tools.create_role.executor:execute",
  ...
}
```

**`role_setup/tool.json`:**
```json
{
  "name": "role_setup",
  "executor": "openteam.server.resources.tools.role_setup.executor:execute",
  ...
}
```

Slack/TWG tools: **no `executor` field** — handled by `IntegrationToolExecutor` fallback.

`ToolDefinition.from_dict()` silently ignores the `executor` key — non-breaking, verified.

### Step 2 — Add `execute()` entry points to existing tool executors

Standard signature for ALL action tools:
```python
async def execute(
    arguments: dict[str, Any], session_context: dict[str, Any]
) -> ToolExecutionResult:
    """Generic executor entry point called by ToolDispatcher."""
```

`session_context` contains: `working_dir`, `session_id`, `cloud_id`, `uct_token`, `email`
— captured once at `ToolDispatcher` construction, not passed per call from CI.

**`create_role/executor.py`** — wrap `build_create_role_inferencer()`:
```python
async def execute(arguments, session_context):
    inferencer = build_create_role_inferencer(
        cloud_id=session_context.get("cloud_id"),
        uct_token=session_context.get("uct_token"),
    )
    role_description = arguments.get("role_description", "")
    output_path = arguments.get("--output-path")  # optional
    result_text = await inferencer.ainfer(role_description)
    # Include output path in result so LLM can reference it in Phase 1b
    return ToolExecutionResult(
        result=str(result_text),
        context_updates={"role_document_path": output_path} if output_path else {},
    )
```

**`role_setup/executor.py`** — wrap `build_role_setup_inferencer()`:
```python
async def execute(arguments, session_context):
    inferencer = build_role_setup_inferencer(
        role_document_path=arguments.get("role_document_path", ""),
        cloud_id=session_context.get("cloud_id"),
        uct_token=session_context.get("uct_token"),
    )
    # role_setup takes the file path directly — reads content internally
    result_text = await inferencer.ainfer(arguments.get("role_document_path", ""))
    return ToolExecutionResult(result=str(result_text))
```

### Step 3 — Create `ToolDispatcher` class

**New file:** `src/openteam/server/services/tool_dispatcher.py`

```python
class ToolDispatcher:
    """Registry-driven generic tool dispatcher.

    Reads 'executor' field from each tool's tool.json (via source_path on ToolDefinition).
    Falls back to IntegrationToolExecutor for integration tools (Slack, TWG).
    Session context is captured at construction — __call__ conforms to
    ToolExecutorCallable protocol: async (tool_name, arguments) → ToolExecutionResult.
    """

    def __init__(
        self,
        tool_registry: dict[str, ToolDefinition],
        integration_executor: IntegrationToolExecutor,
        session_context: dict[str, Any],
    ):
        self._integration_executor = integration_executor
        self._session_context = session_context
        self._executor_map: dict[str, Callable] = {}
        self._load_executors(tool_registry)

    def _load_executors(self, tool_registry: dict) -> None:
        """Read 'executor' from each tool's source tool.json, import the callable."""
        for name, tool_def in tool_registry.items():
            if not tool_def.source_path:  # guard: skip tools without source_path
                continue
            tool_json_path = Path(tool_def.source_path)
            if not tool_json_path.exists():
                continue
            data = json.loads(tool_json_path.read_text())
            executor_ref = data.get("executor")
            if executor_ref:
                try:
                    self._executor_map[name] = self._import_callable(executor_ref)
                except (ImportError, AttributeError) as e:
                    logger.warning("Failed to load executor for %s: %s", name, e)

    @staticmethod
    def _import_callable(ref: str) -> Callable:
        """Import 'module.path:callable_name' → callable."""
        module_path, _, callable_name = ref.rpartition(":")
        module = importlib.import_module(module_path)
        return getattr(module, callable_name)

    def handles(self, tool_name: str) -> bool:
        return (tool_name in self._executor_map or
                self._integration_executor.handles(tool_name))

    async def __call__(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        # 1. Registry-declared executors (create_role, role_setup, future tools)
        if tool_name in self._executor_map:
            return await self._executor_map[tool_name](
                arguments, self._session_context
            )
        # 2. Integration tools fallback (Slack, TWG)
        if self._integration_executor.handles(tool_name):
            return await self._integration_executor(tool_name, arguments)
        # 3. Unknown
        return ToolExecutionResult(result=f"Unknown tool: {tool_name}")
```

### Step 4 — Wire into `conversation_service.py`

Replace the hardcoded closure (lines 267–288) with `ToolDispatcher`, **preserving SOP phase tracking**:

```python
from openteam.server.services.tool_dispatcher import ToolDispatcher

session_context = {
    "working_dir": self._working_dir,
    "session_id": session.get("id") if session else None,
    # cloud_id, uct_token from env/config as needed
}
dispatcher = ToolDispatcher(
    tool_registry=tool_registry,
    integration_executor=integration_executor,
    session_context=session_context,
)
conv_inferencer = None  # assigned after closure (Python closure captures by name)

async def tool_executor(tool_name, arguments):
    result = await dispatcher(tool_name, arguments)
    # Preserve existing SOP phase-tracking logic:
    # Auto-derive context_updates from tool_phase_map (set by _render_prompt() from SOP)
    if hasattr(result, "context_updates") and conv_inferencer is not None:
        tool_phase_map = conv_inferencer.prior_context.get("tool_phase_map", {})
        tool_phase = tool_phase_map.get(tool_name)
        if tool_phase and "current_phase" not in result.context_updates:
            result.context_updates["current_phase"] = tool_phase
            result.context_updates["phase_status"] = "completed"
    return result
```

---

## Files to Create/Modify

| File | Action | Change |
|---|---|---|
| `server/services/tool_dispatcher.py` | **CREATE** | `ToolDispatcher` class |
| `server/resources/tools/create_role/tool.json` | **MODIFY** | Add `"executor": "...executor:execute"` |
| `server/resources/tools/role_setup/tool.json` | **MODIFY** | Add `"executor": "...executor:execute"` |
| `server/resources/tools/create_role/executor.py` | **MODIFY** | Add `execute(arguments, session_context)` |
| `server/resources/tools/role_setup/executor.py` | **MODIFY** | Add `execute(arguments, session_context)` |
| `server/services/conversation_service.py` | **MODIFY** | Replace hardcoded closure with `ToolDispatcher` |

---

## What This Fixes

| Problem | Before | After |
|---|---|---|
| `create_role` invocation | ❌ "Unknown tool" | ✅ Dispatched via `executor:execute()` |
| `role_setup` invocation | ❌ "Unknown tool" | ✅ Dispatched via `executor:execute()` |
| Adding a new tool | ❌ Modify `dispatch.py` + `conversation_service.py` | ✅ Create `tool.json` + `executor.py` |
| Integration tools (Slack, TWG) | ✅ Working | ✅ Still working (fallback path) |
| SOP phase tracking | ✅ Working | ✅ Preserved in wrapper |

---

## Future Work (Out of Scope)

1. **Streaming/long-running tools** — `create_role` and `role_setup` are long-running (minutes).
   Currently they block the WebSocket turn. Need `asynchronous: true` + background task pattern
   (like RankEvolve's task queue).
2. **Parameter validation** — validate `arguments` against `tool.json` parameter schema before dispatch.
3. **`session_context` formalization** — define canonical keys (cloud_id source, uct_token source, etc.).
4. **`create_role` output path** — `ToolExecutionResult.context_updates["role_document_path"]`
   needs to flow into `prior_context` so Phase 1b can reference it in the `confirmation` `view` param.

---

## Verification

1. **Unit test** — `ToolDispatcher` with mock registry pointing to `create_role/tool.json` → verifies `execute()` is imported and dispatched
2. **Integration test** — start rovodev session, LLM invokes `create_role` → no "Unknown tool", inferencer builds
3. **Regression** — Slack/TWG tools still dispatch via `IntegrationToolExecutor` fallback
4. **Existing tests** — `test_create_role_dryrun.py` passes after `execute()` added to `executor.py`
