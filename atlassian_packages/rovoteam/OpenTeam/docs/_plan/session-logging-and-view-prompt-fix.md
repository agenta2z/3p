# Plan: Proper Session Logging (RankEvolve Pattern) + View Prompt Fix + SOP Fix

**Date:** 2026-04-18  
**Status:** Ready to implement — FINAL CORRECTED VERSION

---

## Critical Architecture Decision: JsonLogger Directly (NOT SessionLogger)

`SessionLogger.__init__` ALWAYS creates a NEW nested subdirectory (`base_log_dir / f"{session_id}_{timestamp}"`). There is NO `from_existing()` API. Using `SessionLogger` would create:
```
session-xxx_20260418/        ← existing OpenTeam dir
  session-xxx_20260418_xxx/  ← UNWANTED nested dir created by SessionLogger
    manifest.json
    turn_001/
```

**Fix:** Use `JsonLogger` directly with the `group=` parameter — this gives IDENTICAL file structure to RankEvolve WITHOUT directory ownership conflicts.

Note: `SessionLogger` has no `from_existing()` method — the class spans lines 22-294 of `session_logger.py` (verified; `SessionLogReader` starts at line 296). Using `JsonLogger` directly bypasses the directory ownership issue entirely:

```python
from python_utils.io_utils.json_io import JsonLogger

json_logger = JsonLogger(
    file_path=str(session_dir / "session.jsonl"),
    append=True,
    parts_min_size=0,        # all fields extracted to parts/ (matches RankEvolve)
    is_artifact=True,        # auto-sets parts_key_paths (matches RankEvolve)
    parts_file_namer=lambda obj: obj.get("type", ""),  # matches RankEvolve
    # space_ext_mode omitted: only affects space= param, not group=/subfolder=
)
# Log with group= to route to turn subdir:
json_logger({"type": "UserInput", "item": "..."}, 
            group="turn_001",            # → writes to session_dir/turn_001/session.jsonl
            parts_key_path_root="item")  # → large items go to turn_001/session.jsonl.parts/
```

This produces (close to RankEvolve's structure — adapted to avoid SessionLogger's nested dir):
```
session-xxx_20260418/
  session.jsonl             ← cross-turn session log
  turn_001/
    session.jsonl           ← per-turn JSONL (UserInput, PromptTemplate, RenderedPrompt, ...)
    RenderedPrompt.parts/   ← auto-created (parts_min_size=0, type name used as dir)
      timestamp.txt
    PromptTemplate.parts/
      timestamp.txt
    stream_*.txt            ← streaming cache (cache_folder=turn_dir)
```

**Adapts RankEvolve's pattern** using `JsonLogger` directly. Key differences from RankEvolve:
- No `SessionLogger` wrapper (avoids nested dir creation)
- Manual `group=` routing instead of `start_turn()`
- OpenTeam uses `inferencer.system_prompt` property (→ `base_inferencer.system_prompt`) instead of `conversation.system_prompt`

---

## Issue 1: View Prompt 404

### Root Cause

**A.** Welcome message (turn 1) is never a `run_conversation_turn` call → no data saved → 404.

**B.** `save_turn_data` writes to `session_dir/turns/turn_NNN/` but after this fix it should write to `session_dir/turn_NNN/` (unified structure). The REST API must be updated too.

**C.** `pending_input` preamble messages have `turnNumber` set (to upcoming turn) but no `promptData` inline → View Prompt does a REST fetch that may 404 if turn not yet saved.

### Fix 1A — Graceful empty response instead of 404

**File:** `server/routes/view_routes.py` — fix existing bug: `session_store.runtime_dir` → `session_store.runtime_root`

```python
# Line 51 — EXISTING BUG: SessionStore has no runtime_dir attr (it's runtime_root)
# This causes security check to always fall through to the weaker string-based fallback
runtime_dir = getattr(session_store, "runtime_root", None)  # was: "runtime_dir"
```

**File:** `server/routes/session_routes.py`

