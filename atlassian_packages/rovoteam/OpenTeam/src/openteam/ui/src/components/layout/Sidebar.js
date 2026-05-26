/**
 * Sidebar — left navigation panel for "Manager Sessions".
 */

import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/Add';
import SettingsIcon from '@mui/icons-material/Settings';
import BugReportIcon from '@mui/icons-material/BugReport';
import ChatIcon from '@mui/icons-material/Chat';
import { useTheme } from '@mui/material/styles';
import { useApiData } from '../../hooks/useApiData';
import { postJson } from '../../utils/api';
import SettingsDrawer from './SettingsDrawer';

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
    if (!buckets.has(key)) buckets.set(key, { agent, sessions: [] });
    buckets.get(key).sessions.push(session);
  }
  const groups = Array.from(buckets.values());
  for (const g of groups) g.sessions.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
  groups.sort((a, b) => (a.agent.name || '').localeCompare(b.agent.name || '', undefined, { sensitivity: 'base' }));
  return groups;
}

function SessionItem({ session, isActive, onClick }) {
  const theme = useTheme();
  return (
    <Box
      onClick={() => onClick?.(session.id)}
      sx={{
        px: 2, py: 1.5, cursor: 'pointer', borderRadius: 1, mx: 1, mb: 0.5,
        transition: 'background-color 0.15s',
        backgroundColor: isActive ? theme.custom.surfaces.activeHighlight : 'transparent',
        borderLeft: isActive ? `3px solid ${theme.palette.primary.main}` : '3px solid transparent',
        '&:hover': {
          backgroundColor: isActive ? theme.custom.surfaces.activeHighlight : theme.custom.surfaces.hoverBg,
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <ChatIcon sx={{ fontSize: 14, color: isActive ? 'primary.light' : 'text.secondary', flexShrink: 0 }} />
        <Typography variant="body2" sx={{ fontWeight: isActive ? 600 : 500, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: isActive ? 'primary.light' : 'text.primary' }}>
          {session.title}
        </Typography>
      </Box>
      <Typography variant="caption" sx={{
        color: 'text.disabled', pl: 2.75,
        fontSize: '0.6rem', fontFamily: 'monospace',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        display: 'block',
      }}>
        {session.id}
      </Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary', pl: 2.75 }}>
        {relativeTime(session.updated_at)} · {session.message_count} msgs
      </Typography>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  TaskSubtab — indented task entry under a session                   */
/* ------------------------------------------------------------------ */

const TASK_STATUS_CFG = {
  starting:  { label: 'Starting…', color: 'warning' },
  running:   { label: 'Running',   color: 'info' },
  completed: { label: 'Complete',  color: 'success' },
  error:     { label: 'Error',     color: 'error' },
};

function TaskSubtab({ task, isActive, onClick }) {
  const theme = useTheme();
  const cfg = TASK_STATUS_CFG[task.status] || TASK_STATUS_CFG.running;
  return (
    <Box
      onClick={onClick}
      sx={{
        pl: 4.5, pr: 1.5, py: 0.75, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 0.75, mx: 1, mb: 0.25,
        borderRadius: 1,
        backgroundColor: isActive ? theme.custom.surfaces.activeHighlight : 'transparent',
        borderLeft: isActive ? `3px solid ${theme.palette.primary.light}` : '3px solid transparent',
        '&:hover': { backgroundColor: isActive ? theme.custom.surfaces.activeHighlight : theme.custom.surfaces.hoverBg },
      }}
    >
      <Typography
        variant="body2"
        sx={{
          fontSize: '0.75rem', flex: 1, lineHeight: 1.3,
          color: isActive ? 'primary.light' : 'text.secondary',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}
      >
        {(task.label || task.toolName || task.id).slice(0, 28)}
      </Typography>
      <Chip
        label={cfg.label}
        size="small"
        color={cfg.color}
        variant="outlined"
        sx={{ height: 16, fontSize: '0.6rem', flexShrink: 0, '& .MuiChip-label': { px: 0.75 } }}
      />
    </Box>
  );
}

export default function Sidebar({ onSessionClick, activeSessionId, tasks, activeTaskId, onTaskClick }) {
  const theme = useTheme();
  const { data: sessions, loading, refetch } = useApiData('/sessions');
  const groupedSessions = useMemo(() => buildGroupedSessions(sessions), [sessions]);
  const [creating, setCreating] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleNewSession = async () => {
    setCreating(true);
    try {
      const newSession = await postJson('/sessions', {});
      onSessionClick?.(newSession.id);  // navigate immediately (responsive UX)
      refetch();                         // sidebar catches up asynchronously
    } catch (err) {
      console.error('Failed to create session:', err);
      // Graceful: in mock mode POST returns 400, button stays but nothing happens
    } finally {
      setCreating(false);
    }
  };

  return (
    <Box
      sx={{
        width: 250, minWidth: 250, height: '100%', display: 'flex', flexDirection: 'column',
        backgroundColor: theme.custom.surfaces.sidebarBg,
        borderRight: '1px solid', borderColor: 'divider',
      }}
    >
      <Box sx={{ px: 2, py: 2 }}>
        <Typography variant="body2" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.8, color: 'text.secondary', fontSize: '0.7rem' }}>
          Manager Sessions
        </Typography>
      </Box>

      <Divider />

      <Box sx={{ flexGrow: 1, overflowY: 'auto', py: 1 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={20} sx={{ color: 'text.secondary' }} />
          </Box>
        ) : groupedSessions.length > 0 ? (
          groupedSessions.map((group) => (
            <Box key={primaryAgentGroupKey(group.agent)} sx={{ mb: 1 }}>
              <Typography variant="caption" sx={{ display: 'block', px: 2, py: 0.75, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.6, color: 'text.secondary', fontSize: '0.65rem' }}>
                {group.agent.name || 'Conversation'}
              </Typography>
              {group.sessions.map((session) => {
                const isActiveSession = session.id === activeSessionId;
                const sessionTaskList = isActiveSession ? Object.values(tasks || {}) : [];
                return (
                  <React.Fragment key={session.id}>
                    <SessionItem
                      session={session}
                      isActive={isActiveSession && !activeTaskId}
                      onClick={onSessionClick}
                    />
                    {/* Task subtabs — indented under active session */}
                    {sessionTaskList.map(task => (
                      <TaskSubtab
                        key={task.id}
                        task={task}
                        isActive={activeTaskId === task.id}
                        onClick={() => onTaskClick?.(task.id)}
                      />
                    ))}
                  </React.Fragment>
                );
              })}
            </Box>
          ))
        ) : (
          <Typography variant="caption" sx={{ color: 'text.secondary', px: 2, py: 2, display: 'block' }}>No sessions yet</Typography>
        )}
      </Box>

      <Box sx={{ px: 2, py: 1.5 }}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={creating ? <CircularProgress size={14} sx={{ color: 'text.secondary' }} /> : <AddIcon />}
          onClick={handleNewSession}
          disabled={creating}
          sx={{
            textTransform: 'none',
            borderColor: theme.custom.surfaces.inputBorder,
            color: 'text.secondary',
            fontSize: '0.8rem',
            '&:hover': {
              borderColor: 'primary.main',
              color: 'primary.light',
              backgroundColor: theme.custom.surfaces.highlightSubtle,
            },
          }}
        >
          {creating ? 'Creating...' : 'New Session'}
        </Button>
      </Box>

      <Divider />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 2, py: 1.5 }}>
        <IconButton size="small" sx={{ color: 'text.secondary' }} title="Settings" onClick={() => setSettingsOpen(true)}>
          <SettingsIcon sx={{ fontSize: 18 }} />
        </IconButton>
        <Typography variant="caption" sx={{ color: 'text.secondary', cursor: 'pointer', '&:hover': { color: 'text.primary' } }} onClick={() => setSettingsOpen(true)}>
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

      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </Box>
  );
}
