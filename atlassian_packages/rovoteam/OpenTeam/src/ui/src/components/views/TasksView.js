/**
 * TasksView — main Tasks dashboard view.
 *
 * Fetches tasks, projects, and employees; resolves full task
 * details in parallel; applies client-side filters; and renders
 * summary stats, a filter bar, suggested-actions banner, and
 * a sorted list of TaskCards.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BoltIcon from '@mui/icons-material/Bolt';
import Button from '@mui/material/Button';
import { useApiData } from '../../hooks/useApiData';
import { LoadingIndicator, EmptyState } from '../../shared';
import { TaskCard } from '../tasks/TaskCard';
import { TaskFilters } from '../tasks/TaskFilters';
import { fetchJson } from '../../utils/api';

/* ------------------------------------------------------------------ */
/*  SuggestedActionsBanner                                              */
/* ------------------------------------------------------------------ */

function SuggestedActionsBanner({ actions, loading }) {
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          p: 1.5,
          mb: 2,
          borderRadius: 2,
          backgroundColor: 'rgba(74, 144, 217, 0.06)',
          border: '1px solid rgba(74, 144, 217, 0.15)',
        }}
      >
        <CircularProgress size={14} sx={{ color: 'primary.light' }} />
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Loading AI suggestions...
        </Typography>
      </Box>
    );
  }

  if (!actions?.length) return null;

  return (
    <Box
      sx={{
        p: 2,
        mb: 3,
        borderRadius: 2,
        backgroundColor: 'rgba(74, 144, 217, 0.06)',
        border: '1px solid rgba(74, 144, 217, 0.15)',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
        <AutoAwesomeIcon sx={{ fontSize: 16, color: 'primary.light' }} />
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            color: 'primary.light',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          AI Suggested Actions
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {actions.map((action, idx) => (
          <Box
            key={action.id || idx}
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 1,
              p: 1,
              borderRadius: 1,
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.04)' },
              transition: 'background-color 0.15s',
            }}
          >
            <BoltIcon sx={{ fontSize: 14, color: 'warning.main', mt: 0.25, flexShrink: 0 }} />
            <Box sx={{ minWidth: 0, flexGrow: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 500, lineHeight: 1.4 }}>
                {action.title || action.message}
              </Typography>
              {action.description && (
                <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.4 }}>
                  {action.description}
                </Typography>
              )}
            </Box>
            {action.action_label && (
              <Button
                size="small"
                variant="outlined"
                sx={{
                  fontSize: '0.65rem',
                  flexShrink: 0,
                  borderColor: 'rgba(255, 255, 255, 0.15)',
                  color: 'text.secondary',
                  textTransform: 'none',
                  whiteSpace: 'nowrap',
                }}
              >
                {action.action_label}
              </Button>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Summary stats bar                                                   */
/* ------------------------------------------------------------------ */

function SummaryStats({ tasks }) {
  const total = tasks.length;
  const inProgress = tasks.filter(
    (t) => t.status === 'in-progress' || t.status === 'in_progress'
  ).length;
  const pending = tasks.filter((t) => t.status === 'pending').length;
  const completed = tasks.filter(
    (t) => t.status === 'done' || t.status === 'completed'
  ).length;

  const stats = [
    { value: total, label: 'total' },
    { value: inProgress, label: 'in progress', color: '#4a90d9' },
    { value: pending, label: 'pending', color: '#f06292' },
    { value: completed, label: 'completed', color: '#4caf50' },
  ];

  return (
    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
      {stats.map((s, i) => (
        <React.Fragment key={s.label}>
          {i > 0 && (
            <Box component="span" sx={{ mx: 0.75, opacity: 0.4 }}>
              {'\u00b7'}
            </Box>
          )}
          <Box component="span" sx={{ color: s.color || 'text.secondary', fontWeight: 600 }}>
            {s.value}
          </Box>{' '}
          {s.label}
        </React.Fragment>
      ))}
    </Typography>
  );
}

/* ------------------------------------------------------------------ */
/*  Sort helper — pending first, in-progress second, then rest           */
/* ------------------------------------------------------------------ */

const STATUS_SORT_ORDER = {
  pending: 0,
  'in-progress': 1,
  in_progress: 1,
  'in-review': 2,
  in_review: 2,
  backlog: 3,
  done: 4,
  completed: 4,
};

function getStatusOrder(status) {
  const key = status?.toLowerCase() || '';
  return STATUS_SORT_ORDER[key] ?? 3;
}

/* ------------------------------------------------------------------ */
/*  TasksView                                                           */
/* ------------------------------------------------------------------ */

export default function TasksView() {
  // Fetch list endpoints
  const { data: tasks, loading: tasksLoading, error: tasksError } = useApiData('/tasks');
  const { data: projects, loading: projectsLoading } = useApiData('/projects');
  const { data: employees, loading: employeesLoading } = useApiData('/employees');
  const { data: suggestedActions, loading: actionsLoading } = useApiData(
    '/intelligence/suggested-actions?context=tasks'
  );

  // Detailed tasks (with resolved assignees, dependencies, project name)
  const [detailedTasks, setDetailedTasks] = useState([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  // Filters
  const [filters, setFilters] = useState({
    status: 'all',
    priority: 'all',
    projectId: 'all',
    assigneeId: 'all',
  });

  const handleFilterChange = useCallback((key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Fetch full detail for every task in parallel
  const fetchTaskDetails = useCallback(async (taskList) => {
    if (!taskList?.length) {
      setDetailedTasks([]);
      return;
    }

    setDetailsLoading(true);
    setDetailsError(null);

    try {
      const detailPromises = taskList.map(async (t) => {
        try {
          const detail = await fetchJson(`/tasks/${t.id}`);
          return { ...t, ...detail };
        } catch (err) {
          console.warn(`Failed to fetch details for task ${t.id}:`, err);
          return t;
        }
      });

      const results = await Promise.all(detailPromises);
      setDetailedTasks(results);
    } catch (err) {
      console.error('Failed to fetch task details:', err);
      setDetailsError(err);
      setDetailedTasks(taskList);
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tasks?.length) {
      fetchTaskDetails(tasks);
    }
  }, [tasks, fetchTaskDetails]);

  // Choose best available data
  const allTasks = detailedTasks.length > 0 ? detailedTasks : tasks || [];

  // Client-side filtering
  const filteredTasks = useMemo(() => {
    let result = [...allTasks];

    // Status filter
    if (filters.status !== 'all') {
      result = result.filter((t) => {
        const s = t.status?.toLowerCase().replace(/_/g, '-') || '';
        return s === filters.status;
      });
    }

    // Priority filter
    if (filters.priority !== 'all') {
      result = result.filter((t) => {
        const p = t.priority?.toLowerCase() || '';
        return p === filters.priority;
      });
    }

    // Project filter
    if (filters.projectId !== 'all') {
      result = result.filter((t) => {
        const projId = t.project_id || t.project?.id;
        return projId === filters.projectId;
      });
    }

    // Assignee filter
    if (filters.assigneeId !== 'all') {
      result = result.filter((t) => {
        const assignees = t.assignees || t.assignee_ids || [];
        return assignees.some((a) => {
          const id = typeof a === 'object' ? a.id : a;
          return id === filters.assigneeId;
        });
      });
    }

    // Sort: pending first, in-progress second, then others
    result.sort((a, b) => getStatusOrder(a.status) - getStatusOrder(b.status));

    return result;
  }, [allTasks, filters]);

  // ---------- Render states ----------

  if (tasksLoading) return <LoadingIndicator text="Loading tasks..." />;

  if (tasksError) {
    return (
      <Typography color="error">
        Failed to load tasks: {tasksError.message}
      </Typography>
    );
  }

  if (!tasks?.length) return <EmptyState message="No tasks found" />;

  return (
    <Box>
      {/* Page header */}
      <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 600 }}>
        Tasks
      </Typography>
      <SummaryStats tasks={allTasks} />

      {/* Suggested actions banner */}
      <SuggestedActionsBanner actions={suggestedActions} loading={actionsLoading} />

      {/* Filter bar */}
      <Box sx={{ mb: 3 }}>
        <TaskFilters
          filters={filters}
          onFilterChange={handleFilterChange}
          projects={projects || []}
          employees={employees || []}
        />
      </Box>

      {/* Details loading indicator */}
      {detailsLoading && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <CircularProgress size={14} />
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Loading task details...
          </Typography>
        </Box>
      )}

      {/* Details error (non-fatal) */}
      {detailsError && (
        <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mb: 2 }}>
          Some task details could not be loaded. Showing available data.
        </Typography>
      )}

      {/* Task cards */}
      {filteredTasks.length === 0 ? (
        <EmptyState message="No tasks match the current filters" />
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {filteredTasks.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </Box>
      )}
    </Box>
  );
}
