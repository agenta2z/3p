# Foldable Messages + Prompt Viewer Slide Panel — Implementation Plan

**Goal:** Make every AI response bubble foldable (max-height, scrollable) with a header bar containing "View Prompt" and "View Full Response" buttons that open a right-side slide panel.

---

## 1. Current State Analysis

### What exists today (OpenTeam)

| Component | File | Current behaviour |
|---|---|---|
| `AgentMessage` | `ManagerChatView.js` | Flat box with ThinkingFold + MarkdownRenderer. No max-height, no fold, no header bar. |
| `StreamingMessage` | `components/chat/StreamingMessage.js` | Paper bubble with agent chip. No fold, no header, no buttons. |
| `ThinkingFold` | `components/chat/ThinkingFold.js` | Collapsible thinking section ✅ — already works |
| `useManagerChat` | `hooks/useManagerChat.js` | WS handler. Messages carry `thinkingContent`, `responsePhase`, `sessionContext`. No prompt data yet. |
| Server WS route | `manager_websocket_routes.py` | Sends `token`, `message_start`, `message_end`. No prompt metadata sent. |
| Server `run_conversation_turn` | `conversation_service.py` | Uses `ConversationalInferencer`. The inferencer stores `_last_rendered_prompt`, `_last_template_source`, `_last_template_feed`, `_last_template_config` after each `run_agentic_loop()`. |

### What rankevolve does (reference pattern)

| Mechanism | How |
|---|---|
| Foldable response | `ProgressSection.js` — `<Collapse in={!isCollapsed}>` with a header click-toggle |
| Header bar | Box with agent name, fold toggle arrow, "View Prompt" button |
| Max height on response body | `maxHeight: 320, overflow: 'hidden'` with a "View Full Response" button that opens FileViewer |
| "View Prompt" | Opens right-side MUI `<Drawer anchor="right">` via `useFileViewer` hook. **Prompt data is read from disk files via REST** (`session_logger` writes PromptTemplate/RenderedPrompt to disk per-turn, REST endpoint reads them back). |
| Slide panel tabs | Shows: Template source, Template Feed (key/values), Rendered Prompt — 3 tabs |
| "View Full Response" | Opens same FileViewer drawer with response content |

### Key Architectural Insight — How to get prompt data

**Rankevolve approach:** logs prompts to disk files via `session_logger`, then serves them via a `/experiment/files/` REST endpoint. Complex — requires session log dir plumbing.

**Simpler approach for OpenTeam:** The AF `ConversationalInferencer` already stores the last turn's prompt data in memory as instance attributes after `run_agentic_loop()`:
- `inferencer._last_template_source` — raw Jinja2 template text
- `inferencer._last_template_feed` — dict of template variables (placeholder key/values)
- `inferencer._last_rendered_prompt` — fully rendered prompt string
- `inferencer._last_template_config` — template config dict

**Plan:** After each turn completes, the server sends this data to the client in the `message_end` WS message as extra fields. The client stores them on the message object and the slide panel reads from there. **No disk files, no REST endpoint needed.**

---

## 2. What Needs to Be Built

### Frontend (React)

| Component | Action |
|---|---|
| `AgentMessageBubble` | NEW — extract from `AgentMessage` in `ManagerChatView.js`. Add foldable max-height body, header bar with fold toggle + "View Prompt" + "View Full Response" buttons. |
| `PromptViewerDrawer` | NEW — right-side MUI `<Drawer anchor="right">` with 3 tabs: Template, Variables, Rendered Prompt. |
| `usePromptViewer` | NEW — hook for drawer open/close state and selected content. |
| `ManagerChatView.js` | MODIFY — use new `AgentMessageBubble`, wire prompt viewer drawer, pass `promptData` from message. |
| `StreamingMessage.js` | MODIFY — add header bar + fold toggle (no prompt/full-response buttons during streaming — they appear only on completed messages). |
| `useManagerChat.js` | MODIFY — handle `promptData` field on `message_end`, store on message object. |

### Backend (Python)

| File | Action |
|---|---|
| `manager_websocket_routes.py` | MODIFY — after `run_conversation_turn()` completes, read `inferencer._last_*` fields and include in `message_end`. |
| `conversation_service.py` | MODIFY — `run_conversation_turn()` returns prompt data alongside `AgenticResult`. |

---

## 3. Detailed Implementation

### Step 1 — Backend: Send prompt data in `message_end`

