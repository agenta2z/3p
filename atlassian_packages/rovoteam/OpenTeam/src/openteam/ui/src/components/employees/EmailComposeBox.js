import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import CloseIcon from '@mui/icons-material/Close';

const URGENCY_OPTIONS = [
  { value: 'Normal', estimate: '~8 hours' },
  { value: 'High', estimate: '~2 hours' },
  { value: 'Critical', estimate: '~30 minutes' },
];

export default function EmailComposeBox({ agentName, onClose, onSend }) {
  const [urgency, setUrgency] = useState('Normal');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sent, setSent] = useState(false);

  const estimate = URGENCY_OPTIONS.find((o) => o.value === urgency)?.estimate || '~8 hours';

  const handleSend = () => {
    if (onSend) onSend({ urgency, subject, body });
    setSent(true);
    setTimeout(() => {
      if (onClose) onClose();
    }, 1500);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.75,
          borderBottom: '1px solid', borderBottomColor: 'divider',
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
          Email {agentName}
        </Typography>
        <IconButton size="small" onClick={onClose} sx={{ p: 0.25 }}>
          <CloseIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
        </IconButton>
      </Box>

      {sent ? (
        <Box sx={{ px: 1.5, py: 3, textAlign: 'center' }}>
          <Typography variant="caption" sx={{ color: 'success.main', fontWeight: 600, fontSize: '0.85rem' }}>
            Email sent!
          </Typography>
        </Box>
      ) : (
        <Box sx={{ px: 1.5, py: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {/* Urgency */}
          <TextField
            select
            size="small"
            label="Urgency"
            value={urgency}
            onChange={(e) => setUrgency(e.target.value)}
            sx={{ '& .MuiInputBase-root': { fontSize: '0.8rem' } }}
          >
            {URGENCY_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: '0.8rem' }}>
                {opt.value}
              </MenuItem>
            ))}
          </TextField>

          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem', mt: -0.5 }}>
            Estimated response time: {estimate}
          </Typography>

          {/* Subject */}
          <TextField
            size="small"
            label="Subject"
            fullWidth
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            sx={{ '& .MuiInputBase-root': { fontSize: '0.8rem' } }}
          />

          {/* Body */}
          <TextField
            size="small"
            label="Body"
            fullWidth
            multiline
            rows={3}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            sx={{ '& .MuiInputBase-root': { fontSize: '0.8rem' } }}
          />

          {/* Buttons */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, pt: 0.5, pb: 0.5 }}>
            <Button
              size="small"
              onClick={onClose}
              sx={{
                textTransform: 'none',
                fontSize: '0.7rem',
                color: 'text.secondary',
              }}
            >
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              onClick={handleSend}
              disabled={!subject.trim() || !body.trim()}
              sx={{
                textTransform: 'none',
                fontSize: '0.7rem',
              }}
            >
              Send Email
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}
