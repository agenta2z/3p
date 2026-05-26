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
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import LockIcon from '@mui/icons-material/Lock';
import GroupsIcon from '@mui/icons-material/Groups';
import Tooltip from '@mui/material/Tooltip';
import HistoryIcon from '@mui/icons-material/History';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import SendIcon from '@mui/icons-material/Send';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import Popover from '@mui/material/Popover';
import TextField from '@mui/material/TextField';
import { StatusBadge, ProgressBar, PendingReasonPopover } from '../../shared';
import SkillChips from './SkillChips';
import AgentStatsRow from './AgentStatsRow';
import RoleControlPopover from './RoleControlPopover';
import OrgCollaborationPopover from './OrgCollaborationPopover';
import PermissionsPopover from './PermissionsPopover';
import AgentCommHub from './AgentCommHub';
import { useTheme, alpha } from '@mui/material/styles';
import { useApiData } from '../../hooks/useApiData';

function getAvatarColor(name, theme) {
  const colors = theme.custom.categorical;
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

function PendingNudge({ agentName, hoursStuck, blockerSummary, blockerName, escalateTarget, theme }) {
  const [draftAnchor, setDraftAnchor] = useState(null);
  const [draftTarget, setDraftTarget] = useState('');
  const [draftText, setDraftText] = useState('');
  const [sent, setSent] = useState(false);

  const openDraft = (target, e) => {
    setDraftAnchor(e.currentTarget);
    setDraftTarget(target);
    setSent(false);
    if (target === blockerName) {
      setDraftText(
        `Hi ${blockerName},\n\n` +
        `Just a friendly follow-up — ${agentName} has been waiting ${hoursStuck}+ hours for your review on: "${blockerSummary}"\n\n` +
        `Would you be able to take a look when you get a chance? If you're unavailable, please let me know and I can arrange an alternate reviewer.\n\n` +
        `Thanks!`
      );
    } else {
      setDraftText(
        `Hi ${escalateTarget},\n\n` +
        `${agentName} has been blocked for ${hoursStuck}+ hours: "${blockerSummary}"\n\n` +
        `The original reviewer (${blockerName}) appears to be unavailable. Could you provide interim approval or designate an alternate reviewer? ${agentName} can resume immediately once unblocked.\n\n` +
        `This is auto-generated based on the pending blocker duration.`
      );
    }
  };

  const handleSend = () => {
    setSent(true);
    setTimeout(() => setDraftAnchor(null), 2000);
  };

  const actionBtnSx = {
    mt: 0.5, height: 22,
    textTransform: 'none', fontSize: '0.6rem',
    borderRadius: 3, px: 1,
  };

  return (
    <>
      <Box
        sx={{
          display: 'flex', alignItems: 'flex-start', gap: 1,
          p: 1.25, borderRadius: 1.5,
          backgroundColor: alpha(theme.palette.warning.main, 0.06),
          border: `1px solid ${alpha(theme.palette.warning.main, 0.2)}`,
        }}
      >
        <WarningAmberIcon sx={{ fontSize: 16, color: theme.palette.warning.main, mt: 0.25, flexShrink: 0 }} />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.warning.main, fontSize: '0.65rem', display: 'block', lineHeight: 1.3 }}>
            Blocked for {hoursStuck}h+ — {blockerSummary}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
            {blockerName && (
              <Button
                size="small"
                startIcon={<AutoFixHighIcon sx={{ fontSize: 12 }} />}
                onClick={(e) => openDraft(blockerName, e)}
                sx={{
                  ...actionBtnSx,
                  color: theme.palette.warning.main,
                  backgroundColor: alpha(theme.palette.warning.main, 0.08),
                  '&:hover': { backgroundColor: alpha(theme.palette.warning.main, 0.15) },
                }}
              >
                Follow up with {blockerName}
              </Button>
            )}
            <Button
              size="small"
              startIcon={<AutoFixHighIcon sx={{ fontSize: 12 }} />}
              onClick={(e) => openDraft(escalateTarget, e)}
              sx={{
                ...actionBtnSx,
                color: theme.palette.primary.main,
                backgroundColor: alpha(theme.palette.primary.main, 0.08),
                '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.15) },
              }}
            >
              Escalate to {escalateTarget}
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Draft message popover */}
      <Popover
        open={Boolean(draftAnchor)}
        anchorEl={draftAnchor}
        onClose={() => setDraftAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        PaperProps={{
          sx: {
            width: 420, maxHeight: '60vh',
            backgroundColor: 'background.paper',
            border: '1px solid', borderColor: 'divider',
            borderRadius: 2, p: 2, overflow: 'auto',
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
          <AutoFixHighIcon sx={{ fontSize: 16, color: theme.palette.primary.main }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
            AI-Generated Draft
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', ml: 'auto' }}>
            To: {draftTarget}
          </Typography>
        </Box>
        {sent ? (
          <Box sx={{
            p: 2, textAlign: 'center',
            backgroundColor: alpha(theme.palette.success.main, 0.08),
            borderRadius: 1.5,
            border: `1px solid ${alpha(theme.palette.success.main, 0.2)}`,
          }}>
            <Typography variant="body2" sx={{ color: theme.palette.success.main, fontWeight: 500 }}>
              Message sent to {draftTarget}
            </Typography>
          </Box>
        ) : (
          <>
            <TextField
              multiline
              rows={6}
              fullWidth
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
              variant="outlined"
              size="small"
              sx={{ mb: 1.5, '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
            />
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.75 }}>
              <Button size="small" onClick={() => setDraftAnchor(null)}
                sx={{ textTransform: 'none', fontSize: '0.7rem', color: 'text.secondary' }}>
                Cancel
              </Button>
              <Button size="small" variant="contained" onClick={handleSend}
                startIcon={<SendIcon sx={{ fontSize: 12 }} />}
                sx={{ textTransform: 'none', fontSize: '0.7rem' }}>
                Send to {draftTarget}
              </Button>
            </Box>
          </>
        )}
      </Popover>
    </>
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
export function EmployeeCard({ employee, roleSkillsMap = {}, roleConfigs = {}, orgs = [], allEmployees = [], onEmployeeClick }) {
  // Local skill state for editing (AI agents only) — must be before any early return
  const [skills, setSkills] = useState(employee?.specializations || []);
  const [roleControlAnchor, setRoleControlAnchor] = useState(null);
  const [orgCollabAnchor, setOrgCollabAnchor] = useState(null);
  const [permissionsAnchor, setPermissionsAnchor] = useState(null);
  const [pendingAnchor, setPendingAnchor] = useState(null);
  const theme = useTheme();

  // Fetch org-related data for AI employees
  const isAIEmployee = employee?.type === 'ai';
  const { data: orgMembership } = useApiData(
    isAIEmployee && employee?.id ? `/employees/${employee.id}/org` : null
  );
  const { data: orgTree } = useApiData(
    isAIEmployee && orgMembership?.org_id ? `/orgs/${orgMembership.org_id}/tree` : null
  );
  const { data: collaborationConfig } = useApiData(
    isAIEmployee && employee?.id ? `/employees/${employee.id}/collaboration` : null
  );
  const { data: aclData } = useApiData(
    isAIEmployee && employee?.id ? `/employees/${employee.id}/acl` : null
  );
  const { data: orgDefaultAcl } = useApiData(
    isAIEmployee && orgMembership?.org_id ? `/orgs/${orgMembership.org_id}/default-acl` : null
  );

  // Close other popovers when one opens
  const openOrgCollab = (e) => {
    e.stopPropagation();
    setRoleControlAnchor(null);
    setPermissionsAnchor(null);
    setOrgCollabAnchor(e.currentTarget);
  };
  const openPermissions = (e) => {
    e.stopPropagation();
    setRoleControlAnchor(null);
    setOrgCollabAnchor(null);
    setPermissionsAnchor(e.currentTarget);
  };

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
  const avatarColor = getAvatarColor(name, theme);

  return (
    <Paper
      elevation={0}
      sx={{
        backgroundColor: 'background.paper',
        border: '1px solid', borderColor: 'divider',
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
            {isAI && orgMembership?.reports_to && (() => {
              const mgr = allEmployees.find(e => e.id === orgMembership.reports_to);
              return mgr ? (
                <Typography component="span" sx={{ fontWeight: 400, color: 'text.secondary', fontSize: '0.75rem', ml: 0.75 }}>
                  (report to: {mgr.name})
                </Typography>
              ) : null;
            })()}
          </Typography>
          {role && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.3 }}>
                {role}
              </Typography>
              {isAI && (
                <>
                  <Tooltip
                    title={`Configure ${name}'s role settings — description, mindsets, SOPs, communication rules, and guardrails.`}
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
                        '&:hover': { backgroundColor: 'action.selected' },
                      }}
                    >
                      Role Control
                    </Button>
                  </Tooltip>
                  <Button
                    size="small"
                    startIcon={<AccountTreeIcon sx={{ fontSize: '12px !important' }} />}
                    onClick={openOrgCollab}
                    sx={{
                      height: 20,
                      fontSize: '0.6rem',
                      textTransform: 'none',
                      borderRadius: 3,
                      px: 0.75,
                      minWidth: 0,
                      color: 'text.secondary',
                      '&:hover': { backgroundColor: 'action.selected' },
                    }}
                  >
                    Org & Collab
                  </Button>
                  <Button
                    size="small"
                    startIcon={<LockIcon sx={{ fontSize: '12px !important' }} />}
                    onClick={openPermissions}
                    sx={{
                      height: 20,
                      fontSize: '0.6rem',
                      textTransform: 'none',
                      borderRadius: 3,
                      px: 0.75,
                      minWidth: 0,
                      color: 'text.secondary',
                      '&:hover': { backgroundColor: 'action.selected' },
                    }}
                  >
                    Permissions
                  </Button>
                </>
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
              backgroundColor: isAI ? 'action.selected' : 'action.hover',
              color: isAI ? 'primary.main' : 'success.main',
              fontWeight: 600,
              fontSize: '0.6rem',
            }}
          />
          <Box
            onClick={employee.pending_reason ? (e) => { e.stopPropagation(); setPendingAnchor(e.currentTarget); } : undefined}
            sx={employee.pending_reason ? { cursor: 'pointer', '&:hover': { opacity: 0.8 } } : {}}
          >
            <StatusBadge status={status} size="small" />
          </Box>
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
              borderColor: 'divider',
              color: 'text.secondary',
              fontSize: '0.65rem',
            }}
          />
        ))}
      </Box>
      )}

      {/* Skills — AI employees only */}
      {isAI && (
        <SkillChips
          skills={skills}
          role={role}
          agentName={name}
          editable
          roleSkillsMap={roleSkillsMap}
          onSkillsChange={setSkills}
        />
      )}

      {/* Current Task */}
      {current_task_name && (
        <Box
          sx={{
            p: 1.25,
            borderRadius: 1.5,
            backgroundColor: 'action.hover',
            border: '1px solid', borderColor: 'divider',
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
        <AgentStatsRow metrics={metrics} taskQueue={employee.task_queue} currentTaskId={employee.current_task_id} employeeId={employee.id} allEmployees={allEmployees} />
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

      {/* Pending nudge — smart action suggestion for stale blockers */}
      {isAI && employee.pending_reason && (() => {
        const pendingSince = employee.pending_reason.pending_since;
        const hoursStuck = pendingSince ? Math.floor((Date.now() - new Date(pendingSince).getTime()) / 3600000) : 0;
        const escalateOption = employee.pending_reason.resolution?.options?.find(o => o.action_type === 'escalate');
        const escalateTarget = escalateOption?.label?.replace('Escalate to ', '') || 'the team lead';
        const blockerSummary = employee.pending_reason.summary || 'Pending blocker';
        // Extract blocker name from summary (e.g., "Waiting for schema approval from Dylan Park")
        const fromMatch = blockerSummary.match(/from\s+(.+?)(?:\s*\(|$)/);
        const blockerName = fromMatch ? fromMatch[1].trim() : null;

        return hoursStuck > 12 ? (
          <PendingNudge
            agentName={name}
            hoursStuck={hoursStuck}
            blockerSummary={blockerSummary}
            blockerName={blockerName}
            escalateTarget={escalateTarget}
            theme={theme}
          />
        ) : null;
      })()}

      {/* Communication — humans also get Send Message / Send Email (in bottom row) */}

      {/* Popovers (rendered but not visible until anchor is set) */}
      {isAI && (
        <RoleControlPopover
          anchorEl={roleControlAnchor}
          open={Boolean(roleControlAnchor)}
          onClose={() => setRoleControlAnchor(null)}
          role={role}
          roleConfig={roleConfigs[role] || null}
        />
      )}
      {isAI && (
        <OrgCollaborationPopover
          anchorEl={orgCollabAnchor}
          open={Boolean(orgCollabAnchor)}
          onClose={() => setOrgCollabAnchor(null)}
          employee={employee}
          orgMembership={orgMembership}
          orgTree={orgTree}
          allOrgs={orgs}
          allEmployees={allEmployees}
          collaborationConfig={collaborationConfig}
        />
      )}
      {isAI && (
        <PermissionsPopover
          anchorEl={permissionsAnchor}
          open={Boolean(permissionsAnchor)}
          onClose={() => setPermissionsAnchor(null)}
          employeeId={employee.id}
          aclData={aclData}
          orgDefaultAcl={orgDefaultAcl}
        />
      )}
      {employee.pending_reason && (
        <PendingReasonPopover
          anchorEl={pendingAnchor}
          open={Boolean(pendingAnchor)}
          onClose={() => setPendingAnchor(null)}
          reasons={[{
            ...employee.pending_reason,
            task_title: employee.current_task_name || employee.pending_reason?.summary,
          }]}
        />
      )}

      {/* Spacer to push bottom row down */}
      <Box sx={{ flexGrow: 1 }} />

      {/* Bottom row: Send actions (left) | View actions (right) */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <AgentCommHub agentName={name} agentId={employee.id} hideHistory />
        <Box sx={{ flexGrow: 1 }} />
        {isAI && (
          <Button
            size="small"
            endIcon={<HistoryIcon sx={{ fontSize: 14 }} />}
            sx={{
              textTransform: 'none',
              color: 'primary.light',
              fontSize: '0.75rem',
              flexShrink: 0,
              '&:hover': { backgroundColor: 'action.hover' },
            }}
          >
            View History
          </Button>
        )}
        <Button
          size="small"
          endIcon={<ArrowForwardIcon sx={{ fontSize: 14 }} />}
          onClick={() => onEmployeeClick?.(employee.id)}
          sx={{
            textTransform: 'none',
            color: 'primary.light',
            fontSize: '0.75rem',
            flexShrink: 0,
            '&:hover': { backgroundColor: 'action.hover' },
          }}
        >
          View Profile
        </Button>
      </Box>
    </Paper>
  );
}

export default EmployeeCard;