```python
data = svc.get_turn_data(session_id, turn_number)
if data is None:
    return {"data": {"rendered_prompt": "", "template_source": "",
                     "note": f"No prompt data for turn {turn_number}"}}
```

**File:** `ui/src/components/views/ManagerChatView.js` — `handleViewPrompt`

The existing function has a 3-branch structure. Add the null-check INSIDE branch 2 (slow path):

```javascript
// Existing branch 2 (slow path — REST fetch):
} else if (message.turnNumber && fetchTurnData) {
    // fetchTurnData may return empty data (graceful 200) for uncaptured turns
    const data = await fetchTurnData(sessionId, message.turnNumber);
    if (!data?.rendered_prompt && !data?.template_source) {
        console.debug('[ViewPrompt] no prompt data for turn', message.turnNumber);
        return;  // Don't open empty drawer
    }
    promptViewer.openPrompt(data);  // matches existing call at ManagerChatView.js:279
}
```

### Fix 1B — Update save_turn_data/get_turn_data to use session_dir/turn_NNN/

**File:** `server/services/session_store.py`

Change the turn directory from `session_dir/turns/turn_NNN/` → `session_dir/turn_NNN/`:

```python
def save_turn_data(self, session_id, turn_number, turn_data):
    session_dir = self._find_session_dir(session_id)  # or get_session_dir()
    if session_dir is None:
        return
    # CHANGED: turn_NNN/ at session root (matches RankEvolve) instead of turns/turn_NNN/
    turn_dir = session_dir / f"turn_{turn_number:03d}"
    turn_dir.mkdir(parents=True, exist_ok=True)
    # ... write individual files as before
    self._atomic_write(turn_dir / "turn.json", turn_data)

def get_turn_data(self, session_id, turn_number):
    session_dir = self._find_session_dir(session_id)
    if session_dir is None:
        return None
    # CHANGED: look at session_dir/turn_NNN/ first (new unified location)
    turn_dir = session_dir / f"turn_{turn_number:03d}"
    combined = turn_dir / "turn.json"
    if combined.is_file():
        return json.loads(combined.read_text(encoding="utf-8"))
    # Fallback: old turns/ location for existing sessions
    old_turn_file = session_dir / "turns" / f"turn_{turn_number:03d}.json"
    if old_turn_file.is_file():
        return json.loads(old_turn_file.read_text(encoding="utf-8"))
    old_turn_dir = session_dir / "turns" / f"turn_{turn_number:03d}" / "turn.json"
    if old_turn_dir.is_file():
        return json.loads(old_turn_dir.read_text(encoding="utf-8"))
    return None

def get_session_dir(self, session_id: str) -> Path | None:
    """Public wrapper for _find_session_dir."""
    return self._find_session_dir(session_id)
```

### Fix 1C — Inline prompt_data in pending_input WS message

**File:** `server/services/websocket_interactive.py` — `asend_response()`

Send prompt data inline. `asend_response` already accepts `**kwargs` — read `prompt_data` from kwargs:

```python
async def asend_response(self, response, flag=None, **kwargs):
    # ... existing mode building ...
    msg = {
        "type": "pending_input",
        "content": str(response),
        "input_mode": input_mode.to_dict(),
    }
    # Include prompt_data from caller (passed as kwarg by _handle_conversation_tool)
    # OR from cached _last_prompt_data set between iterations by on_new_turn
    _pd = kwargs.pop('prompt_data', None) or getattr(self, '_last_prompt_data', None)
    if _pd:
        msg["prompt_data"] = _pd
    await self._send(msg)
```

Initialize `_last_prompt_data = None` in `WebSocketInteractive.__init__`.

**File:** `AgentFoundation/.../conversational_inferencer.py` — `_handle_conversation_tool()` (~line 953)

Pass prompt_data as kwarg directly from inferencer — this is the ONLY point where prompt data is available inline before `asend_response` is called:

