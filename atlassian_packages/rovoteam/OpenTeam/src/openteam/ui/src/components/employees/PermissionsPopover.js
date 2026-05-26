/**
 * PermissionsPopover — fine-grained ACL permission panel for AI employees.
 *
 * Four tabs:
 * 1. Data Access
 * 2. Actions
 * 3. Communication
 * 4. System Access
 *
 * Supports org-default inheritance with per-employee overrides.
 */

import React, { useState, useEffect } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Switch from '@mui/material/Switch';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import StorageIcon from '@mui/icons-material/Storage';
import BuildIcon from '@mui/icons-material/Build';
import ForumIcon from '@mui/icons-material/Forum';
import DnsIcon from '@mui/icons-material/Dns';
import LockIcon from '@mui/icons-material/Lock';
import { useTheme, alpha } from '@mui/material/styles';

const PERMISSION_SCHEMA = {
  data_access: {
    label: 'Data Access',
    icon: <StorageIcon sx={{ fontSize: 16 }} />,
    permissions: [
      { key: 'read_project_data', label: 'Read Project Data', desc: 'View project details, tasks, and sprints' },
      { key: 'read_employee_data', label: 'Read Employee Data', desc: 'View other employees\' profiles and metrics' },
      { key: 'read_financials', label: 'Read Financials', desc: 'View budget, cost, and billing data' },
      { key: 'read_audit_logs', label: 'Read Audit Logs', desc: 'View system audit trail' },
      { key: 'read_analytics', label: 'Read Analytics', desc: 'View dashboard analytics and reports' },
    ],
  },
  actions: {
    label: 'Actions',
    icon: <BuildIcon sx={{ fontSize: 16 }} />,
    permissions: [
      { key: 'deploy_code', label: 'Deploy Code', desc: 'Trigger deployments to staging/production' },
      { key: 'approve_prs', label: 'Approve PRs', desc: 'Approve pull requests' },
      { key: 'create_tasks', label: 'Create Tasks', desc: 'Create new tasks in any project' },
      { key: 'modify_sprints', label: 'Modify Sprints', desc: 'Change sprint scope, dates, assignments' },
      { key: 'merge_to_main', label: 'Merge to Main', desc: 'Merge code to main/production branch' },
      { key: 'create_projects', label: 'Create Projects', desc: 'Create new projects' },
      { key: 'delete_resources', label: 'Delete Resources', desc: 'Delete tasks, projects, or artifacts' },
      { key: 'manage_team_members', label: 'Manage Team Members', desc: 'Add/remove team members' },
    ],
  },
  communication: {
    label: 'Communication',
    icon: <ForumIcon sx={{ fontSize: 16 }} />,
    permissions: [
      { key: 'initiate_conversations', label: 'Initiate Conversations', desc: 'Start new conversation threads' },
      { key: 'send_external_emails', label: 'Send External Emails', desc: 'Send email outside the organization' },
      { key: 'post_to_slack', label: 'Post to Slack', desc: 'Post messages to Slack channels' },
      { key: 'create_calendar_events', label: 'Create Calendar Events', desc: 'Create/modify calendar events' },
    ],
  },
  system_access: {
    label: 'System Access',
    icon: <DnsIcon sx={{ fontSize: 16 }} />,
    permissions: [
      { key: 'access_cicd', label: 'Access CI/CD', desc: 'Access CI/CD pipelines' },
      { key: 'access_databases', label: 'Access Databases', desc: 'Direct database access (read/write)' },
      { key: 'access_cloud_resources', label: 'Access Cloud Resources', desc: 'Access AWS/GCP/Azure console' },
      { key: 'access_secrets_vault', label: 'Access Secrets Vault', desc: 'Access secrets/credentials manager' },
    ],
  },
};

const CATEGORIES = Object.keys(PERMISSION_SCHEMA);

function formatPermissionLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function PermissionsPopover({
  anchorEl,
  open,
  onClose,
  employeeId,
  aclData,
  orgDefaultAcl,
}) {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);
  const [inheritFromOrg, setInheritFromOrg] = useState(true);
  const [entries, setEntries] = useState([]);

  // Initialize from props
  useEffect(() => {
    if (aclData) {
      setInheritFromOrg(aclData.inherited_from_org ?? true);
      setEntries(aclData.entries || []);
    } else if (orgDefaultAcl) {
      setInheritFromOrg(true);
      setEntries(orgDefaultAcl.entries || []);
    }
  }, [aclData, orgDefaultAcl]);

  const getEntryValue = (category, permission) => {
    const source = inheritFromOrg ? (orgDefaultAcl?.entries || []) : entries;
    const entry = source.find(e => e.category === category && e.permission === permission);
    return entry?.granted ?? false;
  };

  const togglePermission = (category, permission) => {
    if (inheritFromOrg) return;
    setEntries(prev => {
      const idx = prev.findIndex(e => e.category === category && e.permission === permission);
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = { ...updated[idx], granted: !updated[idx].granted };
        return updated;
      }
      return [...prev, { category, permission, granted: true }];
    });
  };

  const handleInheritToggle = () => {
    if (inheritFromOrg) {
      // Switching to custom: copy org defaults as starting point
      setEntries(orgDefaultAcl?.entries ? [...orgDefaultAcl.entries] : []);
    }
    setInheritFromOrg(!inheritFromOrg);
  };

  const handleResetToDefaults = () => {
    setInheritFromOrg(true);
    setEntries(orgDefaultAcl?.entries || []);
  };

  const getCategoryCount = (category) => {
    const schema = PERMISSION_SCHEMA[category];
    const total = schema.permissions.length;
    const granted = schema.permissions.filter(p => getEntryValue(category, p.key)).length;
    return { granted, total };
  };

  const currentCategory = CATEGORIES[activeTab];
  const schema = PERMISSION_SCHEMA[currentCategory];

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      slotProps={{
        paper: {
          sx: {
            width: 460,
            maxHeight: '80vh',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
          },
        },
      }}
    >
      {/* Header */}
      <Box sx={{ px: 2, pt: 1.5, pb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <LockIcon sx={{ fontSize: 18, color: 'primary.main' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
            Permissions
          </Typography>
        </Box>
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
          Fine-grained access control for this AI employee
        </Typography>

        {/* Inherit toggle */}
        <Box sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          backgroundColor: inheritFromOrg ? alpha(theme.palette.info.main, 0.08) : 'action.hover',
          border: '1px solid', borderColor: inheritFromOrg ? alpha(theme.palette.info.main, 0.3) : 'divider',
          borderRadius: 1.5, px: 1.5, py: 0.75, mb: 1,
        }}>
          <Box>
            <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
              Use Org Defaults
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>
              {inheritFromOrg ? 'Permissions inherited from organization template' : 'Custom permissions active'}
            </Typography>
          </Box>
          <Switch
            size="small"
            checked={inheritFromOrg}
            onChange={handleInheritToggle}
          />
        </Box>
      </Box>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        variant="fullWidth"
        sx={{
          minHeight: 36,
          borderBottom: '1px solid',
          borderColor: 'divider',
          '& .MuiTab-root': { minHeight: 36, py: 0.5, fontSize: '0.7rem', textTransform: 'none' },
        }}
      >
        {CATEGORIES.map(cat => {
          const { granted, total } = getCategoryCount(cat);
          return (
            <Tab
              key={cat}
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {PERMISSION_SCHEMA[cat].icon}
                  <span>{PERMISSION_SCHEMA[cat].label}</span>
                  <Chip
                    label={`${granted}/${total}`}
                    size="small"
                    sx={{
                      height: 18, fontSize: '0.6rem', ml: 0.25,
                      backgroundColor: granted === total
                        ? alpha(theme.palette.success.main, 0.15)
                        : granted > 0
                          ? alpha(theme.palette.warning.main, 0.15)
                          : alpha(theme.palette.error.main, 0.1),
                      color: granted === total
                        ? theme.palette.success.main
                        : granted > 0
                          ? theme.palette.warning.main
                          : theme.palette.error.main,
                    }}
                  />
                </Box>
              }
            />
          );
        })}
      </Tabs>

      {/* Permission list */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5 }}>
        {schema.permissions.map((perm, idx) => {
          const granted = getEntryValue(currentCategory, perm.key);
          return (
            <Box
              key={perm.key}
              sx={{
                display: 'flex', alignItems: 'flex-start', gap: 0.5,
                py: 0.75,
                borderBottom: idx < schema.permissions.length - 1 ? '1px solid' : 'none',
                borderColor: 'divider',
                opacity: inheritFromOrg ? 0.7 : 1,
              }}
            >
              <Checkbox
                size="small"
                checked={granted}
                disabled={inheritFromOrg}
                onChange={() => togglePermission(currentCategory, perm.key)}
                sx={{ p: 0.25, mt: 0.25 }}
              />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>
                  {perm.label}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>
                  {perm.desc}
                </Typography>
              </Box>
              <Chip
                label={granted ? 'Granted' : 'Denied'}
                size="small"
                sx={{
                  height: 20, fontSize: '0.6rem', mt: 0.25,
                  backgroundColor: granted
                    ? alpha(theme.palette.success.main, 0.12)
                    : alpha(theme.palette.error.main, 0.08),
                  color: granted ? theme.palette.success.main : theme.palette.error.main,
                }}
              />
            </Box>
          );
        })}
      </Box>

      {/* Footer */}
      <Divider />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 2, py: 1 }}>
        <Button
          size="small"
          onClick={handleResetToDefaults}
          sx={{ textTransform: 'none', fontSize: '0.7rem', color: 'text.secondary' }}
        >
          Reset to Org Defaults
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={onClose}
          sx={{ textTransform: 'none', fontSize: '0.7rem' }}
        >
          Apply
        </Button>
      </Box>
    </Popover>
  );
}
