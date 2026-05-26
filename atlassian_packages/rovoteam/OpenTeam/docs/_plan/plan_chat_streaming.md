# Plan: Rich Chat Streaming UI for OpenTeam Manager Sessions

> **Author:** Rovo Dev
> **Date:** 2026-04-06
> **Status:** Phase 2 — depends on `plan_conversation_migration.md` (Phase 1 HTTP POST chat) being complete
> **Source of truth:** Deep investigation of rankevolve `src/webui/src/` + `react/src/` + backend

---

## 1. Executive Summary

Phase 1 (`plan_conversation_migration.md`) enables basic HTTP POST chat in `ManagerChatView.js`.
This plan upgrades the chat to a **rich streaming experience** modelled directly on rankevolve's production `AgentChatPanel` + `useAgentChat` + `agent_websocket_routes.py` pattern:

| Feature | Phase 1 (HTTP POST) | Phase 2 (This Plan) |
|---|---|---|
| Send message | ✅ HTTP POST, wait for full response | ✅ WebSocket, instant |
| Response display | ✅ After round-trip completes | ✅ Token-by-token streaming |
| Streaming cursor | ❌ | ✅ Blinking `@keyframes blink` cursor |
| "Thinking..." indicator | ❌ | ✅ Shown between `message_start` and first token |
| Agent/phase badges | ❌ | ✅ `🤖 AI Team`, phase chips per message |
| Cancel in-flight | ❌ | ✅ Cancel button → `{type: "cancel"}` |
| Markdown rendering | ❌ Hand-rolled dangerouslySetInnerHTML | ✅ react-markdown + Prism syntax highlight |
| Auto-reconnect | ❌ | ✅ Exponential backoff (1s → 30s max) |
| Heartbeat | ❌ | ✅ 30s ping/pong |
| Connection status | ❌ | ✅ Live connected/connecting/error badge |

---

## 2. Architecture

```
ManagerChatView.js
    │  uses
    ▼
useManagerChat.js   (NEW — adapted from rankevolve's useAgentChat.js)
    │  WebSocket
    ▼
FastAPI WS /ws/manager  (NEW — adapted from agent_websocket_routes.py)
    │  calls
    ▼
ConversationService  (from plan_conversation_migration.md)
    │  calls
    ▼
RovoChatInferencer  (streaming HTTP — AgentFoundation)
```

**Why WebSocket over SSE?**
Rankevolve chose WebSocket for bidirectional control (cancel, ping, command routing). For OpenTeam, the same reasoning applies: cancel support + connection health monitoring justify the extra complexity over SSE.

---

## 3. New Files

```
src/
  server/
    routes/
      manager_websocket_routes.py   ← NEW (adapt from rankevolve agent_websocket_routes.py)
  ui/src/
    hooks/
      useManagerChat.js             ← NEW (adapt from rankevolve useAgentChat.js)
    components/
      chat/
        StreamingMessage.js         ← NEW (copy from rankevolve, minor adaptation)
        MarkdownRenderer.js         ← NEW (copy from rankevolve verbatim)
        ChatInput.js                ← NEW (copy from rankevolve verbatim)
```

**Modified files:**
```
src/server/main.py                  ← add WS router
src/ui/src/components/views/ManagerChatView.js   ← replace useApiData with useManagerChat
src/ui/package.json                 ← add react-markdown, remark-gfm, react-syntax-highlighter
```

---

## 4. File Specifications

### 4.1 `src/server/routes/manager_websocket_routes.py` — NEW

Adapted from `rankevolve/src/webui/backend/routes/agent_websocket_routes.py`.
Key simplifications for OpenTeam:
- No `AgentServiceBridge` / file-queue indirection — call `ConversationService` directly
- No `switch_session` (sessions are fixed per WS connection)
- No `server_monitor_loop` (no separate server process)
- Retain: heartbeat, cancellation, session init handshake, `pending_input_response` forwarding

