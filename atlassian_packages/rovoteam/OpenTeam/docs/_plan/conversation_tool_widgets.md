# Conversation Tool Widgets — Implementation Plan

## Critical Pre-Investigation Findings

### What the other agent's plan got wrong (verified against actual source)

The other plan references these files as "borrow from rankevolve":
- `components/widgets/SingleChoiceWidget.js`
- `components/widgets/ConfirmationWidget.js`
- `components/widgets/TextInputWidget.js`
- `components/widgets/WidgetRegistry.js`
- `contexts/SessionContext.js`

**None of these exist.** The rankevolve webui has NO `widgets/` directory and NO `contexts/` directory. Furthermore, **rankevolve's `useAgentChat.js` has NO `pending_input` handler** — rankevolve itself hasn't implemented this feature. We must build everything from scratch.

The correct reference source is the **AF `input_modes.py`** protocol spec and **AF webui `agent_websocket_routes.py`** pattern.

---

## Root Cause Analysis

### Why raw ToolsToInvoke JSON appears in the chat

The AF `ConversationalInferencer` streams LLM output including `ToolsToInvoke` JSON blocks, then **post-processes** them internally to extract and execute conversation tool calls. The `stripToolsToInvoke()` function in `ThinkingFold.js` correctly strips these before rendering. So the raw JSON is **already stripped** — it never shows in the final message.

**The real problem**: After the agentic loop calls `asend_response()` and blocks on `aget_input()`, the frontend receives a `pending_input` WS message — but has no handler for it. The message is silently dropped. The UI is stuck, and the user has no widget to interact with.

**Separately**: Some `ToolsToInvoke` JSON may appear in `pre_response` (thinking) content before the inferencer strips it — this is handled by the existing `stripToolsToInvoke` regex. No changes needed there.

---

## Complete Data Flow (Target State)

```
LLM emits ToolsToInvoke JSON in response stream
    ↓
ConversationalInferencer post-processes stream → extracts ConversationTool calls
    ↓ (internally)
_handle_conversation_tool() → builds InputModeConfig
    ↓
asend_response(text, input_mode=InputModeConfig) → WebSocketInteractive
    ↓
WebSocket send: {"type": "pending_input", "content": "...", "input_mode": {...}}
    ↓
useManagerChat handles case 'pending_input':
  - Commits any partial streaming text as completed message
  - Sets pendingInput state: {content, inputMode}
  - Clears streamingMessage
    ↓
ManagerChatView renders ConversationToolWidget (above chat input)
ChatInput is DISABLED while pendingInput is active
    ↓
User interacts with widget (clicks button, types text, makes choice)
    ↓
Widget calls onSubmit(response)
    ↓
sendPendingInputResponse() sends: {"type": "pending_input_response", "content": "..."}
    ↓
manager_websocket_routes.py routes to active_input_queue.put(content) ✅ (already implemented)
    ↓
WebSocketInteractive.aget_input() unblocks → returns content to inferencer
    ↓
Inferencer continues the agentic loop
    ↓
Eventually sends message_end → pendingInput cleared, chat re-enabled
```

---

## AF `input_mode` Protocol (The Source of Truth)

From `agent_foundation/ui/input_modes.py`:

```
InputMode.FREE_TEXT         → clarification tool / default
InputMode.PRESS_TO_CONTINUE → (rare — "press to continue")
InputMode.EXACT_STRING      → (rare — specific string expected)
InputMode.SINGLE_CHOICE     → single_choice conversation tool
InputMode.MULTIPLE_CHOICES  → multiple_choice conversation tool
```

**Special case — FREE_TEXT with confirmation metadata:**
```json
{
  "mode": "free_text",
  "prompt": "Shall I proceed?",
  "metadata": {
    "widget_type": "confirmation",
    "note_variable": "additional_instructions"
  }
}
```

**Single choice:**
```json
{
  "mode": "single_choice",
  "prompt": "Pick the autonomy level",
  "options": [
    {"label": "High", "value": "high"},
    {"label": "Medium", "value": "medium"}
  ],
  "allow_custom": true
}
```

