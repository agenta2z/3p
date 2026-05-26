/**
 * EmployeeDetailView — full employee profile drill-down.
 *
 * Displays employee info, current task, task queue, sprint metrics,
 * recent activity, and AI-specific sections (thinking, autonomy, decisions).
 *
 * Props:
 *   employeeId - string
 *   onBack     - callback to return to previous view
 */

import React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Avatar from '@mui/material/Avatar';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SecurityIcon from '@mui/icons-material/Security';
import GavelIcon from '@mui/icons-material/Gavel';
import TimelineIcon from '@mui/icons-material/Timeline';
import AssignmentIcon from '@mui/icons-material/Assignment';
import ListAltIcon from '@mui/icons-material/ListAlt';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';
import CancelIcon from '@mui/icons-material/Cancel';
import { useApiData } from '../../hooks/useApiData';
import { StatusBadge, ProgressBar, SectionCard, LoadingIndicator, EmptyState } from '../../shared';

/* ------------------------------------------------------------------ */
/*  Priority color helper                                              */
/* ------------------------------------------------------------------ */

const PRIORITY_COLORS = {
  critical: '#f44336',
  high: '#ff9800',
  medium: '#4a90d9',
  low: '#90a4ae',
};

/* ------------------------------------------------------------------ */
/*  Decision status icon                                               */
/* ------------------------------------------------------------------ */

function DecisionIcon({ status }) {
  switch (status?.toLowerCase()) {
    case 'approved': return <CheckCircleIcon sx={{ fontSize: 16, color: '#4caf50' }} />;
    case 'pending': return <PendingIcon sx={{ fontSize: 16, color: '#ff9800' }} />;
    case 'rejected': return <CancelIcon sx={{ fontSize: 16, color: '#f44336' }} />;
    default: return <PendingIcon sx={{ fontSize: 16, color: '#90a4ae' }} />;
  }
}

/* ------------------------------------------------------------------ */
/*  EmployeeDetailView                                                 */
/* ------------------------------------------------------------------ */

