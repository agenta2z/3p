import React from 'react';
import Box from '@mui/material/Box';
import { QuickLinkButton } from '../../shared';

export function QuickLinksRow({ links = [] }) {
  if (!links.length) return null;

  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
      {links.map((link, idx) => (
        <QuickLinkButton
          key={link.url || idx}
          label={link.label}
          url={link.url}
          icon={link.icon}
        />
      ))}
    </Box>
  );
}

export default QuickLinksRow;
