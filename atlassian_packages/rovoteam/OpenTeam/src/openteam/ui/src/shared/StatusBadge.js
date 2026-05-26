/**
 * StatusBadge — colored chip for any status string.
 * Uses theme palette via component-side domain mapping.
 */

import React from 'react';
import Chip from '@mui/material/Chip';
import { useTheme, alpha } from '@mui/material/styles';

const STATUS_PALETTE = {
  'in-progress': 'primary',
  'planning':    'warning',
  'completed':   'success',
  'on-hold':     'neutral',
  'backlog':     'neutral',
  'in-review':   'info',
  'done':        'success',
  'pending':     'secondary',
  'active':      'success',
  'idle':        'neutral',
  'away':        'warning',
  'queued':      'warning',
  'blocked':     'error',
};

const STATUS_LABELS = {
  'in-progress': 'In Progress',
  'planning':    'Planning',
  'completed':   'Completed',
  'on-hold':     'On Hold',
  'backlog':     'Backlog',
  'in-review':   'In Review',
  'done':        'Done',
  'pending':     'Pending',
  'active':      'Active',
  'idle':        'Idle',
  'away':        'Away',
  'queued':      'Queued',
  'blocked':     'Blocked',
};

function getStatusConfig(status, theme) {
  const key = status?.toLowerCase() || '';
  const paletteKey = STATUS_PALETTE[key] || 'neutral';
  const color = theme.palette[paletteKey] || theme.palette.info;
  const label = STATUS_LABELS[key] || status || 'Unknown';
  return { color: color.main, bg: alpha(color.main, 0.15), label };
}

export function StatusBadge({ status, variant = 'filled', size = 'small', onClick }) {
  const theme = useTheme();
  const config = getStatusConfig(status, theme);
  const isPending = status?.toLowerCase() === 'pending';
  const isClickable = isPending && onClick;

  if (variant === 'outlined') {
    return (
      <Chip label={config.label} size={size} variant="outlined" onClick={isClickable ? onClick : undefined} sx={{
        borderColor: config.color, color: config.color,
        ...(isClickable && { cursor: 'pointer', '&:hover': { backgroundColor: alpha(config.color, 0.12) } }),
      }} />
    );
  }

  return (
    <Chip label={config.label} size={size} onClick={isClickable ? onClick : undefined} sx={{
      backgroundColor: config.bg, color: config.color, fontWeight: 500,
      ...(isClickable && { cursor: 'pointer', '&:hover': { backgroundColor: alpha(config.color, 0.2) } }),
    }} />
  );
}

export default StatusBadge;
