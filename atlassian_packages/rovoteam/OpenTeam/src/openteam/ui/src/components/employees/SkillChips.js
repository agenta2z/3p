/**
 * SkillChips — editable skill chip list for AI agents.
 *
 * For AI agents: removable chips + "Add Primary Skill" + "Skill Control" + "Role Control" buttons.
 * For humans: static (non-removable) chips.
 */

import React, { useState, useMemo } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import Tooltip from '@mui/material/Tooltip';
import AddIcon from '@mui/icons-material/Add';
import TuneIcon from '@mui/icons-material/Tune';
import AddSkillPopover from './AddSkillPopover';
import SkillControlPopover from './SkillControlPopover';

export default function SkillChips({
  skills = [],
  role,
  agentName,
  editable = false,
  roleSkillsMap = {},
  onSkillsChange,
}) {
  const [addAnchorEl, setAddAnchorEl] = useState(null);
  const [controlAnchorEl, setControlAnchorEl] = useState(null);

  const handleRemove = (skillToRemove) => {
    const newSkills = skills.filter(s => s !== skillToRemove);
    onSkillsChange?.(newSkills);
  };

  const handleAdd = (skillName) => {
    if (!skills.includes(skillName)) {
      onSkillsChange?.([...skills, skillName]);
    }
  };

  const allKnownSkills = useMemo(() => {
    const set = new Set();
    Object.values(roleSkillsMap).forEach(r => {
      (r.skills || []).forEach(s => set.add(s));
    });
    return Array.from(set).sort();
  }, [roleSkillsMap]);

  const buttonSx = {
    height: 22,
    fontSize: '0.6rem',
    textTransform: 'none',
    borderRadius: 3,
    px: 1,
    minWidth: 0,
  };

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center' }}>
      {/* Add Primary Skill — first in row */}
      {editable && (
        <Tooltip
          title="Primary skills persist in this agent's skill list and are always included in the agent's prompt context."
          arrow
          placement="top"
        >
          <Button
            size="small"
            startIcon={<AddIcon sx={{ fontSize: '12px !important' }} />}
            onClick={(e) => setAddAnchorEl(e.currentTarget)}
            sx={{ ...buttonSx, color: 'primary.light', '&:hover': { backgroundColor: 'action.hover' } }}
          >
            Add Primary Skill
          </Button>
        </Tooltip>
      )}

      {/* Skill chips */}
      {skills.map((skill) => (
        <Chip
          key={skill}
          label={skill}
          size="small"
          onDelete={editable ? () => handleRemove(skill) : undefined}
          sx={{
            height: 22,
            fontSize: '0.6rem',
            backgroundColor: 'action.hover',
            color: 'text.secondary',
            '& .MuiChip-deleteIcon': {
              fontSize: 14,
              color: 'text.secondary',
              '&:hover': { color: 'error.main' },
            },
          }}
        />
      ))}

      {editable && (
        <>
          {/* Skill Control */}
          <Tooltip title="Configure skill priorities, block list, and allow list" arrow placement="top">
            <Button
              size="small"
              startIcon={<TuneIcon sx={{ fontSize: '12px !important' }} />}
              onClick={(e) => setControlAnchorEl(e.currentTarget)}
              sx={{ ...buttonSx, color: 'text.secondary', '&:hover': { backgroundColor: 'action.selected' } }}
            >
              Skill Control
            </Button>
          </Tooltip>

          {/* Popovers */}
          <AddSkillPopover
            anchorEl={addAnchorEl}
            open={Boolean(addAnchorEl)}
            onClose={() => setAddAnchorEl(null)}
            agentName={agentName}
            role={role}
            currentSkills={skills}
            roleSkillsMap={roleSkillsMap}
            onAdd={handleAdd}
          />

          <SkillControlPopover
            anchorEl={controlAnchorEl}
            open={Boolean(controlAnchorEl)}
            onClose={() => setControlAnchorEl(null)}
            agentName={agentName}
            primarySkills={skills}
            allKnownSkills={allKnownSkills}
          />

        </>
      )}
    </Box>
  );
}
