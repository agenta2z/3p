/**
 * useManagerChat — WebSocket-based hook for Manager ↔ AI streaming chat.
 *
 * Adapted from rankevolve's useAgentChat.js.
 * Manages connection to /ws/manager, token streaming, auto-reconnect.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  parseResponseTags,
  parseSessionContext,
  stripSessionContext,
  stripResponseTags,
  stripAnsi,
  stripAcliNoise,
  stripToolsToInvoke,
} from '../components/chat/ThinkingFold';
import { useGraphState } from './useGraphState';

const WS_RECONNECT_BASE_MS = 1000;
const WS_RECONNECT_MAX_MS = 30000;

/**
 * Resolve the widgetType string from a pendingInput object.
 * Used when inserting a committed widget_response message into history.
 */
function _resolveWidgetType(pendingInput) {
  const inputMode = pendingInput?.inputMode || {};
  return inputMode.metadata?.widget_type || inputMode.mode || 'free_text';
}

function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // In development, CRA proxy doesn't reliably forward WebSocket upgrades.
  // Connect directly to the backend port instead.
  const backendPort = process.env.REACT_APP_BACKEND_PORT || '8000';
  const host = window.location.hostname;
  const isDev = process.env.NODE_ENV === 'development';
  const wsHost = isDev ? `${host}:${backendPort}` : window.location.host;
  return `${proto}//${wsHost}/ws/manager`;
}

