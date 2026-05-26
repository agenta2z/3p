/**
 * ManagerChatView — Phase 2: WebSocket streaming chat with AI team.
 *
 * Displays the selected Manager Session as a streaming chat interface with:
 * - Real-time token streaming from WebSocket
 * - Blinking cursor during streaming
 * - "Thinking..." indicator
 * - Agent metadata badges
 * - Cancel button for in-flight requests
 * - Connection status display
 * - Markdown rendering with syntax highlighting
 *
 * Adapted from rankevolve's AgentChatPanel pattern.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import { useTheme } from '@mui/material/styles';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PersonIcon from '@mui/icons-material/Person';
import { useApiData } from '../../hooks/useApiData';
import { useServerStatus } from '../../hooks/useServerStatus';
import { useManagerChat } from '../../hooks/useManagerChat';
import { usePromptViewer } from '../../hooks/usePromptViewer';
import { LoadingIndicator } from '../../shared';
import { MarkdownRenderer } from '../chat/MarkdownRenderer';
import { StreamingMessage } from '../chat/StreamingMessage';
import { ChatInput } from '../chat/ChatInput';
import { AgentMessageBubble } from '../chat/AgentMessageBubble';
import { PromptViewerDrawer } from '../chat/PromptViewerDrawer';
import ConversationToolWidget from '../chat-widgets/ConversationToolWidget';
import { useFileViewer } from '../../hooks/useFileViewer';
import { FileViewer } from '../layout/FileViewer';
import ConnectionStatusBar from '../layout/ConnectionStatusBar';
import { TaskCard } from '../chat/TaskCard';
import { TaskPanel } from '../chat/TaskPanel';
import { BackendSelector } from '../chat/BackendSelector';


/**
 * CommittedWidgetMessage — read-only record of a user's widget submission.
 * Rendered in message history after pendingInput is cleared (RankEvolve: widget_response role).
 */
