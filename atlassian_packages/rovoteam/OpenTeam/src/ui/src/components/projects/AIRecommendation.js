import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import BoltIcon from '@mui/icons-material/Bolt';

const PRIORITY_COLORS = {
  high: '#f44336',
  medium: '#ff9800',
  low: '#4a90d9',
};

export function AIRecommendation({ recommendation }) {
  if (!recommendation) return null;

  const { type, message, priority, action } = recommendation;
  const borderColor = PRIORITY_COLORS[priority?.toLowerCase()] || PRIORITY_COLORS.low;

  return (
    <Box
      sx={{
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
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
                  backgroundColor: `${borderColor}15`,
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
                    backgroundColor: `${borderColor}15`,
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
                  backgroundColor: `${borderColor}15`,
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
