/**
 * ConversationView — AI-to-AI or AI-to-Human conversation thread drill-down.
 *
 * Displays message thread with sender avatars, timestamps, code blocks,
 * and conversation metadata.
 *
 * Props:
 *   conversationId - string
 *   onBack         - callback to return to previous view
 */

import React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Avatar from '@mui/material/Avatar';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import LinkIcon from '@mui/icons-material/Link';
import { useApiData } from '../../hooks/useApiData';
import { LoadingIndicator, EmptyState } from '../../shared';

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const AVATAR_COLORS = ['#4a90d9', '#7c4dff', '#00bcd4', '#ff7043', '#4caf50', '#e91e63'];

function getSenderColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || '').length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

/**
 * Render message content with simple code block support.
 * Lines wrapped in triple backticks get rendered in <pre> blocks.
 */
function MessageContent({ content }) {
  if (!content) return null;

  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <Box sx={{ '& pre': { my: 1 } }}>
      {parts.map((part, idx) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const code = part.slice(3, -3).replace(/^\w*\n/, ''); // strip optional language hint
          return (
            <Box
              key={idx}
              component="pre"
              sx={{
                p: 1.5,
                borderRadius: 1,
                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                overflow: 'auto',
                fontSize: '0.8rem',
                fontFamily: '"Fira Code", "Consolas", monospace',
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {code}
            </Box>
          );
        }
        return (
          <Typography key={idx} variant="body2" sx={{ lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {part}
          </Typography>
        );
      })}
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Message bubble                                                     */
/* ------------------------------------------------------------------ */

function MessageBubble({ message }) {
  const isAI = message.sender_type === 'ai';
  const senderColor = getSenderColor(message.sender_name || message.sender);

  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, py: 1.5 }}>
      <Avatar
        src={message.avatar_url}
        sx={{
          width: 32,
          height: 32,
          bgcolor: senderColor,
          fontSize: 14,
          flexShrink: 0,
          mt: 0.25,
        }}
      >
        {isAI ? <SmartToyIcon sx={{ fontSize: 18 }} /> : (message.sender_name || message.sender || '?').charAt(0).toUpperCase()}
      </Avatar>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 0.5 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {message.sender_name || message.sender}
          </Typography>
          {message.timestamp && (
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {message.timestamp}
            </Typography>
          )}
        </Box>
        <MessageContent content={message.content || message.text || message.body} />
      </Box>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  ConversationView                                                   */
/* ------------------------------------------------------------------ */

export default function ConversationView({ conversationId, onBack }) {
  const { data: conversation, loading, error } = useApiData(
    conversationId ? `/conversations/${conversationId}` : null
  );

  if (loading) return <LoadingIndicator text="Loading conversation..." />;

  if (error) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <Typography color="error">Failed to load conversation: {error.message}</Typography>
      </Box>
    );
  }

  if (!conversation) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <EmptyState message="Conversation not found" />
      </Box>
    );
  }

  const messages = conversation.messages || [];
  const participants = conversation.participants || [];
  const participantNames = participants.map(p => p.name || p).filter(Boolean);

  // Build header title "X <-> Y"
  const headerNames = participantNames.length >= 2
    ? `${participantNames[0]} \u2194 ${participantNames[1]}`
    : participantNames.join(', ') || 'Unknown';

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <ChatBubbleOutlineIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
        <Typography variant="h5" sx={{ fontWeight: 600, flexGrow: 1 }}>
          Conversation: {headerNames}
        </Typography>
      </Box>

      {/* Topic + links */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3, ml: 7.5, flexWrap: 'wrap' }}>
        {conversation.topic && (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Topic: {conversation.topic}
          </Typography>
        )}
        {conversation.project && (
          <Chip
            icon={<LinkIcon sx={{ fontSize: 14 }} />}
            label={`Project: ${conversation.project_name || conversation.project}`}
            size="small"
            variant="outlined"
            sx={{ borderColor: 'rgba(255,255,255,0.15)', color: 'text.secondary' }}
          />
        )}
        {conversation.related_task && (
          <Chip
            icon={<LinkIcon sx={{ fontSize: 14 }} />}
            label={`Task: ${conversation.related_task_name || conversation.related_task}`}
            size="small"
            variant="outlined"
            sx={{ borderColor: 'rgba(255,255,255,0.15)', color: 'text.secondary' }}
          />
        )}
      </Box>

      {/* Message thread */}
      <Paper
        elevation={0}
        sx={{
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 2,
          px: 3,
          py: 1,
          mb: 3,
        }}
      >
        {messages.length === 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', py: 4, textAlign: 'center' }}>
            No messages in this conversation
          </Typography>
        ) : (
          messages.map((msg, idx) => (
            <React.Fragment key={msg.id || idx}>
              <MessageBubble message={msg} />
              {idx < messages.length - 1 && <Divider sx={{ opacity: 0.3 }} />}
            </React.Fragment>
          ))
        )}
      </Paper>

      {/* Metadata footer */}
      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          gap: 4,
          flexWrap: 'wrap',
          p: 2,
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 2,
        }}
      >
        {conversation.started_at && (
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Started</Typography>
            <Typography variant="body2">{conversation.started_at}</Typography>
          </Box>
        )}
        <Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Messages</Typography>
          <Typography variant="body2">{messages.length}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Participants</Typography>
          <Typography variant="body2">{participantNames.join(', ') || 'None'}</Typography>
        </Box>
        {conversation.referenced_people?.length > 0 && (
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Referenced</Typography>
            <Typography variant="body2">
              {conversation.referenced_people.map(p => p.name || p).join(', ')}
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
