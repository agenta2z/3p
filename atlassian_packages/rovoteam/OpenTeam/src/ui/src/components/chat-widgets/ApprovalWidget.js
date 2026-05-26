/**
 * ApprovalWidget — decision prompt with approve/reject buttons.
 *
 * Shows a warning-styled header, question text, optional context,
 * and two action buttons. Tracks approval state locally.
 *
 * Props:
 *   data.question      - string
 *   data.context        - string (optional reasoning/context)
 *   data.approve_label  - string (default: "Approve")
 *   data.reject_label   - string (default: "Reject")
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';

const WIDGET_BOX_SX = {
  backgroundColor: 'rgba(255, 255, 255, 0.04)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: 2,
  p: 2,
  mt: 1.5,
};

export default function ApprovalWidget({ data }) {
  const { question, context, approve_label = 'Approve', reject_label = 'Reject' } = data || {};
  const [decision, setDecision] = useState(null); // 'approved' | 'rejected' | null

  const handleApprove = () => {
    console.log('[ApprovalWidget] Approved:', question);
    setDecision('approved');
  };

  const handleReject = () => {
    console.log('[ApprovalWidget] Rejected:', question);
    setDecision('rejected');
  };

  return (
    <Box sx={WIDGET_BOX_SX}>
      {/* Header */}
      <Typography
        variant="subtitle2"
        sx={{ color: '#ffb74d', fontWeight: 600, mb: 1 }}
      >
        {'\u26A1'} Decision Required
      </Typography>

      {/* Question */}
      <Typography variant="body2" sx={{ color: 'text.primary', mb: 1 }}>
        {question}
      </Typography>

      {/* Context */}
      {context && (
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', mb: 1.5, pl: 1.5, borderLeft: '2px solid rgba(255, 255, 255, 0.1)' }}
        >
          {context}
        </Typography>
      )}

      {/* Actions or result */}
      {decision ? (
        <Typography
          variant="body2"
          sx={{
            color: decision === 'approved' ? '#4caf50' : '#f44336',
            fontWeight: 500,
            mt: 0.5,
          }}
        >
          {decision === 'approved' ? `Approved \u2713` : `Rejected \u2717`}
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
          <Button
            variant="contained"
            size="small"
            onClick={handleApprove}
            sx={{
              backgroundColor: '#2e7d32',
              color: '#fff',
              textTransform: 'none',
              '&:hover': { backgroundColor: '#388e3c' },
            }}
          >
            {approve_label}
          </Button>
          <Button
            variant="outlined"
            size="small"
            onClick={handleReject}
            sx={{
              borderColor: 'rgba(255, 255, 255, 0.2)',
              color: 'text.secondary',
              textTransform: 'none',
              '&:hover': { borderColor: 'rgba(255, 255, 255, 0.4)', backgroundColor: 'rgba(255, 255, 255, 0.04)' },
            }}
          >
            {reject_label}
          </Button>
        </Box>
      )}
    </Box>
  );
}