**File:** `src/openteam/server/routes/manager_websocket_routes.py`

After `run_conversation_turn()` completes, read the inferencer's cached prompt data and include in `message_end`:

```python
result = await conv_svc.run_conversation_turn(
    session, text, interactive=interactive, data_service=data_svc,
)
final_content = result.text if hasattr(result, "text") else str(result)

# Read prompt data from the per-session inferencer
inferencer = conv_svc._get_session_inferencer(sid)
prompt_data = {}
if inferencer:
    prompt_data = {
        "template_source": getattr(inferencer, "_last_template_source", "") or "",
        "template_feed": getattr(inferencer, "_last_template_feed", {}) or {},
        "rendered_prompt": getattr(inferencer, "_last_rendered_prompt", "") or "",
        "template_config": getattr(inferencer, "_last_template_config", {}) or {},
    }

await send_safe({
    "type": "message_end",
    "final_content": final_content,
    "message_id": msg_id,
    "prompt_data": prompt_data,   # ← NEW
})
```

**Note on `_get_session_inferencer` visibility:** It's a method on `ConversationService` — the route can call it via `conv_svc._get_session_inferencer(sid)`. Alternatively, add a public `get_last_prompt_data(session_id)` method to `ConversationService` for cleaner encapsulation (preferred).

**Add to `conversation_service.py`:**
```python
def get_last_prompt_data(self, session_id: str) -> dict:
    """Return cached prompt data from the last turn for a given session."""
    inf = self._inferencers.get(session_id)
    if inf is None:
        return {}
    return {
        "template_source": getattr(inf, "_last_template_source", "") or "",
        "template_feed": getattr(inf, "_last_template_feed", {}) or {},
        "rendered_prompt": getattr(inf, "_last_rendered_prompt", "") or "",
        "template_config": getattr(inf, "_last_template_config", {}) or {},
    }
```

---

### Step 2 — Frontend: Handle `prompt_data` in `useManagerChat`

**File:** `src/openteam/ui/src/hooks/useManagerChat.js`

In the `message_end` handler, include `promptData` on the stored message:

```javascript
case 'message_end': {
    // ... existing parsing ...
    setMessages(prev => [...prev, {
        id: data.message_id || `msg-${Date.now()}`,
        role: 'agent',
        content: displayContent,
        timestamp: new Date().toISOString(),
        thinkingContent: finalParsed.thinkingContent,
        responsePhase: finalPhase,
        sessionContext: finalCtx,
        promptData: data.prompt_data || null,   // ← NEW
    }]);
    // ...
}
```

---

### Step 3 — New component: `AgentMessageBubble`

**File:** `src/openteam/ui/src/components/chat/AgentMessageBubble.js`

Extract `AgentMessage` from `ManagerChatView.js` into a proper component, adding:

1. **Foldable body** — `maxHeight: 320px` on the response content box, hidden overflow. "View Full Response" button in header if content exceeds threshold.
2. **Header bar** — always visible: agent name chip, fold toggle arrow, "View Prompt" button (if promptData present), "View Full Response" button (if content is long).
3. **Fold toggle** — click header to collapse/expand. Collapsed state shows only ~2 lines of content.