```python
await active_interactive.asend_response(
    assistant_text,
    flag=InteractionFlags.PendingInput,
    input_mode=input_mode,
    prompt_data={                               # ← ADD: inline prompt data for View Prompt
        "rendered_prompt": getattr(self, "_last_rendered_prompt", "") or "",
        "template_source": getattr(self, "_last_template_source", "") or "",
        "template_feed": getattr(self, "_last_template_feed", {}) or {},
        "template_config": getattr(self, "_last_template_config", {}) or {},
    },
)
```

No callbacks needed. Works immediately on the FIRST widget response (before `on_new_turn` fires).

**File:** `ui/src/hooks/useManagerChat.js` — `pending_input` handler

```javascript
case 'pending_input': {
    // ... existing displayContent stripping logic ...
    setMessages(prev => [...prev, {
        id: `pending-pre-${Date.now()}`,
        role: 'agent',
        content: displayContent,
        rawContent: streamContent,
        timestamp: new Date().toISOString(),
        agent_name: streamingMetadataRef.current?.agent_name || 'Orchestrator',
        thinkingContent: parsed.thinkingContent || '',
        responsePhase: hasResponse ? phase : 'no_tags',
        sessionContext: null,
        promptData: data.prompt_data || null,    // ← inline from WS message
        turnNumber: (turnCountRef.current || 0) + 1,
    }]);
    // ...
}
```

---

## Issue 2: Proper Session Logging with JsonLogger

### Wiring in conversation_service.py

**File:** `server/services/conversation_service.py`

Cache `JsonLogger` per session (not per call), wire `on_new_turn` callback exactly matching RankEvolve:

