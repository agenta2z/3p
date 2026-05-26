/**
 * SkillControlPopover — advanced skill configuration panel.
 *
 * Three sections:
 * 1. Skill Priority (Multipliers) — assign weight to any skill
 * 2. Block List — skills the agent should never use
 * 3. Allow List — optional restriction to only permitted skills
 */

import React, { useState } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import SettingsIcon from '@mui/icons-material/Settings';
import BlockIcon from '@mui/icons-material/Block';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import TuneIcon from '@mui/icons-material/Tune';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTheme } from '@mui/material/styles';

const MULTIPLIER_OPTIONS = [0.1, 0.25, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0];

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

export default function SkillControlPopover({
  anchorEl,
  open,
  onClose,
  agentName,
  primarySkills = [],
  allKnownSkills = [],
}) {
  // Local state for all controls
  const theme = useTheme();
  const [multipliers, setMultipliers] = useState(() => {
    const m = {};
    primarySkills.forEach(s => { m[s] = 1.0; });
    return m;
  });
  const [newMultiplierSkill, setNewMultiplierSkill] = useState('');
  const [blockedSkills, setBlockedSkills] = useState([]);
  const [newBlockSkill, setNewBlockSkill] = useState('');
  const [allowList, setAllowList] = useState([]);
  const [newAllowSkill, setNewAllowSkill] = useState('');
  const [restrictToAllowList, setRestrictToAllowList] = useState(false);

  const handleMultiplierChange = (skill, value) => {
    setMultipliers(prev => ({ ...prev, [skill]: value }));
  };

  const handleAddMultiplier = () => {
    if (newMultiplierSkill && !multipliers[newMultiplierSkill]) {
      setMultipliers(prev => ({ ...prev, [newMultiplierSkill]: 1.0 }));
      setNewMultiplierSkill('');
    }
  };

  const handleRemoveMultiplier = (skill) => {
    if (primarySkills.includes(skill)) return; // can't remove primary
    setMultipliers(prev => {
      const next = { ...prev };
      delete next[skill];
      return next;
    });
  };

  const handleAddBlocked = () => {
    if (newBlockSkill && !blockedSkills.includes(newBlockSkill)) {
      setBlockedSkills(prev => [...prev, newBlockSkill]);
      setNewBlockSkill('');
    }
  };

  const handleAddAllow = () => {
    if (newAllowSkill && !allowList.includes(newAllowSkill)) {
      setAllowList(prev => [...prev, newAllowSkill]);
      setNewAllowSkill('');
    }
  };

  const handleReset = () => {
    const m = {};
    primarySkills.forEach(s => { m[s] = 1.0; });
    setMultipliers(m);
    setBlockedSkills([]);
    setAllowList([]);
    setRestrictToAllowList(false);
  };

  // Skills available for multiplier (not already in multipliers)
  const availableForMultiplier = allKnownSkills.filter(s => !multipliers[s]);
  // Skills available for block (not already blocked or primary)
  const availableForBlock = allKnownSkills.filter(s => !blockedSkills.includes(s) && !primarySkills.includes(s));
  // Skills available for allow
  const availableForAllow = allKnownSkills.filter(s => !allowList.includes(s) && !primarySkills.includes(s));

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      PaperProps={{
        sx: {
          width: 420,
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
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <SettingsIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Skill Control — {agentName}
        </Typography>
      </Box>

      {/* ── Section 1: Skill Priority (Multipliers) ── */}
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<TuneIcon sx={{ fontSize: 14, color: 'primary.light' }} />}
          title="Skill Priority (Multipliers)"
        />
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5, lineHeight: 1.4 }}>
          Assign weight multipliers to any skill. Higher = more emphasis in prompt & task matching.
          Primary skills always persist (top priority).
        </Typography>

        {/* Multiplier rows */}
        {Object.entries(multipliers).map(([skill, value]) => (
          <Box key={skill} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
            <Typography variant="body2" sx={{ flexGrow: 1, fontSize: '0.8rem', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {skill}
              {primarySkills.includes(skill) && (
                <Typography component="span" variant="caption" sx={{ color: 'primary.light', ml: 0.5, fontSize: '0.6rem' }}>
                  PRIMARY
                </Typography>
              )}
            </Typography>
            <Select
              value={value}
              onChange={(e) => handleMultiplierChange(skill, e.target.value)}
              size="small"
              sx={{ width: 90, fontSize: '0.8rem', '& .MuiSelect-select': { py: 0.5 } }}
            >
              {MULTIPLIER_OPTIONS.map(m => (
                <MenuItem key={m} value={m} sx={{ fontSize: '0.8rem' }}>{m}x</MenuItem>
              ))}
            </Select>
            {!primarySkills.includes(skill) && (
              <IconButton size="small" onClick={() => handleRemoveMultiplier(skill)} sx={{ color: 'text.secondary', p: 0.25 }}>
                <DeleteOutlineIcon sx={{ fontSize: 16 }} />
              </IconButton>
            )}
          </Box>
        ))}

        {/* Add multiplier */}
        <Box sx={{ display: 'flex', gap: 0.75, mt: 1 }}>
          <Select
            value={newMultiplierSkill}
            onChange={(e) => setNewMultiplierSkill(e.target.value)}
            displayEmpty
            size="small"
            sx={{ flexGrow: 1, fontSize: '0.8rem' }}
            renderValue={(v) => v || <span style={{ color: theme.palette.text.secondary }}>+ Add skill multiplier...</span>}
          >
            {availableForMultiplier.map(s => (
              <MenuItem key={s} value={s} sx={{ fontSize: '0.8rem' }}>{s}</MenuItem>
            ))}
          </Select>
          <Button size="small" onClick={handleAddMultiplier} disabled={!newMultiplierSkill} sx={{ textTransform: 'none', fontSize: '0.75rem', minWidth: 50 }}>
            Add
          </Button>
        </Box>
      </Box>

      {/* ── Section 2: Block List ── */}
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<BlockIcon sx={{ fontSize: 14, color: 'error.main' }} />}
          title="Block List"
        />
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1, lineHeight: 1.4 }}>
          Skills this agent should NEVER use, even if suggested.
        </Typography>

        {blockedSkills.length > 0 ? (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
            {blockedSkills.map(skill => (
              <Chip
                key={skill}
                label={skill}
                size="small"
                onDelete={() => setBlockedSkills(prev => prev.filter(s => s !== skill))}
                sx={{
                  height: 22,
                  fontSize: '0.65rem',
                  backgroundColor: 'action.hover',
                  color: 'error.light',
                  '& .MuiChip-deleteIcon': { fontSize: 14, color: 'error.light' },
                }}
              />
            ))}
          </Box>
        ) : (
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1, fontStyle: 'italic' }}>
            No blocked skills
          </Typography>
        )}

        <Box sx={{ display: 'flex', gap: 0.75 }}>
          <Select
            value={newBlockSkill}
            onChange={(e) => { setNewBlockSkill(e.target.value); }}
            displayEmpty
            size="small"
            sx={{ flexGrow: 1, fontSize: '0.8rem' }}
            renderValue={(v) => v || <span style={{ color: theme.palette.text.secondary }}>Add to block list...</span>}
          >
            {availableForBlock.map(s => (
              <MenuItem key={s} value={s} sx={{ fontSize: '0.8rem' }}>{s}</MenuItem>
            ))}
          </Select>
          <Button size="small" onClick={handleAddBlocked} disabled={!newBlockSkill} sx={{ textTransform: 'none', fontSize: '0.75rem', minWidth: 50 }}>
            Block
          </Button>
        </Box>
      </Box>

      {/* ── Section 3: Allow List ── */}
      <Box sx={sectionSx}>
        <SectionTitle
          icon={<CheckCircleOutlineIcon sx={{ fontSize: 14, color: 'success.main' }} />}
          title="Allow List"
        />

        <FormControlLabel
          control={
            <Checkbox
              checked={restrictToAllowList}
              onChange={(e) => setRestrictToAllowList(e.target.checked)}
              size="small"
              sx={{ py: 0 }}
            />
          }
          label={
            <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.4 }}>
              Restrict to allow list only — agent can ONLY use primary skills + skills below
            </Typography>
          }
          sx={{ mb: 1, ml: -0.5 }}
        />

        {!restrictToAllowList && (
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1, fontStyle: 'italic' }}>
            Unchecked — agent can use any non-blocked skill
          </Typography>
        )}

        {allowList.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
            {allowList.map(skill => (
              <Chip
                key={skill}
                label={skill}
                size="small"
                onDelete={() => setAllowList(prev => prev.filter(s => s !== skill))}
                sx={{
                  height: 22,
                  fontSize: '0.65rem',
                  backgroundColor: 'action.hover',
                  color: 'success.light',
                  '& .MuiChip-deleteIcon': { fontSize: 14, color: 'success.light' },
                }}
              />
            ))}
          </Box>
        )}

        <Box sx={{ display: 'flex', gap: 0.75 }}>
          <Select
            value={newAllowSkill}
            onChange={(e) => setNewAllowSkill(e.target.value)}
            displayEmpty
            size="small"
            sx={{ flexGrow: 1, fontSize: '0.8rem' }}
            renderValue={(v) => v || <span style={{ color: theme.palette.text.secondary }}>Add to allow list...</span>}
          >
            {availableForAllow.map(s => (
              <MenuItem key={s} value={s} sx={{ fontSize: '0.8rem' }}>{s}</MenuItem>
            ))}
          </Select>
          <Button size="small" onClick={handleAddAllow} disabled={!newAllowSkill} sx={{ textTransform: 'none', fontSize: '0.75rem', minWidth: 50 }}>
            Allow
          </Button>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'divider', mb: 1.5 }} />

      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button size="small" onClick={handleReset} sx={{ textTransform: 'none', color: 'text.secondary', fontSize: '0.75rem' }}>
          Reset to Defaults
        </Button>
        <Button size="small" variant="contained" onClick={onClose} sx={{ textTransform: 'none', fontSize: '0.75rem' }}>
          Apply
        </Button>
      </Box>
    </Popover>
  );
}