```jsx
export function AgentMessageBubble({ message, onViewPrompt }) {
    const [folded, setFolded] = useState(false);
    const [contentOverflows, setContentOverflows] = useState(false);
    const contentRef = useRef(null);
    const MAX_HEIGHT = 320;

    // Detect overflow after render
    useEffect(() => {
        if (contentRef.current) {
            setContentOverflows(contentRef.current.scrollHeight > MAX_HEIGHT);
        }
    }, [message.content]);

    const agentName = message.agent_name || 'AI Assistant';
    const hasPromptData = Boolean(message.promptData?.rendered_prompt);

    return (
        <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
            <Avatar ... />
            <Box sx={{ maxWidth: '75%', flex: 1 }}>
                {/* Header bar — always visible, acts as fold toggle */}
                <Box
                    onClick={() => setFolded(f => !f)}
                    sx={{
                        display: 'flex', alignItems: 'center', gap: 1,
                        px: 1.5, py: 0.75, cursor: 'pointer',
                        backgroundColor: 'rgba(255,255,255,0.03)',
                        borderRadius: '4px 16px 0 0',
                        border: '1px solid rgba(255,255,255,0.08)',
                        borderBottom: 'none',
                        '&:hover': { backgroundColor: 'rgba(255,255,255,0.06)' },
                    }}
                >
                    {/* Agent name */}
                    <Typography variant="caption" sx={{ fontWeight: 600, color: '#4a90d9', flex: 1 }}>
                        {agentName}
                    </Typography>

                    {/* View Prompt button */}
                    {hasPromptData && (
                        <Button
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.65rem', height: 20, py: 0, px: 1 }}
                            onClick={(e) => { e.stopPropagation(); onViewPrompt(message.promptData); }}
                        >
                            View Prompt
                        </Button>
                    )}

                    {/* View Full Response button — only if content overflows */}
                    {contentOverflows && (
                        <Button
                            size="small"
                            variant="outlined"
                            color="secondary"
                            sx={{ fontSize: '0.65rem', height: 20, py: 0, px: 1 }}
                            onClick={(e) => { e.stopPropagation(); onViewFullResponse(message.content); }}
                        >
                            View Full Response
                        </Button>
                    )}

                    {/* Fold toggle arrow */}
                    <Typography sx={{ color: 'text.disabled', fontSize: '0.75rem', userSelect: 'none' }}>
                        {folded ? '▸' : '▾'}
                    </Typography>
                </Box>

                {/* Collapsible body */}
                <Collapse in={!folded}>
                    <Box
                        ref={contentRef}
                        sx={{
                            backgroundColor: 'rgba(255,255,255,0.05)',
                            border: '1px solid rgba(255,255,255,0.08)',
                            borderTop: 'none',
                            px: 2, py: 1.5,
                            borderRadius: '0 0 16px 16px',
                            maxHeight: MAX_HEIGHT,
                            overflow: 'hidden',   // clips — "View Full Response" opens drawer
                            lineHeight: 1.6,
                            fontSize: '0.9rem',
                        }}
                    >
                        {message.thinkingContent && message.responsePhase !== 'no_tags' && (
                            <ThinkingFold thinkingContent={message.thinkingContent} />
                        )}
                        <MarkdownRenderer content={message.content} />
                        {message.widgets?.length > 0 && (
                            <ChatWidgetRenderer widgets={message.widgets} />
                        )}
                        {message.sessionContext && (
                            <SessionContextBar {...message.sessionContext} />
                        )}
                    </Box>
                </Collapse>

                <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5, ml: 0.5 }}>
                    {formatTime(message.timestamp)}
                </Typography>
            </Box>
        </Box>
    );
}
```

---

### Step 4 — New component: `PromptViewerDrawer`

**File:** `src/openteam/ui/src/components/chat/PromptViewerDrawer.js`

Right-side MUI Drawer with 3 tabs. "Full Response" is a 4th mode (no tabs, just the content).

```jsx
const TABS = ['Template', 'Variables', 'Rendered Prompt'];

export function PromptViewerDrawer({ open, onClose, promptData, fullResponseContent }) {
    const [tab, setTab] = useState(0);
    const isFullResponse = Boolean(fullResponseContent) && !promptData;

    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={onClose}
            PaperProps={{
                sx: {
                    width: { xs: '100%', sm: 640, md: 760 },
                    display: 'flex', flexDirection: 'column',
                    backgroundColor: 'background.default',
                }
            }}
        >
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1.5,
                        borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <Typography variant="h6" sx={{ flex: 1, fontSize: '0.95rem', fontWeight: 600 }}>
                    {isFullResponse ? '📄 Full Response' : '🔍 Prompt Inspector'}
                </Typography>
                <IconButton onClick={onClose} size="small">
                    <CloseIcon fontSize="small" />
                </IconButton>
            </Box>

            {/* Tabs (only for prompt view) */}
            {!isFullResponse && (
                <Tabs value={tab} onChange={(_, v) => setTab(v)}
                      sx={{ borderBottom: '1px solid rgba(255,255,255,0.08)', px: 2 }}>
                    {TABS.map((label, i) => (
                        <Tab key={label} label={label} value={i}
                             sx={{ fontSize: '0.8rem', minHeight: 40 }} />
                    ))}
                </Tabs>
            )}

            {/* Content */}
            <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                {isFullResponse && (
                    <MarkdownRenderer content={fullResponseContent} />
                )}

                {!isFullResponse && promptData && (
                    <>
                        {/* Tab 0: Template source (Jinja2) */}
                        {tab === 0 && (
                            <Box sx={{ fontFamily: 'monospace', fontSize: '0.8rem',
                                       whiteSpace: 'pre-wrap', color: 'text.secondary',
                                       backgroundColor: 'rgba(0,0,0,0.3)', p: 2, borderRadius: 1 }}>
                                {promptData.template_source || '(no template source available)'}
                            </Box>
                        )}

                        {/* Tab 1: Variables / Template Feed */}
                        {tab === 1 && (
                            <Box>
                                {Object.entries(promptData.template_feed || {}).map(([key, value]) => (
                                    <Box key={key} sx={{ mb: 2 }}>
                                        <Typography variant="caption"
                                            sx={{ color: 'primary.light', fontWeight: 600,
                                                  fontFamily: 'monospace', display: 'block', mb: 0.5 }}>
                                            {key}
                                        </Typography>
                                        <Box sx={{ fontFamily: 'monospace', fontSize: '0.78rem',
                                                   whiteSpace: 'pre-wrap', color: 'text.secondary',
                                                   backgroundColor: 'rgba(0,0,0,0.2)',
                                                   p: 1.5, borderRadius: 1, maxHeight: 200,
                                                   overflow: 'auto' }}>
                                            {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                                        </Box>
                                    </Box>
                                ))}
                            </Box>
                        )}

                        {/* Tab 2: Rendered Prompt */}
                        {tab === 2 && (
                            <Box sx={{ fontFamily: 'monospace', fontSize: '0.8rem',
                                       whiteSpace: 'pre-wrap', color: 'text.secondary',
                                       backgroundColor: 'rgba(0,0,0,0.3)', p: 2, borderRadius: 1 }}>
                                {promptData.rendered_prompt || '(no rendered prompt available)'}
                            </Box>
                        )}
                    </>
                )}
            </Box>
        </Drawer>
    );
}
```

