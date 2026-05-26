/**
 * ProgressBar — linear progress with optional percentage label.
 * Uses theme palette for auto-coloring.
 */

import React from 'react';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

function getProgressColor(percent, theme) {
  if (percent >= 75) return theme.palette.success.main;
  if (percent >= 40) return theme.palette.warning.main;
  return theme.palette.error.main;
}

export function ProgressBar({ percent = 0, color, showLabel = true, height = 8 }) {
  const theme = useTheme();
  const barColor = color || getProgressColor(percent, theme);
  const clampedPercent = Math.min(100, Math.max(0, percent));

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
      <Box sx={{ flexGrow: 1 }}>
        <LinearProgress variant="determinate" value={clampedPercent} sx={{
          height, borderRadius: height / 2,
          backgroundColor: theme.custom.surfaces.overlayMedium,
          '& .MuiLinearProgress-bar': { borderRadius: height / 2, backgroundColor: barColor },
        }} />
      </Box>
      {showLabel && <Typography variant="body2" sx={{ color: 'text.secondary', minWidth: 40, textAlign: 'right' }}>{Math.round(clampedPercent)}%</Typography>}
    </Box>
  );
}

export default ProgressBar;
