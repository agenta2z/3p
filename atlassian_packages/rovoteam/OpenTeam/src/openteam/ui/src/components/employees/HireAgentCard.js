import React, { useState } from 'react';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import AddIcon from '@mui/icons-material/Add';
import ScienceIcon from '@mui/icons-material/Science';
import SchoolIcon from '@mui/icons-material/School';
import HireAgentPopover from './HireAgentPopover';

const GREEK = ['Alpha','Beta','Gamma','Delta','Epsilon','Zeta','Eta','Theta','Iota','Kappa','Lambda','Mu'];

const ROLES = [
  { name: 'Machine Learning Engineer', emoji: '\u{1F9E0}' },
  { name: 'Software Engineer',         emoji: '\u{1F527}' },
  { name: 'QA / Testing Engineer',     emoji: '\u{1F9EA}' },
  { name: 'Program Manager',           emoji: '\u{1F4CB}' },
  { name: 'UX Designer',               emoji: '\u{1F3A8}' },
  { name: 'Custom Role...',            emoji: '\u{2795}' },
];

export default function HireAgentCard({ roleSkillsMap, teams, existingAgentCount }) {
  const [selectedRole, setSelectedRole] = useState(null);
  const [popoverAnchor, setPopoverAnchor] = useState(null);
  const [onboarding, setOnboarding] = useState(['ai-lab']);

  const suggestedName = `Agent-${GREEK[existingAgentCount] || 'New'}`;

  const handleRoleClick = (event, role) => {
    setSelectedRole(role.name);
    setPopoverAnchor(event.currentTarget);
  };

  const handlePopoverClose = () => {
    setPopoverAnchor(null);
    setSelectedRole(null);
  };

  return (
    <Paper
      elevation={0}
      sx={{
        backgroundColor: 'action.hover',
        border: '1px dashed', borderColor: 'divider',
        borderRadius: 3,
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        height: '100%',
      }}
    >
      {/* Header row: icon + title/subtitle */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, width: '100%' }}>
        <Box
          sx={{
            width: 44,
            height: 44,
            border: '2px dashed', borderColor: 'divider',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <AddIcon sx={{ fontSize: 22, color: 'text.secondary' }} />
        </Box>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
            Hire New AI Employee
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Expand your team with a new AI employee
          </Typography>
        </Box>
      </Box>

      {/* Onboarding procedure multi-select dropdown */}
      <Box sx={{ width: '100%', mt: 0.5 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.6rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', mb: 0.5 }}>
          Onboarding Procedures
        </Typography>
        <Select
          multiple
          value={onboarding}
          onChange={(e) => setOnboarding(e.target.value)}
          size="small"
          fullWidth
          renderValue={(selected) => selected.map(v => v === 'ai-lab' ? 'AI-Lab Onboarding' : 'General Onboarding').join(', ')}
          sx={{ fontSize: '0.8rem' }}
        >
          <MenuItem value="ai-lab" sx={{ fontSize: '0.8rem' }}>
            <Checkbox size="small" checked={onboarding.includes('ai-lab')} sx={{ py: 0 }} />
            <ScienceIcon sx={{ fontSize: 14, color: 'primary.main', mr: 0.75 }} />
            <ListItemText primary="AI-Lab Onboarding" primaryTypographyProps={{ fontSize: '0.8rem' }} />
          </MenuItem>
          <MenuItem value="general" sx={{ fontSize: '0.8rem' }}>
            <Checkbox size="small" checked={onboarding.includes('general')} sx={{ py: 0 }} />
            <SchoolIcon sx={{ fontSize: 14, color: 'success.main', mr: 0.75 }} />
            <ListItemText primary="General Onboarding" primaryTypographyProps={{ fontSize: '0.8rem' }} />
          </MenuItem>
        </Select>
      </Box>

      {/* 2x3 role button grid */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 1,
          width: '100%',
          mt: 1,
        }}
      >
        {ROLES.map((role) => (
          <Paper
            key={role.name}
            elevation={0}
            onClick={(e) => handleRoleClick(e, role)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.75,
              px: 1.25,
              py: 0.75,
              borderRadius: 1.5,
              backgroundColor: 'action.hover',
              border: '1px solid', borderColor: 'divider',
              cursor: 'pointer',
              transition: 'background-color 0.15s, border-color 0.15s',
              '&:hover': {
                backgroundColor: 'action.selected',
                borderColor: 'divider',
              },
            }}
          >
            <Typography sx={{ fontSize: '1rem', lineHeight: 1 }}>{role.emoji}</Typography>
            <Typography variant="caption" sx={{ fontWeight: 500, lineHeight: 1.2 }}>
              {role.name}
            </Typography>
          </Paper>
        ))}
      </Box>

      {/* Popover for hiring */}
      <HireAgentPopover
        anchorEl={popoverAnchor}
        open={Boolean(popoverAnchor)}
        onClose={handlePopoverClose}
        role={selectedRole}
        roleSkillsMap={roleSkillsMap}
        teams={teams}
        suggestedName={suggestedName}
      />
    </Paper>
  );
}
