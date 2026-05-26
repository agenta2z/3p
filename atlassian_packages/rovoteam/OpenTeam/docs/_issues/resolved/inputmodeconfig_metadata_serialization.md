# Issue: InputModeConfig.to_dict() Drops metadata — Confirmation Widget Renders as TextInput

**Date:** 2026-04-18  
**Resolved:** 2026-04-18  
**Severity:** High  
**Status:** Resolved  

---

## Context

After `create_role` task completion, the UI should show a ConfirmationWidget with
`[View Role Document] [Approve & Proceed] [Request Changes]` buttons. Instead, it
rendered a plain TextInput (free-text clarification prompt).

The LLM output was correct — it produced a proper `"name":"confirmation"` conversation
tool with `metadata.view`, `metadata.view_label`, `metadata.yes_label`, `metadata.no_label`.
The server-side parser correctly extracted everything. The UI dispatch logic was correct.
The server was restarted. Yet the widget still showed as TextInput.

---

## Root Cause

`InputModeConfig.to_dict()` in `agent_foundation/ui/input_modes.py` did NOT serialize
the `metadata` field. The `metadata` dict (containing `widget_type`, `view`, `yes_label`,
`no_label`, etc.) was silently dropped during serialization for WebSocket transport.

```python
# BEFORE (broken) — to_dict() only serializes mode, prompt, and mode-specific fields
def to_dict(self) -> Dict[str, Any]:
    d = {'mode': self.mode.value}
    if self.prompt:
        d['prompt'] = self.prompt
    # ... EXACT_STRING and SINGLE_CHOICE/MULTIPLE_CHOICES branches ...
    return d  # metadata NEVER included
```

The `metadata` field was added to the `InputModeConfig` dataclass (line 35) but
`to_dict()` and `from_dict()` were never updated to handle it. This is a classic
dataclass serialization drift — adding a field without updating hand-written
serialization methods.

### The Full Chain (8 hops)

```
1. LLM outputs:        {"type":"conversation","name":"confirmation","arguments":{"metadata":{...}}}  OK
2. Parser extracts:    ConversationTool(tool_type="confirmation", metadata={view, view_label, ...})   OK
3. _build_input_mode:  InputModeConfig(mode=FREE_TEXT, metadata={widget_type:"confirmation", ...})    OK
4. to_dict():          {mode: "free_text", prompt: "..."}  <-- metadata DROPPED here
5. WS message:         {"type":"pending_input","input_mode":{mode:"free_text",prompt:"..."}}          BROKEN
6. Client dispatch:    metadata.widget_type || mode  →  undefined || "free_text"  →  TextInputWidget  BROKEN
```

### Why It Was Hard to Find

- Every layer looked correct in isolation when reading source code
- The bug was in a "boring" utility method (`to_dict()`) that appeared obviously correct
- Investigation focused on parsing (hops 1-3) and UI dispatch (hop 6-8), skipping the
  serialization boundary (hop 4)
- Early misdirection toward "server not restarted" and "code not loaded" hypotheses
  consumed investigation time

---

## Impact

- **Confirmation widget** rendered as TextInput — no Approve/Decline buttons, no View Document
- **Compound widgets** (multi-tool tabbed input) lost their metadata
- **Any widget type relying on metadata** was affected
- **Single choice and multiple choice widgets** were NOT affected — their data lives in
  `options` (serialized separately), not in `metadata`

---

## Fix

### `InputModeConfig.to_dict()` — serialize metadata

```python
def to_dict(self) -> Dict[str, Any]:
    d = {'mode': self.mode.value}
    if self.prompt:
        d['prompt'] = self.prompt
    if self.metadata:                    # ADDED
        d['metadata'] = self.metadata    # ADDED
    # ... rest unchanged ...
```

### `InputModeConfig.from_dict()` — deserialize metadata (symmetry)

```python
@classmethod
def from_dict(cls, d):
    # ... existing code ...
    config.metadata = d.get('metadata', {})  # ADDED
    return config
```

---

## Additional Changes (same session)

### Server file logging

Added `logging.FileHandler` in `main.py` lifespan to persist all logs to
`<server_dir>/server.log`. Each server run gets its own log file alongside
session/turn/task data. Handler is removed on shutdown to prevent accumulation.

### Diagnostic logging

- `conversation_response_parser.py`: log parser input (length + first 120 chars)
- `conversational_inferencer.py`: log clean_response source (output_file vs raw_stream),
  and log when `has_conversation_tool=False` (previously only logged the True case)

---

## Files Modified

| File | Change |
|---|---|
| `AgentFoundation/src/agent_foundation/ui/input_modes.py` | `to_dict()` + `from_dict()` metadata |
| `OpenTeam/src/openteam/server/main.py` | FileHandler for `server.log` |
| `AgentFoundation/src/.../conversation_response_parser.py` | Parser input logging |
| `AgentFoundation/src/.../conversational_inferencer.py` | Clean response + tool detection logging |

---

## Verification

After server restart:
1. `server.log` appears in server workspace directory
2. Create role flow -> task completes -> auto-advance -> ConfirmationWidget renders with
   View Document, Approve, and Request Changes buttons
3. Server log shows: `[asend_response] input_mode.mode=free_text metadata={widget_type: confirmation, view: ...}`
4. Browser console shows: `[pending_input] input_mode: {"mode":"free_text","metadata":{"widget_type":"confirmation",...}}`