```python
class ConversationService:
    def __init__(self, ...):
        # ... existing ...
        self._session_loggers: dict[str, Any] = {}  # session_id → JsonLogger

    def _get_or_create_session_logger(self, session_id: str, data_service=None):
        """Get or create a JsonLogger for this session. Cached per session."""
        if session_id in self._session_loggers:
            return self._session_loggers[session_id]

        if data_service is None or not hasattr(data_service, 'get_session_dir'):
            return None

        session_dir = data_service.get_session_dir(session_id)
        if session_dir is None:
            return None

        try:
            from python_utils.io_utils.json_io import JsonLogger, SpaceExtMode
            logger = JsonLogger(
                file_path=str(session_dir / "session.jsonl"),
                append=True,
                parts_min_size=0,          # extract ALL fields to parts/ dirs (matches RankEvolve)
                is_artifact=True,              # auto-sets parts_key_paths (matches RankEvolve)
                # NOTE: space_ext_mode only applies when space= is used (not group=/subfolder=)
                # — omitted as it's a no-op here.
                parts_file_namer=lambda obj: (
                    obj.get("type", "") if isinstance(obj, dict) else ""
                ),  # matches RankEvolve's lambda obj: obj.get("type", "")
            )
            self._session_loggers[session_id] = logger
            return logger
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to create JsonLogger: %s", e)
            return None

    async def run_conversation_turn(self, session, user_message, *, interactive, data_service=None):
        sid = session["id"]
        inferencer = self._get_session_inferencer(sid)
        json_logger = self._get_or_create_session_logger(sid, data_service)

        # Track last widget response so final turn has correct user_input
        last_widget_response = [None]  # mutable closure; None means use original user_message

        # Determine initial turn number from existing turn dirs
        session_dir = (data_service.get_session_dir(sid)
                       if data_service and hasattr(data_service, 'get_session_dir') else None)
        if session_dir:
            # Count existing turn dirs at session root (new RankEvolve-style turn_NNN/).
            # Don't use max(new_style, old_style) — that would undercount during migration
            # if a session has turns in BOTH locations. Instead: count new-style (our going-forward
            # format). Fallback to old turns/ count only if no new-style dirs exist yet.
            new_style = [d for d in session_dir.iterdir()
                          if d.is_dir() and d.name.startswith('turn_')]
            if new_style:
                existing_turns = len(new_style)
            else:
                old_style_dir = session_dir / "turns"
                existing_turns = len([d for d in old_style_dir.iterdir()
                                       if d.is_dir() and d.name.startswith('turn_')]) if old_style_dir.is_dir() else 0
            initial_turn_number = existing_turns + 1
        else:
            initial_turn_number = sum(
                1 for m in session.get("messages", [])
                if m.get("role") in ("assistant", "agent")
            ) + 1

        current_turn = [initial_turn_number]

        # Set cache_folder for first turn
        if session_dir and inferencer:
            turn_dir = session_dir / f"turn_{initial_turn_number:03d}"
            turn_dir.mkdir(parents=True, exist_ok=True)
            if hasattr(inferencer, 'cache_folder'):
                inferencer.cache_folder = str(turn_dir)

        # Log initial user input
        if json_logger:
            try:
                json_logger({"type": "UserInput", "item": user_message},
                            group=f"turn_{initial_turn_number:03d}",
                            parts_key_path_root="item")
            except Exception:
                pass

        async def _on_new_turn(prev_turn: int, widget_response: str) -> int:
            """Log prev turn's artifacts, advance turn, set cache_folder.
            Mirrors RankEvolve message_handlers.py _on_new_turn exactly."""
            if json_logger and session_dir:
                import json as _json
                _grp = f"turn_{prev_turn:03d}"
                try:
                    if getattr(inferencer, '_last_template_source', None):
                        json_logger({"type": "PromptTemplate",
                                     "item": inferencer._last_template_source},
                                    group=_grp, parts_key_path_root="item")
                    if getattr(inferencer, '_last_template_feed', None):
                        json_logger({"type": "TemplateFeed",
                                     "item": _json.dumps(inferencer._last_template_feed,
                                                          indent=2, ensure_ascii=False, default=str)},
                                    group=_grp, parts_key_path_root="item")
                    if getattr(inferencer, '_last_rendered_prompt', None):
                        json_logger({"type": "RenderedPrompt",
                                     "item": inferencer._last_rendered_prompt},
                                    group=_grp, parts_key_path_root="item")
                    if getattr(inferencer, '_last_template_config', None):
                        json_logger({"type": "TemplateConfig",
                                     "item": _json.dumps(inferencer._last_template_config,
                                                          ensure_ascii=False)},
                                    group=_grp, parts_key_path_root="item")
                    json_logger({"type": "ApiPayload",
                                 "item": _json.dumps({
                                     "system_prompt": getattr(inferencer, "system_prompt", "") or "",
                                     # Use inferencer._messages (live state) not session["messages"]
                                     # (session is a snapshot from before the turn; _messages is
                                     # updated live via add_message() throughout the loop)
                                     "messages": list(getattr(inferencer, '_messages', [])),
                                 }, indent=2, ensure_ascii=False, default=str)},
                                group=_grp, parts_key_path_root="item")
                    json_logger({"type": "InferenceResponse", "item": ""},
                                group=_grp, parts_key_path_root="item")
                except Exception:
                    pass

                # Save turn.json for this completed iteration (for View Prompt REST API)
                # IMPORTANT: save_turn_data must be called inside _on_new_turn for
                # intermediate turns — calling only after run_agentic_loop returns would
                # miss all turns except the last one.
                if data_service and hasattr(data_service, 'save_turn_data'):
                    try:
                        _prompt_data = self.get_last_prompt_data(sid) or {}
                        _prompt_data["user_input"] = widget_response
                        data_service.save_turn_data(sid, prev_turn, _prompt_data)
                        # Also update interactive._last_prompt_data for inline prompt_data in pending_input
                        if hasattr(interactive, '_last_prompt_data'):
                            interactive._last_prompt_data = _prompt_data
                    except Exception:
                        pass

                last_widget_response[0] = widget_response  # track for final turn user_input

                new_turn = prev_turn + 1
                current_turn[0] = new_turn
                new_turn_dir = session_dir / f"turn_{new_turn:03d}"
                new_turn_dir.mkdir(parents=True, exist_ok=True)
                if hasattr(inferencer, 'cache_folder'):
                    inferencer.cache_folder = str(new_turn_dir)
                try:
                    json_logger({"type": "UserInput", "item": widget_response},
                                group=f"turn_{new_turn:03d}",
                                parts_key_path_root="item")
                except Exception:
                    pass
            else:
                current_turn[0] = prev_turn + 1

            return current_turn[0]

        result = await inferencer.run_agentic_loop(
            user_message,
            interactive=interactive,
            session_id=sid,
            turn_number=initial_turn_number,
            on_new_turn=_on_new_turn,
        )

        # NOTE: save_turn_data for intermediate turns is called inside _on_new_turn.
        # The final turn's save_turn_data is called below after run_agentic_loop returns.

        # Log final turn's artifacts. on_new_turn fires BETWEEN iterations AND after
        # conversation tool interactions — but NOT after the very last iteration.
        # Must log ALL 7 types (same as _on_new_turn) for consistency with RankEvolve:
        if json_logger and session_dir:
            import json as _json
            _grp = f"turn_{current_turn[0]:03d}"
            try:
                if result.last_template_source:
                    json_logger({"type": "PromptTemplate",
                                 "item": result.last_template_source},
                                group=_grp, parts_key_path_root="item")
                if result.last_template_feed:
                    json_logger({"type": "TemplateFeed",
                                 "item": _json.dumps(result.last_template_feed,
                                                      indent=2, ensure_ascii=False, default=str)},
                                group=_grp, parts_key_path_root="item")
                if result.last_rendered_prompt:
                    json_logger({"type": "RenderedPrompt",
                                 "item": result.last_rendered_prompt},
                                group=_grp, parts_key_path_root="item")
                if result.last_template_config:
                    json_logger({"type": "TemplateConfig",
                                 "item": _json.dumps(result.last_template_config,
                                                      ensure_ascii=False)},
                                group=_grp, parts_key_path_root="item")
                json_logger({"type": "ApiPayload",
                             "item": _json.dumps({
                                 # system_prompt: ConversationalInferencer has system_prompt property
                                 # (→ base_inferencer.system_prompt, same concept as RankEvolve's)
                                 "system_prompt": getattr(inferencer, "system_prompt", "") or "",
                                 # Use inferencer._messages (live state) not session["messages"]
                                 "messages": list(getattr(inferencer, '_messages', [])),
                             }, indent=2, ensure_ascii=False, default=str)},
                            group=_grp, parts_key_path_root="item")
                json_logger({"type": "InferenceResponse", "item": result.raw_response or ""},
                            group=_grp, parts_key_path_root="item")
            except Exception as _e:
                import logging as _log
                _log.getLogger(__name__).debug("[conversation_service] JsonLogger final turn failed: %s", _e)

        # Save via save_turn_data for REST API (View Prompt)
        # Use last_widget_response if available (multi-turn), else original user_message
        if data_service and hasattr(data_service, 'save_turn_data'):
            prompt_data = self.get_last_prompt_data(sid) or {}
            prompt_data["user_input"] = last_widget_response[0] or user_message
            try:
                data_service.save_turn_data(sid, current_turn[0], prompt_data)
            except Exception as _e:
                import logging as _log
                _log.getLogger(__name__).debug("[conversation_service] save_turn_data failed: %s", _e)

        # Attach authoritative turn number to result for process_message to use
        result.turn_number = current_turn[0]
        return result
```