export function useManagerChat(sessionId) {
  const [messages, setMessages] = useState([]);
  const [streamingMessage, setStreamingMessage] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [pendingInput, setPendingInput] = useState(null);
  // Task subtab state
  const [tasks, setTasks] = useState({});
  const [activeTabType, setActiveTabType] = useState('session');
  const [activeTaskId, setActiveTaskId] = useState(null);

  // Graph visualization state (sub-graphs, drill-down, batching)
  const graphState = useGraphState(setTasks);

  const wsRef = useRef(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const streamingContentRef = useRef('');
  const streamingMetadataRef = useRef({});
  const connectRef = useRef(null);
  const submittedRef = useRef(false);      // double-submit guard
  const pendingInputRef = useRef(null);    // stable ref to current pendingInput (avoids stale closure)
  const turnCountRef = useRef(0);          // tracks current turn number for live messages
  // Most-recent task_status task_id that is still in flight ("starting"/"running" but not
  // "completed"/"error"/"cancelled"). Routed through cancelRequest + sendPendingInputResponse
  // so dev-tool cancels and Approve/Reject widget responses reach the right per-task queue
  // (see manager_websocket_routes.py Patch 3.4 / R9b).
  const currentTaskIdRef = useRef(null);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    const delay = Math.min(
      WS_RECONNECT_BASE_MS * Math.pow(2, reconnectAttemptRef.current),
      WS_RECONNECT_MAX_MS
    );
    reconnectAttemptRef.current += 1;
    reconnectTimerRef.current = setTimeout(() => {
      if (connectRef.current) connectRef.current();
    }, delay);
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    const url = getWsUrl();
    setConnectionStatus('connecting');

    const ws = new WebSocket(url);
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

    ws.onerror = () => {
      setConnectionStatus('error');
    };

    ws.onmessage = (event) => {
      try {
        handleServerMessage(JSON.parse(event.data));
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };
  }, [sessionId, scheduleReconnect]);

  // Keep connectRef up to date
  connectRef.current = connect;

  const handleServerMessage = useCallback((data) => {
    switch (data.type) {
      case 'task_status': {
        const { task_id, status, request, tool_name, error: taskError } = data;
        // Track currently in-flight dev-tool task_id so cancelRequest +
        // sendPendingInputResponse can route by task_id (manager_websocket_routes
        // Patch 3.4 / R9b). Clear on terminal states.
        if (status === 'starting' || status === 'running') {
          currentTaskIdRef.current = task_id;
        } else if (currentTaskIdRef.current === task_id &&
                   (status === 'completed' || status === 'error' || status === 'cancelled')) {
          currentTaskIdRef.current = null;
        }
        if (status === 'starting') {
          const label = request || tool_name || 'Task';
          setTasks(prev => ({
            ...prev,
            [task_id]: {
              id: task_id, label, toolName: tool_name,
              status: 'starting', streamContent: '', isStreaming: false, error: null,
            },
          }));
          setMessages(prev => [...prev, {
            id: `task-ref-${task_id}`, role: 'task_ref',
            taskId: task_id, label, status: 'starting',
            timestamp: new Date().toISOString(),
          }]);
        } else {
          setTasks(prev => prev[task_id]
            ? { ...prev, [task_id]: { ...prev[task_id], status, error: taskError || null } }
            : prev
          );
          setMessages(prev => prev.map(msg =>
            msg.role === 'task_ref' && msg.taskId === task_id ? { ...msg, status } : msg
          ));
        }
        break;
      }

      case 'graph_topology': {
        const tid = data.task_id;
        if (tid) graphState.handleGraphTopology(tid, data);
        break;
      }

      case 'node_status': {
        if (data.task_id) graphState.handleNodeStatus(data.task_id, data);
        break;
      }

      case 'node_stream': {
        if (data.task_id) graphState.handleNodeStream(data.task_id, data);
        break;
      }

      case 'graph_reconcile': {
        if (data.task_id) graphState.handleGraphReconcile(data.task_id, data);
        break;
      }

      case 'task_completed': {
        const { task_id: cTaskId, tool_name: cToolName, result_summary, workspace, document_path } = data;
        // Auto-advance: send a new WS message to trigger next conversation turn
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const parts = [
            `[System notification: Task '${cToolName || cTaskId}' (${cTaskId}) completed successfully.`,
            workspace ? `Workspace: ${workspace}.` : '',
            document_path ? `Generated document: ${document_path}.` : '',
            result_summary ? `Summary: ${result_summary.slice(0, 300)}.` : '',
            `CRITICAL: Present 3-5 bullet points summarizing the key aspects of the document, then`,
            `you MUST respond with a "confirmation" conversation tool (NOT "clarification" or "free_text").`,
            document_path
              ? `Set metadata.view to "${document_path}", metadata.view_label to "View Role Document",`
                + ` metadata.yes_label to "✅ Approve & Proceed", metadata.no_label to "❌ Request Changes".`
              : `Set metadata.yes_label to "✅ Approve & Proceed", metadata.no_label to "❌ Request Changes".`,
            `Example ToolsToInvoke block:`,
            '```json ToolsToInvoke',
            JSON.stringify({
              type: 'conversation',
              name: 'confirmation',
              arguments: {
                prompt: 'Review and approve the role document to proceed to Phase 2?',
                metadata: {
                  view: document_path || '',
                  view_label: 'View Role Document',
                  yes_label: '✅ Approve & Proceed',
                  no_label: '❌ Request Changes',
                },
              },
            }),
            '```]',
          ].filter(Boolean).join(' ');
          wsRef.current.send(JSON.stringify({ type: 'message', content: parts, is_auto_advance: true }));
        }
        break;
      }

      case 'token': {
        // Route task tokens to task panel — do NOT add to conversation stream
        const tokenTaskId = data.task_id || data.metadata?.task_id;
        if (tokenTaskId) {
          setTasks(prev => {
            const t = prev[tokenTaskId];
            if (!t) return prev;
            let sc = (t.streamContent || '') + data.content;
            if (sc.length > 200_000) sc = sc.slice(50_000);
            return { ...prev, [tokenTaskId]: { ...t, isStreaming: true, streamContent: sc } };
          });
          break;
        }
        // Conversation streaming (existing behaviour)
        streamingContentRef.current += data.content;
        if (data.metadata) {
          streamingMetadataRef.current = data.metadata;
        }
        // Parse <Response> tags to separate thinking from response
        const parsedToken = parseResponseTags(streamingContentRef.current);
        // Extract session context if present
        const ctxToken = parseSessionContext(streamingContentRef.current);
        setStreamingMessage({
          role: 'agent',
          content: streamingContentRef.current,
          metadata: streamingMetadataRef.current,
          thinkingContent: parsedToken.thinkingContent,
          responseContent: parsedToken.responseContent,
          responsePhase: parsedToken.phase,
          sessionContext: ctxToken,
        });
        setIsStreaming(true);
        break;
      }

      case 'message_start':
        streamingContentRef.current = '';
        streamingMetadataRef.current = {};
        setStreamingMessage({ role: 'agent', content: '', metadata: {}, responsePhase: 'pre_response' });
        setIsStreaming(true);
        break;

      case 'pending_input': {
        // Commit any in-progress streaming content as a completed message
        // (the AI's preamble text before the conversation tool invocation)
        const streamContent = streamingContentRef.current;
        if (streamContent && streamContent.trim()) {
          const parsed = parseResponseTags(streamContent);
          // 'pre_response': only thinking so far, no <Response> tag yet.
          // Don't show raw thinking as message content — show nothing (thinking-only preamble).
          // 'in_response' or 'post_response': use parsed.responseContent (already after <Response>).
          // 'no_tags': no XML tags at all — show stripped full content (old-style responses).
          const phase = parsed.phase;
          let displayContent;
          if (phase === 'pre_response') {
            // Only thinking content — no user-visible response yet. Skip commit.
            displayContent = '';
          } else if (phase === 'no_tags') {
            displayContent = stripSessionContext(stripAnsi(stripAcliNoise(stripToolsToInvoke(streamContent))));
          } else {
            // in_response or post_response: use the extracted response content
            displayContent = stripSessionContext(stripAnsi(stripAcliNoise(stripToolsToInvoke(parsed.responseContent || ''))));
          }
          // For pre_response: still commit if there's thinking content (show collapsed ThinkingFold)
          // so the user can see the AI was reasoning, even though no response was emitted yet.
          const hasResponse = displayContent.trim().length > 0;
          const hasThinking = (parsed.thinkingContent || '').trim().length > 0;
          if (hasResponse || hasThinking) {
            setMessages(prev => [...prev, {
              id: `pending-pre-${Date.now()}`,
              role: 'agent',
              content: displayContent,
              rawContent: streamContent, // original raw LLM output for "Full Response" RAW tab
              timestamp: new Date().toISOString(),
              agent_name: streamingMetadataRef.current?.agent_name || 'Orchestrator',
              thinkingContent: parsed.thinkingContent || '',
              responsePhase: hasResponse ? phase : 'no_tags',
              sessionContext: null,
              // Server now sends prompt_data inline on pending_input messages
              // (via WebSocketInteractive.asend_response), so the View Prompt
              // button on this preamble can open the drawer immediately without
              // a REST round-trip. Falls back to null if the server hasn't
              // populated it (older code path or missing inferencer state).
              promptData: data.prompt_data || null,
              turnNumber: (turnCountRef.current || 0) + 1,
            }]);
          }
        }
        // Clear streaming state (turn is still active — don't set isStreaming=false)
        setStreamingMessage(null);
        streamingContentRef.current = '';
        streamingMetadataRef.current = {};
        // Show the conversation tool widget; reset submit guard for fresh widget
        submittedRef.current = false;
        console.debug('[pending_input] input_mode:', JSON.stringify(data.input_mode, null, 2));
        const newPending = {
          content: data.content,
          inputMode: data.input_mode || null,
        };
        pendingInputRef.current = newPending;
        setPendingInput(newPending);
        break;
      }

      case 'stream_correction': {
        // Server has clean output from --output-file (no TUI noise, intact code fences).
        // Replace the in-progress streaming display with the clean version before
        // message_end commits it. streamingContentRef is updated so message_end
        // uses clean content as the fallback if final_content is empty.
        const rawClean = data.content || '';
        streamingContentRef.current = rawClean;

        const corrParsed = parseResponseTags(rawClean);
        const corrPhase = corrParsed.phase === 'pre_response' ? 'no_tags' : corrParsed.phase;
        let corrDisplay;
        if (corrPhase === 'no_tags') {
          corrDisplay = stripAnsi(stripAcliNoise(stripToolsToInvoke(rawClean)));
        } else {
          corrDisplay = stripSessionContext(
            stripAnsi(stripAcliNoise(stripToolsToInvoke(corrParsed.responseContent)))
          );
        }

        setStreamingMessage(prev => prev ? {
          ...prev,
          content: rawClean,
          displayContent: corrDisplay,
          thinkingContent: corrParsed.thinkingContent,
          responsePhase: corrPhase,
        } : prev);
        break;
      }

      case 'message_end': {
        console.debug('[useManagerChat] message_end — turn_number:', data.turn_number,
          '| prompt_data keys:', Object.keys(data.prompt_data || {}),
          '| rendered_prompt len:', (data.prompt_data?.rendered_prompt || '').length);
        // pendingInput is normally already cleared on submit (RankEvolve pattern),
        // but keep as safety net for edge cases (error mid-turn, WS reconnect, etc.).
        // Setting null→null is a React no-op in normal flow.
        setPendingInput(null);
        pendingInputRef.current = null;
        submittedRef.current = false;
        const finalContent = data.final_content || streamingContentRef.current;
        const finalParsed = parseResponseTags(finalContent);
        // If stream ended without <Response>, treat as no_tags
        const finalPhase = finalParsed.phase === 'pre_response' ? 'no_tags' : finalParsed.phase;
        const finalCtx = parseSessionContext(finalContent);

        // Clean up the display content
        let displayContent;
        if (finalPhase === 'no_tags') {
          displayContent = stripAnsi(stripAcliNoise(stripToolsToInvoke(finalContent)));
        } else {
          // Strip noise from the response portion too (including any leaked ToolsToInvoke blocks)
          displayContent = stripSessionContext(stripAnsi(stripAcliNoise(stripToolsToInvoke(finalParsed.responseContent))));
        }

        const turnNumber = data.turn_number || ++turnCountRef.current;
        setMessages(prev => [...prev, {
          id: data.message_id || `msg-${Date.now()}`,
          role: 'agent',
          content: displayContent,
          timestamp: new Date().toISOString(),
          thinkingContent: finalParsed.thinkingContent,
          responsePhase: finalPhase,
          sessionContext: finalCtx,
          promptData: data.prompt_data || null,
          turnNumber,
          // Match the preamble path's pattern: prefer the explicit value from
          // the server, fall back to the streaming metadata captured at
          // message_start, then a sensible default. Without this, the bubble
          // header rendered the AgentMessageBubble fallback "AI Assistant"
          // for the FINAL committed message — even though the same session's
          // preamble messages correctly showed "Orchestrator".
          agent_name: data.agent_name
            || streamingMetadataRef.current?.agent_name
            || 'Orchestrator',
        }]);
        setStreamingMessage(null);
        streamingContentRef.current = '';
        streamingMetadataRef.current = {};
        setIsStreaming(false);
        break;
      }

      case 'turn_boundary': {
        // Server signals a turn boundary (e.g. after a conversation tool interaction).
        // Update turn counter; cache_folder may be used by PromptViewer.
        const tbTurnNumber = data.turn_number;
        const tbCacheFolder = data.cache_folder;
        if (tbTurnNumber != null) {
          turnCountRef.current = tbTurnNumber;
        }
        // Attach cache_folder to the most recent agent message so View Prompt works
        if (tbCacheFolder) {
          setMessages(prev => {
            const idx = [...prev].reverse().findIndex(m => m.role === 'agent');
            if (idx === -1) return prev;
            const realIdx = prev.length - 1 - idx;
            return prev.map((m, i) => i === realIdx
              ? { ...m, turnNumber: tbTurnNumber || m.turnNumber, cacheFolder: tbCacheFolder }
              : m
            );
          });
        }
        break;
      }

      case 'auto_advance':
        // Server auto-continues without user input (e.g. async tool completion).
        // Don't add to message list — next message_start/token/message_end follows.
        break;

      case 'error':
        // Clear any stuck widget on error
        setPendingInput(null);
        pendingInputRef.current = null;
        submittedRef.current = false;
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
        setPendingInput(null);
        pendingInputRef.current = null;
        submittedRef.current = false;
        setIsStreaming(false);
        setStreamingMessage(null);
        setTasks({});
        setActiveTabType('session');
        setActiveTaskId(null);
        // Load existing messages from session history,
        // parsing thinking/response phases for agent messages.
        // Compute turn_number for each agent message (1-based count of agent msgs seen so far).
        if (data.messages) {
          let agentTurnCount = 0;
          setMessages(data.messages.map((msg, i) => {
            // Hide auto-advance system messages (RankEvolve pattern)
            if (msg.metadata?.is_auto_advance) return null;
            const isAgent = msg.role === 'assistant' || msg.role === 'agent';
            if (isAgent) agentTurnCount += 1;
            const base = {
              id: msg.id || `loaded-${i}`,
              role: msg.role === 'manager' ? 'manager' : 'agent',
              content: msg.content,
              timestamp: msg.timestamp,
              agent_name: msg.agent_name,
              // carry persisted turn_number if present (set by server), else compute
              turnNumber: msg.turn_number || (isAgent ? agentTurnCount : null),
            };
            // For agent messages, parse out thinking vs response content
            if (msg.role === 'assistant' || msg.role === 'agent') {
              const { phase, thinkingContent, responseContent } = parseResponseTags(msg.content);
              const sessionContext = parseSessionContext(msg.content);
              if (phase === 'post_response' || phase === 'in_response') {
                // Clean the display content — show only the response portion
                let cleaned = stripResponseTags(responseContent);
                cleaned = stripSessionContext(cleaned);
                cleaned = stripAnsi(cleaned);
                cleaned = stripAcliNoise(cleaned);
                base.content = cleaned;
                base.thinkingContent = thinkingContent;
                base.responsePhase = phase;
              } else if (phase === 'pre_response') {
                // No <Response> tag — still clean up noise
                base.content = stripSessionContext(stripAnsi(stripAcliNoise(msg.content)));
                base.responsePhase = 'no_tags';
              }
              if (sessionContext) {
                base.sessionContext = sessionContext;
              }
            }
            return base;
          }).filter(Boolean));
          // Sync turnCountRef so live messages continue from the right turn number
          turnCountRef.current = agentTurnCount;
        }
        break;

      case 'heartbeat':
      case 'pong':
        break;

      default:
        console.log('Unknown WS message type:', data.type);
    }
  }, []);

  const fetchTurnData = useCallback(async (sid, turnNum) => {
    try {
      const res = await fetch(`/api/sessions/${sid}/turns/${turnNum}`);
      if (!res.ok) return null;
      const json = await res.json();
      return json.data || null;
    } catch (e) {
      console.warn('Failed to fetch turn data:', e);
      return null;
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

  // Switch between session conversation and a task panel
  const switchTab = useCallback((tabId, tabType) => {
    setActiveTabType(tabType || 'session');
    setActiveTaskId(tabType === 'task' ? tabId : null);
  }, []);

  const sendPendingInputResponse = useCallback((response) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[PendingInput] WebSocket not open — cannot send response');
      return;
    }
    // Double-submit guard — prevents two widget_response messages on rapid clicks
    if (submittedRef.current) return;
    submittedRef.current = true;

    // Insert committed widget_response message into history (RankEvolve: ADD_WIDGET_MESSAGE).
    // This persists the user's choice visually after the widget unmounts.
    const currentPending = pendingInputRef.current;
    if (currentPending) {
      const _widgetType = _resolveWidgetType(currentPending);
      const _viewPath = currentPending.inputMode?.metadata?.view || null;
      const _viewLabel = currentPending.inputMode?.metadata?.view_label || 'View Document';
      const _viewType = currentPending.inputMode?.metadata?.view_type || 'file';
      console.debug('[sendPendingInputResponse] widgetType:', _widgetType,
        'viewPath:', _viewPath, 'viewType:', _viewType,
        'response:', typeof response === 'string' ? response : JSON.stringify(response).slice(0, 100));
      setMessages(prev => [...prev, {
        id: `widget-resp-${Date.now()}`,
        role: 'widget_response',
        widgetType: _widgetType,
        prompt: currentPending.inputMode?.prompt || currentPending.content || '',
        response,
        inputMode: currentPending.inputMode,
        viewPath: _viewPath,
        viewLabel: _viewLabel,
        viewType: _viewType,
        timestamp: new Date().toISOString(),
      }]);
    }

    // Clear pendingInput immediately (RankEvolve: CLEAR_PENDING_INPUT).
    // widget_response message above preserves the user's choice in history.
    // Immediate clear re-enables chat input and puts widget_response above AI streaming.
    setPendingInput(null);
    pendingInputRef.current = null;

    // Send to server. Include task_id so dev-tool widget responses route to the
    // per-task input queue (manager_websocket_routes R9b); omitted task_id falls
    // through to the conversation queue (existing behavior).
    const content = typeof response === 'string' ? response : JSON.stringify(response);
    const payload = { type: 'pending_input_response', content };
    if (currentTaskIdRef.current) payload.task_id = currentTaskIdRef.current;
    wsRef.current.send(JSON.stringify(payload));
  }, []);

  const cancelRequest = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Include task_id so the dispatcher cancels the matching dev-tool task
      // (manager_websocket_routes Patch 3.4); omitted falls through to
      // active_task cancel (existing behavior).
      const payload = { type: 'cancel' };
      if (currentTaskIdRef.current) payload.task_id = currentTaskIdRef.current;
      wsRef.current.send(JSON.stringify(payload));
    }
    setPendingInput(null);
    setIsStreaming(false);
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
    fetchTurnData,
    pendingInput,
    sendPendingInputResponse,
    isConnected: connectionStatus === 'connected',
    // Task subtab state
    tasks,
    activeTabType,
    activeTaskId,
    switchTab,
    // Graph visualization state (sub-graphs, drill-down, navigation)
    graphState,
  };
}

export default useManagerChat;