function CommittedWidgetMessage({ message, onView, onViewFolder }) {
  const theme = useTheme();
  const { widgetType, response, prompt } = message;

  console.debug('[CommittedWidgetMessage] widgetType:', widgetType, 'viewPath:', message.viewPath, 'response:', response);

  const containerSx = {
    px: 2, py: 1.5, borderRadius: 2,
    border: '1px solid',
    borderColor: theme.custom?.surfaces?.cardBorder || 'rgba(255,255,255,0.1)',
    backgroundColor: theme.custom?.surfaces?.overlayLight || 'rgba(255,255,255,0.03)',
    maxWidth: theme.custom?.layout?.widgetMaxWidth || '75%',
  };

  // Confirmation with View button (matches RankEvolve post-task review pattern)
  if (widgetType === 'confirmation') {
    const isApproved = response === 'yes' || response?.choice === 'yes';
    const viewPath = message.viewPath;
    const viewLabel = message.viewLabel || 'View Document';
    const viewType = message.viewType || 'file';

    const handleView = () => {
      if (viewType === 'folder' && onViewFolder) {
        onViewFolder(viewPath);
      } else if (onView) {
        onView(viewPath);
      }
    };

    return (
      <Box sx={containerSx}>
        {prompt && (
          <Typography variant="body2" sx={{ color: 'text.primary', mb: 1 }}>
            {prompt}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
          {viewPath && (onView || onViewFolder) && (
            <Button variant="outlined" size="small"
              onClick={handleView}
              sx={{
                textTransform: 'none', fontSize: '0.85rem',
                borderColor: 'rgba(74,144,217,0.4)', color: 'primary.main',
                '&:hover': { borderColor: 'primary.main', backgroundColor: 'rgba(74,144,217,0.08)' },
              }}>
              {viewType === 'folder' ? '📁' : '📄'} {viewLabel}
            </Button>
          )}
          <Button variant="contained" size="small" disabled
            sx={{
              textTransform: 'none', fontSize: '0.85rem',
              '&.Mui-disabled': {
                backgroundColor: isApproved ? 'rgba(46,125,50,0.3)' : 'rgba(244,67,54,0.3)',
                color: 'rgba(255,255,255,0.7)',
              },
            }}>
            {isApproved ? '✅ Approved' : '❌ Declined'}
          </Button>
        </Box>
      </Box>
    );
  }

  // Other widget types
  let statusText = '';
  let statusColor = 'text.secondary';

  if (widgetType === 'single_choice') {
    const opts = message.inputMode?.options || [];
    const idx = response?.choice_index;
    const label = idx != null
      ? (opts[idx]?.label || `Option ${idx + 1}`)
      : (response?.custom_text || JSON.stringify(response));
    statusText = `Selected: ${label}`;
    statusColor = 'primary.main';
  } else if (widgetType === 'multiple_choice' || widgetType === 'multiple_choices') {
    const opts = message.inputMode?.options || [];
    const sels = response?.selections || [];
    const labels = sels.map(s =>
      s.custom_text || opts[s.choice_index]?.label || `Option ${s.choice_index + 1}`
    );
    statusText = labels.length > 0 ? `Selected: ${labels.join(', ')}` : 'Submitted';
    statusColor = 'primary.main';
  } else {
    const text = response?.content || (typeof response === 'string' ? response : JSON.stringify(response));
    statusText = text ? `"${text}"` : 'Submitted';
    statusColor = 'text.primary';
  }

  return (
    <Box sx={containerSx}>
      {prompt && (
        <Typography variant="caption" sx={{ color: 'text.disabled', display: 'block', mb: 0.5 }}>
          {prompt.length > 80 ? prompt.slice(0, 80) + '…' : prompt}
        </Typography>
      )}
      <Typography variant="body2" sx={{ color: statusColor, fontWeight: 500 }}>
        {statusText}
      </Typography>
    </Box>
  );
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  const d = new Date(timestamp);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}


function ManagerMessage({ message }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
      <Box sx={{ maxWidth: '70%', display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
        <Box
          sx={{
            backgroundColor: 'primary.dark',
            color: 'white',
            px: 2,
            py: 1.5,
            borderRadius: '16px 16px 4px 16px',
            lineHeight: 1.5,
            fontSize: '0.9rem',
            '& p': { m: 0 },
            '& pre': { overflow: 'auto' },
          }}
        >
          <MarkdownRenderer content={message.content} />
        </Box>
        <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5, mr: 0.5 }}>
          {formatTime(message.timestamp)}
        </Typography>
      </Box>
      <Avatar sx={{ ml: 1, width: 32, height: 32, bgcolor: 'primary.main', flexShrink: 0 }}>
        <PersonIcon sx={{ fontSize: 18 }} />
      </Avatar>
    </Box>
  );
}




function ErrorMessage({ message }) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
      <Box
        sx={{
          px: 2,
          py: 1,
          borderRadius: 2,
          backgroundColor: 'rgba(255, 50, 50, 0.1)',
          border: '1px solid rgba(255, 50, 50, 0.3)',
          maxWidth: '80%',
        }}
      >
        <Typography variant="body2" sx={{ color: 'error.main', fontSize: '0.85rem' }}>
          ⚠️ {message.content}
        </Typography>
      </Box>
    </Box>
  );
}


/**
 * Connection status indicator
 */
function WsStatusBadge({ status }) {
  const config = {
    connected: { color: '#4caf50', label: 'Connected' },
    connecting: { color: '#ff9800', label: 'Connecting...' },
    disconnected: { color: '#f44336', label: 'Disconnected' },
    error: { color: '#f44336', label: 'Error' },
  }[status] || { color: '#9e9e9e', label: status };

  return (
    <Chip
      size="small"
      label={config.label}
      sx={{
        height: 20,
        fontSize: '0.65rem',
        backgroundColor: `${config.color}22`,
        color: config.color,
        borderColor: config.color,
      }}
      variant="outlined"
    />
  );
}


