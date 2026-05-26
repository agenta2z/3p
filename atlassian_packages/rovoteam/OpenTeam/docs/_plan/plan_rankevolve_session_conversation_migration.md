# Migration Plan: RankEvolve → OpenTeam Chat Conversation System

**Created:** 2026-04-15  
**Status:** Final — Integrated from two independent plan analyses + deep code investigation  
**Authors:** Cross-validated from two AI agent analyses + direct source reading

---

## Critical Analysis: Comparing Both Plans

Two independent plans were written. After thorough investigation of every relevant file, here is the honest reconciliation:

### Plan A (My earlier plan) — Strengths & Errors
✅ Correctly identified: widget lifecycle bugs, double-submit, no submitted state persistence in messages  
✅ Correctly identified: full session architecture (SessionContext, per-session WS routing, turn management)  
❌ **Overcomplicated**: Proposed replacing `useManagerChat` with a full RankEvolve `SessionContext` — but OpenTeam already has `useManagerChat` working well for sessions. The full context migration is valid long-term but not the immediate priority.  
❌ **Incorrect claim**: "ConfirmationWidget has no submitted state" — it DOES have `submitted` local state already (line 34: `const [submitted, setSubmitted] = useState(null)`)  
❌ **Missed**: The `ChatWidgetRenderer` system (ApprovalWidget/ChoiceWidget) is disconnected — no `onSubmit` prop at all  
❌ **Missed**: Auto-advance handling needed  

### Plan B (Other agent's plan) — Strengths & Errors
✅ Correctly identified: Phase-by-phase approach is more surgical and lower risk  
✅ Correctly identified: `ConfirmationWidget` already has `submitted` local state  
✅ Correctly identified: `SingleChoiceWidget` and `MultipleChoiceWidget` **lack** submitted state  
✅ Correctly identified: `ChatWidgetRenderer` / `ApprovalWidget` / `ChoiceWidget` disconnected — need `onSubmit`  
✅ Correctly identified: auto-advance pattern from RankEvolve  
✅ Correctly identified: turn number tracking already partially done  
❌ **Wrong on key design**: "Clear `pendingInput` immediately on submit" — WRONG. The current code correctly comments "do NOT clear pendingInput here — wait for message_end". Clearing immediately means the widget vanishes BEFORE the server has started responding, leaving the user with no feedback during inference latency. The correct approach is: submit → widget shows "submitted" non-interactive state → server responds → message_end → widget fully clears.  
❌ **Missed**: The `widget_response` message approach from RankEvolve is more complex than needed. OpenTeam already stores submitted responses in message history via `message_end`. The simpler fix is to show the submitted state IN the widget until `message_end`, then let it become part of the committed message history.  
❌ **Missed**: The multi-session SessionContext is genuinely needed for full conversation capability  

### Ground Truth From Code Investigation

After reading every file directly:

| Fact | Reality |
|---|---|
| `ConfirmationWidget.js` has submitted state | ✅ YES — `const [submitted, setSubmitted] = useState(null)` at line 34 |
| `SingleChoiceWidget.js` has submitted state | ❌ NO — no submitted state, stays interactive |
| `MultipleChoiceWidget.js` has submitted state | ❌ NO — no submitted state, stays interactive |
| `useManagerChat.js` clears pendingInput on submit | ❌ NO — deliberately waits for `message_end` |
| `useManagerChat.js` clears pendingInput on `message_end` | ✅ YES — line 199 |
| `ChatWidgetRenderer` widgets have `onSubmit` | ❌ NO — `ApprovalWidget` logs to console only |
| Server sends `turn_boundary` with `turn_number` | ✅ YES — `websocket_interactive.py:102-103` |
| Server sends `turn_number` on `message_end` | ✅ YES — `manager_websocket_routes.py:187` |
| `useManagerChat.js` handles `turn_boundary` | ❌ NO — not in switch/case |
| Server sends `auto_advance` type | ❌ NO — OpenTeam server doesn't send this yet |
| Widget disappears abruptly after submit | ✅ YES — local `submitted` state not propagated to ConversationToolWidget |

---

## The Real Problems (Confirmed, Not Assumed)

### Problem 1: Widget submitted state not propagated upward (MOST CRITICAL)

`ConfirmationWidget` has `submitted` local state, but:
1. `ConversationToolWidget` doesn't know about it — it still renders the widget
2. When `message_end` fires, `pendingInput` is cleared → entire widget unmounts
3. No record in message history of what the user chose (the widget just vanishes)

The widget goes: **interactive → [nothing]** instead of **interactive → submitted (locked) → gone after server responds**

