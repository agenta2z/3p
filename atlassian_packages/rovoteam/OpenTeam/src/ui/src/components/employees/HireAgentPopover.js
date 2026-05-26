import React, { useState, useEffect, useMemo } from 'react';
import Popover from '@mui/material/Popover';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';

const AUTONOMY_LEVELS = ['Low', 'Medium', 'High', 'Full'];

export default function HireAgentPopover({
  anchorEl,
  open,
  onClose,
  role,
  roleSkillsMap,
  teams,
  suggestedName,
}) {
  const [agentName, setAgentName] = useState(suggestedName || '');
  const [teamId, setTeamId] = useState('');
  const [autonomy, setAutonomy] = useState('Medium');
  const [hireNotes, setHireNotes] = useState('');
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [hired, setHired] = useState(false);

  // Derive skill pool from roleSkillsMap for the selected role
  const skillPool = useMemo(() => {
    if (!role || !roleSkillsMap) return [];
    // Try exact match first, then loose match
    const pool = roleSkillsMap[role] || [];
    return Array.isArray(pool) ? pool : [];
  }, [role, roleSkillsMap]);

  // Reset form whenever the popover opens with a new role
  useEffect(() => {
    if (open) {
      setAgentName(suggestedName || '');
      setTeamId('');
      setAutonomy('Medium');
      setHireNotes('');
      setHired(false);
      // Pre-check the first 4-5 skills as defaults
      const defaults = skillPool.slice(0, Math.min(5, skillPool.length));
      setSelectedSkills(defaults);
    }
  }, [open, suggestedName, skillPool]);

  const handleSkillToggle = (skill) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  const handleHire = () => {
    setHired(true);
    setTimeout(() => {
      onClose();
    }, 2000);
  };

  return (
    <Popover
      open={open}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      transformOrigin={{ vertical: 'top', horizontal: 'center' }}
      slotProps={{
        paper: {
          sx: { width: 420, p: 2.5, borderRadius: 2 },
        },
      }}
    >
      {/* Success message */}
      {hired ? (
        <Alert severity="success" sx={{ m: 1 }}>
          {agentName} ({role}) hired!
        </Alert>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Header */}
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            {'\u{1F680}'} Hire New AI Employee &mdash; {role}
          </Typography>

          {/* Agent Name */}
          <TextField
            label="Agent Name"
            size="small"
            fullWidth
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            helperText="Auto-suggested. You can change it."
          />

          {/* Team Assignment */}
          <FormControl size="small" fullWidth>
            <InputLabel>Team</InputLabel>
            <Select
              value={teamId}
              label="Team"
              onChange={(e) => setTeamId(e.target.value)}
            >
              {(teams || []).map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Starting Skills */}
          {skillPool.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.5, display: 'block' }}>
                Starting Skills
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {skillPool.map((skill) => (
                  <FormControlLabel
                    key={skill}
                    control={
                      <Checkbox
                        size="small"
                        checked={selectedSkills.includes(skill)}
                        onChange={() => handleSkillToggle(skill)}
                      />
                    }
                    label={<Typography variant="body2">{skill}</Typography>}
                    sx={{ ml: 0, height: 32 }}
                  />
                ))}
              </Box>
            </Box>
          )}

          {/* Autonomy Level */}
          <FormControl size="small" fullWidth>
            <InputLabel>Autonomy Level</InputLabel>
            <Select
              value={autonomy}
              label="Autonomy Level"
              onChange={(e) => setAutonomy(e.target.value)}
            >
              {AUTONOMY_LEVELS.map((level) => (
                <MenuItem key={level} value={level}>
                  {level}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Hire Notes */}
          <TextField
            label="Hire Notes"
            size="small"
            fullWidth
            multiline
            rows={2}
            value={hireNotes}
            onChange={(e) => setHireNotes(e.target.value)}
            placeholder="Optional notes..."
          />

          {/* Footer buttons */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 0.5 }}>
            <Button size="small" onClick={onClose}>
              Cancel
            </Button>
            <Button size="small" variant="contained" onClick={handleHire}>
              {'\u{1F680}'} Hire Employee
            </Button>
          </Box>
        </Box>
      )}
    </Popover>
  );
}
