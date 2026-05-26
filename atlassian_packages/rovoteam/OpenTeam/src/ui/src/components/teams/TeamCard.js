import React from 'react';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import GroupsIcon from '@mui/icons-material/Groups';
import SpeedIcon from '@mui/icons-material/Speed';
import FolderIcon from '@mui/icons-material/Folder';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { SectionCard, PersonChip, ProgressBar, StatusBadge } from '../../shared';

/**
 * StatChip — small inline stat display (label + value).
 */
function StatChip({ label, value, color = 'text.primary' }) {
  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.75,
        px: 1.5,
        py: 0.75,
        borderRadius: 1.5,
        backgroundColor: 'rgba(255, 255, 255, 0.04)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
      }}
    >
      <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{ fontWeight: 600, color, whiteSpace: 'nowrap' }}
      >
        {value}
      </Typography>
    </Box>
  );
}

/**
 * TeamCard — card for a single team with full details.
 *
 * Props:
 *   team - object from /api/teams/{id}?resolve=members,projects
 *          includes: id, name, description, members[], projects[],
 *          sprint_velocity, active_projects_count, completion_rate
 */
export function TeamCard({ team }) {
  if (!team) return null;

  const {
    name,
    description,
    members = [],
    projects = [],
    sprint_velocity,
    active_projects_count,
    completion_rate,
  } = team;

  // Split members into AI agents and humans
  const aiMembers = members.filter((m) => m.type === 'ai');
  const humanMembers = members.filter((m) => m.type !== 'ai');
  const sortedMembers = [...aiMembers, ...humanMembers];

  return (
    <Paper
      elevation={0}
      sx={{
        backgroundColor: 'background.paper',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: 3,
        p: 2.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      {/* Team name + member count badge */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <GroupsIcon sx={{ color: 'primary.light', fontSize: 24 }} />
        <Typography variant="h6" sx={{ fontWeight: 600, flexGrow: 1 }}>
          {name}
        </Typography>
        <Chip
          label={`${members.length} member${members.length !== 1 ? 's' : ''}`}
          size="small"
          sx={{
            backgroundColor: 'rgba(74, 144, 217, 0.12)',
            color: 'primary.light',
            fontWeight: 500,
          }}
        />
      </Box>

      {/* Description */}
      {description && (
        <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.5 }}>
          {description}
        </Typography>
      )}

      {/* Team Composition */}
      {sortedMembers.length > 0 && (
        <SectionCard title="Team Composition" icon={<GroupsIcon sx={{ fontSize: 16 }} />}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {sortedMembers.map((member) => (
              <PersonChip
                key={member.id}
                name={member.name}
                role={member.role}
                type={member.type === 'ai' ? 'ai' : 'human'}
                size="small"
              />
            ))}
          </Box>
        </SectionCard>
      )}

      {/* Team Stats */}
      <SectionCard title="Team Stats" icon={<SpeedIcon sx={{ fontSize: 16 }} />}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {sprint_velocity != null && (
            <StatChip label="Sprint Velocity" value={sprint_velocity} color="primary.light" />
          )}
          <StatChip
            label="Active Projects"
            value={active_projects_count ?? projects.filter((p) => p.status !== 'completed').length}
            color="#ff9800"
          />
          {completion_rate != null && (
            <StatChip
              label="Completion Rate"
              value={`${Math.round(completion_rate)}%`}
              color="#4caf50"
            />
          )}
        </Box>
      </SectionCard>

      {/* Active Projects */}
      {projects.length > 0 && (
        <SectionCard
          title="Active Projects"
          icon={<FolderIcon sx={{ fontSize: 16 }} />}
          collapsible
          defaultExpanded
        >
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {projects.map((project) => (
              <Box key={project.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {project.name}
                  </Typography>
                  {project.status && <StatusBadge status={project.status} size="small" />}
                </Box>
                <ProgressBar
                  percent={project.progress_percent ?? 0}
                  height={6}
                  showLabel
                />
              </Box>
            ))}
          </Box>
        </SectionCard>
      )}

      {/* AI Team Health */}
      {aiMembers.length > 0 && (
        <SectionCard
          title="AI Team Health"
          icon={<SmartToyIcon sx={{ fontSize: 16 }} />}
          collapsible
          defaultExpanded
        >
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {aiMembers.map((agent) => (
              <Box
                key={agent.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  p: 1,
                  borderRadius: 1.5,
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                }}
              >
                <PersonChip name={agent.name} role={agent.role} type="ai" size="small" />
                <Box sx={{ flexGrow: 1, minWidth: 0 }} />
                <StatusBadge status={agent.status || 'active'} size="small" />
                {agent.current_task_name && (
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      maxWidth: 200,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {agent.current_task_name}
                  </Typography>
                )}
              </Box>
            ))}
          </Box>
        </SectionCard>
      )}

      {/* View Team Details button */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
        <Button
          size="small"
          endIcon={<ArrowForwardIcon sx={{ fontSize: 14 }} />}
          sx={{
            textTransform: 'none',
            color: 'primary.light',
            fontSize: '0.8rem',
            '&:hover': { backgroundColor: 'rgba(74, 144, 217, 0.08)' },
          }}
        >
          View Team Details
        </Button>
      </Box>
    </Paper>
  );
}

export default TeamCard;
