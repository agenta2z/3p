/**
 * AddSkillPopover — dropdown to add a skill from the role pool.
 *
 * Features:
 * - "Include out-of-role skills" checkbox to expand pool across all roles
 * - Dropdown shows available skills (pool minus already-primary), grouped by role when expanded
 * - Custom skill text input option
 * - Skill details text field for prompt context
 * - Add as Primary button
 */

import React, { useState } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Divider from '@mui/material/Divider';
import ListSubheader from '@mui/material/ListSubheader';
import AddIcon from '@mui/icons-material/Add';

const CUSTOM_SKILL_VALUE = '__custom__';

export default function AddSkillPopover({
  anchorEl,
  open,
  onClose,
  agentName,
  role,
  currentSkills = [],
  roleSkillsMap = {},
  onAdd,
}) {
  const [includeOutOfRole, setIncludeOutOfRole] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState('');
  const [customSkill, setCustomSkill] = useState('');
  const [details, setDetails] = useState('');

  const handleClose = () => {
    setSelectedSkill('');
    setCustomSkill('');
    setDetails('');
    setIncludeOutOfRole(false);
    onClose();
  };

  const handleAdd = () => {
    const skillName = selectedSkill === CUSTOM_SKILL_VALUE ? customSkill.trim() : selectedSkill;
    if (!skillName) return;
    onAdd(skillName, details.trim() || null);
    handleClose();
  };

  // Build available skills list
  const currentSet = new Set(currentSkills.map(s => s.toLowerCase()));

  const buildMenuItems = () => {
    const items = [];

    if (!includeOutOfRole) {
      // Only current role's pool
      const pool = roleSkillsMap[role]?.skills || [];
      const available = pool.filter(s => !currentSet.has(s.toLowerCase()));
      available.forEach(skill => {
        items.push({ type: 'skill', label: skill, value: skill });
      });
    } else {
      // All roles, grouped, current role first
      const roles = Object.keys(roleSkillsMap);
      const sortedRoles = [role, ...roles.filter(r => r !== role)];

      sortedRoles.forEach(r => {
        const pool = roleSkillsMap[r]?.skills || [];
        const available = pool.filter(s => !currentSet.has(s.toLowerCase()));
        if (available.length > 0) {
          items.push({ type: 'header', label: r });
          available.forEach(skill => {
            items.push({ type: 'skill', label: skill, value: skill });
          });
        }
      });
    }

    // Custom option at bottom
    items.push({ type: 'divider' });
    items.push({ type: 'skill', label: '+ Type custom skill...', value: CUSTOM_SKILL_VALUE });

    return items;
  };

  const menuItems = buildMenuItems();
  const isCustom = selectedSkill === CUSTOM_SKILL_VALUE;
  const canAdd = isCustom ? customSkill.trim().length > 0 : selectedSkill.length > 0;

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      PaperProps={{
        sx: {
          width: 380,
          backgroundColor: 'background.paper',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 2,
          p: 2.5,
        },
      }}
    >
      {/* Header */}
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
        Add Skill to {agentName}
      </Typography>

      {/* Out-of-role checkbox */}
      <FormControlLabel
        control={
          <Checkbox
            checked={includeOutOfRole}
            onChange={(e) => {
              setIncludeOutOfRole(e.target.checked);
              setSelectedSkill('');
            }}
            size="small"
            sx={{ py: 0 }}
          />
        }
        label={
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Include out-of-role skills
          </Typography>
        }
        sx={{ mb: 1.5, ml: -0.5 }}
      />

      {/* Skill dropdown */}
      <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block', mb: 0.5 }}>
        Select Skill:
      </Typography>
      <Select
        value={selectedSkill}
        onChange={(e) => setSelectedSkill(e.target.value)}
        displayEmpty
        fullWidth
        size="small"
        sx={{ mb: 1.5, fontSize: '0.85rem' }}
        renderValue={(val) => {
          if (!val) return <span style={{ color: '#666' }}>Pick from {includeOutOfRole ? 'all' : 'role'} skills...</span>;
          if (val === CUSTOM_SKILL_VALUE) return 'Custom skill';
          return val;
        }}
        MenuProps={{
          PaperProps: {
            sx: { maxHeight: 300, backgroundColor: 'background.paper' },
          },
        }}
      >
        {menuItems.map((item, i) => {
          if (item.type === 'header') {
            return (
              <ListSubheader
                key={`header-${i}`}
                sx={{
                  backgroundColor: 'background.paper',
                  color: 'text.secondary',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                  lineHeight: 2.5,
                }}
              >
                {item.label}
              </ListSubheader>
            );
          }
          if (item.type === 'divider') {
            return <Divider key={`div-${i}`} sx={{ my: 0.5, borderColor: 'rgba(255,255,255,0.08)' }} />;
          }
          return (
            <MenuItem key={item.value} value={item.value} sx={{ fontSize: '0.85rem' }}>
              {item.value === CUSTOM_SKILL_VALUE ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'primary.light' }}>
                  <AddIcon sx={{ fontSize: 14 }} />
                  {item.label}
                </Box>
              ) : (
                item.label
              )}
            </MenuItem>
          );
        })}
      </Select>

      {/* Custom skill text input */}
      {isCustom && (
        <TextField
          fullWidth
          size="small"
          placeholder="Type custom skill name..."
          value={customSkill}
          onChange={(e) => setCustomSkill(e.target.value)}
          sx={{ mb: 1.5 }}
          autoFocus
        />
      )}

      {/* Skill details */}
      {(selectedSkill || isCustom) && (
        <>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block', mb: 0.5 }}>
            Skill Details (optional):
          </Typography>
          <TextField
            fullWidth
            size="small"
            multiline
            rows={2}
            placeholder='Describe how this agent uses this skill, e.g. "Expert in CUDA kernels for training transformer models"'
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            sx={{ mb: 2 }}
          />
        </>
      )}

      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
        <Button size="small" onClick={handleClose} sx={{ textTransform: 'none', color: 'text.secondary' }}>
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          disabled={!canAdd}
          onClick={handleAdd}
          sx={{ textTransform: 'none' }}
        >
          Add as Primary
        </Button>
      </Box>
    </Popover>
  );
}