```python
"""WebSocket endpoint for real-time Manager ↔ AI chat streaming.

Protocol (client → server):
    {"type": "message", "content": "user text"}
    {"type": "cancel"}
    {"type": "ping"}

Protocol (server → client):
    {"type": "session_init", "session_id": "...", "config": {...}}
    {"type": "message_start"}
    {"type": "token", "content": "chunk", "metadata": {"agent_name": "AI Team"}}
    {"type": "message_end", "final_content": "...", "message_id": "..."}
    {"type": "status", "status": "complete"|"error", "detail": "..."}
    {"type": "error", "message": "..."}
    {"type": "heartbeat"}
    {"type": "pong"}
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/manager")
async def manager_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]

    # Check for client-provided session_id in init message
    try:
        first_msg = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
        if first_msg.get("type") == "init" and first_msg.get("session_id"):
            session_id = first_msg["session_id"]
            logger.info("Client provided session_id=%s", session_id)
        else:
            init_data = first_msg  # process below as normal message
    except asyncio.TimeoutError:
        init_data = None

    # Send session_init handshake
    await websocket.send_json({
        "type": "session_init",
        "session_id": session_id,
    })

    active_task: asyncio.Task[Any] | None = None

    async def send_callback(msg: dict[str, Any]) -> None:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(msg)
        except Exception:
            pass

    async def heartbeat_loop() -> None:
        try:
            while True:
                await asyncio.sleep(30)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"type": "heartbeat"})
        except asyncio.CancelledError:
            pass

    async def process_message(session_id: str, text: str) -> None:
        """Call ConversationService and stream tokens back to client."""
        conv_svc = websocket.app.state.conversation_service
        try:
            await send_callback({"type": "message_start"})
            final_content = ""
            # ConversationService.astream_response() yields (chunk, metadata) tuples
            async for chunk, metadata in conv_svc.astream_response(
                session_id=session_id,
                user_message=text,
            ):
                final_content += chunk
                await send_callback({
                    "type": "token",
                    "content": chunk,
                    "metadata": metadata,
                })
            await send_callback({
                "type": "message_end",
                "final_content": final_content,
                "message_id": str(uuid.uuid4())[:8],
            })
        except asyncio.CancelledError:
            logger.info("Message processing cancelled (session=%s)", session_id)
            await send_callback({"type": "status", "status": "complete", "detail": "Cancelled"})
        except Exception as e:
            logger.error("Error processing message (session=%s): %s", session_id, e, exc_info=True)
            await send_callback({"type": "error", "message": str(e)})

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        # Process any non-init first message
        if init_data is not None:
            msg_type = init_data.get("type", "")
            if msg_type == "message":
                content = init_data.get("content", "").strip()
                if content:
                    active_task = asyncio.create_task(process_message(session_id, content))

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "cancel":
                if active_task and not active_task.done():
                    active_task.cancel()
                await send_callback({"type": "status", "status": "complete", "detail": "Cancelled"})

            elif msg_type == "message":
                content = data.get("content", "").strip()
                if not content:
                    continue
                # Cancel previous in-flight task
                if active_task and not active_task.done():
                    active_task.cancel()
                active_task = asyncio.create_task(process_message(session_id, content))

    except WebSocketDisconnect:
        logger.info("Manager WebSocket disconnected (session=%s)", session_id)
    except Exception as e:
        logger.error("Manager WebSocket error (session=%s): %s", session_id, e, exc_info=True)
    finally:
        heartbeat_task.cancel()
        if active_task and not active_task.done():
            active_task.cancel()
```

**Wire into `main.py`:**
```python
from server.routes.manager_websocket_routes import router as manager_ws_router
app.include_router(manager_ws_router, prefix="/ws", tags=["websocket"])
```

---

### 4.2 `ConversationService.astream_response()` — ADD METHOD

The WebSocket route calls `conv_svc.astream_response(session_id, user_message)` which must be added to `ConversationService` (from `plan_conversation_migration.md`):

```python
async def astream_response(
    self,
    session_id: str,
    user_message: str,
) -> AsyncIterator[tuple[str, dict]]:
    """Stream response tokens from RovoChatInferencer.

    Yields:
        (chunk: str, metadata: dict) tuples.
        metadata contains {"agent_name": "AI Team"} for UI badge rendering.
    """
    # 1. Persist user message
    self._session_store.append_message(session_id, {
        "role": "manager",
        "content": user_message,
        "timestamp": _iso_now(),
    })

    # 2. Render prompt with full history
    history = self._session_store.get_messages(session_id)
    prompt = self._render_prompt(history)

    # 3. Stream from RovoChatInferencer
    metadata = {"agent_name": "AI Team"}
    full_response = ""
    async for chunk in self._inferencer.aiter_infer(prompt):
        full_response += chunk
        yield chunk, metadata

    # 4. Persist AI response
    self._session_store.append_message(session_id, {
        "role": "agent",
        "agent_name": "AI Team",
        "content": full_response,
        "timestamp": _iso_now(),
    })
```

