import React, { useState, useRef, useEffect, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SendIcon from '@mui/icons-material/Send';
import { useTheme, alpha } from '@mui/material/styles';

const CANNED_RESPONSES = [
  "Got it. I'll take a look and follow up shortly.",
  "Thanks for the context — adjusting my approach now.",
  "Acknowledged. I'll prioritize this in my current cycle.",
  "Understood. Let me check the latest data and get back to you.",
  "Good point. I'll incorporate that into my next iteration.",
];

function isAiEmployee(employeeId, allEmployees) {
  if (!allEmployees || !employeeId) return false;
  const emp = allEmployees.find((e) => e.id === employeeId);
  return emp ? emp.type === 'ai' || emp.type === 'agent' : false;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function renderContent(content, mentions) {
  if (!content) return null;

  // Split on code blocks (triple backticks)
  const parts = content.split(/(```[\s\S]*?```)/g);

  return parts.map((part, i) => {
    if (part.startsWith('```') && part.endsWith('```')) {
      const code = part.slice(3, -3).replace(/^\w*\n/, '');
      return (
        <Box
          key={i}
          component="pre"
          sx={{
            backgroundColor: 'rgba(0,0,0,0.6)',
            color: '#e0e0e0',
            fontFamily: 'monospace',
            fontSize: '0.7rem',
            p: 0.75,
            borderRadius: 0.75,
            my: 0.5,
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {code}
        </Box>
      );
    }

    // Handle @mentions within text
    if (mentions && mentions.length > 0) {
      const mentionPattern = /@(\w[\w\s]*?\w|\w)/g;
      const segments = [];
      let lastIdx = 0;
      let match;

      while ((match = mentionPattern.exec(part)) !== null) {
        if (match.index > lastIdx) {
          segments.push({ text: part.slice(lastIdx, match.index), isMention: false });
        }
        segments.push({ text: match[0], isMention: true });
        lastIdx = match.index + match[0].length;
      }
      if (lastIdx < part.length) {
        segments.push({ text: part.slice(lastIdx), isMention: false });
      }

      if (segments.length > 0) {
        return (
          <span key={i}>
            {segments.map((seg, j) =>
              seg.isMention ? (
                <Box
                  key={j}
                  component="span"
                  sx={{
                    backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.15),
                    color: 'primary.light',
                    borderRadius: 0.5,
                    px: 0.5,
                    py: 0.1,
                    fontSize: '0.72rem',
                    fontWeight: 600,
                  }}
                >
                  {seg.text}
                </Box>
              ) : (
                <span key={j}>{seg.text}</span>
              )
            )}
          </span>
        );
      }
    }

    return <span key={i}>{part}</span>;
  });
}

export default function ConversationThread({
  messages = [],
  allEmployees = [],
  currentEmployeeId,
  showReplyInput = false,
  onSendMessage,
}) {
  const theme = useTheme();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const responseIdx = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    setInput('');

    if (onSendMessage) {
      onSendMessage(text);

      // Simulated reply after 1.5s
      setTimeout(() => {
        const reply = CANNED_RESPONSES[responseIdx.current % CANNED_RESPONSES.length];
        responseIdx.current += 1;
        if (onSendMessage) {
          onSendMessage(reply);
        }
      }, 1500);
    }
  }, [input, onSendMessage]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
      {/* Messages area */}
      <Box
        sx={{
          maxHeight: 350,
          overflowY: 'auto',
          px: 1.5,
          py: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
        }}
      >
        {messages.length === 0 && (
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              textAlign: 'center',
              py: 3,
              fontSize: '0.75rem',
            }}
          >
            No messages
          </Typography>
        )}

        {messages.map((msg) => {
          const isCurrentEmployee = msg.sender_id === currentEmployeeId;
          const senderIsAi = isAiEmployee(msg.sender_id, allEmployees);

          return (
            <Box
              key={msg.id}
              sx={{
                display: 'flex',
                justifyContent: isCurrentEmployee ? 'flex-end' : 'flex-start',
                gap: 0.5,
              }}
            >
              {/* Avatar on the left for others */}
              {!isCurrentEmployee && (
                senderIsAi ? (
                  <SmartToyIcon
                    sx={{
                      fontSize: 14,
                      color: 'text.secondary',
                      mt: 1.5,
                      flexShrink: 0,
                    }}
                  />
                ) : (
                  <Avatar
                    sx={{
                      width: 20,
                      height: 20,
                      fontSize: '0.6rem',
                      mt: 1.5,
                      flexShrink: 0,
                      bgcolor: alpha(theme.palette.primary.main, 0.3),
                    }}
                  >
                    {(msg.sender_name || '?')[0].toUpperCase()}
                  </Avatar>
                )
              )}

              <Box sx={{ maxWidth: '80%' }}>
                {/* Sender name + timestamp */}
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    fontSize: '0.6rem',
                    display: 'block',
                    textAlign: isCurrentEmployee ? 'right' : 'left',
                    mb: 0.2,
                    lineHeight: 1.2,
                  }}
                >
                  {msg.sender_name || 'Unknown'}
                  {msg.timestamp && (
                    <Box component="span" sx={{ ml: 0.5, opacity: 0.7 }}>
                      {formatTimestamp(msg.timestamp)}
                    </Box>
                  )}
                </Typography>

                {/* Bubble */}
                <Box
                  sx={{
                    px: 1,
                    py: 0.5,
                    borderRadius: 1.5,
                    backgroundColor: isCurrentEmployee
                      ? alpha(theme.palette.primary.main, 0.2)
                      : 'action.hover',
                  }}
                >
                  <Typography
                    variant="body2"
                    component="div"
                    sx={{ fontSize: '0.75rem', lineHeight: 1.4 }}
                  >
                    {renderContent(msg.content, msg.mentions)}
                  </Typography>
                </Box>
              </Box>

              {/* Avatar on the right for current employee */}
              {isCurrentEmployee && (
                <SmartToyIcon
                  sx={{
                    fontSize: 14,
                    color: 'primary.light',
                    mt: 1.5,
                    flexShrink: 0,
                  }}
                />
              )}
            </Box>
          );
        })}
        <div ref={messagesEndRef} />
      </Box>

      {/* Reply input */}
      {showReplyInput && (
        <Box
          sx={{
            display: 'flex',
            gap: 0.5,
            px: 1.5,
            py: 0.75,
            borderTop: '1px solid',
            borderTopColor: 'divider',
          }}
        >
          <TextField
            size="small"
            fullWidth
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            sx={{
              '& .MuiInputBase-root': {
                fontSize: '0.8rem',
                height: 30,
              },
            }}
          />
          <IconButton
            size="small"
            onClick={handleSend}
            disabled={!input.trim()}
            sx={{ color: 'primary.light' }}
          >
            <SendIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>
      )}
    </Box>
  );
}
