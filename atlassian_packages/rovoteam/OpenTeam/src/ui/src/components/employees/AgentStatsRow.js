/**
 * AgentStatsRow — time-windowed AI agent stats with period selector.
 *
 * Shows: Work/Uptime ratio, Crashes/Healed, AI-AI msgs/threads, AI-Human msgs/threads
 * Work time turns red if below 8h/day average for the period.
 * Crashes/Healed turns red if heal rate < 80%.
 * Entire row clickable to change period.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import CheckIcon from '@mui/icons-material/Check';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const PERIODS = [
  { key: '24h', label: 'Past 24 hours', days: 1 },
  { key: '7d', label: 'Past 7 days', days: 7 },
  { key: '14d', label: 'Past 14 days', days: 14 },
  { key: '30d', label: 'Past 30 days', days: 30 },
  { key: '6m', label: 'Past 6 months', days: 180 },
  { key: 'all', label: 'All time', days: 365 },
];

function StatBox({ value, sublabel, label, color }) {
  return (
    <Box sx={{ textAlign: 'center', flex: 1, minWidth: 55 }}>
      <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '0.85rem', lineHeight: 1.2, color: color || 'text.primary' }}>
        {value}
      </Typography>
      {sublabel && (
        <Typography variant="caption" sx={{ color: color || 'text.secondary', fontSize: '0.5rem', lineHeight: 1, display: 'block' }}>
          {sublabel}
        </Typography>
      )}
      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.55rem', lineHeight: 1, mt: 0.25, display: 'block' }}>
        {label}
      </Typography>
    </Box>
  );
}

function getWorkRateColor(workHours, periodDays) {
  if (!periodDays || !workHours) return 'text.primary';
  const avgPerDay = workHours / periodDays;
  if (avgPerDay < 8) return '#f44336'; // below 8h/day → red
  return 'text.primary';
}

function getCrashHealColor(crashes, healed, periodDays) {
  if (crashes === 0) return 'text.primary';
  const rate = healed / crashes;
  const crashesPerDay = periodDays > 0 ? crashes / periodDays : 0;
  if (rate < 0.8) return '#f44336'; // low heal rate → red
  if (crashesPerDay > 2) return '#ff9800'; // >2 crashes/day → yellow
  return 'text.primary';
}

export default function AgentStatsRow({ metrics, taskQueue = [], currentTaskId }) {
  const [selectedPeriod, setSelectedPeriod] = useState('7d');
  const [anchorEl, setAnchorEl] = useState(null);

  const timeSeries = metrics?.time_series || {};
  const periodData = timeSeries[selectedPeriod] || {};

  // Tasks: active (has current task) + queued count
  const activeTasks = currentTaskId ? 1 : 0;
  const queuedTasks = taskQueue?.length || 0;
  const totalQueuedHours = (taskQueue || []).reduce((sum, t) => sum + (t.estimated_hours || 0), 0);
  // Yellow if queued estimated time > 8 hours (1 work day)
  const taskQueueColor = totalQueuedHours > 8 ? '#ff9800' : 'text.primary';
  const periodInfo = PERIODS.find(p => p.key === selectedPeriod) || PERIODS[1];

  const uptime = periodData.uptime_hours ?? 0;
  const work = periodData.work_hours ?? 0;
  const crashes = periodData.crashes ?? 0;
  const healed = periodData.healed ?? 0;
  const issues = periodData.issues ?? 0;
  const resolved = periodData.resolved ?? 0;
  const aiAiMsgs = periodData.ai_ai_chats ?? 0;
  const aiAiThreads = periodData.ai_ai_threads ?? 0;
  const aiHumanMsgs = periodData.ai_human_chats ?? 0;
  const aiHumanThreads = periodData.ai_human_threads ?? 0;

  const workColor = getWorkRateColor(work, periodInfo.days);
  const crashColor = getCrashHealColor(crashes, healed, periodInfo.days);
  const issueColor = issues > 0 && resolved / issues < 0.8 ? '#f44336' : 'text.primary';

  if (!timeSeries || Object.keys(timeSeries).length === 0) {
    return null;
  }

  return (
    <>
      <Box
        onClick={(e) => setAnchorEl(e.currentTarget)}
        sx={{
          cursor: 'pointer',
          borderRadius: 1.5,
          p: 1,
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.04)',
          transition: 'background-color 0.15s, border-color 0.15s',
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.04)',
            borderColor: 'rgba(255, 255, 255, 0.08)',
          },
        }}
      >
        {/* Period label */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75 }}>
          <Typography
            variant="caption"
            sx={{
              color: 'primary.light',
              fontSize: '0.6rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 0.3,
            }}
          >
            {periodInfo.label}
          </Typography>
          <ExpandMoreIcon sx={{ fontSize: 12, color: 'primary.light', opacity: 0.7 }} />
        </Box>

        {/* Stats row */}
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <StatBox
            value={`${activeTasks}/${queuedTasks}`}
            sublabel={totalQueuedHours > 0 ? `~${totalQueuedHours}h queued` : 'no queue'}
            label="Tasks / Queued"
            color={taskQueueColor}
          />
          <StatBox
            value={`${work}h/${uptime}h`}
            sublabel={`${periodInfo.days > 0 ? (work / periodInfo.days).toFixed(1) : 0}h/day`}
            label="Work / Uptime"
            color={workColor}
          />
          <StatBox
            value={`${crashes}/${healed}`}
            sublabel={crashes > 0 ? `${Math.round((healed / crashes) * 100)}% healed` : 'no crashes'}
            label="Crashes / Healed"
            color={crashColor}
          />
          <StatBox
            value={`${issues}/${resolved}`}
            sublabel={issues > 0 ? `${Math.round((resolved / issues) * 100)}% resolved` : 'no issues'}
            label="Issues / Resolved"
            color={issueColor}
          />
          <StatBox
            value={`${aiAiMsgs}`}
            sublabel={aiAiThreads > 0 ? `${aiAiThreads} threads` : ''}
            label="AI-AI Chats"
          />
          <StatBox
            value={`${aiHumanMsgs}`}
            sublabel={aiHumanThreads > 0 ? `${aiHumanThreads} threads` : ''}
            label="AI-Human"
          />
        </Box>
      </Box>

      {/* Period selector menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        PaperProps={{
          sx: {
            backgroundColor: 'background.paper',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            minWidth: 180,
          },
        }}
      >
        {PERIODS.map((period) => (
          <MenuItem
            key={period.key}
            onClick={() => { setSelectedPeriod(period.key); setAnchorEl(null); }}
            selected={period.key === selectedPeriod}
            sx={{ fontSize: '0.85rem' }}
          >
            {period.key === selectedPeriod && (
              <ListItemIcon sx={{ minWidth: 28 }}>
                <CheckIcon sx={{ fontSize: 16, color: 'primary.light' }} />
              </ListItemIcon>
            )}
            {period.key !== selectedPeriod && <Box sx={{ width: 28 }} />}
            {period.label}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
