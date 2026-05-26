/**
 * SprintBoardView — Kanban sprint board drill-down for a single project.
 *
 * Shows four columns (Backlog, In Progress, In Review, Done) with compact
 * task cards, a project header with back navigation, and a sprint summary bar.
 *
 * Props:
 *   projectId - string (project to display)
 *   onBack    - callback to return to the previous view
 */

import React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import FlagIcon from '@mui/icons-material/Flag';
import { useApiData } from '../../hooks/useApiData';
import { StatusBadge, ProgressBar, PersonChip, LoadingIndicator, EmptyState } from '../../shared';

/* ------------------------------------------------------------------ */
/*  Priority dot color helper                                          */
/* ------------------------------------------------------------------ */

const PRIORITY_COLORS = {
  critical: '#f44336',
  high: '#ff9800',
  medium: '#4a90d9',
  low: '#90a4ae',
};

function PriorityDot({ priority }) {
  const color = PRIORITY_COLORS[priority?.toLowerCase()] || PRIORITY_COLORS.medium;
  return (
    <Box
      sx={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        flexShrink: 0,
      }}
      title={priority}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Compact task card for the sprint board                             */
/* ------------------------------------------------------------------ */

function TaskCard({ task }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 1.5,
        backgroundColor: 'rgba(255, 255, 255, 0.04)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        borderRadius: 1.5,
        '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.06)' },
        transition: 'background-color 0.15s',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 0.75 }}>
        <PriorityDot priority={task.priority} />
        <Typography variant="body2" sx={{ fontWeight: 500, lineHeight: 1.3, flexGrow: 1 }}>
          {task.title || task.name || 'Untitled Task'}
        </Typography>
      </Box>

      {task.progress != null && (
        <Box sx={{ mb: 0.75 }}>
          <ProgressBar percent={task.progress} height={4} showLabel={false} />
        </Box>
      )}

      {task.assignees?.length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
          {task.assignees.map((a, idx) => (
            <PersonChip
              key={a.id || idx}
              name={a.name || a}
              type={a.type}
              size="small"
            />
          ))}
        </Box>
      )}
    </Paper>
  );
}

/* ------------------------------------------------------------------ */
/*  Kanban column                                                      */
/* ------------------------------------------------------------------ */

const COLUMN_DEFS = [
  { key: 'backlog', label: 'Backlog', color: '#90a4ae' },
  { key: 'in-progress', label: 'In Progress', color: '#4a90d9' },
  { key: 'in-review', label: 'In Review', color: '#ce93d8' },
  { key: 'done', label: 'Done', color: '#4caf50' },
];

function KanbanColumn({ label, color, tasks }) {
  return (
    <Paper
      elevation={0}
      sx={{
        flex: 1,
        minWidth: 220,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      {/* Column header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 2,
          py: 1.25,
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: color }} />
        <Typography variant="body2" sx={{ fontWeight: 600, flexGrow: 1 }}>
          {label}
        </Typography>
        <Chip label={tasks.length} size="small" sx={{ height: 20, fontSize: '0.7rem', backgroundColor: 'rgba(255,255,255,0.08)' }} />
      </Box>

      {/* Task cards */}
      <Box sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 1, flexGrow: 1, overflowY: 'auto' }}>
        {tasks.length === 0 ? (
          <Typography variant="caption" sx={{ color: 'text.secondary', textAlign: 'center', py: 3 }}>
            No tasks
          </Typography>
        ) : (
          tasks.map((task, idx) => <TaskCard key={task.id || idx} task={task} />)
        )}
      </Box>
    </Paper>
  );
}

/* ------------------------------------------------------------------ */
/*  SprintBoardView                                                    */
/* ------------------------------------------------------------------ */

export default function SprintBoardView({ projectId, onBack }) {
  const { data: sprint, loading, error } = useApiData(
    projectId ? `/projects/${projectId}/sprint` : null
  );

  if (loading) return <LoadingIndicator text="Loading sprint board..." />;

  if (error) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <Typography color="error">
          Failed to load sprint: {error.message}
        </Typography>
      </Box>
    );
  }

  if (!sprint) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <EmptyState message="No active sprint found for this project" />
      </Box>
    );
  }

  // Bucket tasks into columns
  const buckets = { backlog: [], 'in-progress': [], 'in-review': [], done: [] };
  (sprint.tasks || []).forEach((task) => {
    const status = (task.status || 'backlog').toLowerCase();
    if (buckets[status]) {
      buckets[status].push(task);
    } else {
      buckets.backlog.push(task);
    }
  });

  const totalTasks = sprint.tasks?.length || 0;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {sprint.project_name || sprint.name || `Project ${projectId}`}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
            <FlagIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Sprint {sprint.sprint_number || sprint.id || ''}
            </Typography>
            {sprint.status && <StatusBadge status={sprint.status} size="small" />}
            {sprint.deadline && (
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Due: {sprint.deadline}
              </Typography>
            )}
          </Box>
        </Box>
      </Box>

      {/* Kanban columns */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, overflowX: 'auto', minHeight: 400 }}>
        {COLUMN_DEFS.map((col) => (
          <KanbanColumn
            key={col.key}
            label={col.label}
            color={col.color}
            tasks={buckets[col.key]}
          />
        ))}
      </Box>

      {/* Sprint summary bar */}
      <Divider sx={{ mb: 2 }} />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 3,
          px: 2,
          py: 1.5,
          borderRadius: 2,
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        <Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Total</Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{totalTasks}</Typography>
        </Box>
        {COLUMN_DEFS.map((col) => (
          <Box key={col.key}>
            <Typography variant="caption" sx={{ color: col.color, display: 'block' }}>{col.label}</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{buckets[col.key].length}</Typography>
          </Box>
        ))}
        {sprint.velocity != null && (
          <Box sx={{ ml: 'auto' }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Velocity</Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>{sprint.velocity} pts</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
