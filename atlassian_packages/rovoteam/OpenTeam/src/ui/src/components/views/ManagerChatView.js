/**
 * ManagerChatView — shows a manager-AI conversation thread.
 *
 * Displays the selected Manager Session as a chat interface with
 * manager messages (right-aligned, blue) and AI agent responses
 * (left-aligned, dark background with agent name).
 */

import React, { useEffect, useRef } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import IconButton from '@mui/material/IconButton';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import { useApiData } from '../../hooks/useApiData';
import { LoadingIndicator } from '../../shared';
import ChatWidgetRenderer from '../chat-widgets/ChatWidgetRenderer';

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
            whiteSpace: 'pre-wrap',
            lineHeight: 1.5,
            fontSize: '0.9rem',
          }}
        >
          {message.content}
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

function AgentMessage({ message }) {
  const agentName = message.agent_name || 'AI Assistant';

  // Markdown-like rendering: bold, bullets, tables, headers
  const renderContent = (content) => {
    const lines = content.split('\n');
    const elements = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Detect table block: consecutive lines starting with |
      if (line.trim().startsWith('|')) {
        const tableLines = [];
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          tableLines.push(lines[i]);
          i++;
        }
        elements.push(renderTable(tableLines, elements.length));
        continue;
      }

      const boldParsed = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

      // Section headers (### or **)
      if (line.match(/^#{1,3}\s/)) {
        const text = line.replace(/^#{1,3}\s/, '');
        const parsed = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        elements.push(
          <Box key={i} sx={{ py: 0.3, mt: 0.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.primary' }} dangerouslySetInnerHTML={{ __html: parsed }} />
          </Box>
        );
        i++;
        continue;
      }

      // Bullet points
      if (line.match(/^[\s]*[•\-\*]\s/)) {
        const indent = line.match(/^(\s*)/)[1].length;
        elements.push(
          <Box key={i} sx={{ pl: indent / 2 + 1, py: 0.15 }} dangerouslySetInnerHTML={{ __html: boldParsed }} />
        );
        i++;
        continue;
      }

      // Empty line
      if (line.trim() === '') {
        elements.push(<Box key={i} sx={{ height: 8 }} />);
        i++;
        continue;
      }

      // Regular text
      elements.push(<Box key={i} sx={{ py: 0.15 }} dangerouslySetInnerHTML={{ __html: boldParsed }} />);
      i++;
    }

    return elements;
  };

  // Render markdown table as styled HTML table
  const renderTable = (tableLines, keyBase) => {
    // Parse header row
    const parseRow = (line) =>
      line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim());

    // Skip separator rows like |---|---|---| or | --- | --- |
    const isSeparator = (l) => {
      const inner = l.replace(/^\|/, '').replace(/\|$/, '');
      return inner.split('|').every(cell => cell.trim().match(/^[-:]+$/));
    };
    const rows = tableLines.filter(l => !isSeparator(l));
    if (rows.length === 0) return null;

    const headerCells = parseRow(rows[0]);
    const bodyRows = rows.slice(1).map(parseRow);

    return (
      <Box key={`table-${keyBase}`} sx={{ overflowX: 'auto', my: 1 }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.82rem',
          lineHeight: 1.4,
        }}>
          <thead>
            <tr>
              {headerCells.map((cell, ci) => (
                <th key={ci} style={{
                  textAlign: 'left',
                  padding: '6px 10px',
                  borderBottom: '1px solid rgba(255,255,255,0.15)',
                  color: '#a0a0a0',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }} dangerouslySetInnerHTML={{ __html: cell.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#e0e0e0">$1</strong>') }} />
              ))}
            </tr>
          </thead>
          <tbody>
            {bodyRows.map((row, ri) => (
              <tr key={ri} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                {row.map((cell, ci) => (
                  <td key={ci} style={{
                    padding: '5px 10px',
                    color: '#e0e0e0',
                  }} dangerouslySetInnerHTML={{ __html: cell.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
      <Avatar sx={{ mr: 1, width: 32, height: 32, bgcolor: '#4a90d9', flexShrink: 0 }}>
        <SmartToyIcon sx={{ fontSize: 18 }} />
      </Avatar>
      <Box sx={{ maxWidth: '75%', display: 'flex', flexDirection: 'column' }}>
        <Typography variant="caption" sx={{ fontWeight: 600, color: '#4a90d9', mb: 0.5 }}>
          {agentName}
        </Typography>
        <Box
          sx={{
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            px: 2,
            py: 1.5,
            borderRadius: '4px 16px 16px 16px',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.6,
            fontSize: '0.9rem',
            color: 'text.primary',
          }}
        >
          {renderContent(message.content)}
          {message.widgets?.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              <ChatWidgetRenderer widgets={message.widgets} />
            </Box>
          )}
        </Box>
        <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.5, ml: 0.5 }}>
          {formatTime(message.timestamp)}
        </Typography>
      </Box>
    </Box>
  );
}

export default function ManagerChatView({ sessionId, onBack }) {
  const { data: session, loading, error } = useApiData(
    sessionId ? `/sessions/${sessionId}` : null
  );
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session]);

  if (loading) return <LoadingIndicator />;
  if (error) {
    return (
      <Box>
        <IconButton onClick={onBack} sx={{ color: 'text.secondary', mb: 1 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography color="error">Failed to load session: {error.message}</Typography>
      </Box>
    );
  }
  if (!session) return null;

  const messages = session.messages || [];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', mx: -3, mt: -3, mb: -3 }}>
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
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
            {session.title}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            {messages.length} messages
          </Typography>
        </Box>
      </Box>

      {/* Messages */}
      <Box sx={{ flexGrow: 1, overflow: 'auto', px: 3, py: 2 }}>
        {messages.map((msg) => {
          if (msg.role === 'manager') {
            return <ManagerMessage key={msg.id} message={msg} />;
          }
          return <AgentMessage key={msg.id} message={msg} />;
        })}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input (disabled placeholder) */}
      <Box
        sx={{
          px: 2,
          py: 1.5,
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
          backgroundColor: 'background.paper',
          flexShrink: 0,
        }}
      >
        <TextField
          fullWidth
          placeholder="Type a message to your AI team... (demo mode)"
          disabled
          size="small"
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton disabled size="small">
                  <SendIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: 3,
              backgroundColor: 'rgba(255, 255, 255, 0.03)',
            },
          }}
        />
      </Box>
    </Box>
  );
}
