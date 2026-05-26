import React from 'react';
import Box from '@mui/material/Box';
import PeopleIcon from '@mui/icons-material/People';
import { SectionCard, PersonChip } from '../../shared';

export function HumanTeamSection({ humans = [] }) {
  if (!humans.length) return null;

  return (
    <SectionCard
      title="Human Team"
      icon={<PeopleIcon sx={{ fontSize: 18 }} />}
    >
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {humans.map((person) => (
          <PersonChip
            key={person.id}
            name={person.name}
            role={person.role}
            type={person.type || 'human'}
            size="small"
          />
        ))}
      </Box>
    </SectionCard>
  );
}

export default HumanTeamSection;