### Problem 2: `SingleChoiceWidget` and `MultipleChoiceWidget` have NO submitted state

After user selects and submits, these stay fully interactive — user can re-click and re-submit. Double-submit is possible.

### Problem 3: `ChatWidgetRenderer` widgets are disconnected from server

`ApprovalWidget` and `ChoiceWidget` only `console.log()` on decision — no `onSubmit` prop, no WS communication. These are dashboard-view widgets, but if they get shown during an agentic conversation, responses never reach the server.

### Problem 4: `turn_boundary` event not handled by UI

Server sends `{"type": "turn_boundary", "turn_number": N, "cache_folder": "..."}` but `useManagerChat.js` has no case for it. Turn number for "View Prompt" button is computed client-side from `message_end.turn_number`. The `cache_folder` (needed to fetch prompt data) is only in `turn_boundary` and currently lost.

### Problem 5: No multi-session support (medium priority)

`useManagerChat(sessionId)` creates one WS per component mount. No session sidebar, no session switching.

---

## Integrated Solution — 5 Phases (Best of Both Plans)

### Phase 1: Fix Widget Submitted State (Highest Impact, 2 files)

**The right design** (not Plan B's "clear immediately" — that's wrong):

```
User submits → widget locally marks submitted (already works in Confirmation)
             → ConversationToolWidget receives submitted signal
             → widget renders in non-interactive "locked" state
             → user's response added to messages as widget_response
             → server processes, streams response
             → message_end clears pendingInput → widget unmounts cleanly
```

**Files to change:**

#### `chat-widgets/SingleChoiceWidget.js`
Add `submitted` local state (pattern from ConfirmationWidget which already has this):
```jsx
const [submitted, setSubmitted] = useState(false);
const [submittedLabel, setSubmittedLabel] = useState('');

const handleSubmit = (opt, idx) => {
  setSubmitted(true);
  setSubmittedLabel(opt.label || `Option ${idx + 1}`);
  onSubmit({ choice_index: idx });
};

if (submitted) {
  return (
    <Box sx={{ color: 'primary.main', fontWeight: 500, fontSize: '0.9rem', py: 0.5 }}>
      ✓ Selected: {submittedLabel}
    </Box>
  );
}
// ... existing interactive render
```

#### `chat-widgets/MultipleChoiceWidget.js`
Same pattern:
```jsx
const [submitted, setSubmitted] = useState(false);
const [submittedLabels, setSubmittedLabels] = useState([]);

const handleSubmit = () => {
  const labels = [...selections].map(i => options[i]?.label || `Option ${i + 1}`);
  setSubmitted(true);
  setSubmittedLabels(labels);
  const result = [...selections].map(i => ({ choice_index: i }));
  if (customText.trim()) result.push({ custom_text: customText.trim() });
  onSubmit({ selections: result });
};

if (submitted) {
  return (
    <Box sx={{ color: 'primary.main', fontWeight: 500, fontSize: '0.9rem', py: 0.5 }}>
      ✓ Selected: {submittedLabels.join(', ')}
    </Box>
  );
}
```

#### `hooks/useManagerChat.js`
On `sendPendingInputResponse`, add user widget-response to message history. Do NOT clear `pendingInput` yet — wait for `message_end`:
```js
const sendPendingInputResponse = useCallback((response) => {
  if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
  
  // Add submitted response to message history so it persists after widget clears
  const responseLabel = formatWidgetResponse(pendingInput, response);
  if (responseLabel) {
    setMessages(prev => [...prev, {
      id: `widget-resp-${Date.now()}`,
      role: 'manager',
      content: responseLabel,
      isWidgetResponse: true,
      timestamp: new Date().toISOString(),
    }]);
  }
  
  const content = typeof response === 'string' ? response : JSON.stringify(response);
  wsRef.current.send(JSON.stringify({ type: 'pending_input_response', content }));
  // Do NOT setPendingInput(null) here — widget stays in submitted state until message_end
}, [pendingInput]);

function formatWidgetResponse(pendingInput, response) {
  if (!pendingInput) return null;
  const mode = pendingInput.inputMode?.mode || 'free_text';
  const meta = pendingInput.inputMode?.metadata || {};
  if (typeof response === 'string') {
    if (response === 'yes') return `✅ ${meta.yes_label || 'Confirmed'}`;
    if (response === 'no') return `❌ ${meta.no_label || 'Declined'}`;
    return response;
  }
  if (response?.choice === 'yes') return `✅ ${meta.yes_label || 'Confirmed'}`;
  if (response?.choice === 'no') return `❌ ${meta.no_label || 'Declined'}`;
  if (response?.choice_index !== undefined) {
    const opts = pendingInput.inputMode?.metadata?.options || [];
    return `Selected: ${opts[response.choice_index]?.label || `Option ${response.choice_index + 1}`}`;
  }
  if (response?.selections) {
    const opts = pendingInput.inputMode?.metadata?.options || [];
    const labels = response.selections.map(s => opts[s.choice_index]?.label || `Option ${s.choice_index + 1}`);
    return `Selected: ${labels.join(', ')}`;
  }
  if (response?.content) return response.content;
  return JSON.stringify(response);
}
```

