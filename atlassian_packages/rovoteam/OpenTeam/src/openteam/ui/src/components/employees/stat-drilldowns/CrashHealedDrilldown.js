/**
 * CrashHealedDrilldown -- health summary and crash event log.
 *
 * Shows heal rate, crash frequency, and expandable crash event details.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useTheme, alpha } from '@mui/material/styles';
import { useApiData } from '../../../hooks/useApiData';

const sectionSx = {
  backgroundColor: 'action.hover',
  border: '1px solid',
  borderColor: 'divider',
  borderRadius: 1.5,
  p: 1.25,
  mb: 1,
};

function CrashEventItem({ event }) {
  const [expanded, setExpanded] = useState(false);
  const theme = useTheme();

  return (
    <Box
      sx={{
        ...sectionSx,
        cursor: 'pointer',
        '&:hover': { backgroundColor: alpha(theme.palette.action.hover, 0.8) },
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Chip
          label={event.error_type || 'Unknown'}
          size="small"
          sx={{
            height: 20,
            fontSize: '0.6rem',
            fontWeight: 600,
            backgroundColor: alpha(theme.palette.error.main, 0.1),
            color: 'error.main',
          }}
        />
        <Typography
          variant="caption"
          sx={{ fontSize: '0.65rem', color: 'text.secondary', flexGrow: 1 }}
        >
          {event.timestamp ? new Date(event.timestamp).toLocaleString() : 'Unknown time'}
        </Typography>
        {event.healed && (
          <CheckCircleOutlineIcon sx={{ fontSize: 14, color: 'success.main' }} />
        )}
        {expanded
          ? <ExpandLessIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          : <ExpandMoreIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
        }
      </Box>

      {expanded && (
        <Box sx={{ mt: 1, pl: 0.5 }}>
          {event.description && (
            <Box sx={{ mb: 0.75 }}>
              <Typography
                variant="caption"
                sx={{ fontSize: '0.6rem', fontWeight: 600, color: 'text.secondary', display: 'block' }}
              >
                Description
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.7rem', lineHeight: 1.4 }}>
                {event.description}
              </Typography>
            </Box>
          )}

          {event.root_cause_analysis && (
            <Box sx={{ mb: 0.75 }}>
              <Typography
                variant="caption"
                sx={{ fontSize: '0.6rem', fontWeight: 600, color: 'text.secondary', display: 'block' }}
              >
                Root Cause
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.7rem', lineHeight: 1.4 }}>
                {event.root_cause_analysis}
              </Typography>
            </Box>
          )}

          {event.self_heal_action && (
            <Box sx={{ mb: 0.75 }}>
              <Typography
                variant="caption"
                sx={{ fontSize: '0.6rem', fontWeight: 600, color: 'text.secondary', display: 'block' }}
              >
                Self-Heal Action
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {event.healed && (
                  <CheckCircleOutlineIcon sx={{ fontSize: 12, color: 'success.main' }} />
                )}
                <Typography variant="caption" sx={{ fontSize: '0.7rem', lineHeight: 1.4 }}>
                  {event.self_heal_action}
                </Typography>
              </Box>
            </Box>
          )}

          {event.recovery_time_seconds != null && (
            <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
              Recovery time: {event.recovery_time_seconds}s
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}

export default function CrashHealedDrilldown({ employeeId, periodData, periodInfo }) {
  const theme = useTheme();

  const { data: crashEvents, loading } = useApiData(
    employeeId ? `/employees/${employeeId}/crash-events` : null
  );

  const crashes = periodData?.crashes ?? 0;
  const healed = periodData?.healed ?? 0;
  const days = periodInfo?.days || 1;
  const healRate = crashes > 0 ? Math.round((healed / crashes) * 100) : 100;
  const healColor = healRate >= 80 ? 'success.main' : 'error.main';
  const crashesPerDay = days > 0 ? (crashes / days).toFixed(1) : 0;

  const events = Array.isArray(crashEvents) ? crashEvents : crashEvents?.events || [];
  const sortedEvents = [...events].sort(
    (a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0)
  );

  return (
    <Box>
      {/* Health Summary */}
      <Box sx={sectionSx}>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
            fontSize: '0.6rem',
            color: 'text.secondary',
            display: 'block',
            mb: 1,
          }}
        >
          Health Summary
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Big heal rate */}
          <Box sx={{ textAlign: 'center' }}>
            <Typography
              variant="h4"
              sx={{ fontWeight: 700, fontSize: '1.5rem', color: healColor, lineHeight: 1 }}
            >
              {healRate}%
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
              Heal Rate
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', gap: 2, flexGrow: 1, justifyContent: 'center' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {crashesPerDay}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                Crashes/Day
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {crashes}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                Total Crashes
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {healed}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                Self-Healed
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Crash Event Log */}
      <Typography
        variant="caption"
        sx={{
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: 0.5,
          fontSize: '0.6rem',
          color: 'text.secondary',
          display: 'block',
          mb: 0.75,
        }}
      >
        Crash Event Log
      </Typography>

      {loading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 2 }}>
          <CircularProgress size={16} />
          <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Loading crash events...</Typography>
        </Box>
      ) : sortedEvents.length === 0 ? (
        <Box
          sx={{
            p: 1.5,
            borderRadius: 1.5,
            backgroundColor: alpha(theme.palette.success.main, 0.08),
            border: '1px solid',
            borderColor: alpha(theme.palette.success.main, 0.2),
            textAlign: 'center',
          }}
        >
          <CheckCircleOutlineIcon sx={{ fontSize: 20, color: 'success.main', mb: 0.5 }} />
          <Typography variant="caption" sx={{ fontSize: '0.75rem', color: 'success.main', display: 'block' }}>
            No crashes recorded
          </Typography>
        </Box>
      ) : (
        sortedEvents.map((event, idx) => (
          <CrashEventItem key={event.id || idx} event={event} />
        ))
      )}
    </Box>
  );
}
