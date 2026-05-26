/**
 * SettingsDrawer — slide-out settings panel with ThemeSwitcher.
 */
import React from 'react';
import Drawer from '@mui/material/Drawer';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import { ThemeSwitcher } from '../../theme';

export default function SettingsDrawer({ open, onClose }) {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: 340,
          backgroundColor: 'background.paper',
          borderLeft: '1px solid',
          borderColor: 'divider',
          p: 3,
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          ⚙ Settings
        </Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </Box>

      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1.5 }}>
        Theme
      </Typography>
      <ThemeSwitcher variant="cards" />
    </Drawer>
  );
}
