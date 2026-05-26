/**
 * TaskQueueDrilldown -- shows in-progress task details and queued tasks.
 *
 * Two tabs: "In Progress" and "Queued".
 * Fetches task details and thinking state for the active task.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import VisibilityIcon from '@mui/icons-material/Visibility';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import { useTheme, alpha } from '@mui/material/styles';
import { useApiData } from '../../../hooks/useApiData';
import ThinkingStatePanel from './shared/ThinkingStatePanel';

const PRIORITY_COLOR = {
  high: 'warning',
  medium: 'primary',
  low: 'success',
};

const PRIORITY_DOT_COLOR = {
  high: 'warning.main',
  medium: 'primary.main',
  low: 'success.main',
};

const sectionSx = {
  backgroundColor: 'action.hover',
  border: '1px solid',
  borderColor: 'divider',
  borderRadius: 1.5,
  p: 1.25,
  mb: 1,
};

export default function TaskQueueDrilldown({ employeeId, taskQueue = [], currentTaskId, periodInfo }) {
  const theme = useTheme();
  const [tab, setTab] = useState(0);

  const { data: taskDetails, loading: taskLoading } = useApiData(
    currentTaskId ? `/tasks/${currentTaskId}` : null
  );
  const { data: thinkingData, loading: thinkingLoading } = useApiData(
    employeeId ? `/intelligence/employees/${employeeId}/thinking` : null
  );

  const totalQueuedHours = taskQueue.reduce((sum, t) => sum + (t.estimated_hours || 0), 0);

  return (
    <Box>
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
        <Tab label="In Progress" />
        <Tab label={`Queued (${taskQueue.length})`} />
      </Tabs>

      {/* In Progress Tab */}
      {tab === 0 && (
        <Box>
          {taskLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 2 }}>
              <CircularProgress size={16} />
              <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>Loading task...</Typography>
            </Box>
          ) : !currentTaskId || !taskDetails ? (
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem', p: 1 }}>
              No task currently in progress.
            </Typography>
          ) : (
            <>
              {/* Task header */}
              <Box sx={sectionSx}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75 }}>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, fontSize: '0.8rem', flexGrow: 1 }}
                  >
                    {taskDetails.title || taskDetails.name || 'Untitled Task'}
                  </Typography>
                  {taskDetails.priority && (
                    <Chip
                      label={taskDetails.priority}
                      size="small"
                      color={PRIORITY_COLOR[taskDetails.priority] || 'default'}
                      sx={{ height: 20, fontSize: '0.6rem', fontWeight: 600 }}
                    />
                  )}
                </Box>

                {/* Progress bar */}
                {taskDetails.progress != null && (
                  <Box sx={{ mb: 0.75 }}>
                    <Box
                      sx={{
                        width: '100%',
                        height: 6,
                        borderRadius: 3,
                        backgroundColor: alpha(theme.palette.primary.main, 0.12),
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          width: `${Math.min(taskDetails.progress, 100)}%`,
                          height: '100%',
                          borderRadius: 3,
                          backgroundColor: 'primary.main',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </Box>
                    <Typography
                      variant="caption"
                      sx={{ fontSize: '0.6rem', color: 'text.secondary', mt: 0.25, display: 'block' }}
                    >
                      {taskDetails.progress}% complete
                    </Typography>
                  </Box>
                )}

                {/* Metadata */}
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  {taskDetails.estimated_hours != null && (
                    <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                      Est: {taskDetails.estimated_hours}h
                    </Typography>
                  )}
                  {taskDetails.due_date && (
                    <Typography variant="caption" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
                      Due: {new Date(taskDetails.due_date).toLocaleDateString()}
                    </Typography>
                  )}
                </Box>
              </Box>

              {/* Thinking state */}
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

              {/* Most recent activity */}
              {taskDetails.activity && taskDetails.activity.length > 0 && (
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
                      mb: 0.5,
                    }}
                  >
                    Latest Activity
                  </Typography>
                  <Typography variant="caption" sx={{ fontSize: '0.7rem', color: 'text.primary', lineHeight: 1.4 }}>
                    {taskDetails.activity[taskDetails.activity.length - 1].description ||
                      taskDetails.activity[taskDetails.activity.length - 1].message ||
                      JSON.stringify(taskDetails.activity[taskDetails.activity.length - 1])}
                  </Typography>
                </Box>
              )}

              {/* Action buttons */}
              <Box sx={{ display: 'flex', gap: 0.75, mt: 0.5 }}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<VisibilityIcon sx={{ fontSize: '14px !important' }} />}
                  sx={{
                    fontSize: '0.65rem',
                    textTransform: 'none',
                    borderRadius: 2,
                    py: 0.25,
                    borderColor: 'divider',
                    color: 'text.secondary',
                  }}
                >
                  View Details
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<NotificationsActiveIcon sx={{ fontSize: '14px !important' }} />}
                  sx={{
                    fontSize: '0.65rem',
                    textTransform: 'none',
                    borderRadius: 2,
                    py: 0.25,
                    borderColor: 'divider',
                    color: 'text.secondary',
                  }}
                >
                  Nudge
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<SwapHorizIcon sx={{ fontSize: '14px !important' }} />}
                  sx={{
                    fontSize: '0.65rem',
                    textTransform: 'none',
                    borderRadius: 2,
                    py: 0.25,
                    borderColor: 'divider',
                    color: 'text.secondary',
                  }}
                >
                  Reassign
                </Button>
              </Box>
            </>
          )}
        </Box>
      )}

      {/* Queued Tab */}
      {tab === 1 && (
        <Box>
          {taskQueue.length === 0 ? (
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem', p: 1 }}>
              No tasks in queue.
            </Typography>
          ) : (
            <>
              {taskQueue.map((item, idx) => (
                <Box
                  key={item.id || idx}
                  sx={{
                    ...sectionSx,
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1,
                  }}
                >
                  {/* Priority dot */}
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      backgroundColor: PRIORITY_DOT_COLOR[item.priority] || 'grey.400',
                      flexShrink: 0,
                      mt: 0.5,
                    }}
                  />
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
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
                        {item.title || item.name || 'Untitled'}
                      </Typography>
                      {item.estimated_hours != null && (
                        <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary', flexShrink: 0 }}>
                          ~{item.estimated_hours}h
                        </Typography>
                      )}
                    </Box>
                    {item.depends_on && (
                      <Chip
                        label={`Blocked by: ${item.depends_on}`}
                        size="small"
                        sx={{
                          height: 18,
                          fontSize: '0.55rem',
                          mt: 0.5,
                          backgroundColor: alpha(theme.palette.error.main, 0.1),
                          color: 'error.main',
                        }}
                      />
                    )}
                    {item.reason && (
                      <Typography
                        variant="caption"
                        sx={{
                          fontSize: '0.65rem',
                          color: 'text.secondary',
                          fontStyle: 'italic',
                          display: 'block',
                          mt: 0.25,
                          lineHeight: 1.3,
                        }}
                      >
                        Why queued? {item.reason}
                      </Typography>
                    )}
                  </Box>
                </Box>
              ))}

              {/* Total estimated hours */}
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  pt: 0.5,
                  borderTop: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="caption" sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary' }}>
                  Total estimated: {totalQueuedHours}h
                </Typography>
              </Box>
            </>
          )}
        </Box>
      )}
    </Box>
  );
}