**File:** `server/routes/manager_websocket_routes.py`

Use `result.turn_number` instead of recomputing:

```python
# result.text is the field name (NOT result.final_content — that doesn't exist).
# The existing code at line 118 of manager_websocket_routes.py already does:
#   final_content = result.text if hasattr(result, "text") else str(result)
# Add one line AFTER that to use the authoritative turn_number from result:
turn_number = getattr(result, 'turn_number', turn_number)  # prefer authoritative value
```

---

## Issue 3: SOP Extra Clarification Questions (Two Sources)

**File:** `server/resources/prompt_templates/conversation/main/_variables/workflow/sop.jinja2`

### Sub-fix 3a: Phase 0 — LLM asking extra scope/focus question before multiple_choices

The LLM spontaneously asks "In one or two sentences, what's the primary scope/focus for this PM?" before or instead of invoking the `multiple_choices` tool. This violates the SOP but the SOP isn't strong enough to prevent it.

**Fix:** Add "IMMEDIATELY invoke" instruction and reinforce "no prior questions":

```jinja2
## Phase 0 -- Role Specification [initial]: `role_description`

**IMMEDIATELY invoke** the `multiple_choices` conversation tool below — do NOT ask any scope,
focus, domain, or clarification questions first. Do NOT send any text before invoking the tool.
The tool IS the question. Ask user what the role primarily does...
```

