/**
 * RoleControlPopover — advanced role configuration panel.
 *
 * Four sections (internal agent configuration):
 * 1. Role Description
 * 2. Mindset Presets
 * 3. SOPs (Standard Operating Procedures)
 * 4. Guardrails
 *
 * Communication/collaboration rules have moved to OrgCollaborationPopover,
 * which manages all external interaction scope (org, role, and employee level).
 */

import React, { useState, useEffect, useCallback } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Chip from '@mui/material/Chip';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import SettingsIcon from '@mui/icons-material/Settings';
import PsychologyIcon from '@mui/icons-material/Psychology';
import AssignmentIcon from '@mui/icons-material/Assignment';
import SecurityIcon from '@mui/icons-material/Security';
import DescriptionIcon from '@mui/icons-material/Description';
import EditIcon from '@mui/icons-material/Edit';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import AddIcon from '@mui/icons-material/Add';
import { useTheme } from '@mui/material/styles';

const AUTONOMY_OPTIONS = ['low', 'medium', 'high', 'full'];
const ESCALATION_OPTIONS = ['30min', '1h', '2h', '4h', '8h'];
const TOKEN_BUDGET_OPTIONS = ['10K', '50K', '100K', '500K', 'Unlimited'];
const OUTPUT_REVIEW_OPTIONS = ['always', 'on_errors', 'never'];
const APPROVAL_ITEMS = [
  'architecture_decisions',
  'external_api_integrations',
  'database_schema_changes',
  'production_deployments',
  'release_sign_offs',
  'test_environment_changes',
  'quality_gate_modifications',
  'budget_changes',
  'timeline_changes',
  'scope_changes',
  'external_commitments',
  'design_system_changes',
  'user_facing_copy_changes',
  'navigation_changes',
  'branding_updates',
];

const sectionSx = {
  backgroundColor: 'action.hover',
  border: '1px solid', borderColor: 'divider',
  borderRadius: 1.5,
  p: 1.5,
  mb: 1.5,
};

const sectionHeaderSx = {
  display: 'flex',
  alignItems: 'center',
  gap: 0.75,
  mb: 1,
};

function SectionTitle({ icon, title }) {
  return (
    <Box sx={sectionHeaderSx}>
      {icon}
      <Typography variant="caption" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, fontSize: '0.65rem', color: 'text.secondary' }}>
        {title}
      </Typography>
    </Box>
  );
}

const DEFAULT_CONFIG = {
  description: '',
  mindsets: [],
  sops: [],
  guardrails: {
    max_concurrent_tasks: 3,
    max_autonomy: 'medium',
    escalation_threshold: '2h',
    max_token_budget: '100K',
    output_review: 'on_errors',
    approval_required: [],
  },
};

function formatApprovalLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function RoleControlPopover({
  anchorEl,
  open,
  onClose,
  role,
  roleConfig,
}) {
  const config = roleConfig || DEFAULT_CONFIG;
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState(0);

  // ── State ──
  const [description, setDescription] = useState(config.description || '');
  const [mindsets, setMindsets] = useState(() =>
    (config.mindsets || []).map(m => ({ ...m, enabled: m.default_enabled }))
  );
  const [customMindset, setCustomMindset] = useState('');
  const [showCustomMindset, setShowCustomMindset] = useState(false);

  const [sops, setSops] = useState(() => (config.sops || []).map(s => ({ ...s })));
  const [editingSopIdx, setEditingSopIdx] = useState(null);
  const [showAddSop, setShowAddSop] = useState(false);
  const [newSop, setNewSop] = useState({ title: '', trigger: '', steps: '' });

  const [maxConcurrent, setMaxConcurrent] = useState(config.guardrails?.max_concurrent_tasks ?? 3);
  const [maxAutonomy, setMaxAutonomy] = useState(config.guardrails?.max_autonomy || 'medium');
  const [escalation, setEscalation] = useState(config.guardrails?.escalation_threshold || '2h');
  const [tokenBudget, setTokenBudget] = useState(config.guardrails?.max_token_budget || '100K');
  const [outputReview, setOutputReview] = useState(config.guardrails?.output_review || 'on_errors');
  const [approvalRequired, setApprovalRequired] = useState(config.guardrails?.approval_required || []);

  // Reset all state when config changes
  const resetToDefaults = useCallback(() => {
    setDescription(config.description || '');
    setMindsets((config.mindsets || []).map(m => ({ ...m, enabled: m.default_enabled })));
    setCustomMindset('');
    setShowCustomMindset(false);
    setSops((config.sops || []).map(s => ({ ...s })));
    setEditingSopIdx(null);
    setShowAddSop(false);
    setNewSop({ title: '', trigger: '', steps: '' });
    setMaxConcurrent(config.guardrails?.max_concurrent_tasks ?? 3);
    setMaxAutonomy(config.guardrails?.max_autonomy || 'medium');
    setEscalation(config.guardrails?.escalation_threshold || '2h');
    setTokenBudget(config.guardrails?.max_token_budget || '100K');
    setOutputReview(config.guardrails?.output_review || 'on_errors');
    setApprovalRequired(config.guardrails?.approval_required || []);
  }, [config]);

  // Re-init when roleConfig changes (e.g. different agent selected)
  useEffect(() => {
    resetToDefaults();
  }, [roleConfig, resetToDefaults]);

  // ── Mindset handlers ──
  const toggleMindset = (idx) => {
    setMindsets(prev => prev.map((m, i) => i === idx ? { ...m, enabled: !m.enabled } : m));
  };

  const addCustomMindset = () => {
    if (customMindset.trim()) {
      setMindsets(prev => [...prev, { text: customMindset.trim(), default_enabled: false, enabled: true }]);
      setCustomMindset('');
      setShowCustomMindset(false);
    }
  };

  // ── SOP handlers ──
  const removeSop = (idx) => {
    setSops(prev => prev.filter((_, i) => i !== idx));
    if (editingSopIdx === idx) setEditingSopIdx(null);
  };

  const updateSop = (idx, field, value) => {
    setSops(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  const addSop = () => {
    if (newSop.title.trim() && newSop.trigger.trim()) {
      const steps = newSop.steps.split('\n').map(s => s.trim()).filter(Boolean);
      setSops(prev => [...prev, { title: newSop.title.trim(), trigger: newSop.trigger.trim(), steps }]);
      setNewSop({ title: '', trigger: '', steps: '' });
      setShowAddSop(false);
    }
  };

  // ── Approval handlers ──
  const toggleApproval = (item) => {
    setApprovalRequired(prev =>
      prev.includes(item) ? prev.filter(x => x !== item) : [...prev, item]
    );
  };

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      PaperProps={{
        sx: {
          width: 480,
          maxHeight: '80vh',
          backgroundColor: 'background.paper',
          border: '1px solid', borderColor: 'divider',
          borderRadius: 2,
          p: 2.5,
          overflow: 'auto',
        },
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <SettingsIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Role Control — {role}
        </Typography>
      </Box>

      {/* Tab Navigation */}
      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{
          minHeight: 36,
          mb: 1.5,
          borderBottom: '1px solid', borderBottomColor: 'divider',
          '& .MuiTab-root': {
            textTransform: 'none',
            minHeight: 36,
            fontSize: '0.75rem',
            fontWeight: 500,
            py: 0,
            px: 1.5,
            minWidth: 0,
          },
        }}
      >
        <Tab icon={<DescriptionIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="Description" />
        <Tab icon={<PsychologyIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="Mindsets" />
        <Tab icon={<AssignmentIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="SOPs" />
        <Tab icon={<SecurityIcon sx={{ fontSize: 14 }} />} iconPosition="start" label="Guardrails" />
      </Tabs>

      {/* ── Tab 0: Role Description ── */}
      {activeTab === 0 && (
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<DescriptionIcon sx={{ fontSize: 14, color: 'primary.light' }} />}
          title="Role Description"
        />
        <TextField
          multiline
          rows={3}
          fullWidth
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          variant="outlined"
          size="small"
          sx={{
            '& .MuiOutlinedInput-root': {
              fontSize: '0.8rem',
              color: 'text.primary',
            },
          }}
        />
      </Box>
      )}

      {/* ── Tab 1: Mindset Presets ── */}
      {activeTab === 1 && (
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<PsychologyIcon sx={{ fontSize: 14, color: 'primary.light' }} />}
          title="Mindset Presets"
        />
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1, lineHeight: 1.4 }}>
          Toggle mindsets that shape how this agent approaches work.
        </Typography>

        {mindsets.map((m, idx) => (
          <FormControlLabel
            key={idx}
            control={
              <Checkbox
                checked={m.enabled}
                onChange={() => toggleMindset(idx)}
                size="small"
                sx={{ py: 0.25 }}
              />
            }
            label={
              <Typography variant="caption" sx={{ fontSize: '0.75rem' }}>
                {m.text}
              </Typography>
            }
            sx={{ display: 'flex', ml: -0.5, mb: 0 }}
          />
        ))}

        {showCustomMindset ? (
          <Box sx={{ display: 'flex', gap: 0.75, mt: 1 }}>
            <TextField
              value={customMindset}
              onChange={(e) => setCustomMindset(e.target.value)}
              placeholder="Type a custom mindset..."
              size="small"
              fullWidth
              sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
              onKeyDown={(e) => { if (e.key === 'Enter') addCustomMindset(); }}
            />
            <Button size="small" onClick={addCustomMindset} disabled={!customMindset.trim()} sx={{ textTransform: 'none', fontSize: '0.75rem', minWidth: 50 }}>
              Add
            </Button>
          </Box>
        ) : (
          <Button
            size="small"
            startIcon={<AddIcon sx={{ fontSize: 14 }} />}
            onClick={() => setShowCustomMindset(true)}
            sx={{ textTransform: 'none', fontSize: '0.7rem', color: 'primary.light', mt: 0.5 }}
          >
            Add custom mindset
          </Button>
        )}
      </Box>
      )}

      {/* ── Tab 2: SOPs ── */}
      {activeTab === 2 && (
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<AssignmentIcon sx={{ fontSize: 14, color: 'primary.light' }} />}
          title="Standard Operating Procedures"
        />

        {sops.map((sop, idx) => (
          <Box
            key={idx}
            sx={{
              mb: 1.5,
              p: 1,
              borderRadius: 1,
              backgroundColor: 'action.hover',
              border: '1px solid', borderColor: 'divider',
            }}
          >
            {editingSopIdx === idx ? (
              /* Editing mode */
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <TextField
                  label="Title"
                  value={sop.title}
                  onChange={(e) => updateSop(idx, 'title', e.target.value)}
                  size="small"
                  fullWidth
                  sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
                />
                <TextField
                  label="Trigger"
                  value={sop.trigger}
                  onChange={(e) => updateSop(idx, 'trigger', e.target.value)}
                  size="small"
                  fullWidth
                  sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
                />
                <TextField
                  label="Steps (one per line)"
                  value={Array.isArray(sop.steps) ? sop.steps.join('\n') : sop.steps}
                  onChange={(e) => updateSop(idx, 'steps', e.target.value.split('\n'))}
                  size="small"
                  fullWidth
                  multiline
                  rows={3}
                  sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
                />
                <Button size="small" onClick={() => setEditingSopIdx(null)} sx={{ textTransform: 'none', fontSize: '0.7rem', alignSelf: 'flex-end' }}>
                  Done
                </Button>
              </Box>
            ) : (
              /* View mode */
              <>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
                    {sop.title}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.25 }}>
                    <IconButton size="small" onClick={() => setEditingSopIdx(idx)} sx={{ color: 'text.secondary', p: 0.25 }}>
                      <EditIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                    <IconButton size="small" onClick={() => removeSop(idx)} sx={{ color: 'error.main', p: 0.25 }}>
                      <DeleteOutlineIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Box>
                </Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontStyle: 'italic' }}>
                  Trigger: {sop.trigger}
                </Typography>
                {Array.isArray(sop.steps) && sop.steps.map((step, si) => (
                  <Typography key={si} variant="caption" sx={{ display: 'block', color: 'text.secondary', pl: 1, lineHeight: 1.6, fontSize: '0.7rem' }}>
                    {si + 1}. {step}
                  </Typography>
                ))}
              </>
            )}
          </Box>
        ))}

        {showAddSop ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1, p: 1, borderRadius: 1, border: '1px dashed', borderColor: 'divider' }}>
            <TextField
              label="Title"
              value={newSop.title}
              onChange={(e) => setNewSop(prev => ({ ...prev, title: e.target.value }))}
              size="small"
              fullWidth
              sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
            />
            <TextField
              label="Trigger"
              value={newSop.trigger}
              onChange={(e) => setNewSop(prev => ({ ...prev, trigger: e.target.value }))}
              size="small"
              fullWidth
              sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
            />
            <TextField
              label="Steps (one per line)"
              value={newSop.steps}
              onChange={(e) => setNewSop(prev => ({ ...prev, steps: e.target.value }))}
              size="small"
              fullWidth
              multiline
              rows={3}
              sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.8rem' } }}
            />
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.75 }}>
              <Button size="small" onClick={() => { setShowAddSop(false); setNewSop({ title: '', trigger: '', steps: '' }); }} sx={{ textTransform: 'none', fontSize: '0.7rem', color: 'text.secondary' }}>
                Cancel
              </Button>
              <Button size="small" onClick={addSop} disabled={!newSop.title.trim() || !newSop.trigger.trim()} sx={{ textTransform: 'none', fontSize: '0.7rem' }}>
                Add
              </Button>
            </Box>
          </Box>
        ) : (
          <Button
            size="small"
            startIcon={<AddIcon sx={{ fontSize: 14 }} />}
            onClick={() => setShowAddSop(true)}
            sx={{ textTransform: 'none', fontSize: '0.7rem', color: 'primary.light', mt: 0.5 }}
          >
            Add SOP
          </Button>
        )}
      </Box>
      )}

      {/* ── Tab 3: Guardrails ── */}
      {activeTab === 3 && (
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<SecurityIcon sx={{ fontSize: 14, color: 'primary.light' }} />}
          title="Guardrails"
        />

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, mb: 1.5 }}>
          {/* Max Concurrent Tasks */}
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.65rem' }}>
              Max Concurrent Tasks
            </Typography>
            <Select
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(e.target.value)}
              size="small"
              fullWidth
              sx={{ fontSize: '0.8rem', '& .MuiSelect-select': { py: 0.5 } }}
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                <MenuItem key={n} value={n} sx={{ fontSize: '0.8rem' }}>{n}</MenuItem>
              ))}
            </Select>
          </Box>

          {/* Max Autonomy */}
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.65rem' }}>
              Max Autonomy
            </Typography>
            <Select
              value={maxAutonomy}
              onChange={(e) => setMaxAutonomy(e.target.value)}
              size="small"
              fullWidth
              sx={{ fontSize: '0.8rem', '& .MuiSelect-select': { py: 0.5 } }}
            >
              {AUTONOMY_OPTIONS.map(o => (
                <MenuItem key={o} value={o} sx={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>{o.charAt(0).toUpperCase() + o.slice(1)}</MenuItem>
              ))}
            </Select>
          </Box>

          {/* Escalation Threshold */}
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.65rem' }}>
              Escalation Threshold
            </Typography>
            <Select
              value={escalation}
              onChange={(e) => setEscalation(e.target.value)}
              size="small"
              fullWidth
              sx={{ fontSize: '0.8rem', '& .MuiSelect-select': { py: 0.5 } }}
            >
              {ESCALATION_OPTIONS.map(o => (
                <MenuItem key={o} value={o} sx={{ fontSize: '0.8rem' }}>{o}</MenuItem>
              ))}
            </Select>
          </Box>

          {/* Max Token Budget */}
          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.65rem' }}>
              Max Token Budget
            </Typography>
            <Select
              value={tokenBudget}
              onChange={(e) => setTokenBudget(e.target.value)}
              size="small"
              fullWidth
              sx={{ fontSize: '0.8rem', '& .MuiSelect-select': { py: 0.5 } }}
            >
              {TOKEN_BUDGET_OPTIONS.map(o => (
                <MenuItem key={o} value={o} sx={{ fontSize: '0.8rem' }}>{o}</MenuItem>
              ))}
            </Select>
          </Box>

          {/* Output Review */}
          <Box sx={{ gridColumn: 'span 2' }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.65rem' }}>
              Output Review
            </Typography>
            <Select
              value={outputReview}
              onChange={(e) => setOutputReview(e.target.value)}
              size="small"
              fullWidth
              sx={{ fontSize: '0.8rem', '& .MuiSelect-select': { py: 0.5 } }}
            >
              {OUTPUT_REVIEW_OPTIONS.map(o => (
                <MenuItem key={o} value={o} sx={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>
                  {o === 'on_errors' ? 'On errors' : o.charAt(0).toUpperCase() + o.slice(1)}
                </MenuItem>
              ))}
            </Select>
          </Box>
        </Box>

        {/* Approval Required */}
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.75, fontSize: '0.65rem', fontWeight: 600 }}>
          APPROVAL REQUIRED FOR
        </Typography>
        {APPROVAL_ITEMS.map((item) => (
          <FormControlLabel
            key={item}
            control={
              <Checkbox
                checked={approvalRequired.includes(item)}
                onChange={() => toggleApproval(item)}
                size="small"
                sx={{ py: 0.15 }}
              />
            }
            label={
              <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                {formatApprovalLabel(item)}
              </Typography>
            }
            sx={{ display: 'flex', ml: -0.5, mb: 0 }}
          />
        ))}
      </Box>
      )}

      <Divider sx={{ borderColor: 'divider', mb: 1.5 }} />

      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button size="small" onClick={resetToDefaults} sx={{ textTransform: 'none', color: 'text.secondary', fontSize: '0.75rem' }}>
          Reset to Defaults
        </Button>
        <Button size="small" variant="contained" onClick={onClose} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
          Apply
        </Button>
      </Box>
    </Popover>
  );
}
