/**
 * OrgCollaborationPopover — organization assignment & collaboration scope panel.
 *
 * Three tabs:
 * 1. Organization — org tree, reports_to assignment
 * 2. Collaboration — scope rules per org, role, and employee
 * 3. Summary — effective permission matrix with resolution cascade
 *
 * Collaboration rules unified here (previously split with RoleControlPopover):
 * - Org-level: scope per other organization
 * - Role-level: scope per role (e.g., block UX Designers, full access to Engineers)
 * - Employee-level: individual overrides
 * Resolution: employee > role > org > default
 */

import React, { useState, useEffect, useMemo } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Avatar from '@mui/material/Avatar';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import GroupsIcon from '@mui/icons-material/Groups';
import SummarizeIcon from '@mui/icons-material/Summarize';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import StarIcon from '@mui/icons-material/Star';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import BadgeIcon from '@mui/icons-material/Badge';
import { useTheme, alpha } from '@mui/material/styles';

const ALL_KNOWN_ROLES = [
  'Software Engineer',
  'Machine Learning Engineer',
  'QA / Testing Engineer',
  'Program Manager',
  'UX Designer',
  'Tech Lead',
  'Engineering Manager',
];

const SCOPE_OPTIONS = [
  { value: 'full', label: 'Full', color: 'success' },
  { value: 'read_only', label: 'Read Only', color: 'info' },
  { value: 'request', label: 'Request', color: 'warning' },
  { value: 'blocked', label: 'Blocked', color: 'error' },
];

const SCOPE_COLORS = {
  full: 'success',
  read_only: 'info',
  request: 'warning',
  blocked: 'error',
};

