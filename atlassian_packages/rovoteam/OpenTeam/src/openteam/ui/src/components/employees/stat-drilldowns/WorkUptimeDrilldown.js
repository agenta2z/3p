/**
 * WorkUptimeDrilldown -- detailed view of work hours, uptime, utilization,
 * brain state, and work session breakdown.
 */

import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import { useTheme, alpha } from '@mui/material/styles';
import { useApiData } from '../../../hooks/useApiData';
import ThinkingStatePanel from './shared/ThinkingStatePanel';

const sectionSx = {
  backgroundColor: 'action.hover',
  border: '1px solid',
  borderColor: 'divider',
  borderRadius: 1.5,
  p: 1.25,
  mb: 1,
};

const WORK_TYPE_COLORS = {
  coding: 'primary',
  reviewing: 'info',
  communicating: 'success',
  idle: 'grey',
};

function SummaryMetric({ label, value, sub, color }) {
  return (
    <Box sx={{ textAlign: 'center', flex: 1, minWidth: 60 }}>
      <Typography
        variant="h6"
        sx={{ fontWeight: 700, fontSize: '0.9rem', lineHeight: 1.2, color: color || 'text.primary' }}
      >
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" sx={{ color: color || 'text.secondary', fontSize: '0.55rem', display: 'block' }}>
          {sub}
        </Typography>
      )}
      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', display: 'block' }}>
        {label}
      </Typography>
    </Box>
  );
}

export default function WorkUptimeDrilldown({ employeeId, periodData, periodInfo, metrics }) {
  const theme = useTheme();

  const { data: thinkingData, loading: thinkingLoading } = useApiData(
    employeeId ? `/intelligence/employees/${employeeId}/thinking` : null
  );

  const workHours = periodData?.work_hours ?? 0;
  const uptimeHours = periodData?.uptime_hours ?? 0;
  const days = periodInfo?.days || 1;
  const utilization = uptimeHours > 0 ? Math.round((workHours / uptimeHours) * 100) : 0;
  const dailyAvg = days > 0 ? (workHours / days).toFixed(1) : 0;
  const dailyColor = parseFloat(dailyAvg) >= 8 ? 'success.main' : 'error.main';

  // Work sessions from thinking data agent state
  const workSessions = thinkingData?.work_sessions || thinkingData?.agent_state?.work_sessions || [];
  const sessionTotal = workSessions.reduce((sum, s) => sum + (s.hours || s.duration_hours || 0), 0);

  return (
    <Box>
      {/* Summary */}
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
          Summary
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <SummaryMetric label="Work Hours" value={`${workHours}h`} />
          <SummaryMetric label="Uptime" value={`${uptimeHours}h`} />
          <SummaryMetric label="Utilization" value={`${utilization}%`} />
          <SummaryMetric
            label="Daily Avg"
            value={`${dailyAvg}h`}
            sub={parseFloat(dailyAvg) >= 8 ? 'above 8h baseline' : 'below 8h baseline'}
            color={dailyColor}
          />
        </Box>
      </Box>

      {/* Brain State */}
      <Box sx={{ mb: 1 }}>
        {thinkingLoading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="caption" sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
              Loading thinking state...
            </Typography>
          </Box>
        ) : (
          <ThinkingStatePanel thinkingState={thinkingData} />
        )}
      </Box>

      {/* Work Breakdown */}
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
          Work Breakdown
        </Typography>

        {thinkingLoading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="caption" sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
              Loading...
            </Typography>
          </Box>
        ) : workSessions.length === 0 ? (
          <Typography variant="caption" sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
            No work session data available.
          </Typography>
        ) : (
          <>
            {/* Stacked bar */}
            <Box
              sx={{
                display: 'flex',
                width: '100%',
                height: 12,
                borderRadius: 6,
                overflow: 'hidden',
                mb: 1,
              }}
            >
              {workSessions.map((session, idx) => {
                const hours = session.hours || session.duration_hours || 0;
                const pct = sessionTotal > 0 ? (hours / sessionTotal) * 100 : 0;
                const type = (session.type || session.category || 'idle').toLowerCase();
                const colorKey = WORK_TYPE_COLORS[type] || 'grey';
                const bgColor = colorKey === 'grey'
                  ? theme.palette.grey[400]
                  : theme.palette[colorKey]?.main || theme.palette.grey[400];

                return (
                  <Box
                    key={idx}
                    sx={{
                      width: `${pct}%`,
                      backgroundColor: bgColor,
                      minWidth: pct > 0 ? 2 : 0,
                    }}
                  />
                );
              })}
            </Box>

            {/* Legend */}
            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
              {workSessions.map((session, idx) => {
                const hours = session.hours || session.duration_hours || 0;
                const pct = sessionTotal > 0 ? Math.round((hours / sessionTotal) * 100) : 0;
                const type = (session.type || session.category || 'idle').toLowerCase();
                const colorKey = WORK_TYPE_COLORS[type] || 'grey';
                const dotColor = colorKey === 'grey'
                  ? theme.palette.grey[400]
                  : theme.palette[colorKey]?.main || theme.palette.grey[400];

                return (
                  <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: dotColor,
                        flexShrink: 0,
                      }}
                    />
                    <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                      {type} {pct}% ({hours.toFixed(1)}h)
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}
