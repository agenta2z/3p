/**
 * TaskCard — inline chat card for a background async task (create_role, role_setup, etc.).
 *
 * Appears in the conversation stream when a long-running tool is dispatched
 * as a background task. Shows live status and an "Open Task" button to switch
 * to the TaskPanel streaming view.
 *
 * Props:
 *   taskId    - unique task ID (e.g. "task-a3f9")
 *   label     - human-readable task label (role description / request snippet)
 *   status    - 'starting' | 'running' | 'completed' | 'error'
 *   onOpenTask(taskId) - called when user clicks "Open Task"
 */

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useTheme } from '@mui/material/styles';

const STATUS_CONFIG = {
  starting: { label: 'Starting…', color: 'warning', showSpinner: true },
  running:  { label: 'Running',   color: 'info',    showSpinner: true },
  completed:{ label: 'Complete',  color: 'success',  showSpinner: false },
  error:    { label: 'Error',     color: 'error',   showSpinner: false },
};

export function TaskCard({ taskId, label, status, onOpenTask }) {
  const theme = useTheme();
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.starting;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1.25,
        borderRadius: 2,
        border: '1px solid',
        borderColor: theme.custom?.surfaces?.cardBorder || 'rgba(255,255,255,0.1)',
        backgroundColor: theme.custom?.surfaces?.overlayLight || 'rgba(255,255,255,0.03)',
        maxWidth: '80%',
      }}
    >
      {/* Status icon / spinner */}
      <Box sx={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
        {cfg.showSpinner ? (
          <CircularProgress size={16} color={cfg.color} />
        ) : status === 'completed' ? (
          <CheckCircleIcon sx={{ fontSize: 18, color: 'success.main' }} />
        ) : (
          <ErrorIcon sx={{ fontSize: 18, color: 'error.main' }} />
        )}
      </Box>

      {/* Label */}
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{ fontWeight: 500, color: 'text.primary', mb: 0.25,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {label || taskId}
        </Typography>
        <Chip
          label={cfg.label}
          color={cfg.color}
          size="small"
          variant="outlined"
          sx={{ height: 18, fontSize: '0.7rem' }}
        />
      </Box>

      {/* Open Task button */}
      <Button
        size="small"
        variant="outlined"
        endIcon={<OpenInNewIcon sx={{ fontSize: 14 }} />}
        onClick={() => onOpenTask && onOpenTask(taskId)}
        sx={{
          flexShrink: 0,
          fontSize: '0.75rem',
          py: 0.25,
          px: 1,
          textTransform: 'none',
          borderColor: 'rgba(255,255,255,0.2)',
          color: 'text.secondary',
          '&:hover': { borderColor: 'primary.main', color: 'primary.main' },
        }}
      >
        Open Task
      </Button>
    </Box>
  );
}

export default TaskCard;