### Phase 2: Handle `turn_boundary` in UI (1 file)

Server already sends `turn_boundary` with `cache_folder` but UI ignores it. This is needed for the "View Prompt" button to work correctly when turns happen via conversation tools (not just at `message_end`).

#### `hooks/useManagerChat.js`
Add case:
```js
case 'turn_boundary': {
  // Store cache_folder so PromptViewer can fetch prompt data for this turn
  const turnNumber = data.turn_number;
  const cacheFolder = data.cache_folder;
  // Update the last agent message to attach the cache_folder
  setMessages(prev => {
    const idx = [...prev].reverse().findIndex(m => m.role === 'assistant');
    if (idx === -1) return prev;
    const realIdx = prev.length - 1 - idx;
    return prev.map((m, i) => i === realIdx
      ? { ...m, turnNumber, cacheFolder }
      : m
    );
  });
  break;
}
```

### Phase 3: Connect `ChatWidgetRenderer` to Server (3 files, lower priority)

`ApprovalWidget` and `ChoiceWidget` are used in the ConversationView (dashboard context). They have local submitted state but never communicate to the server. For now, they're only shown in the dashboard with no agentic flow backing them. However, if they'll ever be triggered by the server, they need `onSubmit` wiring.

#### `chat-widgets/ChatWidgetRenderer.js`
```jsx
// Add onSubmit prop threading
export default function ChatWidgetRenderer({ widgets, onSubmit }) {
  return widgets.map((widget, i) => {
    const Component = WIDGET_MAP[widget.type];
    if (!Component) return <UnknownWidget key={i} .../>;
    return <Component key={i} data={widget.data} onSubmit={onSubmit ? (r) => onSubmit(widget, r) : undefined} />;
  });
}
```

#### `chat-widgets/ApprovalWidget.js`
```jsx
export default function ApprovalWidget({ data, onSubmit }) {
  const handleApprove = () => {
    setDecision('approved');
    onSubmit?.({ decision: 'approved' }); // ← add this
  };
  const handleReject = () => {
    setDecision('rejected');
    onSubmit?.({ decision: 'rejected' }); // ← add this
  };
}
```

#### `chat-widgets/ChoiceWidget.js`
```jsx
export default function ChoiceWidget({ data, onSubmit }) {
  const handleConfirm = () => {
    const selected = options.find((o) => o.id === selectedId);
    setConfirmed(true);
    onSubmit?.({ selected_id: selectedId, selected_label: selected?.label }); // ← add
  };
}
```

### Phase 4: Auto-Advance Support (2 files, when server supports it)

OpenTeam's server does NOT currently send `auto_advance` messages. This feature requires server-side changes first. Add UI handling pre-emptively:

#### `hooks/useManagerChat.js`
```js
case 'auto_advance': {
  // Auto-advance: server is auto-continuing without user input.
  // Don't add to visible messages, don't trigger user action.
  // The next streaming response will appear automatically.
  break;
}
```

#### `components/views/ManagerChatView.js`
```jsx
{messages.map(msg => {
  if (msg.metadata?.is_auto_advance) return null; // hide auto-advance messages
  // ... rest of rendering
})}
```

**Server-side work needed** (separate task):
```python
# In WebSocketInteractive or ConversationService
await self._send({
    "type": "auto_advance",
    "reason": "continuing autonomous step",
    "session_id": session_id,
})
```

### Phase 5: Full Session Context — Multi-Session Support (medium priority)

Borrow RankEvolve's `SessionContext` + `useSessionManager` pattern. Full details in original Plan A. This is the biggest undertaking and should be done after Phases 1-3 are stable.

Key file mapping:

