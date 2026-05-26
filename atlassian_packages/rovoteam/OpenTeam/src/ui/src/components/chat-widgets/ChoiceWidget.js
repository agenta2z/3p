/**
 * ChoiceWidget — multiple-option selector for manager decisions.
 *
 * Shows a prompt, selectable option cards with hover/selected states,
 * and a confirm button. Tracks selection state locally.
 *
 * Props:
 *   data.prompt  - string (header text)
 *   data.options - array of { id, label, description }
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

export default function ChoiceWidget({ data }) {
  const { prompt, options = [] } = data || {};
  const [selectedId, setSelectedId] = useState(null);
  const [confirmed, setConfirmed] = useState(false);

  const handleConfirm = () => {
    const selected = options.find((o) => o.id === selectedId);
    console.log('[ChoiceWidget] Selected:', selected);
    setConfirmed(true);
  };

  const selectedLabel = options.find((o) => o.id === selectedId)?.label;

  return (
    <Box sx={WIDGET_BOX_SX}>
      {/* Header */}
      <Typography variant="subtitle2" sx={{ color: 'text.primary', fontWeight: 600, mb: 1.5 }}>
        {prompt || 'Choose an option'}
      </Typography>

      {confirmed ? (
        <Typography variant="body2" sx={{ color: '#4a90d9', fontWeight: 500 }}>
          Selected: {selectedLabel}
        </Typography>
      ) : (
        <>
          {/* Option cards */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75, mb: 1.5 }}>
            {options.map((option) => {
              const isSelected = selectedId === option.id;
              return (
                <Box
                  key={option.id}
                  onClick={() => setSelectedId(option.id)}
                  sx={{
                    p: 1.5,
                    borderRadius: 1.5,
                    border: isSelected
                      ? '1px solid #4a90d9'
                      : '1px solid rgba(255, 255, 255, 0.08)',
                    backgroundColor: isSelected
                      ? 'rgba(74, 144, 217, 0.08)'
                      : 'rgba(255, 255, 255, 0.02)',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    '&:hover': {
                      backgroundColor: isSelected
                        ? 'rgba(74, 144, 217, 0.12)'
                        : 'rgba(255, 255, 255, 0.06)',
                      borderColor: isSelected
                        ? '#4a90d9'
                        : 'rgba(255, 255, 255, 0.15)',
                    },
                  }}
                >
                  <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                    {option.label}
                  </Typography>
                  {option.description && (
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.25 }}>
                      {option.description}
                    </Typography>
                  )}
                </Box>
              );
            })}
          </Box>

          {/* Confirm button */}
          <Button
            variant="contained"
            size="small"
            disabled={selectedId == null}
            onClick={handleConfirm}
            sx={{
              backgroundColor: '#4a90d9',
              color: '#fff',
              textTransform: 'none',
              '&:hover': { backgroundColor: '#5a9fe0' },
              '&.Mui-disabled': { backgroundColor: 'rgba(255, 255, 255, 0.08)', color: 'rgba(255, 255, 255, 0.3)' },
            }}
          >
            Confirm Selection
          </Button>
        </>
      )}
    </Box>
  );
}
