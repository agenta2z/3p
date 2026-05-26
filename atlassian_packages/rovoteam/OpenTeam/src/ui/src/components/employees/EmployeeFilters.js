import React from 'react';
import Box from '@mui/material/Box';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';

/**
 * EmployeeFilters — filter bar for the employees view.
 *
 * Props:
 *   filters        - { type: 'all'|'ai'|'human', teamId: string|'', status: string|'' }
 *   onFilterChange - (key, value) => void
 *   teams          - array of { id, name } for the team dropdown
 */
export function EmployeeFilters({ filters, onFilterChange, teams = [] }) {
  const handleTypeChange = (_event, newType) => {
    if (newType !== null) {
      onFilterChange('type', newType);
    }
  };

  const selectSx = {
    minWidth: 140,
    '& .MuiInputBase-root': {
      fontSize: '0.8rem',
      height: 36,
    },
    '& .MuiInputLabel-root': {
      fontSize: '0.8rem',
    },
    '& .MuiOutlinedInput-notchedOutline': {
      borderColor: 'rgba(255, 255, 255, 0.12)',
    },
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        flexWrap: 'wrap',
        mb: 3,
        p: 1.5,
        borderRadius: 2,
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid rgba(255, 255, 255, 0.06)',
      }}
    >
      {/* Type toggle */}
      <ToggleButtonGroup
        value={filters.type}
        exclusive
        onChange={handleTypeChange}
        size="small"
        sx={{
          '& .MuiToggleButton-root': {
            textTransform: 'none',
            fontSize: '0.75rem',
            px: 1.5,
            py: 0.5,
            borderColor: 'rgba(255, 255, 255, 0.12)',
            color: 'text.secondary',
            '&.Mui-selected': {
              backgroundColor: 'rgba(74, 144, 217, 0.15)',
              color: 'primary.light',
              borderColor: 'rgba(74, 144, 217, 0.3)',
              '&:hover': {
                backgroundColor: 'rgba(74, 144, 217, 0.2)',
              },
            },
          },
        }}
      >
        <ToggleButton value="all">All</ToggleButton>
        <ToggleButton value="ai">AI Employees</ToggleButton>
        <ToggleButton value="human">Humans</ToggleButton>
      </ToggleButtonGroup>

      {/* Team filter */}
      <FormControl size="small" sx={selectSx}>
        <InputLabel>Team</InputLabel>
        <Select
          value={filters.teamId}
          label="Team"
          onChange={(e) => onFilterChange('teamId', e.target.value)}
        >
          <MenuItem value="">
            <em>All Teams</em>
          </MenuItem>
          {teams.map((team) => (
            <MenuItem key={team.id} value={team.id}>
              {team.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Status filter */}
      <FormControl size="small" sx={selectSx}>
        <InputLabel>Status</InputLabel>
        <Select
          value={filters.status}
          label="Status"
          onChange={(e) => onFilterChange('status', e.target.value)}
        >
          <MenuItem value="">
            <em>All Statuses</em>
          </MenuItem>
          <MenuItem value="active">Active</MenuItem>
          <MenuItem value="idle">Idle</MenuItem>
          <MenuItem value="away">Away</MenuItem>
          <MenuItem value="pending">Pending</MenuItem>
          <MenuItem value="queued">Queued</MenuItem>
        </Select>
      </FormControl>
    </Box>
  );
}

export default EmployeeFilters;
