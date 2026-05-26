import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import GroupIcon from '@mui/icons-material/Group';
import SprintIcon from '@mui/icons-material/Loop';

function formatDueDate(dueDate) {
  if (!dueDate) return 'No due date';
  try {
    const date = new Date(dueDate);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dueDate;
  }
}

function formatTeamComposition(comp) {
  if (!comp) return null;
  const parts = [];
  if (comp.humans != null) parts.push(`${comp.humans} human${comp.humans !== 1 ? 's' : ''}`);
  if (comp.ai_agents != null) parts.push(`${comp.ai_agents} AI agent${comp.ai_agents !== 1 ? 's' : ''}`);
  return parts.join(' + ') || null;
}

function formatSprint(sprint) {
  if (!sprint || sprint.current == null || sprint.total == null) return null;
  return `Sprint ${sprint.current} of ${sprint.total}`;
}

function MetaItem({ icon, text }) {
  if (!text) return null;
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
      {icon}
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {text}
      </Typography>
    </Box>
  );
}

export function ProjectMeta({ dueDate, teamComposition, sprint }) {
  const iconSx = { fontSize: 14, color: 'text.secondary' };

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
      <MetaItem icon={<CalendarTodayIcon sx={iconSx} />} text={formatDueDate(dueDate)} />
      <MetaItem icon={<GroupIcon sx={iconSx} />} text={formatTeamComposition(teamComposition)} />
      <MetaItem icon={<SprintIcon sx={iconSx} />} text={formatSprint(sprint)} />
    </Box>
  );
}

export default ProjectMeta;
