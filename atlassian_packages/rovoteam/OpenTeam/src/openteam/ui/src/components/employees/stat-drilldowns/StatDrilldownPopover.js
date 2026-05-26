/**
 * StatDrilldownPopover -- orchestrator that renders the correct drill-down
 * panel based on statType. Lazily imports each drill-down component.
 */

import React, { lazy, Suspense } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import CircularProgress from '@mui/material/CircularProgress';
import CloseIcon from '@mui/icons-material/Close';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import BugReportIcon from '@mui/icons-material/BugReport';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ForumIcon from '@mui/icons-material/Forum';
import { useTheme, alpha } from '@mui/material/styles';

const TaskQueueDrilldown = lazy(() => import('./TaskQueueDrilldown'));
const WorkUptimeDrilldown = lazy(() => import('./WorkUptimeDrilldown'));
const CrashHealedDrilldown = lazy(() => import('./CrashHealedDrilldown'));
const IssuesResolvedDrilldown = lazy(() => import('./IssuesResolvedDrilldown'));
const AiAiChatDrilldown = lazy(() => import('./AIAIChatsDrilldown'));
const AiHumanChatDrilldown = lazy(() => import('./AIHumanChatsDrilldown'));

const STAT_CONFIG = {
  tasks: { icon: AssignmentIcon, title: 'Task Queue' },
  work: { icon: AccessTimeIcon, title: 'Work & Uptime' },
  crashes: { icon: ReportProblemIcon, title: 'Crashes & Healing' },
  issues: { icon: BugReportIcon, title: 'Issues & Resolution' },
  'ai-ai': { icon: SmartToyIcon, title: 'AI-AI Communication' },
  'ai-human': { icon: ForumIcon, title: 'AI-Human Communication' },
};

export default function StatDrilldownPopover({
  anchorEl,
  open,
  onClose,
  statType,
  employeeId,
  allEmployees,
  metrics,
  periodData,
  periodInfo,
  taskQueue,
  currentTaskId,
}) {
  const theme = useTheme();
  const config = STAT_CONFIG[statType] || STAT_CONFIG.tasks;
  const Icon = config.icon;

  const renderDrilldown = () => {
    switch (statType) {
      case 'tasks':
        return (
          <TaskQueueDrilldown
            employeeId={employeeId}
            taskQueue={taskQueue}
            currentTaskId={currentTaskId}
            periodInfo={periodInfo}
          />
        );
      case 'work':
        return (
          <WorkUptimeDrilldown
            employeeId={employeeId}
            periodData={periodData}
            periodInfo={periodInfo}
            metrics={metrics}
          />
        );
      case 'crashes':
        return (
          <CrashHealedDrilldown
            employeeId={employeeId}
            periodData={periodData}
            periodInfo={periodInfo}
          />
        );
      case 'issues':
        return (
          <IssuesResolvedDrilldown
            employeeId={employeeId}
            periodData={periodData}
            periodInfo={periodInfo}
          />
        );
      case 'ai-ai':
        return (
          <AiAiChatDrilldown
            employeeId={employeeId}
            allEmployees={allEmployees}
            periodData={periodData}
            periodInfo={periodInfo}
          />
        );
      case 'ai-human':
        return (
          <AiHumanChatDrilldown
            employeeId={employeeId}
            allEmployees={allEmployees}
            periodData={periodData}
            periodInfo={periodInfo}
          />
        );
      default:
        return (
          <Typography variant="caption" sx={{ p: 2, color: 'text.secondary' }}>
            Unknown stat type: {statType}
          </Typography>
        );
    }
  };

  return (
    <Popover
      anchorEl={anchorEl}
      open={open}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      transformOrigin={{ vertical: 'top', horizontal: 'center' }}
      PaperProps={{
        sx: {
          width: 520,
          maxHeight: '75vh',
          overflow: 'auto',
          backgroundColor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          p: 1.5,
          pb: 1,
          borderBottom: '1px solid',
          borderColor: 'divider',
          position: 'sticky',
          top: 0,
          backgroundColor: 'background.paper',
          zIndex: 1,
        }}
      >
        <Icon sx={{ fontSize: 18, color: 'primary.main' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.8rem', flexGrow: 1 }}>
          {config.title}
        </Typography>
        {periodInfo && (
          <Typography
            variant="caption"
            sx={{
              fontSize: '0.65rem',
              color: 'text.secondary',
              backgroundColor: alpha(theme.palette.primary.main, 0.08),
              px: 0.75,
              py: 0.25,
              borderRadius: 1,
            }}
          >
            {periodInfo.label}
          </Typography>
        )}
        <IconButton size="small" onClick={onClose} sx={{ ml: 0.5, p: 0.5 }}>
          <CloseIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ p: 1.5 }}>
        <Suspense
          fallback={
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={24} />
            </Box>
          }
        >
          {renderDrilldown()}
        </Suspense>
      </Box>
    </Popover>
  );
}