### Sub-fix 3b: Phase 1 — Extra confirmation before create_role

Remove the pre-create_role STOP block AND add "proceed DIRECTLY" instruction:

```
## Phase 1 -- Role Creation with Research & Document [__depends on__ Phase 0]:

After the user submits their Phase 0 category selections, proceed DIRECTLY to `/create-role`.
Do NOT ask for additional confirmation, scope clarification, or follow-up questions.
The user's Phase 0 responses ARE their authorization to proceed.
The research phase discovers scope and details autonomously.
```

Remove `__requires confirmation__` from Phase 1 header. Keep Phase 1b (post-create_role confirmation) untouched.

---

## File Summary

| File | Issue | Change |
|------|-------|--------|
| `server/routes/view_routes.py` | bugfix | Fix `runtime_dir` → `runtime_root` (existing bug — security check always falls through) |
| `server/routes/session_routes.py` | 1A | Empty 200 instead of 404 for missing turns |
| `ui/src/components/views/ManagerChatView.js` | 1A | Skip View Prompt drawer if no content |
| `server/services/session_store.py` | 1B | Unify turn dirs to `turn_NNN/` at session root; add `get_session_dir()` public method |
| `server/services/data_service.py` | 1 | Add `get_session_dir()` to `RealSessionDataService` (delegates to `_session_store._find_session_dir`) — CRITICAL: `session_store` attr is private `_session_store` |
| `AgentFoundation/.../conversational_inferencer.py` | 1C | Pass `prompt_data=` kwarg in `_handle_conversation_tool` at line 953 — additive, no impact on other consumers |

**Concrete `data_service.py` code:**

```python
class RealSessionDataService(MockDataService):
    # ... existing __init__, list_sessions, etc. ...

    def get_session_dir(self, session_id: str):
        """Expose session directory path for per-turn cache_folder setup.

        Note: _session_store is private — this public method is the clean access point.
        Used by conversation_service.py to create per-turn JsonLogger groups and set
        inferencer.cache_folder so streaming cache files land in the correct turn dir.
        """
        return self._session_store._find_session_dir(session_id)
```
| `server/services/websocket_interactive.py` | 1C | Send `prompt_data` inline in `pending_input` message; init `_last_prompt_data = None` |
| `ui/src/hooks/useManagerChat.js` | 1C | Use `data.prompt_data` in preamble message commit |
| `server/services/conversation_service.py` | 2 | `_session_loggers` cache; `_get_or_create_session_logger()`; `on_new_turn` wiring; `result.turn_number` |
| `server/routes/manager_websocket_routes.py` | 2 | Use `result.turn_number` instead of recomputing |
| `server/resources/prompt_templates/.../sop.jinja2` | 3 | Remove pre-create_role STOP + add "proceed DIRECTLY" |

**No new dependencies** — `JsonLogger`/`SpaceExtMode` are in `PythonUtils` (already in PYTHONPATH).

---

## Verification

1. After a turn, `session_dir/turn_001/session.jsonl` exists with JSONL records
2. `session_dir/turn_001/session.jsonl.parts/RenderedPrompt/timestamp.txt` auto-created for large fields
3. `stream_*.txt` files appear inside `turn_001/` (cache_folder=turn_dir)
4. `session_dir/turn_001/turn.json` exists (for View Prompt REST API)
5. View Prompt on welcome message → skips gracefully (no 404)
6. View Prompt on LLM response → opens drawer with rendered prompt
7. View Prompt on widget preamble → uses inline prompt_data (no REST fetch needed)
8. Phase 0 → create_role immediately (no extra confirmation)
9. Phase 1b confirmation widget still works
