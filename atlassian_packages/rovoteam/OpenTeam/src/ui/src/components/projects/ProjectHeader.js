import React, { useState, useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import { StatusBadge, PendingReasonPopover } from '../../shared';

export function ProjectHeader({ name, status, blockers = 0, tasks = [] }) {
  const [pendingAnchor, setPendingAnchor] = useState(null);

  // Count pending tasks and collect their reasons
  const pendingTasks = useMemo(() => {
    return tasks.filter(t => {
      const s = (t.status || '').toLowerCase().replace(/_/g, '-');
      return s === 'pending';
    });
  }, [tasks]);

  const pendingReasons = useMemo(() => {
    return pendingTasks.map(t => ({
      ...(t.pending_reason || {}),
      task_title: t.title,
      // Fallback if no pending_reason object
      type: t.pending_reason?.type || 'pending',
      icon: t.pending_reason?.icon || '⏳',
      summary: t.pending_reason?.summary || `Task "${t.title}" is pending`,
    }));
  }, [pendingTasks]);

  const pendingCount = pendingTasks.length;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
      <Typography variant="h6" sx={{ fontWeight: 600, flexGrow: 1, minWidth: 0 }}>
        {name}
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexShrink: 0 }}>
        <StatusBadge status={status} />

        {/* Pending count badge — clickable */}
        {pendingCount > 0 && (
          <>
            <Chip
              label={`${pendingCount} Pending`}
              size="small"
              onClick={(e) => setPendingAnchor(e.currentTarget)}
              sx={{
                backgroundColor: 'rgba(240, 98, 146, 0.15)',
                color: '#f06292',
                fontWeight: 600,
                fontSize: '0.7rem',
                cursor: 'pointer',
                '&:hover': { backgroundColor: 'rgba(240, 98, 146, 0.25)' },
              }}
            />
            <PendingReasonPopover
              anchorEl={pendingAnchor}
              open={Boolean(pendingAnchor)}
              onClose={() => setPendingAnchor(null)}
              reasons={pendingReasons}
            />
          </>
        )}
      </Box>
    </Box>
  );
}

export default ProjectHeader;
