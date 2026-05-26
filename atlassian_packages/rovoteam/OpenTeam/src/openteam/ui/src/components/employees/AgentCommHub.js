/**
 * AgentCommHub — communication action buttons for AI agents.
 *
 * Three buttons: Send Message, Send Email, View History.
 * Each opens a Popover dropdown anchored to the button,
 * floating over the UI without affecting card layout.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Tooltip from '@mui/material/Tooltip';
import Popover from '@mui/material/Popover';
import Typography from '@mui/material/Typography';
import ChatIcon from '@mui/icons-material/Chat';
import EmailIcon from '@mui/icons-material/Email';
import HistoryIcon from '@mui/icons-material/History';
import QuickChatBox from './QuickChatBox';
import EmailComposeBox from './EmailComposeBox';

const buttonSx = {
  height: 22,
  fontSize: '0.6rem',
  textTransform: 'none',
  borderRadius: 3,
  px: 0.75,
  minWidth: 0,
  gap: 0.4,
};

export default function AgentCommHub({ agentName, agentId, onFormalizeChat, hideHistory = false }) {
  const [chatAnchor, setChatAnchor] = useState(null);
  const [emailAnchor, setEmailAnchor] = useState(null);
  const [historyAnchor, setHistoryAnchor] = useState(null);

  const handleFormalize = (messages) => {
    setChatAnchor(null);
    if (onFormalizeChat) onFormalizeChat(messages);
  };

  return (
    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
      {/* Send Message */}
      <Tooltip title="Send message to agent, get instant response" arrow placement="top">
        <Button
          size="small"
          startIcon={<ChatIcon sx={{ fontSize: '12px !important' }} />}
          onClick={(e) => setChatAnchor(chatAnchor ? null : e.currentTarget)}
          sx={{
            ...buttonSx,
            color: chatAnchor ? 'primary.light' : 'text.secondary',
            backgroundColor: chatAnchor ? 'action.hover' : 'transparent',
            '&:hover': { backgroundColor: 'action.selected' },
          }}
        >
          Send Message
        </Button>
      </Tooltip>

      {/* Send Email */}
      <Tooltip title="Agent responds within one workday based on urgency" arrow placement="top">
        <Button
          size="small"
          startIcon={<EmailIcon sx={{ fontSize: '12px !important' }} />}
          onClick={(e) => setEmailAnchor(emailAnchor ? null : e.currentTarget)}
          sx={{
            ...buttonSx,
            color: emailAnchor ? 'primary.light' : 'text.secondary',
            backgroundColor: emailAnchor ? 'action.hover' : 'transparent',
            '&:hover': { backgroundColor: 'action.selected' },
          }}
        >
          Send Email
        </Button>
      </Tooltip>

      {/* View History — hidden when rendered separately in EmployeeCard */}
      {!hideHistory && (
        <Tooltip title="View past conversations with this agent" arrow placement="top">
          <Button
            size="small"
            startIcon={<HistoryIcon sx={{ fontSize: '12px !important' }} />}
            onClick={(e) => setHistoryAnchor(historyAnchor ? null : e.currentTarget)}
            sx={{
              ...buttonSx,
              color: historyAnchor ? 'primary.light' : 'text.secondary',
              backgroundColor: historyAnchor ? 'action.hover' : 'transparent',
              '&:hover': { backgroundColor: 'action.selected' },
            }}
          >
            View History
          </Button>
        </Tooltip>
      )}

      {/* Chat Popover */}
      <Popover
        open={Boolean(chatAnchor)}
        anchorEl={chatAnchor}
        onClose={() => setChatAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        PaperProps={{
          sx: {
            width: 380,
            backgroundColor: 'background.paper',
            border: '1px solid', borderColor: 'divider',
            borderRadius: 2,
            overflow: 'hidden',
          },
        }}
      >
        <QuickChatBox
          agentName={agentName}
          onClose={() => setChatAnchor(null)}
          onFormalize={handleFormalize}
        />
      </Popover>

      {/* Email Popover */}
      <Popover
        open={Boolean(emailAnchor)}
        anchorEl={emailAnchor}
        onClose={() => setEmailAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        PaperProps={{
          sx: {
            width: 380,
            backgroundColor: 'background.paper',
            border: '1px solid', borderColor: 'divider',
            borderRadius: 2,
            overflow: 'hidden',
          },
        }}
      >
        <EmailComposeBox
          agentName={agentName}
          onClose={() => setEmailAnchor(null)}
          onSend={(data) => {
            console.log('Email sent to', agentName, data);
          }}
        />
      </Popover>

      {/* History Popover */}
      <Popover
        open={Boolean(historyAnchor)}
        anchorEl={historyAnchor}
        onClose={() => setHistoryAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        PaperProps={{
          sx: {
            width: 320,
            backgroundColor: 'background.paper',
            border: '1px solid', borderColor: 'divider',
            borderRadius: 2,
            p: 2.5,
          },
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
          Conversation History — {agentName}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Conversation history coming soon...
        </Typography>
      </Popover>
    </Box>
  );
}