---

### 4.3 `src/ui/src/hooks/useManagerChat.js` — NEW

Direct adaptation of rankevolve's `useAgentChat.js`. Changes:
- WS URL: `/ws/manager` (not `/ws/agent`)
- Remove `taskPhase` / `task_status` handling (not needed for OpenTeam)
- Add `sessionId` parameter — connects with session context

```javascript
/**
 * useManagerChat — WebSocket-based hook for Manager ↔ AI streaming chat.
 *
 * Adapted from rankevolve's useAgentChat.js.
 * Manages connection to /ws/manager, token streaming, auto-reconnect.
 */
import { useState, useRef, useCallback, useEffect } from 'react';

const WS_RECONNECT_BASE_MS = 1000;
const WS_RECONNECT_MAX_MS = 30000;

function getWsUrl(sessionId) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/manager`;
}

export function useManagerChat(sessionId) {
  const [messages, setMessages] = useState([]);
  const [streamingMessage, setStreamingMessage] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  const wsRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const streamingContentRef = useRef('');
  const streamingMetadataRef = useRef({});
  const connectRef = useRef(null);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    const delay = Math.min(
      WS_RECONNECT_BASE_MS * Math.pow(2, reconnectAttemptRef.current),
      WS_RECONNECT_MAX_MS
    );
    reconnectAttemptRef.current += 1;
    reconnectTimerRef.current = setTimeout(() => {
      if (connectRef.current) connectRef.current();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    setConnectionStatus('connecting');
    const ws = new WebSocket(getWsUrl(sessionId));
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      reconnectAttemptRef.current = 0;
      // Send init with session_id so server can resume correct conversation
      ws.send(JSON.stringify({ type: 'init', session_id: sessionId }));
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => setConnectionStatus('error');

    ws.onmessage = (event) => {
      try {
        handleServerMessage(JSON.parse(event.data));
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };
  }, [sessionId, scheduleReconnect]);

  connectRef.current = connect;

  const handleServerMessage = useCallback((data) => {
    switch (data.type) {
      case 'token':
        streamingContentRef.current += data.content;
        if (data.metadata) streamingMetadataRef.current = data.metadata;
        setStreamingMessage({
          role: 'agent',
          content: streamingContentRef.current,
          metadata: streamingMetadataRef.current,
        });
        setIsStreaming(true);
        break;

      case 'message_start':
        streamingContentRef.current = '';
        streamingMetadataRef.current = {};
        setStreamingMessage({ role: 'agent', content: '', metadata: {} });
        setIsStreaming(true);
        break;

      case 'message_end':
        setMessages(prev => [...prev, {
          id: data.message_id || `msg-${Date.now()}`,
          role: 'agent',
          content: data.final_content || streamingContentRef.current,
          timestamp: new Date().toISOString(),
        }]);
        setStreamingMessage(null);
        streamingContentRef.current = '';
        streamingMetadataRef.current = {};
        setIsStreaming(false);
        break;

      case 'error':
        setMessages(prev => [...prev, {
          id: `err-${Date.now()}`,
          role: 'error',
          content: data.message,
          timestamp: new Date().toISOString(),
        }]);
        setIsStreaming(false);
        setStreamingMessage(null);
        break;

      case 'status':
        if (data.status === 'complete' || data.status === 'error') {
          setIsStreaming(false);
        }
        break;

      case 'session_init':
      case 'heartbeat':
      case 'pong':
        break;

      default:
        console.log('Unknown WS message type:', data.type);
    }
  }, []);

  const sendMessage = useCallback((text) => {
    if (!text.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setMessages(prev => [...prev, {
      id: `user-${Date.now()}`,
      role: 'manager',
      content: text,
      timestamp: new Date().toISOString(),
    }]);
    wsRef.current.send(JSON.stringify({ type: 'message', content: text }));
  }, []);

  const cancelRequest = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'cancel' }));
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStreamingMessage(null);
    setIsStreaming(false);
  }, []);

  // Connect on mount, reconnect if sessionId changes
  useEffect(() => {
    if (!sessionId) return;
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect, sessionId]);

  return {
    messages,
    streamingMessage,
    isStreaming,
    connectionStatus,
    sendMessage,
    cancelRequest,
    clearMessages,
    isConnected: connectionStatus === 'connected',
  };
}

