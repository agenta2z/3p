/**
 * Sidebar — left navigation panel for "Manager Sessions".
 *
 * Fetches sessions from /api/sessions, groups them by primary_agent, and displays
 * section headers with a clickable list under each agent.
 * Highlights the currently active session.
 *
 * Props:
 *   onSessionClick   - callback(sessionId)
 *   activeSessionId  - currently selected session ID (for highlighting)
 */

import React, { useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/Add';
import SettingsIcon from '@mui/icons-material/Settings';
import BugReportIcon from '@mui/icons-material/BugReport';
import ChatIcon from '@mui/icons-material/Chat';
import { useApiData } from '../../hooks/useApiData';

/* ------------------------------------------------------------------ */
/*  Relative time helper                                                */
/* ------------------------------------------------------------------ */

function relativeTime(isoString) {
  if (!isoString) return '';
  const now = new Date();
  const then = new Date(isoString);
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays === 1) return 'Yesterday';
  return `${diffDays}d ago`;
}

/* ------------------------------------------------------------------ */
/*  Group sessions by primary agent                                    */
/* ------------------------------------------------------------------ */

function primaryAgentGroupKey(agent) {
  if (!agent || agent.id == null || agent.id === '') return '_unassigned';
  return String(agent.id);
}

function buildGroupedSessions(sessions) {
  if (!sessions?.length) return [];
  const buckets = new Map();
  for (const session of sessions) {
    const agent = session.primary_agent || { id: null, name: 'New conversation' };
    const key = primaryAgentGroupKey(agent);
    if (!buckets.has(key)) {
      buckets.set(key, { agent, sessions: [] });
    }
    buckets.get(key).sessions.push(session);
  }
  const groups = Array.from(buckets.values());
  for (const g of groups) {
    g.sessions.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
  }
  groups.sort((a, b) =>
    (a.agent.name || '').localeCompare(b.agent.name || '', undefined, { sensitivity: 'base' })
  );
  return groups;
}

/* ------------------------------------------------------------------ */
/*  Session item                                                       */
/* ------------------------------------------------------------------ */

function SessionItem({ session, isActive, onClick }) {
  return (
    <Box
      onClick={() => onClick?.(session.id)}
      sx={{
        px: 2,
        py: 1.5,
        cursor: 'pointer',
        borderRadius: 1,
        mx: 1,
        mb: 0.5,
        transition: 'background-color 0.15s',
        backgroundColor: isActive ? 'rgba(74, 144, 217, 0.15)' : 'transparent',
        borderLeft: isActive ? '3px solid #4a90d9' : '3px solid transparent',
        '&:hover': {
          backgroundColor: isActive ? 'rgba(74, 144, 217, 0.15)' : 'rgba(255, 255, 255, 0.06)',
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <ChatIcon sx={{ fontSize: 14, color: isActive ? 'primary.light' : 'text.secondary', flexShrink: 0 }} />
        <Typography
          variant="body2"
          sx={{
            fontWeight: isActive ? 600 : 500,
            lineHeight: 1.3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: isActive ? 'primary.light' : 'text.primary',
          }}
        >
          {session.title}
        </Typography>
      </Box>
      <Typography variant="caption" sx={{ color: 'text.secondary', pl: 2.75 }}>
        {relativeTime(session.updated_at)} · {session.message_count} msgs
      </Typography>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Sidebar                                                            */
/* ------------------------------------------------------------------ */

export default function Sidebar({ onSessionClick, activeSessionId }) {
  const { data: sessions, loading } = useApiData('/sessions');
  const groupedSessions = useMemo(() => buildGroupedSessions(sessions), [sessions]);

  return (
    <Box
      sx={{
        width: 250,
        minWidth: 250,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'rgba(0, 0, 0, 0.25)',
        borderRight: '1px solid rgba(255, 255, 255, 0.06)',
      }}
    >
      {/* Header */}
      <Box sx={{ px: 2, py: 2 }}>
        <Typography
          variant="body2"
          sx={{
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: 0.8,
            color: 'text.secondary',
            fontSize: '0.7rem',
          }}
        >
          Manager Sessions
        </Typography>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.06)' }} />

      {/* Session list */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', py: 1 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={20} sx={{ color: 'text.secondary' }} />
          </Box>
        ) : groupedSessions.length > 0 ? (
          groupedSessions.map((group) => (
            <Box key={primaryAgentGroupKey(group.agent)} sx={{ mb: 1 }}>
              <Typography
                variant="caption"
                sx={{
                  display: 'block',
                  px: 2,
                  py: 0.75,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.6,
                  color: 'text.secondary',
                  fontSize: '0.65rem',
                }}
              >
                {group.agent.name || 'Conversation'}
              </Typography>
              {group.sessions.map((session) => (
                <SessionItem
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  onClick={onSessionClick}
                />
              ))}
            </Box>
          ))
        ) : (
          <Typography variant="caption" sx={{ color: 'text.secondary', px: 2, py: 2, display: 'block' }}>
            No sessions yet
          </Typography>
        )}
      </Box>

      {/* New Session button */}
      <Box sx={{ px: 2, py: 1.5 }}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<AddIcon />}
          sx={{
            textTransform: 'none',
            borderColor: 'rgba(255, 255, 255, 0.15)',
            color: 'text.secondary',
            fontSize: '0.8rem',
            '&:hover': {
              borderColor: 'primary.main',
              color: 'primary.light',
              backgroundColor: 'rgba(74, 144, 217, 0.08)',
            },
          }}
        >
          New Session
        </Button>
      </Box>

      <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.06)' }} />

      {/* Footer links */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 2, py: 1.5 }}>
        <IconButton size="small" sx={{ color: 'text.secondary' }} title="Settings">
          <SettingsIcon sx={{ fontSize: 18 }} />
        </IconButton>
        <Typography variant="caption" sx={{ color: 'text.secondary', cursor: 'pointer', '&:hover': { color: 'text.primary' } }}>
          Settings
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <IconButton size="small" sx={{ color: 'text.secondary' }} title="Debug Mode">
          <BugReportIcon sx={{ fontSize: 18 }} />
        </IconButton>
        <Typography variant="caption" sx={{ color: 'text.secondary', cursor: 'pointer', '&:hover': { color: 'text.primary' } }}>
          Debug
        </Typography>
      </Box>
    </Box>
  );
}
