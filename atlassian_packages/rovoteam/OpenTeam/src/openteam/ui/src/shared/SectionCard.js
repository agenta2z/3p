/**
 * SectionCard — card container with title, optional icon, and collapse.
 * Uses theme surface tokens.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Collapse from '@mui/material/Collapse';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTheme } from '@mui/material/styles';

export function SectionCard({ title, icon, children, collapsible = false, defaultExpanded = true, action, subtitle }) {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <Paper elevation={0} sx={{
      backgroundColor: theme.custom.surfaces.cardBg,
      border: `1px solid ${theme.custom.surfaces.cardBorder}`,
      borderRadius: 2, overflow: 'hidden',
    }}>
      <Box onClick={collapsible ? () => setExpanded(!expanded) : undefined} sx={{
        display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.25,
        cursor: collapsible ? 'pointer' : 'default',
        '&:hover': collapsible ? { backgroundColor: theme.custom.surfaces.hoverBg } : {},
      }}>
        {icon && <Box sx={{ display: 'flex', color: 'text.secondary', fontSize: 18 }}>{icon}</Box>}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 0.5, fontSize: '0.7rem' }}>{title}</Typography>
          {subtitle && <Typography variant="caption" sx={{ color: 'text.secondary' }}>{subtitle}</Typography>}
        </Box>
        {action && <Box>{action}</Box>}
        {collapsible && (
          <IconButton size="small" sx={{ color: 'text.secondary' }}>
            <ExpandMoreIcon sx={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s', fontSize: 18 }} />
          </IconButton>
        )}
      </Box>
      {collapsible ? <Collapse in={expanded}><Box sx={{ px: 2, pb: 2 }}>{children}</Box></Collapse> : <Box sx={{ px: 2, pb: 2 }}>{children}</Box>}
    </Paper>
  );
}

export default SectionCard;
