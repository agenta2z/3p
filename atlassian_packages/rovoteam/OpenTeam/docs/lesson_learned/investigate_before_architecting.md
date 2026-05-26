# Lesson Learned: Investigate Session Logs Before Changing Architecture

**Date:** 2026-04-22  
**Origin:** `shared_aggregator_and_async_dispatch_premature_advance` issue  

---

## The Pattern

When a system produces wrong output, the instinct is to change the architecture to prevent the wrong output. But the architecture may be correct — the bug may be elsewhere, and the architectural change introduces new problems worse than the original.

**Always check the session logs first.** The logs show what actually happened, not what you think happened.

---

## What Happened

The user reported "the LLM shows Phase 1 complete before the task finishes." The obvious diagnosis: the fire-and-forget tool dispatch is broken — the LLM shouldn't advance until the task completes.

**The "fix":** Changed fire-and-forget to await. The agentic loop now blocks until the tool completes. The LLM only responds after the file is written.

**What this broke:**
1. The auto-advance mechanism (task_completed → client synthetic message → new turn with Phase 1b guidance) was the SOLE mechanism for providing Phase 1b instructions to the LLM. Removing fire-and-forget removed the auto-advance.
2. The LLM received the tool result but had no Phase 1b guidance (nextstep guidance is rendered once per turn, not per iteration). It generated a generic widget instead of the correct confirmation with "View Role Document."
3. The SOP nextstep guidance never advances past Phase 0 because conversation tools don't update phase tracking. Without the auto-advance, the LLM had no instructions for any phase beyond Phase 0.

**What the session logs actually showed:**
- Turn 003's `InferenceResponse` was **0 bytes** — the LLM generated NO premature text in the original April 20 session
- Turn 004 was the auto-advance turn — it worked correctly, producing the right confirmation with view metadata
- The user saw a "Running" task card alongside the confirmation because of a DIFFERENT bug (stale node status from RAF batching), not because the confirmation appeared too early

**The real root cause** (found 3 days later by reading session logs from a REPRODUCING session):
- Turn had TWO `RovoDevCliInferencer` stream files: iteration #1 (correct tool call), iteration #2 (premature text)
- The agentic loop's `content = _CONTINUE_AFTER_TOOLS` triggered a second LLM call
- The LLM saw "Tool launched asynchronously" in history and stochastically generated "Phase 1 complete!"
- The fix: set a flag on async dispatch, check it before continuing, return early

**The correct fix was 3 lines.** The incorrect architectural change was ~100 lines across 4 files and broke the system.

---

## Why This Took So Long

### 1. Multiple issues masquerading as one

The user saw: confirmation widget + "Running" task card + wrong file content. This LOOKED like premature advancement but was actually three separate bugs:
- Issue #1: Stale Running status (RAF batching race)
- Issue #4: _finalize_output overwriting deliverables
- Issue #5: Premature agentic loop continuation

Fixing issues #1 and #4 first would have made the system APPEAR to work correctly — the premature advancement was stochastic and didn't always manifest.

### 2. Solving the symptom instead of the cause

The symptom (LLM advances too early) led to the architectural change (await instead of fire-and-forget). But the cause (agentic loop iteration #2) was a simple control flow issue. The architectural change addressed the symptom but created new problems.

### 3. Not reading the evidence first

The session logs had the answer from the start. Turn 003's 0-byte InferenceResponse proved the LLM did NOT prematurely advance in the original session. The premature advancement was from a SECOND LLM call within the same turn — visible in the turn_002 stream files. Reading these files first would have saved 2 days.

### 4. Feedback loops without convergence

Multiple review cycles with another agent produced increasingly detailed critiques but didn't converge on the fix. Each review found new edge cases (CancelledError, multi-tool turns, phase_status leakage) that, while technically valid, were irrelevant to the core bug. The fix was 3 lines; the reviews consumed 10x more effort than the implementation.

---

## Generic Learnings

### 1. Read the logs before changing code

For any "the system does X when it should do Y" bug:
1. Find the session/run that exhibited the bug
2. Read the actual logs (rendered prompts, API payloads, responses, turn structure)
3. Trace the exact sequence of events that produced the wrong output
4. THEN propose a fix that addresses the ACTUAL sequence, not the hypothesized one

### 2. Understand the existing design before replacing it

The fire-and-forget + auto-advance pattern was intentional:
- Fire-and-forget: tool runs in background, agentic loop ends, UI shows task progress
- Auto-advance: when task completes, client sends explicit message with Phase 1b instructions
- New turn: prompt re-renders with updated SOP guidance

Replacing this with await removed the ONLY mechanism for providing phase-specific instructions. Understanding WHY the design existed would have prevented the incorrect fix.

### 3. Check if the bug is stochastic before changing architecture

The premature "Phase 1 complete!" was stochastic — it happened in some sessions but not others. The April 20 session worked correctly (0-byte InferenceResponse). A stochastic LLM behavior issue rarely warrants an architectural change — it needs a control flow guard.

### 4. Multiple bugs create misleading symptoms

When three bugs overlap (stale status + file overwrite + premature text), the combined symptom looks like one big bug with an obvious architectural cause. Fix each bug independently with targeted changes, not one sweeping architectural change.

### 5. The simplest fix that could work

The final fix was setting a boolean flag in `_execute_tool_call` and checking it before `continue` in the agentic loop. Three lines of code. The intermediate attempts involved changing return types, adding SOP re-evaluation, modifying executors, and restructuring the dispatch flow — all unnecessary.
