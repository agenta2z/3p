/**
 * AgentStatsRow — time-windowed AI agent stats with clickable drill-downs.
 *
 * Shows: Tasks/Queued, Work/Uptime, Crashes/Healed, Issues/Resolved, AI-AI Chats, AI-Human Chats
 * Each stat box is clickable — opens a contextual drill-down popover.
 * Period selector is in the header label area (not on the stat boxes).
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import CheckIcon from '@mui/icons-material/Check';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTheme, alpha } from '@mui/material/styles';
import StatDrilldownPopover from './stat-drilldowns/StatDrilldownPopover';

const PERIODS = [
  { key: '24h', label: 'Past 24 hours', days: 1 },
  { key: '7d', label: 'Past 7 days', days: 7 },
  { key: '14d', label: 'Past 14 days', days: 14 },
  { key: '30d', label: 'Past 30 days', days: 30 },
  { key: '6m', label: 'Past 6 months', days: 180 },
  { key: 'all', label: 'All time', days: 365 },
];

function StatBox({ value, sublabel, label, color, onClick, active, statType }) {
  const theme = useTheme();
  return (
    <Box
      onClick={onClick}
      sx={{
        textAlign: 'center',
        flex: 1,
        minWidth: 55,
        cursor: 'pointer',
        borderRadius: 1,
        py: 0.5,
        px: 0.25,
        transition: 'background-color 0.15s',
        backgroundColor: active ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
        borderBottom: active ? `2px solid ${theme.palette.primary.main}` : '2px solid transparent',
        '&:hover': {
          backgroundColor: alpha(theme.palette.primary.main, 0.05),
        },
      }}
    >
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
  if (avgPerDay < 8) return 'error.main';
  return 'text.primary';
}

function getCrashHealColor(crashes, healed, periodDays) {
  if (crashes === 0) return 'text.primary';
  const rate = healed / crashes;
  const crashesPerDay = periodDays > 0 ? crashes / periodDays : 0;
  if (rate < 0.8) return 'error.main';
  if (crashesPerDay > 2) return 'warning.main';
  return 'text.primary';
}

export default function AgentStatsRow({ metrics, taskQueue = [], currentTaskId, employeeId, allEmployees = [] }) {
  const [selectedPeriod, setSelectedPeriod] = useState('7d');
  const [periodAnchorEl, setPeriodAnchorEl] = useState(null);
  const [drilldownType, setDrilldownType] = useState(null);
  const [drilldownAnchorEl, setDrilldownAnchorEl] = useState(null);

  const timeSeries = metrics?.time_series || {};
  const periodData = timeSeries[selectedPeriod] || {};
  const periodInfo = PERIODS.find(p => p.key === selectedPeriod) || PERIODS[1];

  // Tasks
  const activeTasks = currentTaskId ? 1 : 0;
  const queuedTasks = taskQueue?.length || 0;
  const totalQueuedHours = (taskQueue || []).reduce((sum, t) => sum + (t.estimated_hours || 0), 0);
  const taskQueueColor = totalQueuedHours > 8 ? 'warning.main' : 'text.primary';

  // Metrics
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
  const issueColor = issues > 0 && resolved / issues < 0.8 ? 'error.main' : 'text.primary';

  if (!timeSeries || Object.keys(timeSeries).length === 0) {
    return null;
  }

  const handleStatClick = (statType) => (e) => {
    e.stopPropagation();
    if (drilldownType === statType) {
      // Toggle off if same stat clicked
      setDrilldownType(null);
      setDrilldownAnchorEl(null);
    } else {
      setDrilldownType(statType);
      setDrilldownAnchorEl(e.currentTarget);
    }
  };

  const handlePeriodClick = (e) => {
    e.stopPropagation();
    setPeriodAnchorEl(e.currentTarget);
  };

  const handlePeriodSelect = (periodKey) => {
    setSelectedPeriod(periodKey);
    setPeriodAnchorEl(null);
    // Close drill-down on period change
    setDrilldownType(null);
    setDrilldownAnchorEl(null);
  };

  const handleDrilldownClose = () => {
    setDrilldownType(null);
    setDrilldownAnchorEl(null);
  };

  return (
    <>
      <Box
        sx={{
          borderRadius: 1.5,
          p: 1,
          backgroundColor: 'action.hover',
          border: '1px solid', borderColor: 'divider',
        }}
      >
        {/* Period label — only this area opens the period selector */}
        <Box
          onClick={handlePeriodClick}
          sx={{
            display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75,
            cursor: 'pointer',
            '&:hover': { opacity: 0.8 },
          }}
        >
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

        {/* Stats row — each box individually clickable */}
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <StatBox
            value={`${activeTasks}/${queuedTasks}`}
            sublabel={totalQueuedHours > 0 ? `~${totalQueuedHours}h queued` : 'no queue'}
            label="Tasks / Queued"
            color={taskQueueColor}
            statType="tasks"
            active={drilldownType === 'tasks'}
            onClick={handleStatClick('tasks')}
          />
          <StatBox
            value={`${work}h/${uptime}h`}
            sublabel={`${periodInfo.days > 0 ? (work / periodInfo.days).toFixed(1) : 0}h/day`}
            label="Work / Uptime"
            color={workColor}
            statType="work"
            active={drilldownType === 'work'}
            onClick={handleStatClick('work')}
          />
          <StatBox
            value={`${crashes}/${healed}`}
            sublabel={crashes > 0 ? `${Math.round((healed / crashes) * 100)}% healed` : 'no crashes'}
            label="Crashes / Healed"
            color={crashColor}
            statType="crashes"
            active={drilldownType === 'crashes'}
            onClick={handleStatClick('crashes')}
          />
          <StatBox
            value={`${issues}/${resolved}`}
            sublabel={issues > 0 ? `${Math.round((resolved / issues) * 100)}% resolved` : 'no issues'}
            label="Issues / Resolved"
            color={issueColor}
            statType="issues"
            active={drilldownType === 'issues'}
            onClick={handleStatClick('issues')}
          />
          <StatBox
            value={`${aiAiMsgs}`}
            sublabel={aiAiThreads > 0 ? `${aiAiThreads} threads` : ''}
            label="AI-AI Chats"
            statType="ai-ai"
            active={drilldownType === 'ai-ai'}
            onClick={handleStatClick('ai-ai')}
          />
          <StatBox
            value={`${aiHumanMsgs}`}
            sublabel={aiHumanThreads > 0 ? `${aiHumanThreads} threads` : ''}
            label="AI-Human"
            statType="ai-human"
            active={drilldownType === 'ai-human'}
            onClick={handleStatClick('ai-human')}
          />
        </Box>
      </Box>

      {/* Period selector menu */}
      <Menu
        anchorEl={periodAnchorEl}
        open={Boolean(periodAnchorEl)}
        onClose={() => setPeriodAnchorEl(null)}
        PaperProps={{
          sx: {
            backgroundColor: 'background.paper',
            border: '1px solid', borderColor: 'divider',
            minWidth: 180,
          },
        }}
      >
        {PERIODS.map((period) => (
          <MenuItem
            key={period.key}
            onClick={() => handlePeriodSelect(period.key)}
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

      {/* Stat drill-down popover */}
      <StatDrilldownPopover
        anchorEl={drilldownAnchorEl}
        open={Boolean(drilldownType)}
        onClose={handleDrilldownClose}
        statType={drilldownType}
        employeeId={employeeId}
        allEmployees={allEmployees}
        metrics={metrics}
        periodData={periodData}
        periodInfo={periodInfo}
        taskQueue={taskQueue}
        currentTaskId={currentTaskId}
      />
    </>
  );
}