---

### Step 5 — New hook: `usePromptViewer`

**File:** `src/openteam/ui/src/hooks/usePromptViewer.js`

```javascript
import { useState, useCallback } from 'react';

export function usePromptViewer() {
    const [open, setOpen] = useState(false);
    const [promptData, setPromptData] = useState(null);
    const [fullResponseContent, setFullResponseContent] = useState(null);

    const openPrompt = useCallback((data) => {
        setPromptData(data);
        setFullResponseContent(null);
        setOpen(true);
    }, []);

    const openFullResponse = useCallback((content) => {
        setFullResponseContent(content);
        setPromptData(null);
        setOpen(true);
    }, []);

    const close = useCallback(() => {
        setOpen(false);
    }, []);

    return { open, promptData, fullResponseContent, openPrompt, openFullResponse, close };
}
```

---

### Step 6 — Wire into `ManagerChatView.js`

Replace `AgentMessage` with `AgentMessageBubble` and add `PromptViewerDrawer`:

```jsx
import { AgentMessageBubble } from '../chat/AgentMessageBubble';
import { PromptViewerDrawer } from '../chat/PromptViewerDrawer';
import { usePromptViewer } from '../../hooks/usePromptViewer';

export default function ManagerChatView({ sessionId, onBack }) {
    // ... existing hooks ...
    const promptViewer = usePromptViewer();

    return (
        <Box ...>
            {/* Messages */}
            {messages.map(msg => {
                if (msg.role === 'manager') return <ManagerMessage key={msg.id} message={msg} />;
                if (msg.role === 'error') return <ErrorMessage key={msg.id} message={msg} />;
                return (
                    <AgentMessageBubble
                        key={msg.id}
                        message={msg}
                        onViewPrompt={promptViewer.openPrompt}
                        onViewFullResponse={promptViewer.openFullResponse}
                    />
                );
            })}

            {/* Streaming message (no prompt/fullresponse buttons) */}
            {streamingMessage && <StreamingMessage ... />}

            {/* Right slide panel */}
            <PromptViewerDrawer
                open={promptViewer.open}
                onClose={promptViewer.close}
                promptData={promptViewer.promptData}
                fullResponseContent={promptViewer.fullResponseContent}
            />
        </Box>
    );
}
```

---

### Step 7 — Update `StreamingMessage.js`

