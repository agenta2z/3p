/**
 * IssuesResolvedDrilldown -- active and resolved issues with resolution rate.
 *
 * Two tabs: "Active" and "Resolved". Header shows resolution rate and counts.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
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

const SEVERITY_COLOR = {
  high: 'error',
  medium: 'warning',
  low: 'info',
};

function getAge(timestamp) {
  if (!timestamp) return 'unknown';
  const diff = Date.now() - new Date(timestamp).getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return '<1h';
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w`;
}

export default function IssuesResolvedDrilldown({ employeeId, periodData, periodInfo }) {
  const theme = useTheme();
  const [tab, setTab] = useState(0);

  const { data: issueEvents, loading } = useApiData(
    employeeId ? `/employees/${employeeId}/issue-events` : null
  );

  const issues = periodData?.issues ?? 0;
  const resolved = periodData?.resolved ?? 0;
  const resolutionRate = issues > 0 ? Math.round((resolved / issues) * 100) : 100;
  const rateColor = resolutionRate >= 80 ? 'success.main' : 'error.main';

  const allEvents = Array.isArray(issueEvents) ? issueEvents : issueEvents?.events || [];
  const activeIssues = allEvents.filter((e) => e.status === 'open');
  const resolvedIssues = allEvents.filter((e) => e.status === 'resolved');

  return (
    <Box>
      {/* Header with resolution rate */}
      <Box sx={sectionSx}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography
              variant="h4"
              sx={{ fontWeight: 700, fontSize: '1.5rem', color: rateColor, lineHeight: 1 }}
            >
              {resolutionRate}%
            </Typography>
            <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
              Resolution Rate
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, flexGrow: 1, justifyContent: 'center' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {issues - resolved}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                Open
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {resolved}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                Resolved
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{
          minHeight: 32,
          mb: 1.5,
          '& .MuiTab-root': {
            minHeight: 32,
            fontSize: '0.7rem',
            textTransform: 'none',
            py: 0.5,
          },
        }}
      >
        <Tab label={`Active (${activeIssues.length})`} />
        <Tab label={`Resolved (${resolvedIssues.length})`} />
      </Tabs>

      {loading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 2 }}>
          <CircularProgress size={16} />
          <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Loading issues...</Typography>
        </Box>
      ) : (
        <>
          {/* Active Tab */}
          {tab === 0 && (
            <Box>
              {activeIssues.length === 0 ? (
                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem', p: 1 }}>
                  No active issues.
                </Typography>
              ) : (
                activeIssues.map((issue, idx) => (
                  <Box key={issue.id || idx} sx={sectionSx}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                      <Chip
                        label={issue.severity || 'unknown'}
                        size="small"
                        color={SEVERITY_COLOR[issue.severity] || 'default'}
                        sx={{ height: 20, fontSize: '0.6rem', fontWeight: 600 }}
                      />
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 500,
                          fontSize: '0.75rem',
                          flexGrow: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {issue.title || 'Untitled Issue'}
                      </Typography>
                      <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary', flexShrink: 0 }}>
                        {getAge(issue.timestamp)} ago
                      </Typography>
                    </Box>
                    {issue.description && (
                      <Typography
                        variant="caption"
                        sx={{
                          fontSize: '0.65rem',
                          color: 'text.secondary',
                          lineHeight: 1.4,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {issue.description}
                      </Typography>
                    )}
                  </Box>
                ))
              )}
            </Box>
          )}

          {/* Resolved Tab */}
          {tab === 1 && (
            <Box>
              {resolvedIssues.length === 0 ? (
                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem', p: 1 }}>
                  No resolved issues.
                </Typography>
              ) : (
                resolvedIssues.map((issue, idx) => (
                  <Box key={issue.id || idx} sx={sectionSx}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                      <Chip
                        label={issue.severity || 'unknown'}
                        size="small"
                        color={SEVERITY_COLOR[issue.severity] || 'default'}
                        sx={{ height: 20, fontSize: '0.6rem', fontWeight: 600 }}
                      />
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 500,
                          fontSize: '0.75rem',
                          flexGrow: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {issue.title || 'Untitled Issue'}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mt: 0.25 }}>
                      {issue.resolution_method && (
                        <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                          Method: {issue.resolution_method}
                        </Typography>
                      )}
                      {issue.resolution_time_hours != null && (
                        <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                          Resolved in: {issue.resolution_time_hours}h
                        </Typography>
                      )}
                    </Box>
                  </Box>
                ))
              )}
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
