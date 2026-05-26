/**
 * ThinkingStatePanel -- agent brain state display for stat drill-downs.
 *
 * Handles BOTH schemas:
 *   Standard (emp-001-004): {current_focus, reasoning_chain[], confidence, blockers[], next_steps[], last_updated}
 *   Alternate (emp-010):    {current_thought, is_thinking, thinking_about_task_id}
 */

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import PsychologyIcon from '@mui/icons-material/Psychology';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
import { useTheme, alpha } from '@mui/material/styles';

function getConfidenceColor(confidence, theme) {
  if (confidence == null) return theme.palette.text.secondary;
  if (confidence > 0.8) return theme.palette.success.main;
  if (confidence >= 0.5) return theme.palette.warning.main;
  return theme.palette.error.main;
}

function getConfidenceLabel(confidence) {
  if (confidence == null) return 'N/A';
  return `${Math.round(confidence * 100)}%`;
}

export default function ThinkingStatePanel({ thinkingState }) {
  const theme = useTheme();

  if (!thinkingState) {
    return (
      <Box sx={{ py: 2, textAlign: 'center' }}>
        <Typography
          variant="caption"
          sx={{ color: 'text.secondary', fontSize: '0.75rem' }}
        >
          No thinking data available
        </Typography>
      </Box>
    );
  }

  // Detect schema type
  const isAlternate = 'current_thought' in thinkingState;

  const currentFocus = isAlternate
    ? thinkingState.current_thought
    : thinkingState.current_focus;
  const reasoningChain = thinkingState.reasoning_chain || [];
  const confidence = thinkingState.confidence;
  const blockers = thinkingState.blockers || [];
  const nextSteps = thinkingState.next_steps || [];
  const isThinking = thinkingState.is_thinking;
  const thinkingAboutTaskId = thinkingState.thinking_about_task_id;

  const confidenceColor = getConfidenceColor(confidence, theme);

  return (
    <Box
      sx={{
        maxHeight: 200,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        p: 1,
      }}
    >
      {/* Current Focus */}
      {currentFocus && (
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
          <PsychologyIcon
            sx={{ fontSize: 14, color: 'primary.light', mt: 0.2, flexShrink: 0 }}
          />
          <Box>
            <Typography
              variant="caption"
              sx={{
                color: 'text.secondary',
                fontSize: '0.6rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: 0.3,
                display: 'block',
                mb: 0.2,
              }}
            >
              Current Focus
            </Typography>
            <Typography
              variant="body2"
              sx={{ fontSize: '0.75rem', fontStyle: 'italic', lineHeight: 1.4 }}
            >
              {currentFocus}
            </Typography>
          </Box>
        </Box>
      )}

      {/* Alternate schema extras */}
      {isAlternate && (
        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
          {isThinking != null && (
            <Chip
              label={isThinking ? 'Thinking...' : 'Idle'}
              size="small"
              sx={{
                height: 18,
                fontSize: '0.6rem',
                fontWeight: 600,
                backgroundColor: isThinking
                  ? alpha(theme.palette.info.main, 0.15)
                  : alpha(theme.palette.text.secondary, 0.1),
                color: isThinking ? 'info.main' : 'text.secondary',
              }}
            />
          )}
          {thinkingAboutTaskId && (
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', fontSize: '0.65rem' }}
            >
              Task: {thinkingAboutTaskId}
            </Typography>
          )}
        </Box>
      )}

      {/* Confidence badge */}
      {confidence != null && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              fontSize: '0.6rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 0.3,
            }}
          >
            Confidence
          </Typography>
          <Chip
            label={getConfidenceLabel(confidence)}
            size="small"
            sx={{
              height: 18,
              fontSize: '0.6rem',
              fontWeight: 700,
              backgroundColor: alpha(confidenceColor, 0.15),
              color: confidenceColor,
            }}
          />
        </Box>
      )}

      {/* Reasoning chain */}
      {reasoningChain.length > 0 && (
        <Box>
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              fontSize: '0.6rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 0.3,
              display: 'block',
              mb: 0.3,
            }}
          >
            Reasoning
          </Typography>
          {reasoningChain.map((step, idx) => (
            <Typography
              key={idx}
              variant="caption"
              sx={{
                display: 'block',
                fontSize: '0.68rem',
                lineHeight: 1.4,
                color: 'text.secondary',
                pl: 0.5,
              }}
            >
              {idx + 1}. {step}
            </Typography>
          ))}
        </Box>
      )}

      {/* Blockers */}
      {blockers.length > 0 && (
        <Box>
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              fontSize: '0.6rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 0.3,
              display: 'block',
              mb: 0.3,
            }}
          >
            Blockers
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {blockers.map((blocker, idx) => (
              <Chip
                key={idx}
                icon={<WarningAmberIcon sx={{ fontSize: 12 }} />}
                label={blocker}
                size="small"
                sx={{
                  height: 20,
                  fontSize: '0.6rem',
                  backgroundColor: alpha(theme.palette.warning.main, 0.12),
                  color: 'warning.main',
                  '& .MuiChip-icon': { color: 'warning.main' },
                }}
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Next steps */}
      {nextSteps.length > 0 && (
        <Box>
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              fontSize: '0.6rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 0.3,
              display: 'block',
              mb: 0.3,
            }}
          >
            Next Steps
          </Typography>
          {nextSteps.map((step, idx) => (
            <Box
              key={idx}
              sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.1 }}
            >
              <ArrowRightIcon
                sx={{ fontSize: 14, color: 'text.secondary', mt: 0.1, flexShrink: 0 }}
              />
              <Typography
                variant="caption"
                sx={{
                  fontSize: '0.68rem',
                  lineHeight: 1.4,
                  color: 'text.secondary',
                }}
              >
                {step}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