Add a minimal header bar to the streaming bubble (fold toggle only — no prompt/full-response buttons since data isn't available yet during streaming):

```jsx
{/* Header bar — fold toggle only during streaming */}
<Box onClick={() => setFolded(f => !f)}
     sx={{ display: 'flex', alignItems: 'center', mb: 1, cursor: 'pointer',
           px: 1, py: 0.5, borderRadius: 1,
           backgroundColor: 'rgba(255,255,255,0.03)',
           '&:hover': { backgroundColor: 'rgba(255,255,255,0.06)' } }}>
    {agentLabel && <Chip label={`🤖 ${agentLabel}`} ... />}
    {isThinking && <Chip label="🧠 Thinking..." ... />}
    <Box sx={{ flex: 1 }} />
    <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>
        {folded ? '▸' : '▾'}
    </Typography>
</Box>

<Collapse in={!folded}>
    {/* existing body */}
</Collapse>
```

---

## 4. Critical Thinking — Design Decisions & Risks

### 4.1 `_last_template_source` May Be Empty

The AF `ConversationalInferencer` stores `_last_template_source` only if `JinjaPromptRenderer.get_template_source()` is called. Check that AF's `JinjaPromptRenderer` populates this field. If not, the Template tab shows `(no template source available)` — graceful degradation. Always check with `|| '(not available)'`.

### 4.2 `template_feed` Can Be Large

The template feed includes `workflow_description` (multi-line), `workflow_status` (multi-line), `action_tools` (JSON), `conversation_history` (list). Rendering all keys as flat text could be very long. The Variables tab should:
- Sort keys alphabetically
- Truncate long values at 2000 chars with "... (truncated)"
- Give special formatting to list/dict values (JSON syntax highlight)

### 4.3 `overflow: 'hidden'` vs `overflow: 'auto'` on Message Body

Using `overflow: 'hidden'` clips content visually — "View Full Response" button is the escape hatch. This is the rankevolve pattern. Alternative: `overflow: 'auto'` with max-height makes it scrollable inline. **Recommendation:** Use `overflow: 'hidden'` (cleaner look) with "View Full Response" button.

### 4.4 `contentOverflows` Detection Timing

`useEffect` checking `contentRef.current.scrollHeight > MAX_HEIGHT` runs after paint. For messages loaded from history on connect, this fires correctly. For the live streaming→complete transition, `message_end` triggers a re-render with final content — the effect runs after that render and correctly detects overflow.

### 4.5 `promptData` Not Available for History Messages

Messages loaded from `session_init` (history) don't have `promptData` — it's only available for the current session's messages (the inferencer's in-memory state is cleared between server restarts). The "View Prompt" button should simply not render when `promptData` is null. ✅ Already handled by `hasPromptData` check.

### 4.6 `_last_template_feed` vs `_last_template_config`

- `_last_template_feed` — the Jinja2 render feed dict (all the variables passed to the template) ← show this in the "Variables" tab
- `_last_template_config` — the `.initial.config.yaml` parsed config (tools.enabled_action_tools etc.) ← show this as a subsection of Variables tab, or a 4th "Config" tab

### 4.7 Fold State Per-Message

Each `AgentMessageBubble` manages its own `folded` state locally — no global store needed. Default: `folded = false` (expanded). Could optionally default long messages to `folded = true`.

---

## 5. File Summary

### New files to create:
- `src/openteam/ui/src/components/chat/AgentMessageBubble.js`
- `src/openteam/ui/src/components/chat/PromptViewerDrawer.js`
- `src/openteam/ui/src/hooks/usePromptViewer.js`

### Files to modify:
- `src/openteam/server/services/conversation_service.py` — add `get_last_prompt_data(session_id)`
- `src/openteam/server/routes/manager_websocket_routes.py` — include `prompt_data` in `message_end`
- `src/openteam/ui/src/hooks/useManagerChat.js` — store `promptData` on message objects
- `src/openteam/ui/src/components/views/ManagerChatView.js` — use `AgentMessageBubble`, wire `PromptViewerDrawer`
- `src/openteam/ui/src/components/chat/StreamingMessage.js` — add fold header bar

### Files unchanged:
- `ThinkingFold.js` ✅
- `MarkdownRenderer.js` ✅
- `ChatInput.js` ✅
- `SessionContextBar.js` ✅

---

## 6. Implementation Order

```
1. conversation_service.py     — get_last_prompt_data()
        ↓
2. manager_websocket_routes.py — include prompt_data in message_end
        ↓
3. useManagerChat.js           — store promptData on message_end
        ↓
4. usePromptViewer.js          — new hook (no deps)
   AgentMessageBubble.js       — new component (no deps)
   PromptViewerDrawer.js       — new component (no deps)
        ↓
5. StreamingMessage.js         — add fold header
        ↓
6. ManagerChatView.js          — wire everything together
```