**Compound (multiple tools in one turn):**
```json
{
  "mode": "free_text",
  "metadata": {
    "compound": true,
    "tools": [
      {"tool_type": "clarification", "prompt": "...", "input_mode": {...}, "output_var": "role_description"},
      {"tool_type": "single_choice", "prompt": "...", "input_mode": {...}, "output_var": "strategy"}
    ]
  }
}
```

**Response format** — what `pending_input_response` sends in `content`:
- FREE_TEXT: plain string (user's typed text)
- SINGLE_CHOICE: the option value string (e.g. `"high"`)
- MULTIPLE_CHOICES: JSON array string (e.g. `'["high", "medium"]'`)
- CONFIRMATION: `"yes"` or `"no"`
- COMPOUND: JSON string of `{output_var: value, ...}` dict

---

## Comparison: My Plan vs Other Agent's Plan

| Aspect | My Plan | Other Plan | Winner |
|---|---|---|---|
| Rankevolve reference files | Builds from scratch (correct — files don't exist) | References non-existent files | **My plan** |
| Streaming→widget transition | Commits partial streaming as message before widget | Same approach | Tie ✅ |
| Widget placement | Inline in chat, above input | Above chat input in ManagerChatView | **Other plan** — cleaner placement |
| Compound tool support | Mentioned | Not addressed | **My plan** |
| confirmation metadata detection | Mentioned | Uses `mode` only (misses confirmation sub-type) | **My plan** |
| `allow_custom` for SingleChoice | Mentioned | Mentioned | Tie |
| Disable ChatInput while pending | Not explicitly stated | ✅ Explicit | **Other plan** |
| `multiple_choices` support | Mentioned | Not addressed | **My plan** |
| PRESS_TO_CONTINUE | Not addressed | Not addressed | Both miss |
| `stripToolsToInvoke` update | Not needed | Proposes unnecessary change | **My plan** |

### Additional value from other plan (adopted):
1. **Disable ChatInput** (`disabled={!isConnected || isStreaming || !!pendingInput}`) — explicit and correct
2. **Widget placement above ChatInput in ManagerChatView** — better UX than inline in StreamingMessage
3. **`pendingInput.content` rendered as markdown** (the AI's preamble text before the widget)

### Issues in other plan (not adopted):
1. References non-existent rankevolve widget files
2. `stripToolsToInvoke` update is unnecessary — the regex already works
3. `mode === 'confirmation'` check is wrong — confirmation uses `mode: 'free_text'` with `metadata.widget_type === 'confirmation'`
4. No compound tool support

---

## Implementation Plan

### Files to Create

| File | Purpose |
|---|---|
| `ui/src/components/chat-widgets/ConversationToolWidget.js` | Main dispatcher + all sub-widgets (TextInput, SingleChoice, MultipleChoice, Confirmation, Compound) |

### Files to Modify

| File | Changes |
|---|---|
| `ui/src/hooks/useManagerChat.js` | Add `pending_input` case, `pendingInput` state, `sendPendingInputResponse()` |
| `ui/src/components/views/ManagerChatView.js` | Render `ConversationToolWidget`, disable ChatInput while pending |
| `ui/src/components/chat-widgets/ApprovalWidget.js` | Add `onSubmit` prop (wires buttons to WS response) |
| `ui/src/components/chat-widgets/ChoiceWidget.js` | Add `onSubmit` prop (wires confirm to WS response) |

### Files NOT modified (already correct)

| File | Reason |
|---|---|
| `server/services/websocket_interactive.py` | `asend_response()` and `aget_input()` fully implemented |
| `server/routes/manager_websocket_routes.py` | `pending_input_response` handler fully implemented |
| `components/chat/ThinkingFold.js` | `stripToolsToInvoke()` regex already correct |

---

## Step-by-Step Implementation

### Step 1 — `useManagerChat.js`: Add `pending_input` handling

**New state:**
```javascript
const [pendingInput, setPendingInput] = useState(null);
```

**New handler in `handleServerMessage` switch:**
```javascript
case 'pending_input': {
  // Commit any in-progress streaming content as a completed message
  // (the AI's preamble text before the conversation tool invocation)
  const streamContent = streamingContentRef.current;
  if (streamContent && streamContent.trim()) {
    const parsed = parseResponseTags(streamContent);
    const phase = parsed.phase === 'pre_response' ? 'no_tags' : parsed.phase;
    const displayContent = phase === 'no_tags'
      ? stripSessionContext(stripAnsi(stripAcliNoise(stripToolsToInvoke(streamContent))))
      : stripSessionContext(stripAnsi(stripAcliNoise(stripToolsToInvoke(parsed.responseContent || streamContent))));

    if (displayContent.trim()) {
      setMessages(prev => [...prev, {
        id: `msg-${Date.now()}`,
        role: 'agent',
        content: displayContent,
        timestamp: new Date().toISOString(),
        thinkingContent: parsed.thinkingContent || '',
        responsePhase: phase,
        sessionContext: null,
        promptData: null,
        turnNumber: null,
      }]);
    }
  }
  // Clear streaming state (but do NOT set isStreaming=false — turn is still active)
  setStreamingMessage(null);
  streamingContentRef.current = '';
  streamingMetadataRef.current = {};

  // Show the conversation tool widget
  setPendingInput({
    content: data.content,      // AI's question/prompt text
    inputMode: data.input_mode || null,  // AF InputModeConfig dict
  });
  break;
}
```

**Also clear `pendingInput` on `message_end`:**
```javascript
case 'message_end': {
  setPendingInput(null);  // ← ADD THIS LINE at the top of the case
  // ... existing message_end handling ...
}
```

**And on disconnect/cancel:**
```javascript
// In the WebSocket onclose handler:
setPendingInput(null);
setIsStreaming(false);

// In cancelRequest:
setPendingInput(null);
```

**New `sendPendingInputResponse` function:**
```javascript
const sendPendingInputResponse = useCallback((response) => {
  if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
    console.warn('[PendingInput] WebSocket not open — cannot send response');
    return;
  }
  const content = typeof response === 'string' ? response : JSON.stringify(response);
  wsRef.current.send(JSON.stringify({
    type: 'pending_input_response',
    content,
  }));
  // Note: setPendingInput(null) NOT called here — the server will send message_end
  // which clears it. This prevents double-clear and keeps UI consistent.
}, []);
```

**Return from hook:**
```javascript
return {
  // ... existing ...
  pendingInput,
  sendPendingInputResponse,
};
```

---

### Step 2 — `ConversationToolWidget.js`: The dispatcher and all sub-widgets

**File: `ui/src/components/chat-widgets/ConversationToolWidget.js`**

The main export dispatches on `inputMode.mode` + `inputMode.metadata.widget_type`:

```javascript
export default function ConversationToolWidget({ pendingInput, onSubmit }) {
  const inputMode = pendingInput?.inputMode;
  const mode = inputMode?.mode || 'free_text';
  const metadata = inputMode?.metadata || {};

  // Compound: multiple tools in one pending_input
  if (metadata.compound && metadata.tools?.length) {
    return <CompoundWidget tools={metadata.tools} preamble={pendingInput.content} onSubmit={onSubmit} />;
  }

  // confirmation sub-type (uses free_text mode with metadata)
  if (mode === 'free_text' && metadata.widget_type === 'confirmation') {
    return <ConfirmationWidget prompt={inputMode.prompt || pendingInput.content} metadata={metadata} onSubmit={onSubmit} />;
  }

  switch (mode) {
    case 'single_choice':
      return <SingleChoiceWidget prompt={inputMode.prompt || pendingInput.content} options={inputMode.options || []} allowCustom={inputMode.allow_custom !== false} onSubmit={onSubmit} />;
    case 'multiple_choices':
      return <MultipleChoiceWidget prompt={inputMode.prompt || pendingInput.content} options={inputMode.options || []} allowCustom={inputMode.allow_custom !== false} onSubmit={onSubmit} />;
    case 'press_to_continue':
      return <PressToContineWidget prompt={inputMode.prompt || pendingInput.content} onSubmit={onSubmit} />;
    default:
      // FREE_TEXT / clarification
      return <TextInputWidget prompt={inputMode?.prompt || pendingInput.content} onSubmit={onSubmit} />;
  }
}
```

**Sub-widget implementations:**

**`TextInputWidget`** (clarification):
- Header: "💬 Clarification Needed"
- Preamble text (MarkdownRenderer)
- MUI TextField (multiline, autoFocus)
- Submit button (disabled if empty)
- `onSubmit(text)` on Enter or button click
- Keyboard: Shift+Enter = newline, Enter = submit

**`ConfirmationWidget`** (confirmation):
- Header: "⚡ Confirmation Required"
- Preamble text (MarkdownRenderer)
- Optional: additional notes TextField (if `metadata.note_variable` is set)
- "Proceed" (primary, filled) and "No" (outlined) buttons
- `onSubmit('yes')` or `onSubmit('no')`
- After click: show "✓ Confirmed" or "✗ Declined" text, disable buttons

**`SingleChoiceWidget`** (single_choice):
- Header: "Select an option"
- Preamble text
- Option cards (clickable Box, highlight on selection)
- If `allowCustom`: show "Other..." option that reveals a text field
- Submit button (disabled until selection)
- `onSubmit(selectedValue)` or `onSubmit(customText)` if custom

**`MultipleChoiceWidget`** (multiple_choices):
- Header: "Select options"
- Preamble text
- MUI Checkbox list, each option selectable
- Submit button
- `onSubmit(JSON.stringify(selectedValues))` — serialized JSON array string

**`PressToContinueWidget`**:
- Simple "Continue" button
- `onSubmit('continue')`

**`CompoundWidget`** (compound mode):
- Renders each sub-tool in sequence (one at a time or all at once)
- Collects all responses into `{output_var: value}` dict
- `onSubmit(JSON.stringify({role_description: "...", strategy: "high"}))` on final submit
- Simplest implementation: render all sub-tools as a form, submit all at once

---

### Step 3 — `ManagerChatView.js`: Render widget + disable input

**Add imports:**
```javascript
import ConversationToolWidget from '../chat-widgets/ConversationToolWidget';
```

**Destructure from hook:**
```javascript
const {
  // ... existing ...
  pendingInput,
  sendPendingInputResponse,
} = useManagerChat(sessionId);
```

**Render widget between messages and ChatInput:**
```jsx
{/* Conversation tool widget — shown when AI needs user input */}
{pendingInput && (
  <Box sx={{ px: 2, pb: 1.5, flexShrink: 0 }}>
    <ConversationToolWidget
      pendingInput={pendingInput}
      onSubmit={sendPendingInputResponse}
    />
  </Box>
)}

{/* Chat Input */}
<Box sx={{ px: 2, py: 1.5, borderTop: '1px solid rgba(255,255,255,0.06)', backgroundColor: 'background.paper', flexShrink: 0 }}>
  <ChatInput
    value={inputValue}
    onChange={setInputValue}
    onSubmit={handleSubmit}
    disabled={!isConnected || isStreaming || !!pendingInput}  // ← disable when pending
  />
</Box>
```

---

### Step 4 — Fix existing `ApprovalWidget` and `ChoiceWidget`

These widgets exist but currently only update local state with no WS communication.

**`ApprovalWidget.js`** — add `onSubmit` prop:
```javascript
export default function ApprovalWidget({ data, onSubmit }) {
  const handleApprove = () => {
    setDecision('approved');
    onSubmit?.('yes');  // ← ADD
  };
  const handleReject = () => {
    setDecision('rejected');
    onSubmit?.('no');  // ← ADD
  };
  // ...
}
```

**`ChoiceWidget.js`** — add `onSubmit` prop:
```javascript
export default function ChoiceWidget({ data, onSubmit }) {
  const handleConfirm = () => {
    const selected = options.find((o) => o.id === selectedId);
    setConfirmed(true);
    onSubmit?.(selected?.value || selected?.id);  // ← ADD
  };
  // ...
}
```

Note: These widgets use a different data schema (`data.question`, `data.options[].id`) vs the AF `input_mode` schema (`prompt`, `options[].value`). They are designed for the existing fixture-based chat, not for live conversation tools. **The new `ConversationToolWidget` is the correct component for live conversation tools** — `ApprovalWidget` and `ChoiceWidget` are separate concerns (fixture data rendering). Don't conflate them.

---

## Critical Design Decisions

### Decision 1: Where to render the widget (above ChatInput)

**Chosen:** In `ManagerChatView`, between the messages list and the ChatInput — not inside `StreamingMessage`. Rationale:
- The AI's streaming preamble is committed as a completed `AgentMessageBubble` before the widget appears
- The widget is a fixed UI element, not part of the message scroll list
- The ChatInput can be easily disabled alongside it

### Decision 2: `setPendingInput(null)` timing

**Chosen:** Clear `pendingInput` in the `message_end` handler (not immediately on submit). Rationale:
- After the user submits, the server continues the agentic loop
- There may be additional tool calls before the final response
- Each new `pending_input` message replaces the previous one
- `message_end` signals the complete turn is done → clear

**Exception:** Clear immediately if WebSocket disconnects or user cancels.

### Decision 3: Compound tool response format

**Chosen:** `JSON.stringify({output_var1: value1, output_var2: value2})` as the `content` string. The server's `active_input_queue.put(content)` passes this string to `aget_input()`. The AF inferencer then calls `json.loads(user_input)` to extract compound values.

**Risk:** If the inferencer doesn't call `json.loads()` on compound responses, it will get a raw JSON string. Verify in AF source: `_handle_compound_tools()` line ~1110+ — it does `if isinstance(user_input, str): user_input = json.loads(user_input)`.

### Decision 4: `sendPendingInputResponse` does NOT clear `pendingInput` immediately

This is intentional — the widget stays visible until `message_end` arrives. This prevents a jarring disappearance before the server responds, and handles the case where the server sends another `pending_input` immediately after (chained questions).

---

## Implementation Order (Dependency-Sorted)

```
1. useManagerChat.js — pending_input case, sendPendingInputResponse, pendingInput state
        ↓
2. ConversationToolWidget.js — all sub-widgets built fresh
        ↓ (parallel)
3. ManagerChatView.js — wire widget + disable ChatInput
        ↓
4. ApprovalWidget.js + ChoiceWidget.js — add onSubmit props (optional, low priority)
```

---

## Verification Checklist

1. **Clarification tool:** AI asks "What should the PM focus on?" → `TextInputWidget` appears → user types → submitted → inferencer continues → AI responds
2. **Single choice:** AI presents 3 autonomy levels → clickable option cards → user selects "High" → `"high"` sent back → inferencer gets `"high"` as variable value
3. **Confirmation:** AI asks "Shall I proceed with create_role?" → "Proceed" / "No" buttons → user clicks Proceed → `"yes"` sent → tool executes
4. **JSON not visible:** No raw `{"type": "conversation"...}` appears in the final response bubble (already handled by `stripToolsToInvoke`)
5. **Chat input disabled:** While widget is showing, `ChatInput` is grayed out and unresponsive
6. **Streaming → widget transition:** The partial AI response (preamble text) is committed as an `AgentMessageBubble` before the widget appears
7. **Widget disappears on message_end:** After the full turn completes, `pendingInput` is cleared, widget gone, ChatInput re-enabled
8. **Multiple pending_inputs in one turn:** If the AI asks for clarification then confirmation in sequence, each replaces the previous widget
9. **Server restart / session reload:** No `pendingInput` state on history messages — `session_init` doesn't carry pending state (fresh session starts clean)
10. **Cancel while waiting:** `cancelRequest()` clears `pendingInput`, sends cancel to server