export default useManagerChat;
```

---

### 4.4 `src/ui/src/components/chat/StreamingMessage.js` — COPY + ADAPT

Copy directly from `rankevolve/src/webui/src/components/agent/StreamingMessage.js`.
Adaptation: replace rankevolve agent labels with OpenTeam agent labels:

```javascript
// CHANGE this block:
const agentLabel = metadata?.agent_id ? {
  base: '🔵 Base Agent',
  review: '🟣 Review Agent',
}[metadata.agent_id] || metadata.agent_id : null;

// TO:
const agentLabel = metadata?.agent_name || null;

// CHANGE phase labels:
const phaseLabel = metadata?.phase ? {
  plan: '📋 Planning',
  implementation: '🔧 Working',
  analysis: '🔍 Analyzing',
}[metadata.phase] || metadata.phase : null;
```

Everything else (blinking cursor CSS, `MarkdownRenderer`, `<Chip>` rendering) is copied verbatim.

---

### 4.5 `src/ui/src/components/chat/MarkdownRenderer.js` — COPY VERBATIM

Copy `rankevolve/src/webui/src/components/common/MarkdownRenderer.js` **verbatim** — no changes needed.

This replaces the hand-rolled `dangerouslySetInnerHTML` markdown rendering in both `ManagerMessage` and `AgentMessage` components. Features:
- `react-markdown` + `remark-gfm` (GFM tables, strikethrough, task lists)
- `react-syntax-highlighter` with Prism `vscDarkPlus` theme
- Auto-language detection (Python, JS, JSON, Bash, SQL, YAML)
- Styled GFM tables

**Add to `src/ui/package.json` dependencies:**
```json
"react-markdown": "^9.0.1",
"remark-gfm": "^4.0.0",
"react-syntax-highlighter": "^15.5.0"
```

---

### 4.6 `src/ui/src/components/chat/ChatInput.js` — COPY VERBATIM

Copy `rankevolve/src/webui/src/components/chat/ChatInput.js` **verbatim** — no changes needed.
Props: `{ value, onChange, onSubmit, disabled }` — already matches what `ManagerChatView` needs.

---

### 4.7 `src/ui/src/components/views/ManagerChatView.js` — REPLACE (Phase 2)

Replace the Phase 1 HTTP POST implementation with `useManagerChat` hook. Key structural changes:

```javascript
import { useManagerChat } from '../../hooks/useManagerChat';
import { MarkdownRenderer } from '../chat/MarkdownRenderer';
import { StreamingMessage } from '../chat/StreamingMessage';
import { ChatInput } from '../chat/ChatInput';

