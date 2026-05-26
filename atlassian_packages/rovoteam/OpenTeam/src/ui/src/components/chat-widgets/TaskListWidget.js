/**
 * TaskListWidget — compact task list with priority dots and progress.
 *
 * Shows a titled list of tasks, each with a colored priority indicator,
 * status badge, small progress bar, and assignee name.
 *
 * Props:
 *   data.title - string (e.g. "Sprint 4 Priorities")
 *   data.tasks - array of { title, status, priority, percent, assignee }
 */

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { StatusBadge, ProgressBar } from '../../shared';

const WIDGET_BOX_SX = {
  backgroundColor: 'rgba(255, 255, 255, 0.04)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 2,
  p: 2,
  mt: 1.5,
};

const PRIORITY_COLORS = {
  high: '#f44336',
  medium: '#ff9800',
  low: '#4caf50',
};

function PriorityDot({ priority }) {
  const color = PRIORITY_COLORS[priority?.toLowerCase()] || '#90a4ae';
  return (
    <Box
      sx={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        flexShrink: 0,
      }}
    />
  );
}

export default function TaskListWidget({ data }) {
  const { title, tasks = [] } = data || {};

  return (
    <Box sx={WIDGET_BOX_SX}>
      {/* Header */}
      {title && (
        <Typography variant="subtitle2" sx={{ color: 'text.primary', fontWeight: 600, mb: 1.5 }}>
          {title}
        </Typography>
      )}

      {/* Task rows */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
        {tasks.map((task, i) => (
          <Box
            key={i}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              py: 0.5,
              borderTop: i > 0 ? '1px solid rgba(255, 255, 255, 0.05)' : 'none',
            }}
          >
            <PriorityDot priority={task.priority} />
            <Typography
              variant="body2"
              sx={{ color: 'text.primary', flex: '1 1 auto', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {task.title}
            </Typography>
            <Box sx={{ flex: '0 0 auto' }}>
              <StatusBadge status={task.status} size="small" />
            </Box>
            <Box sx={{ flex: '0 0 90px' }}>
              <ProgressBar percent={task.percent || 0} height={4} showLabel />
            </Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', flex: '0 0 80px', textAlign: 'right', whiteSpace: 'nowrap' }}>
              {task.assignee}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