export default function ManagerChatView({ sessionId, onBack, onTasksChanged, onActiveTaskChanged, onSwitchTabRef }) {
  // Load session metadata (title etc.) via REST
  const { data: sessionMeta, loading } = useApiData(
    sessionId ? `/sessions/${sessionId}` : null
  );
  const { status: serverStatus, serverInfo } = useServerStatus();

  // WebSocket streaming chat
  const {
    messages,
    streamingMessage,
    isStreaming,
    connectionStatus,
    sendMessage,
    cancelRequest,
    fetchTurnData,
    pendingInput,
    sendPendingInputResponse,
    isConnected,
    tasks,
    activeTabType,
    activeTaskId,
    switchTab,
    graphState,
  } = useManagerChat(sessionId);

  const promptViewer = usePromptViewer();
  const {
    fileViewerOpen, fileContent, fileName, fileError, fileLoading,
    openFileViewer, closeFileViewer,
    folderTree, isFolderMode, selectedFilePath, openFolderViewer, selectFileInFolder,
  } = useFileViewer();

  // Handler for "View Prompt" — uses inline promptData if available (current session),
  // or fetches from REST API for history messages (after server restart).
  const handleViewPrompt = useCallback(async (message) => {
    console.log('[ViewPrompt] clicked', {
      hasPromptData: Boolean(message.promptData?.rendered_prompt),
      turnNumber: message.turnNumber,
      promptDataKeys: message.promptData ? Object.keys(message.promptData) : [],
      renderedPromptLen: message.promptData?.rendered_prompt?.length || 0,
    });
    if (message.promptData?.rendered_prompt) {
      // Fast path: inline prompt data from message_end
      console.log('[ViewPrompt] opening from inline promptData');
      promptViewer.openPrompt(message.promptData);
    } else if (message.turnNumber && fetchTurnData) {
      // Slow path: fetch from disk (history messages / after server restart)
      console.log('[ViewPrompt] fetching from disk, turnNumber=', message.turnNumber);
      const data = await fetchTurnData(sessionId, message.turnNumber);
      console.log('[ViewPrompt] fetched data:', data ? Object.keys(data) : null);
      // Skip drawer if data is empty (no prompt content to show).
      // The server now returns 200 with note="..." for missing turns instead of 404,
      // so we explicitly check for usable content before opening the drawer.
      const hasContent = data && (data.rendered_prompt || data.template_source);
      if (hasContent) {
        promptViewer.openPrompt(data);
      } else {
        console.info('[ViewPrompt] no prompt data available for this turn');
      }
    } else {
      console.warn('[ViewPrompt] no promptData and no turnNumber — nothing to show');
    }
  }, [promptViewer, fetchTurnData, sessionId]);

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll on new messages or streaming updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  const handleSubmit = useCallback((e) => {
    e?.preventDefault();
    if (!inputValue.trim() || !isConnected) return;
    sendMessage(inputValue);
    setInputValue('');
  }, [inputValue, isConnected, sendMessage]);

  const theme = useTheme();
  const widgetMaxWidth = theme.custom?.layout?.widgetMaxWidth || '75%';
  const isRealSessions = serverInfo?.real_sessions;

  // Sync tasks up to App so Sidebar can render task subtabs
  useEffect(() => {
    onTasksChanged?.(tasks);
  }, [tasks, onTasksChanged]);

  // Sync activeTaskId so Sidebar can highlight the active task subtab
  useEffect(() => {
    onActiveTaskChanged?.(activeTaskId);
  }, [activeTaskId, onActiveTaskChanged]);

  // Expose switchTab to App so Sidebar clicks can drive it
  useEffect(() => {
    onSwitchTabRef?.(switchTab);
  }, [switchTab, onSwitchTabRef]);

  if (loading) return <LoadingIndicator />;

  // Task panel view — replaces conversation when a task tab is open
  if (activeTabType === 'task' && activeTaskId) {
    return (
      <TaskPanel
        task={tasks[activeTaskId]}
        onBack={() => switchTab(null, 'session')}
        graphState={graphState}
      />
    );
  }

  const sessionTitle = sessionMeta?.title || 'Session';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', mx: -3, mt: -3, mb: -3 }}>
      {/* Connection Status */}
      <ConnectionStatusBar status={serverStatus} serverInfo={serverInfo} />

      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          px: 2,
          py: 1.5,
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          backgroundColor: 'background.paper',
          flexShrink: 0,
        }}
      >
        <IconButton onClick={onBack} size="small" sx={{ color: 'text.secondary' }}>
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
            {sessionTitle}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {messages.length} messages
          </Typography>
        </Box>
        {isRealSessions && (
          <BackendSelector
            sessionId={sessionId}
            sessionLlmBackend={sessionMeta?.llm_backend}
            sessionLlmModel={sessionMeta?.llm_model}
          />
        )}
        {isRealSessions && <WsStatusBadge status={connectionStatus} />}
      </Box>

      {/* Messages */}
      <Box sx={{ flexGrow: 1, overflow: 'auto', px: 3, py: 2 }}>
        {messages.map((msg) => {
          // Hide auto-advance messages (server-driven continuation, not user-visible)
          if (msg.metadata?.is_auto_advance) return null;
          if (msg.role === 'manager') {
            return <ManagerMessage key={msg.id} message={msg} />;
          }
          if (msg.role === 'error') {
            return <ErrorMessage key={msg.id} message={msg} />;
          }
          if (msg.role === 'widget_response') {
            return (
              <Box key={msg.id} sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2, ml: 5 }}>
                <CommittedWidgetMessage message={msg} onView={openFileViewer} onViewFolder={openFolderViewer} />
              </Box>
            );
          }
          if (msg.role === 'task_ref') {
            return (
              <Box key={msg.id} sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2, ml: 5 }}>
                <TaskCard
                  taskId={msg.taskId}
                  label={msg.label}
                  status={msg.status}
                  onOpenTask={(id) => switchTab(id, 'task')}
                />
              </Box>
            );
          }
          return (
            <AgentMessageBubble
              key={msg.id}
              message={msg}
              onViewPrompt={() => handleViewPrompt(msg)}
              onViewFullResponse={promptViewer.openFullResponse}
            />
          );
        })}

        {/* Streaming token display with blinking cursor */}
        {streamingMessage && (streamingMessage.content || streamingMessage.responsePhase === 'pre_response') && (
          <StreamingMessage
            content={streamingMessage.content}
            metadata={streamingMessage.metadata}
            thinkingContent={streamingMessage.thinkingContent}
            responseContent={streamingMessage.responseContent}
            responsePhase={streamingMessage.responsePhase}
            sessionContext={streamingMessage.sessionContext}
            onCancel={cancelRequest}
          />
        )}

        {/* Conversation tool widget — inside scroll area, aligned with AI messages */}
        {pendingInput && (
          <Box sx={{ mb: 2, ml: 5, maxWidth: widgetMaxWidth }}>
            <ConversationToolWidget
              pendingInput={pendingInput}
              onSubmit={sendPendingInputResponse}
              onView={openFileViewer}
              onViewFolder={openFolderViewer}
            />
          </Box>
        )}

        {/* "Connecting..." when streaming started but no tokens yet */}
        {isStreaming && !streamingMessage && (
          <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2, ml: 5 }}>
            <Typography
              variant="body2"
              sx={{
                color: 'text.secondary',
                fontStyle: 'italic',
                animation: 'pulse 1.5s ease-in-out infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 0.4 },
                  '50%': { opacity: 1 },
                },
              }}
            >
              Connecting...
            </Typography>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </Box>

      {/* Chat Input */}
      <Box
        sx={{
          px: 2,
          // Asymmetric padding: keep top breathing room (separation from
          // messages), but shrink bottom so the input doesn't appear to
          // float away from the window edge. (Was py: 1.5 — symmetric 12px
          // top/bottom — which left a noticeable gap below the input.)
          pt: 1.5,
          pb: 0.5,
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          backgroundColor: 'background.paper',
          flexShrink: 0,
        }}
      >
        {isRealSessions ? (
          <ChatInput
            value={inputValue}
            onChange={setInputValue}
            onSubmit={handleSubmit}
            disabled={!isConnected || isStreaming || !!pendingInput}
          />
        ) : (
          <ChatInput
            value=""
            onChange={() => {}}
            onSubmit={() => {}}
            disabled={true}
          />
        )}
      </Box>

      {/* Right-side slide panel: Prompt Inspector / Full Response */}
      {/* File Viewer — right-panel drawer for viewing role documents and task outputs */}
      <FileViewer
        open={fileViewerOpen}
        onClose={closeFileViewer}
        fileName={fileName}
        fileContent={fileContent}
        fileError={fileError}
        fileLoading={fileLoading}
        isFolderMode={isFolderMode}
        folderTree={folderTree}
        selectedFilePath={selectedFilePath}
        onFileSelect={selectFileInFolder}
      />

      <PromptViewerDrawer
        open={promptViewer.open}
        onClose={promptViewer.close}
        promptData={promptViewer.promptData}
        fullResponseContent={promptViewer.fullResponseContent}
      />
    </Box>
  );
}