export default function ManagerChatView({ sessionId, onBack }) {
  const {
    messages,
    streamingMessage,
    isStreaming,
    connectionStatus,
    sendMessage,
    cancelRequest,
    isConnected,
  } = useManagerChat(sessionId);

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  const handleSubmit = useCallback((e) => {
    e?.preventDefault();
    if (!inputValue.trim() || !isConnected) return;
    sendMessage(inputValue);
    setInputValue('');
  }, [inputValue, isConnected, sendMessage]);

  // Replace ManagerMessage/AgentMessage with MarkdownRenderer-based rendering
  const renderMessage = (msg) => {
    const isManager = msg.role === 'manager';
    const isError = msg.role === 'error';
    return (
      <Box key={msg.id} sx={{ display: 'flex', justifyContent: isManager ? 'flex-end' : 'flex-start', mb: 2 }}>
        {/* ... MUI Paper bubble with MarkdownRenderer inside ... */}
        <MarkdownRenderer content={msg.content} />
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Connection status badge */}
      <ConnectionStatusBar status={connectionStatus} />

      {/* Messages */}
      <Box sx={{ flexGrow: 1, overflow: 'auto', px: 3, py: 2 }}>
        {messages.map(renderMessage)}

        {/* Streaming token display with blinking cursor */}
        {streamingMessage && (
          <StreamingMessage
            content={streamingMessage.content}
            metadata={streamingMessage.metadata}
          />
        )}

        {/* "Thinking..." when streaming started but no tokens yet */}
        {isStreaming && !streamingMessage?.content && (
          <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
              Thinking...
            </Typography>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </Box>

      {/* Cancel button — only shown during streaming */}
      {isStreaming && (
        <Box sx={{ px: 2, pb: 1 }}>
          <Button size="small" variant="outlined" color="warning" onClick={cancelRequest}>
            Cancel
          </Button>
        </Box>
      )}

      {/* Chat input */}
      <ChatInput
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        disabled={!isConnected || isStreaming}
      />
    </Box>
  );
}
```

---

## 5. Implementation Order

| Step | File | Type | Effort | Depends On |
|---|---|---|---|---|
| 1 | `src/ui/package.json` | MODIFY | 5 min | None |
| 2 | `src/ui/src/components/chat/MarkdownRenderer.js` | COPY verbatim | 5 min | Step 1 |
| 3 | `src/ui/src/components/chat/ChatInput.js` | COPY verbatim | 5 min | None |
| 4 | `src/ui/src/components/chat/StreamingMessage.js` | COPY + adapt labels | 15 min | Step 2 |
| 5 | `ConversationService.astream_response()` | ADD method | 1 hr | `plan_conversation_migration.md` done |
| 6 | `src/server/routes/manager_websocket_routes.py` | NEW | 1 hr | Step 5 |
| 7 | `src/server/main.py` | MODIFY (add WS router) | 10 min | Step 6 |
| 8 | `src/ui/src/hooks/useManagerChat.js` | NEW | 30 min | None |
| 9 | `src/ui/src/components/views/ManagerChatView.js` | REPLACE Phase 1 impl | 1 hr | Steps 3,4,8 |

Steps 1-4 and 5-7 and 8 can run in parallel. Step 9 depends on 3, 4, 8.

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `RovoChatInferencer` doesn't support `aiter_infer()` streaming | Low | High | Check `StreamingInferencerBase` — it implements `aiter_infer`. Fall back to batch `ainfer()` + send as single token if needed. |
| WebSocket connection blocked by CORS/proxy in dev | Low | Medium | CRA proxy (`setupProxy.js`) forwards WS — already done in rankevolve's pattern |
| `react-markdown` version conflict with existing CRA deps | Low | Low | Pin to `^9.0.1`; test with `npm install --legacy-peer-deps` if needed |
| Session messages out of sync (WS + HTTP both writing) | Medium | Medium | Phase 2 WS is the single writer for new messages. Phase 1 HTTP endpoint remains for reads only. |
| Large streaming responses cause React re-render thrashing | Low | Medium | Rankevolve uses `streamingContentRef` (not state) for accumulation — only `setStreamingMessage` triggers renders. Adopted verbatim. |

---

## 7. Directly Reusable Files from Rankevolve

| Source | Destination | Changes |
|---|---|---|
| `rankevolve/.../StreamingMessage.js` | `src/ui/src/components/chat/StreamingMessage.js` | Replace agent label map with `metadata.agent_name` |
| `rankevolve/.../MarkdownRenderer.js` | `src/ui/src/components/chat/MarkdownRenderer.js` | **None** — verbatim copy |
| `rankevolve/.../ChatInput.js` | `src/ui/src/components/chat/ChatInput.js` | **None** — verbatim copy |
| `rankevolve/.../useAgentChat.js` | `src/ui/src/hooks/useManagerChat.js` | WS URL, session init, remove `taskPhase` |
| `rankevolve/.../agent_websocket_routes.py` | `src/server/routes/manager_websocket_routes.py` | Remove bridge/queue, call ConversationService directly, simplify to single session |

---

## 8. Verification Plan

### Backend
```bash
# Start server in real-sessions mode
./run.sh --real-sessions

# Test WS connection manually
wscat -c ws://localhost:8000/ws/manager
# Send: {"type": "init", "session_id": "test-123"}
# Expect: {"type": "session_init", "session_id": "test-123"}
# Send: {"type": "message", "content": "Hello, what is my team working on?"}
# Expect: stream of {"type": "token", "content": "..."} then {"type": "message_end", ...}
```

### Frontend
1. Open manager sessions list → click a session → `ManagerChatView` loads
2. Connection status badge shows "Connected" (green)
3. Type a message → Enter → message appears immediately (user bubble, right-aligned)
4. "Thinking..." indicator appears
5. Token stream starts — blinking cursor visible, text builds up
6. On completion — cursor disappears, final message committed to list
7. Click "Cancel" mid-stream → streaming stops, status resets
8. Disconnect network → badge shows "Disconnected" → reconnects automatically with backoff
9. Code blocks in AI response → syntax highlighted with Prism vscDarkPlus
10. Tables in AI response → properly rendered GFM tables
