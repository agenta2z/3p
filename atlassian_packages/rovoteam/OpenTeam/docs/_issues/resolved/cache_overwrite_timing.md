# Issue: Cache Overwrite Timing — Base Class Finally Runs Before RovoDev Override Finally

**Date:** 2026-04-13  
**Resolved:** 2026-04-13  
**Severity:** Medium  
**Status:** ✅ Resolved  
**Related plan:** `AgentFoundation/src/agent_foundation/common/_docs/_plan/streaming_clean_final_output.md`

---

## Context

The `get_final_output()` / `streams_differ_from_final_output` system was implemented to give
`ConversationalInferencer` access to clean LLM output from `--output-file` instead of noisy
TUI stdout. The core fix works correctly for conversation tool detection.

However, the cache overwrite feature (replacing noisy cached stream with clean output) does NOT
work due to a generator delegation timing issue.

---

## Problem

`RovoDevCliInferencer.ainfer_streaming()` is an async generator that wraps the base class:

```python
async def ainfer_streaming(self, ...):
    # ... setup ...
    try:
        async for chunk in super().ainfer_streaming(...):  # base class generator
            yield chunk
    finally:
        # Read --output-file → self._last_clean_output  ← SET HERE
        ...
```

`StreamingInferencerBase.ainfer_streaming()` (base class) has its own `finally` block that
attempts to overwrite the cache with clean content:

```python
finally:
    if self.streams_differ_from_final_output and cache_file:
        final = self.get_final_output()  # ← CALLED HERE
        if final:
            # overwrite cache with clean content
```

**The ordering of finally blocks:**

```
1. Base class inner generator exhausts
2. → Base class ainfer_streaming() finally runs:
       self.get_final_output() → self._last_clean_output is None (not set yet) → None
       → no cache overwrite ❌
       → _finalize_cache() writes noisy content + success marker
3. → RovoDev override's async for exits
4. → RovoDev override's finally runs:
       reads --output-file → self._last_clean_output = "clean content"  ← too late
5. → stream_token_batches() returns raw_response
6. → ConversationalInferencer calls get_final_output() → _last_clean_output ✅ (works!)
```

The base class `finally` runs **before** the RovoDev override `finally`, so `_last_clean_output`
is always `None` when the cache overwrite tries to use it.

---

## Impact

- **Cache files remain noisy** — contains raw TUI stdout (ANSI codes, TUI separators, headers)
  instead of clean `--output-file` content
- **Crash recovery is degraded** — if server crashes mid-session, recovery inference gets
  noisy context instead of clean LLM output
- **Core functionality NOT affected** — conversation tool detection works correctly because
  `ConversationalInferencer` calls `get_final_output()` at step 6 (after RovoDev finally runs)

---

## Verified Working

The core fix IS working:
- `ConversationalInferencer` calls `get_final_output()` AFTER `stream_token_batches()` returns
- At that point, RovoDev override's `finally` has already run → `_last_clean_output` is set
- `parse_conversation_response(clean_output)` correctly detects conversation tools
- Conversation tool widgets appear in the UI ✅

Evidence: `stream_39539624_0dec8cae.txt` in `server_20260413_223147_a132b7c1` shows clean
content for a turn where conversation tools were successfully detected.

---

## Proposed Fix

The fix requires making the base class cache overwrite happen AFTER the subclass has had a
chance to populate `_last_clean_output`. Options:

### Option A — Move file read into base class via a hook (cleanest)

Add a `_before_cache_finalize()` hook to `StreamingInferencerBase` that subclasses override:

```python
# StreamingInferencerBase:
def _before_cache_finalize(self) -> None:
    """Called in finally block before cache overwrite. Subclasses populate state here."""
    pass

# finally block:
finally:
    self._before_cache_finalize()  # ← RovoDev reads file here
    if self.streams_differ_from_final_output:
        final = self.get_final_output()  # ← now has _last_clean_output
        ...
```

```python
# RovoDevCliInferencer:
def _before_cache_finalize(self) -> None:
    """Read --output-file into _last_clean_output before cache finalization."""
    if self.enable_legacy and self._auto_output_file:
        try:
            p = Path(self._auto_output_file)
            self._last_clean_output = p.read_text(encoding="utf-8").strip() or None
        except OSError:
            self._last_clean_output = None
```

This requires storing `auto_output_file` as an instance var (`self._auto_output_file`)
set in `ainfer_streaming()` before yielding.

### Option B — Read file in base class using contextvar (simpler but fragile)

In the base class `finally`, check `_current_output_file.get(None)` directly for reading
(not just in `get_final_output()`). The contextvar is still valid at this point.

### Option C — Accept the limitation (current state)

Cache files remain noisy. Crash recovery works but with noisy context. Acceptable tradeoff
since the primary benefit (clean parsing) is already working.

---

## Files Involved

| File | Location |
|---|---|
| `streaming_inferencer_base.py` | `AgentFoundation/src/agent_foundation/common/inferencers/` |
| `rovodev_cli_inferencer.py` | `AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/external/rovodev/` |

---

## Resolution (2026-04-13)

Implemented **`_get_clean_output_for_cache()` hook** — a variant of Option A that is simpler
and more focused than a generic `_before_cache_finalize()`:

### Changes Made

**`StreamingInferencerBase`** (`streaming_inferencer_base.py`):
- Added `_get_clean_output_for_cache() -> Optional[str]` method (base returns `None`)
- In `_ainfer_streaming()` finally block: replaced `self.get_final_output()` with
  `self._get_clean_output_for_cache()` for the cache overwrite call
- Key timing: `_get_clean_output_for_cache()` is called INSIDE the base class generator's
  finally block — at which point the subclass's own finally hasn't run yet, so contextvar
  is still set and `--output-file` still exists on disk

**`RovoDevCliInferencer`** (`rovodev_cli_inferencer.py`):
- Added `_get_clean_output_for_cache()` override that reads from `_current_output_file`
  contextvar (valid at call time) and returns the clean `--output-file` content
- This is intentionally separate from `get_final_output()` which uses `_last_clean_output`
  (set in the subclass's own finally, after the base class finally has run)

### Why This Works (Timing)

```
Base class _ainfer_streaming() finally:
    → _get_clean_output_for_cache()    ← RovoDev reads file via contextvar ✅
    → overwrites cache with clean text ✅
    → _finalize_cache()

RovoDev ainfer_streaming() finally (runs AFTER):
    → reads --output-file → _last_clean_output (for get_final_output())
    → deletes --output-file
    → clears _current_output_file contextvar
```

### Tests
All 16 tests in `test_get_final_output.py` pass. ✅