| Create | Copy From | Adapt |
|---|---|---|
| `contexts/ManagerSessionContext.js` | `rankevolve/react/src/contexts/SessionContext.js` | Rename Agent→Manager; adapt WS URL; strip experiment/task state |
| `hooks/useManagerSessionManager.js` | `rankevolve/react/src/hooks/useSessionManager.js` | Keep session/pendingInput/streaming; remove experiment/workspace state |
| `hooks/useManagerWebSocket.js` | `rankevolve/react/src/hooks/useAgentWebSocket.js` | Point to `/ws/manager`; adapt `session_init` handshake |

---

## Implementation Order (Prioritized)

```
Week 1 — Widget fixes (Phases 1+2, highest impact):
  ① SingleChoiceWidget.js         — add submitted state             (~20 min)
  ② MultipleChoiceWidget.js       — add submitted state             (~20 min)
  ③ useManagerChat.js             — add formatWidgetResponse()
                                  — add widget_response to messages
                                  — add turn_boundary handler       (~45 min)
  ④ Manual test all widget flows

Week 2 — ChatWidgetRenderer (Phase 3, lower priority):
  ⑤ ChatWidgetRenderer.js         — add onSubmit threading           (~15 min)
  ⑥ ApprovalWidget.js             — add onSubmit call                (~10 min)
  ⑦ ChoiceWidget.js               — add onSubmit call                (~10 min)

Week 3 — Auto-advance (Phase 4, when server ready):
  ⑧ useManagerChat.js             — add auto_advance case            (~10 min)
  ⑨ ManagerChatView.js            — filter is_auto_advance messages  (~10 min)
  ⑩ Server: WebSocketInteractive  — send auto_advance events

Later — Full session context (Phase 5):
  ⑪ Create ManagerSessionContext.js
  ⑫ Create useManagerSessionManager.js
  ⑬ Create useManagerWebSocket.js
  ⑭ Rewrite ManagerChatView.js to use context
```

---

## What NOT To Change (Confirmed Working)

After reading all files, these are working correctly and must NOT be modified:

| File | Why NOT to change |
|---|---|
| `ConversationToolWidget.js` | Correctly dispatches to widget components; compound widget works |
| `ConfirmationWidget.js` | Already has `submitted` local state; just needs `formatWidgetResponse` in hook |
| `TextInputWidget.js` | Works correctly |
| `useManagerChat.js` — `message_end` clearing | Correctly clears `pendingInput` on `message_end` (do not change to clear on submit) |
| `StreamingMessage.js` | Working correctly |
| `ThinkingFold.js` | Working correctly |
| `AgentMessageBubble.js` | Working correctly |
| Server: `WebSocketInteractive` | Correctly sends `pending_input`, `turn_boundary`, `token`, `message_end` |
| Server: `manager_websocket_routes.py` | Correctly routes `pending_input_response` to input queue |

---

## Key Design Principle: Don't Clear pendingInput on Submit

Both plans disagreed on this. **The correct behavior (confirmed from code):**

```
WRONG (Plan B's suggestion):
  Submit → setPendingInput(null) immediately → widget vanishes → user sees nothing for 2-10s while server thinks

CORRECT (current code intent, needs widget state fix):
  Submit → widget locally marks submitted → shows non-interactive "locked" state
         → server processes (2-10 seconds)
         → server streams response
         → message_end → setPendingInput(null) → widget unmounts
```

The widget's LOCAL `submitted` state (already in `ConfirmationWidget`, needs adding to `Single/MultipleChoice`) handles the transition gracefully. The `pendingInput` object stays until `message_end`.

---

## Verification Checklist

After implementation, verify:

- [ ] **Confirmation**: Submit "Proceed" → widget shows "✅ Confirmed — proceeding" (locked, no buttons) → user response "✅ Confirmed" appears in message history → server streams response → widget cleanly disappears
- [ ] **Confirmation**: Submit "No" → widget shows "❌ Declined" locked state → message history shows "❌ Declined"
- [ ] **SingleChoice**: Select option, submit → widget shows "✓ Selected: [option label]" locked → no re-click possible
- [ ] **MultipleChoice**: Select options, submit → widget shows "✓ Selected: A, B" locked → Submit button disabled
- [ ] **TextInput**: Submit text → widget shows text in read-only italic → message history shows the text
- [ ] **Turn boundary**: View Prompt button works after conversation tool interactions (not just free-form messages)
- [ ] **Double-submit**: Cannot submit a widget twice (all widgets block after first submit)
- [ ] **Compound tool**: All steps work sequentially; each step shows non-interactive after submit
- [ ] **Reconnect**: After WS reconnect, existing message history restored; no phantom widgets
- [ ] **No regressions**: Streaming, cancel, ThinkingFold, markdown, PromptViewer all still work
