/**
 * ProjectTasksSection — grouped task list within a project card.
 *
 * Groups tasks by status:
 * - Active (in-progress, in-review, pending) — always visible with progress bars
 * - Queued (backlog) — show 1 preview + "Show N more" paginated expander
 * - Completed (done) — collapsed by default with count
 */

import React, { useState, useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import Chip from '@mui/material/Chip';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { StatusBadge, ProgressBar, SectionCard } from '../../shared';

const ACTIVE_STATUSES = ['in-progress', 'in_progress', 'in-review', 'in_review', 'pending'];
const QUEUED_STATUSES = ['backlog', 'todo', 'not-started'];
const DONE_STATUSES = ['done', 'completed'];
const QUEUED_PAGE_SIZE = 3;

const PRIORITY_COLORS = {
  critical: '#f44336',
  high: '#ff5722',
  medium: '#ff9800',
  low: '#4caf50',
};

function getAssigneeName(task) {
  // Try resolved assignees first, then fall back to IDs
  if (task.assignees?.length) return task.assignees[0].name;
  if (task.assignee_ids?.length) return task.assignee_ids[0];
  return 'Unassigned';
}

function getAssigneeType(task) {
  if (task.assignees?.length) return task.assignees[0].type;
  return 'ai';
}

function ActiveTaskRow({ task }) {
  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
        <Box sx={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#4a90d9', flexShrink: 0 }} />
        <Typography variant="body2" sx={{ fontWeight: 500, flexGrow: 1, fontSize: '0.82rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {task.title}
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem', flexShrink: 0 }}>
          {getAssigneeType(task) === 'ai' ? '🤖' : '👤'} {getAssigneeName(task)}
        </Typography>
        <StatusBadge status={task.status} size="small" />
      </Box>
      <Box sx={{ pl: 2 }}>
        <ProgressBar percent={task.progress_percent || 0} height={4} showLabel />
      </Box>
    </Box>
  );
}

function QueuedTaskRow({ task }) {
  const priorityColor = PRIORITY_COLORS[task.priority] || '#90a4ae';
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
      <Box sx={{ width: 6, height: 6, borderRadius: '50%', border: '1.5px solid rgba(255,255,255,0.3)', flexShrink: 0 }} />
      <Typography variant="body2" sx={{ flexGrow: 1, fontSize: '0.8rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {task.title}
      </Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', flexShrink: 0 }}>
        {getAssigneeType(task) === 'ai' ? '🤖' : '👤'} {getAssigneeName(task)}
      </Typography>
      <Chip
        label={task.priority}
        size="small"
        sx={{ height: 18, fontSize: '0.55rem', backgroundColor: `${priorityColor}20`, color: priorityColor }}
      />
      {task.estimated_hours && (
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', flexShrink: 0 }}>
          ~{task.estimated_hours}h
        </Typography>
      )}
    </Box>
  );
}

function CompletedTaskRow({ task }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.4 }}>
      <CheckCircleIcon sx={{ fontSize: 14, color: '#4caf50' }} />
      <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.secondary', textDecoration: 'line-through', opacity: 0.7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {task.title}
      </Typography>
    </Box>
  );
}

export default function ProjectTasksSection({ tasks = [] }) {
  const [queuedPage, setQueuedPage] = useState(0); // 0 = show 1 preview, 1+ = expanded pages
  const [showCompleted, setShowCompleted] = useState(false);

  const { active, queued, completed } = useMemo(() => {
    const normalize = (s) => (s || '').toLowerCase().replace(/_/g, '-');
    return {
      active: tasks.filter(t => ACTIVE_STATUSES.includes(normalize(t.status))),
      queued: tasks.filter(t => QUEUED_STATUSES.includes(normalize(t.status))),
      completed: tasks.filter(t => DONE_STATUSES.includes(normalize(t.status))),
    };
  }, [tasks]);

  if (tasks.length === 0) return null;

  // Queued pagination: page 0 shows 1 item, each subsequent page shows QUEUED_PAGE_SIZE more
  const queuedPreviewCount = 1;
  const queuedShown = queuedPage === 0
    ? queued.slice(0, queuedPreviewCount)
    : queued.slice(0, queuedPreviewCount + queuedPage * QUEUED_PAGE_SIZE);
  const queuedRemaining = queued.length - queuedShown.length;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {/* Active Tasks */}
      {active.length > 0 && (
        <SectionCard
          title={`Active Tasks (${active.length})`}
          icon={<Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#4a90d9' }} />}
        >
          {active.map(task => (
            <ActiveTaskRow key={task.id} task={task} />
          ))}
        </SectionCard>
      )}

      {/* Queued Tasks */}
      {queued.length > 0 && (
        <SectionCard
          title={`Queued Tasks (${queued.length})`}
          icon={<Box sx={{ width: 8, height: 8, borderRadius: '50%', border: '1.5px solid rgba(255,255,255,0.4)' }} />}
        >
          {queuedShown.map(task => (
            <QueuedTaskRow key={task.id} task={task} />
          ))}
          {queuedRemaining > 0 && (
            <Button
              size="small"
              startIcon={<ExpandMoreIcon sx={{ fontSize: 14 }} />}
              onClick={() => setQueuedPage(prev => prev + 1)}
              sx={{
                textTransform: 'none',
                color: 'primary.light',
                fontSize: '0.7rem',
                mt: 0.5,
                '&:hover': { backgroundColor: 'rgba(74, 144, 217, 0.08)' },
              }}
            >
              Show {Math.min(queuedRemaining, QUEUED_PAGE_SIZE)} more queued task{queuedRemaining > 1 ? 's' : ''}...
            </Button>
          )}
        </SectionCard>
      )}

      {/* Completed Tasks */}
      {completed.length > 0 && (
        <Box>
          <Button
            size="small"
            startIcon={
              <ExpandMoreIcon
                sx={{
                  fontSize: 14,
                  transform: showCompleted ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s',
                }}
              />
            }
            onClick={() => setShowCompleted(!showCompleted)}
            sx={{
              textTransform: 'none',
              color: 'text.secondary',
              fontSize: '0.7rem',
              '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.04)' },
            }}
          >
            Completed ({completed.length})
          </Button>
          <Collapse in={showCompleted}>
            <Box sx={{ pl: 1, pt: 0.5 }}>
              {completed.map(task => (
                <CompletedTaskRow key={task.id} task={task} />
              ))}
            </Box>
          </Collapse>
        </Box>
      )}
    </Box>
  );
}
