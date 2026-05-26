import React, { useState } from 'react';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
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
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        border: '1px dashed rgba(255, 255, 255, 0.15)',
        borderRadius: 3,
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1.5,
        height: '100%',
      }}
    >
      {/* Dashed circle with + icon */}
      <Box
        sx={{
          width: 56,
          height: 56,
          border: '2px dashed rgba(255, 255, 255, 0.25)',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <AddIcon sx={{ fontSize: 28, color: 'text.secondary' }} />
      </Box>

      {/* Title and subtitle */}
      <Typography variant="h6" sx={{ fontWeight: 600, textAlign: 'center' }}>
        Hire New AI Employee
      </Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary', textAlign: 'center' }}>
        Expand your team with a new AI employee
      </Typography>

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
              backgroundColor: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              cursor: 'pointer',
              transition: 'background-color 0.15s, border-color 0.15s',
              '&:hover': {
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                borderColor: 'rgba(255, 255, 255, 0.2)',
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
