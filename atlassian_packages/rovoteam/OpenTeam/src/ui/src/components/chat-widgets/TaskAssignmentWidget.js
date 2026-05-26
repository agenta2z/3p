/**
 * TaskAssignmentWidget — task reassignment confirmation card.
 *
 * Shows the task being reassigned, from/to person chips with utilization,
 * a reason, and confirm/cancel buttons. Tracks confirmation state locally.
 *
 * Props:
 *   data.task_title - string
 *   data.from       - { name, type, utilization }
 *   data.to         - { name, type, utilization }
 *   data.reason     - string
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';

import { PersonChip, ProgressBar } from '../../shared';

const WIDGET_BOX_SX = {
  backgroundColor: 'rgba(255, 255, 255, 0.04)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 2,
  p: 2,
  mt: 1.5,
};

function PersonRow({ label, person }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', flex: '0 0 40px', fontWeight: 500 }}>
        {label}
      </Typography>
      <PersonChip name={person.name} type={person.type || 'human'} size="small" />
      <Box sx={{ flex: '0 0 100px' }}>
        <ProgressBar percent={person.utilization || 0} height={4} showLabel />
      </Box>
    </Box>
  );
}

export default function TaskAssignmentWidget({ data }) {
  const { task_title, from, to, reason } = data || {};
  const [confirmed, setConfirmed] = useState(null); // 'confirmed' | 'cancelled' | null

  const handleConfirm = () => {
    console.log('[TaskAssignmentWidget] Reassigned:', task_title, 'from', from?.name, 'to', to?.name);
    setConfirmed('confirmed');
  };

  const handleCancel = () => {
    console.log('[TaskAssignmentWidget] Cancelled reassignment:', task_title);
    setConfirmed('cancelled');
  };

  return (
    <Box sx={WIDGET_BOX_SX}>
      {/* Header */}
      <Typography variant="subtitle2" sx={{ color: 'text.primary', fontWeight: 600, mb: 1.5 }}>
        {'\u2696\uFE0F'} Reassign Task
      </Typography>

      {/* Task title */}
      <Typography variant="body2" sx={{ color: 'text.primary', mb: 1.5, fontStyle: 'italic' }}>
        &ldquo;{task_title}&rdquo;
      </Typography>

      {/* From / To */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 1.5 }}>
        {from && <PersonRow label="From:" person={from} />}
        {to && <PersonRow label="To:" person={to} />}
      </Box>

      {/* Reason */}
      {reason && (
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', mb: 1.5, pl: 1.5, borderLeft: '2px solid rgba(255, 255, 255, 0.1)' }}
        >
          {reason}
        </Typography>
      )}

      {/* Actions or result */}
      {confirmed ? (
        <Typography
          variant="body2"
          sx={{
            color: confirmed === 'confirmed' ? '#4caf50' : 'text.secondary',
            fontWeight: 500,
          }}
        >
          {confirmed === 'confirmed' ? 'Reassigned \u2713' : 'Cancelled'}
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            size="small"
            onClick={handleConfirm}
            sx={{
              backgroundColor: '#4a90d9',
              color: '#fff',
              textTransform: 'none',
              '&:hover': { backgroundColor: '#5a9fe0' },
            }}
          >
            Confirm
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleCancel}
            sx={{
              borderColor: 'rgba(255, 255, 255, 0.2)',
              color: 'text.secondary',
              textTransform: 'none',
              '&:hover': { borderColor: 'rgba(255, 255, 255, 0.4)', backgroundColor: 'rgba(255, 255, 255, 0.04)' },
            }}
          >
            Cancel
          </Button>
        </Box>
      )}
    </Box>
  );
}