export default function EmployeeDetailView({ employeeId, onBack }) {
  const { data: employee, loading, error } = useApiData(
    employeeId ? `/employees/${employeeId}` : null
  );
  const { data: taskQueue } = useApiData(
    employeeId ? `/employees/${employeeId}/task-queue` : null
  );

  const isAI = employee?.type === 'ai';

  // AI-specific data (only fetched for AI employees)
  const { data: thinking } = useApiData(
    isAI ? `/intelligence/employees/${employeeId}/thinking` : null
  );
  const { data: decisions } = useApiData(
    isAI ? `/intelligence/employees/${employeeId}/decisions` : null
  );
  const { data: autonomy } = useApiData(
    isAI ? `/intelligence/employees/${employeeId}/autonomy` : null
  );

  if (loading) return <LoadingIndicator text="Loading employee profile..." />;

  if (error) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <Typography color="error">Failed to load employee: {error.message}</Typography>
      </Box>
    );
  }

  if (!employee) {
    return (
      <Box>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
          Back
        </Button>
        <EmptyState message="Employee not found" />
      </Box>
    );
  }

  const currentTask = employee.current_task;
  const metrics = employee.sprint_metrics || employee.metrics;
  const activities = employee.recent_activity || employee.activities || [];
  const skills = employee.skills || employee.specializations || [];
  const queueItems = taskQueue?.tasks || taskQueue || [];

  return (
    <Box>
      {/* Back button */}
      <Button startIcon={<ArrowBackIcon />} onClick={onBack} sx={{ mb: 2, textTransform: 'none', color: 'text.secondary' }}>
        Back
      </Button>

      {/* Profile header */}
      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2.5,
          p: 3,
          mb: 3,
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 2,
        }}
      >
        <Avatar
          src={employee.avatar_url}
          sx={{
            width: 72,
            height: 72,
            bgcolor: isAI ? '#1e3a5f' : '#4caf50',
            fontSize: 32,
          }}
        >
          {isAI ? <SmartToyIcon sx={{ fontSize: 36 }} /> : (employee.name?.charAt(0)?.toUpperCase() || <PersonIcon />)}
        </Avatar>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
            <Typography variant="h5" sx={{ fontWeight: 600 }}>
              {employee.name}
            </Typography>
            <StatusBadge status={employee.status} />
            <Chip
              label={isAI ? 'AI Agent' : 'Human'}
              size="small"
              icon={isAI ? <SmartToyIcon sx={{ fontSize: 14 }} /> : <PersonIcon sx={{ fontSize: 14 }} />}
              sx={{
                backgroundColor: isAI ? 'rgba(74, 144, 217, 0.15)' : 'rgba(76, 175, 80, 0.15)',
                color: isAI ? '#4a90d9' : '#4caf50',
                '& .MuiChip-icon': { color: 'inherit' },
              }}
            />
          </Box>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            {employee.role || employee.title}
          </Typography>
          {skills.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {skills.map((skill, idx) => (
                <Chip
                  key={idx}
                  label={typeof skill === 'string' ? skill : skill.name}
                  size="small"
                  variant="outlined"
                  sx={{ borderColor: 'rgba(255,255,255,0.15)', color: 'text.secondary', fontSize: '0.7rem' }}
                />
              ))}
            </Box>
          )}
        </Box>
      </Paper>

      {/* Main content grid */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

        {/* AI-specific: Currently Thinking */}
        {isAI && thinking && (
          <SectionCard title="Currently Thinking" icon={<PsychologyIcon sx={{ fontSize: 18 }} />}>
            <Paper
              elevation={0}
              sx={{
                p: 2,
                backgroundColor: 'rgba(74, 144, 217, 0.06)',
                border: '1px solid rgba(74, 144, 217, 0.15)',
                borderRadius: 2,
                fontStyle: 'italic',
              }}
            >
              <Typography variant="body2" sx={{ color: 'text.primary', lineHeight: 1.6 }}>
                "{thinking.thought || thinking.text || thinking}"
              </Typography>
            </Paper>
          </SectionCard>
        )}

        {/* Current Task */}
        {currentTask && (
          <SectionCard title="Current Task" icon={<AssignmentIcon sx={{ fontSize: 18 }} />}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Typography variant="body1" sx={{ fontWeight: 500 }}>
                {currentTask.title || currentTask.name}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                {currentTask.project && (
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Project: {currentTask.project}
                  </Typography>
                )}
                {currentTask.due_date && (
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Due: {currentTask.due_date}
                  </Typography>
                )}
              </Box>
              {currentTask.progress != null && (
                <ProgressBar percent={currentTask.progress} height={6} />
              )}
              {currentTask.correspondence && (
                <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, lineHeight: 1.5 }}>
                  {currentTask.correspondence}
                </Typography>
              )}
            </Box>
          </SectionCard>
        )}

        {/* Task Queue */}
        <SectionCard title="Task Queue" icon={<ListAltIcon sx={{ fontSize: 18 }} />}>
          {queueItems.length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>No queued tasks</Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {queueItems.map((item, idx) => (
                <Box
                  key={item.id || idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                    p: 1.5,
                    borderRadius: 1.5,
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.04)' },
                    transition: 'background-color 0.15s',
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 700, color: 'text.secondary', minWidth: 24, textAlign: 'right' }}
                  >
                    {idx + 1}.
                  </Typography>
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {item.title || item.name}
                      </Typography>
                      {item.priority && (
                        <Chip
                          label={item.priority}
                          size="small"
                          sx={{
                            height: 18,
                            fontSize: '0.65rem',
                            backgroundColor: PRIORITY_COLORS[item.priority?.toLowerCase()] || '#90a4ae',
                            color: '#fff',
                          }}
                        />
                      )}
                    </Box>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      {item.estimated_hours != null && (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Est: {item.estimated_hours}h
                        </Typography>
                      )}
                      {item.depends_on && (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Depends on: {Array.isArray(item.depends_on) ? item.depends_on.join(', ') : item.depends_on}
                        </Typography>
                      )}
                    </Box>
                    {item.reason && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', display: 'block', mt: 0.25 }}>
                        Why this order: {item.reason}
                      </Typography>
                    )}
                  </Box>
                </Box>
              ))}

              {/* Queue summary */}
              <Divider sx={{ my: 1 }} />
              <Box sx={{ display: 'flex', gap: 3 }}>
                {taskQueue?.total_hours != null && (
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Total: {taskQueue.total_hours}h
                  </Typography>
                )}
                {taskQueue?.sprint_deadline && (
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Sprint deadline: {taskQueue.sprint_deadline}
                  </Typography>
                )}
              </Box>
            </Box>
          )}
        </SectionCard>

        {/* AI-specific: Autonomy Level */}
        {isAI && autonomy && (
          <SectionCard title="Autonomy Level" icon={<SecurityIcon sx={{ fontSize: 18 }} />}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {/* Level indicator */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body1" sx={{ fontWeight: 600 }}>
                  Level {autonomy.level ?? '?'}
                </Typography>
                {autonomy.label && (
                  <Chip label={autonomy.label} size="small" sx={{ backgroundColor: 'rgba(74,144,217,0.15)', color: '#4a90d9' }} />
                )}
                {autonomy.description && (
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    {autonomy.description}
                  </Typography>
                )}
              </Box>

              {/* Recent autonomous decisions */}
              {autonomy.recent_decisions?.length > 0 && (
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', mb: 1 }}>
                    Recent Autonomous Decisions
                  </Typography>
                  {autonomy.recent_decisions.map((d, idx) => (
                    <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
                      <DecisionIcon status={d.status} />
                      <Typography variant="body2">{d.title || d.description}</Typography>
                    </Box>
                  ))}
                </Box>
              )}

              {/* Pending approvals */}
              {autonomy.pending_approvals?.length > 0 && (
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', mb: 1 }}>
                    Pending Approvals
                  </Typography>
                  {autonomy.pending_approvals.map((a, idx) => (
                    <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
                      <PendingIcon sx={{ fontSize: 16, color: '#ff9800' }} />
                      <Typography variant="body2">{a.title || a.description}</Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          </SectionCard>
        )}

        {/* AI-specific: Decision Log */}
        {isAI && decisions?.length > 0 && (
          <SectionCard title="Decision Log" icon={<GavelIcon sx={{ fontSize: 18 }} />}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
              {(Array.isArray(decisions) ? decisions : []).map((d, idx) => (
                <Box
                  key={d.id || idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    p: 1,
                    borderRadius: 1,
                    backgroundColor: 'rgba(255,255,255,0.02)',
                  }}
                >
                  <DecisionIcon status={d.status} />
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {d.title || d.description}
                    </Typography>
                    {d.timestamp && (
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {d.timestamp}
                      </Typography>
                    )}
                  </Box>
                  {d.status && (
                    <Chip
                      label={d.status}
                      size="small"
                      sx={{
                        height: 20,
                        fontSize: '0.65rem',
                        backgroundColor:
                          d.status === 'approved' ? 'rgba(76,175,80,0.15)' :
                          d.status === 'rejected' ? 'rgba(244,67,54,0.15)' :
                          'rgba(255,152,0,0.15)',
                        color:
                          d.status === 'approved' ? '#4caf50' :
                          d.status === 'rejected' ? '#f44336' :
                          '#ff9800',
                      }}
                    />
                  )}
                </Box>
              ))}
            </Box>
          </SectionCard>
        )}

        {/* Sprint Metrics */}
        {metrics && (
          <SectionCard title="Sprint Metrics" icon={<TimelineIcon sx={{ fontSize: 18 }} />}>
            <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {metrics.tasks_completed != null && (
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Tasks Completed</Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>{metrics.tasks_completed}</Typography>
                </Box>
              )}
              {metrics.avg_cycle_time != null && (
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Avg Cycle Time</Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>{metrics.avg_cycle_time}</Typography>
                </Box>
              )}
              {metrics.code_reviews != null && (
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Code Reviews</Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>{metrics.code_reviews}</Typography>
                </Box>
              )}
              {metrics.utilization != null && (
                <Box>
                  <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>Utilization</Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>{metrics.utilization}%</Typography>
                </Box>
              )}
            </Box>
          </SectionCard>
        )}

        {/* Recent Activity */}
        {activities.length > 0 && (
          <SectionCard title="Recent Activity" icon={<TimelineIcon sx={{ fontSize: 18 }} />}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {activities.map((activity, idx) => (
                <Box
                  key={activity.id || idx}
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                    py: 1,
                    borderBottom: idx < activities.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  }}
                >
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      backgroundColor: '#4a90d9',
                      mt: 0.75,
                      flexShrink: 0,
                    }}
                  />
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ lineHeight: 1.4 }}>
                      {activity.description || activity.text || activity.message}
                    </Typography>
                    {activity.timestamp && (
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        {activity.timestamp}
                      </Typography>
                    )}
                  </Box>
                </Box>
              ))}
            </Box>
          </SectionCard>
        )}
      </Box>
    </Box>
  );
}
