import React from 'react';
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { StatusBadge, ProgressBar } from '../../shared';

const STATUS_BORDER_PALETTE = { active: 'success', queued: 'warning', pending: 'secondary' };

function formatSyncTime(lastSync) {
  if (!lastSync) return null;
  const diff = Date.now() - new Date(lastSync).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return `${hrs}h ago`;
}

export function AgentCard({ agent, currentTask, correspondence }) {
  const theme = useTheme();
  if (!agent) return null;

  const status = agent.status?.toLowerCase() || 'active';
  // borderColor resolved in sx below

  return (
    <Box
      sx={{
        backgroundColor: 'action.hover',
        border: '1px solid', borderColor: 'divider',
        borderLeft: `3px solid ${theme.palette[STATUS_BORDER_PALETTE[status] || 'neutral']?.main || theme.palette.neutral.main}`,
        borderRadius: 2,
        p: 1.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
      }}
    >
      {/* Header: name + role + status badge */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
            {agent.name}
            {agent.role && (
              <Typography
                component="span"
                variant="body2"
                sx={{ color: 'text.secondary', fontWeight: 400, ml: 0.5 }}
              >
                ({agent.role})
              </Typography>
            )}
          </Typography>
        </Box>
        <StatusBadge status={agent.status} size="small" />
      </Box>

      {/* Current task */}
      {currentTask && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Current: {currentTask.title}
          </Typography>
          <ProgressBar
            percent={currentTask.progress_percent ?? 0}
            height={6}
            showLabel
          />
        </Box>
      )}

      {/* Active correspondence */}
      {correspondence && (
        <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
          {'💬'} Active correspondence: {correspondence.topic}
          {correspondence.with_name && ` with ${correspondence.with_name}`}
        </Typography>
      )}

      {/* Last sync */}
      {agent.last_sync && (
        <Typography variant="caption" sx={{ color: 'text.secondary', opacity: 0.7 }}>
          Last sync: {formatSyncTime(agent.last_sync)}
        </Typography>
      )}
    </Box>
  );
}

export default AgentCard;
