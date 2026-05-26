/**
 * BackendSelector — dropdown + badge for the active conversation backend
 * of the current session.
 *
 * Behavior:
 *   - Shows server-default badge until the user picks something different.
 *   - Unavailable backends (e.g., claude_cli without claude on PATH) are
 *     listed but disabled, with the status_message in the tooltip.
 *   - On change, POSTs /api/sessions/{sessionId}/backend so the next turn
 *     uses the new backend (server evicts the cached inferencer).
 *
 * Designed as a small, drop-in component for the session header.
 */

import React, { useState, useMemo, useEffect } from 'react';
import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import { useTheme } from '@mui/material/styles';
import { useServerBackends } from '../../hooks/useServerBackends';

export function BackendSelector({ sessionId, sessionLlmBackend, sessionLlmModel, onChanged }) {
  const theme = useTheme();
  const { backends, defaultBackend, defaultModel, loading, error } = useServerBackends();
  const [anchorEl, setAnchorEl] = useState(null);
  const [activeBackend, setActiveBackend] = useState(sessionLlmBackend || null);
  const [activeModel, setActiveModel] = useState(sessionLlmModel || null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // If parent props change (e.g., after refetch), sync local state.
  useEffect(() => {
    if (sessionLlmBackend !== undefined) setActiveBackend(sessionLlmBackend || null);
    if (sessionLlmModel !== undefined) setActiveModel(sessionLlmModel || null);
  }, [sessionLlmBackend, sessionLlmModel]);

  const effectiveBackend = activeBackend || defaultBackend;
  const effectiveModel = activeModel || (() => {
    const desc = backends.find((b) => b.name === effectiveBackend);
    return desc?.default_model || defaultModel;
  })();

  const open = Boolean(anchorEl);
  const handleOpen = (e) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handlePick = async (name) => {
    handleClose();
    if (!sessionId) return;
    if (name === effectiveBackend) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const desc = backends.find((b) => b.name === name);
      const model = desc?.default_model || null;
      const res = await fetch(`/api/sessions/${sessionId}/backend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backend: name, model }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail?.error || `HTTP ${res.status}`);
      }
      const json = await res.json();
      setActiveBackend(json.llm_backend || name);
      setActiveModel(json.llm_model || model);
      if (onChanged) onChanged({ backend: name, model });
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Render
  if (loading) {
    return <CircularProgress size={16} sx={{ ml: 1 }} />;
  }
  if (error) {
    return (
      <Tooltip title={`Could not load backends: ${error.message}`}>
        <Chip
          label="backend ?"
          size="small"
          variant="outlined"
          sx={{ ml: 1, color: 'warning.main' }}
        />
      </Tooltip>
    );
  }

  const badgeLabel = effectiveModel
    ? `${effectiveBackend} · ${effectiveModel}`
    : effectiveBackend || 'backend ?';

  const tooltip = submitError
    ? `Last switch failed: ${submitError}`
    : 'Click to change LLM backend for this session';

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
      <Tooltip title={tooltip}>
        <Chip
          label={submitting ? 'switching...' : badgeLabel}
          size="small"
          variant="outlined"
          onClick={sessionId ? handleOpen : undefined}
          sx={{
            ml: 1,
            cursor: sessionId ? 'pointer' : 'default',
            color: submitError ? 'warning.main' : 'text.secondary',
            borderColor: theme.custom?.surfaces?.cardBorder || 'rgba(255,255,255,0.12)',
          }}
        />
      </Tooltip>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
        {backends.map((b) => {
          const disabled = !b.available;
          const isCurrent = b.name === effectiveBackend;
          const label = b.default_model
            ? `${b.display_name} (${b.default_model})`
            : b.display_name;
          return (
            <Tooltip
              key={b.name}
              title={b.status_message || ''}
              placement="left"
              arrow
            >
              <span>
                <MenuItem
                  disabled={disabled}
                  selected={isCurrent}
                  onClick={() => handlePick(b.name)}
                >
                  {label}
                  {disabled && (
                    <Box
                      component="span"
                      sx={{ ml: 1, color: 'text.disabled', fontSize: '0.75rem' }}
                    >
                      (unavailable)
                    </Box>
                  )}
                </MenuItem>
              </span>
            </Tooltip>
          );
        })}
      </Menu>
    </Box>
  );
}

export default BackendSelector;
