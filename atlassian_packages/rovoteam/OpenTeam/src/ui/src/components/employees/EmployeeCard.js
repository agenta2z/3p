import React, { useState } from 'react';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import Avatar from '@mui/material/Avatar';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import SettingsIcon from '@mui/icons-material/Settings';
import Tooltip from '@mui/material/Tooltip';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import { StatusBadge, ProgressBar } from '../../shared';
import SkillChips from './SkillChips';
import AgentStatsRow from './AgentStatsRow';
import RoleControlPopover from './RoleControlPopover';
import AgentCommHub from './AgentCommHub';

const AI_COLORS = ['#4a90d9', '#7c4dff', '#00bcd4', '#ff7043'];
const HUMAN_COLORS = ['#4caf50', '#ff9800', '#e91e63', '#9c27b0'];

function getAvatarColor(name, type) {
  const colors = type === 'ai' ? AI_COLORS : HUMAN_COLORS;
  let hash = 0;
  for (let i = 0; i < (name || '').length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

function StatBox({ value, label }) {
  return (
    <Box sx={{ textAlign: 'center', flex: 1, minWidth: 50 }}>
      <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1rem', lineHeight: 1.2 }}>
        {value}
      </Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.55rem', lineHeight: 1 }}>
        {label}
      </Typography>
    </Box>
  );
}

/**
 * EmployeeCard — card for a single employee (AI or human).
 *
 * Props:
 *   employee - object from /api/employees
 *     includes: id, name, role, type, status, team_names[], specializations[],
 *     current_task_id, current_task_name, current_task_progress,
 *     metrics { tasks_completed, avg_cycle_time_hours },
 *     active_correspondence { subject, from, preview }
 */
export function EmployeeCard({ employee, roleSkillsMap = {}, roleConfigs = {} }) {
  // Local skill state for editing (AI agents only) — must be before any early return
  const [skills, setSkills] = useState(employee?.specializations || []);
  const [roleControlAnchor, setRoleControlAnchor] = useState(null);

  if (!employee) return null;

  const {
    name,
    role,
    type = 'human',
    status = 'active',
    team_names = [],
    specializations = [],
    current_task_name,
    current_task_progress,
    metrics = {},
    active_correspondence,
  } = employee;

  const isAI = type === 'ai';
  const avatarColor = getAvatarColor(name, type);

  return (
    <Paper
      elevation={0}
      sx={{
        backgroundColor: 'background.paper',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: 3,
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        height: '100%',
      }}
    >
      {/* Header: Avatar + Name + Status */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
        <Avatar
          sx={{
            width: 44,
            height: 44,
            bgcolor: avatarColor,
            fontSize: 20,
            flexShrink: 0,
          }}
        >
          {isAI ? <SmartToyIcon sx={{ fontSize: 24 }} /> : name?.charAt(0)?.toUpperCase()}
        </Avatar>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="body1" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
            {name}
          </Typography>
          {role && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.3 }}>
                {role}
              </Typography>
              {isAI && (
                <Tooltip
                  title={`Configure ${name}'s role settings. Each agent inherits defaults from its role (${role}) but can customize description, mindsets, SOPs, communication rules, and guardrails within allowed bounds.`}
                  arrow
                  placement="top"
                >
                  <Button
                    size="small"
                    startIcon={<SettingsIcon sx={{ fontSize: '12px !important' }} />}
                    onClick={(e) => { e.stopPropagation(); setRoleControlAnchor(e.currentTarget); }}
                    sx={{
                      height: 20,
                      fontSize: '0.6rem',
                      textTransform: 'none',
                      borderRadius: 3,
                      px: 0.75,
                      minWidth: 0,
                      color: 'text.secondary',
                      '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.06)' },
                    }}
                  >
                    Role Control
                  </Button>
                </Tooltip>
              )}
            </Box>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0, alignItems: 'center' }}>
          <Chip
            label={isAI ? 'AI' : 'Human'}
            size="small"
            sx={{
              height: 22,
              backgroundColor: isAI ? 'rgba(74, 144, 217, 0.12)' : 'rgba(76, 175, 80, 0.12)',
              color: isAI ? '#4a90d9' : '#4caf50',
              fontWeight: 600,
              fontSize: '0.6rem',
            }}
          />
          <StatusBadge status={status} size="small" />
        </Box>
      </Box>

      {/* Teams */}
      {team_names.length > 0 && (
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.75 }}>
        {team_names.map((teamName, idx) => (
          <Chip
            key={idx}
            label={teamName}
            size="small"
            variant="outlined"
            sx={{
              borderColor: 'rgba(255, 255, 255, 0.12)',
              color: 'text.secondary',
              fontSize: '0.65rem',
            }}
          />
        ))}
      </Box>
      )}

      {/* Specializations / Skills — editable for AI, static for humans */}
      {(isAI ? skills.length > 0 || true : specializations.length > 0) && (
        <SkillChips
          skills={isAI ? skills : specializations}
          role={role}
          agentName={name}
          editable={isAI}
          roleSkillsMap={roleSkillsMap}
          onSkillsChange={isAI ? setSkills : undefined}
        />
      )}

      {/* Current Task */}
      {current_task_name && (
        <Box
          sx={{
            p: 1.25,
            borderRadius: 1.5,
            backgroundColor: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
          }}
        >
          <Typography
            variant="caption"
            sx={{
              color: 'text.secondary',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
              fontWeight: 600,
              fontSize: '0.6rem',
            }}
          >
            Current Task
          </Typography>
          <Typography
            variant="body2"
            sx={{
              fontWeight: 500,
              mt: 0.25,
              mb: 0.75,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {current_task_name}
          </Typography>
          {current_task_progress != null && (
            <ProgressBar percent={current_task_progress} height={5} showLabel />
          )}
        </Box>
      )}

      {/* Stats — AI agents get time-windowed stats, humans get simple counts */}
      {isAI ? (
        <AgentStatsRow metrics={metrics} taskQueue={employee.task_queue} currentTaskId={employee.current_task_id} />
      ) : (
        metrics.tasks_completed != null && (
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <StatBox value={`${metrics.tasks_completed}`} label="Tasks Done" />
            {metrics.code_reviews_done != null && (
              <StatBox value={`${metrics.code_reviews_done}`} label="Reviews" />
            )}
          </Box>
        )
      )}

      {/* Communication — AI agents get interactive hub, humans keep static correspondence */}
      {isAI ? (
        <AgentCommHub agentName={name} agentId={employee.id} />
      ) : (
        active_correspondence && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 0.75,
              p: 1,
              borderRadius: 1,
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
            }}
          >
            <MailOutlineIcon sx={{ fontSize: 14, color: 'text.secondary', mt: 0.25, flexShrink: 0 }} />
            <Box sx={{ minWidth: 0 }}>
              <Typography
                variant="caption"
                sx={{ fontWeight: 500, display: 'block', lineHeight: 1.3 }}
              >
                {active_correspondence.subject || 'Correspondence'}
              </Typography>
              {active_correspondence.preview && (
                <Typography
                  variant="caption"
                  sx={{
                    color: 'text.secondary',
                    display: 'block',
                    lineHeight: 1.3,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {active_correspondence.preview}
                </Typography>
              )}
            </Box>
          </Box>
        )
      )}

      {/* Role Control Popover */}
      {isAI && (
        <RoleControlPopover
          anchorEl={roleControlAnchor}
          open={Boolean(roleControlAnchor)}
          onClose={() => setRoleControlAnchor(null)}
          role={role}
          roleConfig={roleConfigs[role] || null}
        />
      )}

      {/* Spacer to push button to bottom */}
      <Box sx={{ flexGrow: 1 }} />

      {/* View Profile button */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          size="small"
          endIcon={<ArrowForwardIcon sx={{ fontSize: 14 }} />}
          sx={{
            textTransform: 'none',
            color: 'primary.light',
            fontSize: '0.75rem',
            '&:hover': { backgroundColor: 'rgba(74, 144, 217, 0.08)' },
          }}
        >
          View Profile
        </Button>
      </Box>
    </Paper>
  );
}

export default EmployeeCard;