function ScopeChip({ scope, size = 'small' }) {
  const colorKey = SCOPE_COLORS[scope] || 'default';
  return (
    <Chip
      label={scope?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Unknown'}
      size={size}
      color={colorKey}
      variant="outlined"
      sx={{ height: 20, fontSize: '0.6rem' }}
    />
  );
}

function TreeNode({ node, childrenOf, currentEmployeeId, depth, theme }) {
  const isHead = node.org_role === 'head';
  const isCurrent = node.id === currentEmployeeId;
  const children = childrenOf[node.id] || [];

  return (
    <Box>
      <Box
        sx={{
          display: 'flex', alignItems: 'center', gap: 1,
          py: 0.5, pl: depth > 0 ? `${depth * 20}px` : 0,
          ...(isCurrent ? {
            backgroundColor: alpha(theme.palette.primary.main, 0.1),
            borderRadius: 1, mx: -0.5, px: `${depth * 20 + 4}px`,
          } : {}),
        }}
      >
        {depth > 0 && (
          <Box sx={{
            width: 12, height: '1px',
            backgroundColor: theme.palette.divider,
            flexShrink: 0,
          }} />
        )}
        <Avatar
          sx={{
            width: 24, height: 24, fontSize: 12,
            bgcolor: node.type === 'ai'
              ? alpha(theme.palette.primary.main, 0.3)
              : alpha(theme.palette.success.main, 0.3),
          }}
        >
          {node.type === 'ai'
            ? <SmartToyIcon sx={{ fontSize: 14 }} />
            : node.name?.charAt(0)?.toUpperCase()
          }
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{
            fontSize: '0.75rem', fontWeight: isCurrent ? 600 : 400,
          }}>
            {node.name}
            {isCurrent && (
              <Typography component="span" sx={{
                fontSize: '0.6rem', color: 'primary.main', ml: 0.5,
              }}>
                (you)
              </Typography>
            )}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem' }}>
            {node.role}
          </Typography>
        </Box>
        {isHead && (
          <Chip
            icon={<StarIcon sx={{ fontSize: 10 }} />}
            label="HEAD"
            size="small"
            sx={{
              height: 18, fontSize: '0.55rem',
              backgroundColor: alpha(theme.palette.warning.main, 0.15),
              color: theme.palette.warning.main,
              '& .MuiChip-icon': { color: 'inherit' },
            }}
          />
        )}
        {node.type === 'ai' && (
          <Chip label="AI" size="small" sx={{
            height: 16, fontSize: '0.5rem',
            backgroundColor: alpha(theme.palette.primary.main, 0.15),
            color: theme.palette.primary.main,
          }} />
        )}
      </Box>
      {children.length > 0 && (
        <Box sx={{
          ml: `${(depth + 1) * 10}px`,
          borderLeft: `2px solid ${theme.palette.divider}`,
          pl: 0,
        }}>
          {children.map(child => (
            <TreeNode
              key={child.id}
              node={child}
              childrenOf={childrenOf}
              currentEmployeeId={currentEmployeeId}
              depth={depth + 1}
              theme={theme}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}

export default function OrgCollaborationPopover({
  anchorEl,
  open,
  onClose,
  employee,
  orgMembership,
  orgTree,
  allOrgs,
  allEmployees,
  collaborationConfig,
}) {
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);

  // Collaboration state
  const [defaultScope, setDefaultScope] = useState('request');
  const [rules, setRules] = useState([]);
  const [reportsTo, setReportsTo] = useState(null);

  // Add rule state
  const [showAddRule, setShowAddRule] = useState(false);
  const [newRuleType, setNewRuleType] = useState('org');
  const [newRuleTarget, setNewRuleTarget] = useState('');
  const [newRuleScope, setNewRuleScope] = useState('request');
  const [newRuleNote, setNewRuleNote] = useState('');

  const isAI = employee?.type === 'ai';

  useEffect(() => {
    if (collaborationConfig) {
      setDefaultScope(collaborationConfig.default_cross_org || 'request');
      setRules(collaborationConfig.rules || []);
    }
    if (orgMembership) {
      setReportsTo(orgMembership.reports_to || null);
    }
  }, [collaborationConfig, orgMembership]);

  // Build hierarchical tree from flat nodes + reports_to
  const treeRoot = useMemo(() => {
    if (!orgTree?.nodes) return null;
    const nodes = orgTree.nodes;
    const head = nodes.find(n => n.org_role === 'head');
    if (!head) return null;

    // Build children map: parent_id -> [children]
    const childrenOf = {};
    nodes.forEach(n => {
      if (n.id === head.id) return; // skip head
      const parent = n.reports_to || head.id;
      if (!childrenOf[parent]) childrenOf[parent] = [];
      childrenOf[parent].push(n);
    });

    return { head, childrenOf };
  }, [orgTree]);

  // Humans in the same org (for reports_to dropdown)
  const humansinOrg = useMemo(() => {
    if (!orgTree?.nodes) return [];
    return orgTree.nodes.filter(n => n.type === 'human' && n.id !== employee?.id);
  }, [orgTree, employee]);

  // Other orgs (for collaboration rules)
  const otherOrgs = useMemo(() => {
    if (!allOrgs || !orgMembership) return [];
    return allOrgs.filter(o => o.id !== orgMembership.org_id);
  }, [allOrgs, orgMembership]);

  // Other-org employees (for per-employee rules)
  const otherOrgEmployees = useMemo(() => {
    if (!allEmployees || !orgMembership) return [];
    return allEmployees.filter(e =>
      e.id !== employee?.id && e.type === 'ai'
    );
  }, [allEmployees, employee, orgMembership]);

  const handleAddRule = () => {
    if (!newRuleTarget) return;
    const newRule = {
      target_type: newRuleType,
      target_id: newRuleTarget,
      scope: newRuleScope,
      note: newRuleNote,
    };
    setRules(prev => [...prev, newRule]);
    setShowAddRule(false);
    setNewRuleTarget('');
    setNewRuleScope('request');
    setNewRuleNote('');
  };

  const handleDeleteRule = (idx) => {
    setRules(prev => prev.filter((_, i) => i !== idx));
  };

  const handleRuleScopeChange = (idx, newScope) => {
    setRules(prev => prev.map((r, i) => i === idx ? { ...r, scope: newScope } : r));
  };

  // Resolve display name for a rule target
  const resolveTargetName = (rule) => {
    if (rule.target_type === 'org') {
      const org = allOrgs?.find(o => o.id === rule.target_id);
      return org?.name || rule.target_id;
    }
    if (rule.target_type === 'role') {
      return rule.target_id; // role name is the ID
    }
    const emp = allEmployees?.find(e => e.id === rule.target_id);
    return emp?.name || rule.target_id;
  };

  // Effective collaboration summary
  const effectiveSummary = useMemo(() => {
    const summary = [];
    // Org-level rules
    (otherOrgs || []).forEach(org => {
      const orgRule = rules.find(r => r.target_type === 'org' && r.target_id === org.id);
      summary.push({
        name: org.name,
        type: 'org',
        id: org.id,
        scope: orgRule?.scope || defaultScope,
        source: orgRule ? 'explicit' : 'default',
        note: orgRule?.note || '',
      });
    });
    // Role-level rules
    rules.filter(r => r.target_type === 'role').forEach(rule => {
      summary.push({
        name: rule.target_id,
        type: 'role',
        id: rule.target_id,
        scope: rule.scope,
        source: 'explicit',
        note: rule.note,
      });
    });
    // Individual employee overrides
    rules.filter(r => r.target_type === 'employee').forEach(rule => {
      const emp = allEmployees?.find(e => e.id === rule.target_id);
      if (emp) {
        summary.push({
          name: emp.name,
          type: 'employee',
          id: rule.target_id,
          scope: rule.scope,
          source: 'explicit',
          note: rule.note,
        });
      }
    });
    return summary;
  }, [otherOrgs, rules, defaultScope, allEmployees]);

  const currentOrg = allOrgs?.find(o => o.id === orgMembership?.org_id);
  const hasValidReport = !isAI || reportsTo;

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
            width: 500,
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
          <AccountTreeIcon sx={{ fontSize: 18, color: 'primary.main' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
            Organization & Collaboration
          </Typography>
        </Box>
        {currentOrg && (
          <Chip
            icon={<GroupsIcon sx={{ fontSize: 14 }} />}
            label={currentOrg.name}
            size="small"
            color="info"
            variant="outlined"
            sx={{ height: 22, fontSize: '0.7rem', mb: 0.5 }}
          />
        )}
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
        <Tab icon={<AccountTreeIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="Organization" />
        <Tab icon={<GroupsIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="Collaboration" />
        <Tab icon={<SummarizeIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="Summary" />
      </Tabs>

      {/* Tab content */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5 }}>

        {/* ─── Tab 0: Organization ─── */}
        {activeTab === 0 && (
          <Box>
            {/* Org info */}
            {currentOrg ? (
              <Box sx={{
                backgroundColor: alpha(theme.palette.info.main, 0.06),
                border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
                borderRadius: 1.5, p: 1.5, mb: 2,
              }}>
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                  {currentOrg.name}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {currentOrg.description}
                </Typography>
              </Box>
            ) : (
              <Box sx={{
                backgroundColor: alpha(theme.palette.warning.main, 0.08),
                border: `1px solid ${alpha(theme.palette.warning.main, 0.3)}`,
                borderRadius: 1.5, p: 1.5, mb: 2,
              }}>
                <Typography variant="body2" sx={{ color: theme.palette.warning.main }}>
                  Not assigned to any organization
                </Typography>
              </Box>
            )}

            {/* Org Tree */}
            {treeRoot && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" sx={{
                  fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                  fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 1,
                }}>
                  Org Tree
                </Typography>
                <Box sx={{
                  backgroundColor: 'action.hover',
                  border: '1px solid', borderColor: 'divider',
                  borderRadius: 1.5, p: 1.5,
                }}>
                  <TreeNode
                    node={treeRoot.head}
                    childrenOf={treeRoot.childrenOf}
                    currentEmployeeId={employee?.id}
                    depth={0}
                    theme={theme}
                  />
                </Box>
              </Box>
            )}

            {/* Reports To (AI employees only) */}
            {isAI && (
              <Box sx={{ mb: 1.5 }}>
                <Typography variant="caption" sx={{
                  fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                  fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 0.75,
                }}>
                  Reports To (Human Direct Report)
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Select
                    value={reportsTo || ''}
                    onChange={(e) => setReportsTo(e.target.value || null)}
                    size="small"
                    fullWidth
                    displayEmpty
                    sx={{ fontSize: '0.8rem' }}
                    error={!reportsTo}
                  >
                    <MenuItem value="" disabled>
                      <em>Select human manager...</em>
                    </MenuItem>
                    {humansinOrg.map(h => (
                      <MenuItem key={h.id} value={h.id}>
                        {h.name} — {h.role}
                      </MenuItem>
                    ))}
                  </Select>
                  {reportsTo ? (
                    <CheckCircleIcon sx={{ fontSize: 20, color: theme.palette.success.main, flexShrink: 0 }} />
                  ) : (
                    <Tooltip title="Every AI employee must have a human direct report">
                      <WarningAmberIcon sx={{ fontSize: 20, color: theme.palette.error.main, flexShrink: 0 }} />
                    </Tooltip>
                  )}
                </Box>
                {!reportsTo && (
                  <Typography variant="caption" sx={{ color: theme.palette.error.main, fontSize: '0.65rem', mt: 0.5, display: 'block' }}>
                    Required: AI employees must report to a human in this org
                  </Typography>
                )}
              </Box>
            )}
          </Box>
        )}

        {/* ─── Tab 1: Cross-Org Collaboration ─── */}
        {activeTab === 1 && (
          <Box>
            {/* Default scope */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" sx={{
                fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 0.75,
              }}>
                Default Cross-Org Scope
              </Typography>
              <Select
                value={defaultScope}
                onChange={(e) => setDefaultScope(e.target.value)}
                size="small"
                fullWidth
                sx={{ fontSize: '0.8rem' }}
              >
                {SCOPE_OPTIONS.map(opt => (
                  <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                ))}
              </Select>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', mt: 0.5, display: 'block' }}>
                Applied to all other orgs unless overridden below
              </Typography>
            </Box>

            <Divider sx={{ mb: 1.5 }} />

            {/* Per-org rules */}
            <Typography variant="caption" sx={{
              fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
              fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 1,
            }}>
              Per-Org Rules
            </Typography>
            {otherOrgs.map(org => {
              const ruleIdx = rules.findIndex(r => r.target_type === 'org' && r.target_id === org.id);
              const rule = ruleIdx >= 0 ? rules[ruleIdx] : null;
              return (
                <Box
                  key={org.id}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1,
                    py: 0.75, borderBottom: '1px solid', borderColor: 'divider',
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                      {org.name}
                    </Typography>
                    {rule?.note && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem' }}>
                        {rule.note}
                      </Typography>
                    )}
                  </Box>
                  <Select
                    value={rule?.scope || defaultScope}
                    onChange={(e) => {
                      if (ruleIdx >= 0) {
                        handleRuleScopeChange(ruleIdx, e.target.value);
                      } else {
                        setRules(prev => [...prev, {
                          target_type: 'org', target_id: org.id,
                          scope: e.target.value, note: '',
                        }]);
                      }
                    }}
                    size="small"
                    sx={{ width: 120, fontSize: '0.75rem' }}
                  >
                    {SCOPE_OPTIONS.map(opt => (
                      <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                    ))}
                  </Select>
                  {rule && (
                    <IconButton size="small" onClick={() => handleDeleteRule(ruleIdx)} sx={{ p: 0.25 }}>
                      <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  )}
                </Box>
              );
            })}

            <Divider sx={{ my: 1.5 }} />

            {/* Per-role rules */}
            <Typography variant="caption" sx={{
              fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
              fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 1,
            }}>
              Per-Role Rules
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', display: 'block', mb: 1 }}>
              Control collaboration scope with employees by their role
            </Typography>
            {rules
              .map((r, idx) => ({ ...r, _idx: idx }))
              .filter(r => r.target_type === 'role')
              .map(rule => (
                <Box
                  key={rule.target_id}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1,
                    py: 0.75, borderBottom: '1px solid', borderColor: 'divider',
                  }}
                >
                  <BadgeIcon sx={{ fontSize: 16, color: 'text.secondary', flexShrink: 0 }} />
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                      {rule.target_id}
                    </Typography>
                    {rule.note && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem' }}>
                        {rule.note}
                      </Typography>
                    )}
                  </Box>
                  <Select
                    value={rule.scope}
                    onChange={(e) => handleRuleScopeChange(rule._idx, e.target.value)}
                    size="small"
                    sx={{ width: 120, fontSize: '0.75rem' }}
                  >
                    {SCOPE_OPTIONS.map(opt => (
                      <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                    ))}
                  </Select>
                  <IconButton size="small" onClick={() => handleDeleteRule(rule._idx)} sx={{ p: 0.25 }}>
                    <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Box>
              ))}

            <Divider sx={{ my: 1.5 }} />

            {/* Per-employee rules */}
            <Typography variant="caption" sx={{
              fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
              fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 1,
            }}>
              Per-Employee Overrides
            </Typography>
            {rules
              .map((r, idx) => ({ ...r, _idx: idx }))
              .filter(r => r.target_type === 'employee')
              .map(rule => (
                <Box
                  key={rule.target_id}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1,
                    py: 0.75, borderBottom: '1px solid', borderColor: 'divider',
                  }}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                      {resolveTargetName(rule)}
                    </Typography>
                    {rule.note && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem' }}>
                        {rule.note}
                      </Typography>
                    )}
                  </Box>
                  <Select
                    value={rule.scope}
                    onChange={(e) => handleRuleScopeChange(rule._idx, e.target.value)}
                    size="small"
                    sx={{ width: 120, fontSize: '0.75rem' }}
                  >
                    {SCOPE_OPTIONS.map(opt => (
                      <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                    ))}
                  </Select>
                  <IconButton size="small" onClick={() => handleDeleteRule(rule._idx)} sx={{ p: 0.25 }}>
                    <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Box>
              ))}

            {/* Add rule */}
            {showAddRule ? (
              <Box sx={{
                mt: 1, p: 1.5, backgroundColor: 'action.hover',
                border: '1px solid', borderColor: 'divider', borderRadius: 1.5,
              }}>
                <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                  <Select
                    value={newRuleType}
                    onChange={(e) => { setNewRuleType(e.target.value); setNewRuleTarget(''); }}
                    size="small"
                    sx={{ width: 120, fontSize: '0.75rem' }}
                  >
                    <MenuItem value="org">Org</MenuItem>
                    <MenuItem value="role">Role</MenuItem>
                    <MenuItem value="employee">Employee</MenuItem>
                  </Select>
                  <Select
                    value={newRuleTarget}
                    onChange={(e) => setNewRuleTarget(e.target.value)}
                    size="small"
                    displayEmpty
                    sx={{ flex: 1, fontSize: '0.75rem' }}
                  >
                    <MenuItem value="" disabled><em>Select target...</em></MenuItem>
                    {newRuleType === 'org'
                      ? otherOrgs.map(o => <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>)
                      : newRuleType === 'role'
                        ? ALL_KNOWN_ROLES.filter(r => !rules.some(rule => rule.target_type === 'role' && rule.target_id === r))
                            .map(r => <MenuItem key={r} value={r}>{r}</MenuItem>)
                        : otherOrgEmployees.map(e => <MenuItem key={e.id} value={e.id}>{e.name}</MenuItem>)
                    }
                  </Select>
                  <Select
                    value={newRuleScope}
                    onChange={(e) => setNewRuleScope(e.target.value)}
                    size="small"
                    sx={{ width: 110, fontSize: '0.75rem' }}
                  >
                    {SCOPE_OPTIONS.map(opt => (
                      <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                    ))}
                  </Select>
                </Box>
                <TextField
                  value={newRuleNote}
                  onChange={(e) => setNewRuleNote(e.target.value)}
                  placeholder="Optional note..."
                  size="small"
                  fullWidth
                  sx={{ mb: 1, '& input': { fontSize: '0.75rem' } }}
                />
                <Box sx={{ display: 'flex', gap: 0.75, justifyContent: 'flex-end' }}>
                  <Button size="small" onClick={() => setShowAddRule(false)}
                    sx={{ textTransform: 'none', fontSize: '0.7rem' }}>
                    Cancel
                  </Button>
                  <Button size="small" variant="contained" onClick={handleAddRule}
                    disabled={!newRuleTarget}
                    sx={{ textTransform: 'none', fontSize: '0.7rem' }}>
                    Add Rule
                  </Button>
                </Box>
              </Box>
            ) : (
              <Button
                size="small"
                startIcon={<AddIcon sx={{ fontSize: 14 }} />}
                onClick={() => setShowAddRule(true)}
                sx={{ textTransform: 'none', fontSize: '0.7rem', mt: 1, color: 'text.secondary' }}
              >
                Add Rule
              </Button>
            )}
          </Box>
        )}

        {/* ─── Tab 2: Collaboration Summary ─── */}
        {activeTab === 2 && (
          <Box>
            <Typography variant="caption" sx={{
              fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
              fontSize: '0.65rem', color: 'text.secondary', display: 'block', mb: 1,
            }}>
              Effective Collaboration Permissions
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', display: 'block', mb: 1.5 }}>
              Resolution: employee &gt; role &gt; org &gt; default ({defaultScope.replace(/_/g, ' ')})
            </Typography>

            {effectiveSummary.length === 0 ? (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                No cross-org relationships configured
              </Typography>
            ) : (
              effectiveSummary.map((item, idx) => (
                <Box
                  key={`${item.type}-${item.id}`}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1,
                    py: 0.75,
                    borderBottom: idx < effectiveSummary.length - 1 ? '1px solid' : 'none',
                    borderColor: 'divider',
                  }}
                >
                  {item.type === 'org' ? (
                    <GroupsIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                  ) : item.type === 'role' ? (
                    <BadgeIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                  ) : (
                    <PersonIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                  )}
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.8rem', fontWeight: 500 }}>
                      {item.name}
                    </Typography>
                    {item.note && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem' }}>
                        {item.note}
                      </Typography>
                    )}
                  </Box>
                  <ScopeChip scope={item.scope} />
                  <Chip
                    label={item.source}
                    size="small"
                    variant="outlined"
                    sx={{
                      height: 16, fontSize: '0.5rem',
                      color: 'text.secondary', borderColor: 'divider',
                    }}
                  />
                </Box>
              ))
            )}
          </Box>
        )}
      </Box>

      {/* Footer */}
      <Divider />
      <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 2, py: 1 }}>
        <Button
          size="small"
          onClick={() => {
            if (collaborationConfig) {
              setDefaultScope(collaborationConfig.default_cross_org || 'request');
              setRules(collaborationConfig.rules || []);
            }
          }}
          sx={{ textTransform: 'none', fontSize: '0.7rem', color: 'text.secondary' }}
        >
          Reset
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={onClose}
          disabled={isAI && !hasValidReport}
          sx={{ textTransform: 'none', fontSize: '0.7rem' }}
        >
          Apply
        </Button>
      </Box>
    </Popover>
  );
}
