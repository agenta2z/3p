import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import BoltIcon from '@mui/icons-material/Bolt';

import { useTheme, alpha } from '@mui/material/styles';

const PRIORITY_PALETTE = {
  high: 'error',
  medium: 'warning',
  low: 'primary',
};

export function AIRecommendation({ recommendation }) {
  const theme = useTheme();
  if (!recommendation) return null;

  const { type, message, priority, action } = recommendation;
  const paletteKey = PRIORITY_PALETTE[priority?.toLowerCase()] || 'primary';
  const borderColor = theme.palette[paletteKey]?.main || theme.palette.primary.main;

  return (
    <Box
      sx={{
        backgroundColor: 'action.hover',
        border: '1px solid', borderColor: 'divider',
        borderLeft: `3px solid ${borderColor}`,
        borderRadius: 2,
        p: 1.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
      }}
    >
      {/* Label */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <BoltIcon sx={{ fontSize: 16, color: borderColor }} />
        <Typography
          variant="caption"
          sx={{ fontWeight: 600, color: borderColor, textTransform: 'uppercase', letterSpacing: 0.5 }}
        >
          AI Recommendation
        </Typography>
        {type && (
          <Typography variant="caption" sx={{ color: 'text.secondary', ml: 0.5 }}>
            — {type}
          </Typography>
        )}
      </Box>

      {/* Message */}
      <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.5 }}>
        {message}
      </Typography>

      {/* Action button(s) */}
      {action && (
        <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
          {typeof action === 'string' ? (
            <Button
              size="small"
              variant="outlined"
              sx={{
                fontSize: '0.7rem',
                borderColor: borderColor,
                color: borderColor,
                textTransform: 'none',
                '&:hover': {
                  borderColor: borderColor,
                  backgroundColor: alpha(borderColor, 0.08),
                },
              }}
            >
              {action}
            </Button>
          ) : Array.isArray(action) ? (
            action.map((act, idx) => (
              <Button
                key={idx}
                size="small"
                variant="outlined"
                sx={{
                  fontSize: '0.7rem',
                  borderColor: borderColor,
                  color: borderColor,
                  textTransform: 'none',
                  '&:hover': {
                    borderColor: borderColor,
                    backgroundColor: alpha(borderColor, 0.08),
                  },
                }}
              >
                {act.label || act}
              </Button>
            ))
          ) : action.label ? (
            <Button
              size="small"
              variant="outlined"
              href={action.url || undefined}
              sx={{
                fontSize: '0.7rem',
                borderColor: borderColor,
                color: borderColor,
                textTransform: 'none',
                '&:hover': {
                  borderColor: borderColor,
                  backgroundColor: alpha(borderColor, 0.08),
                },
              }}
            >
              {action.label}
            </Button>
          ) : null}
        </Box>
      )}
    </Box>
  );
}

export default AIRecommendation;
