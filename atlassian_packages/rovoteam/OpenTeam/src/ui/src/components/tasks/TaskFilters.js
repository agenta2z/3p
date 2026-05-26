/**
 * TaskFilters — filter bar for the Tasks view.
 *
 * Provides status chip toggles, and dropdowns for priority,
 * project, and assignee.
 *
 * Props:
 *   filters        - { status, priority, projectId, assigneeId }
 *   onFilterChange - (key, value) => void
 *   projects       - array of project objects (need id, name)
 *   employees      - array of employee objects (need id, name)
 */

import React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';
import FilterListIcon from '@mui/icons-material/FilterList';

/* ------------------------------------------------------------------ */
/*  Constants                                                           */
/* ------------------------------------------------------------------ */

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'backlog', label: 'Backlog' },
  { value: 'in-progress', label: 'In Progress' },
  { value: 'in-review', label: 'In Review' },
  { value: 'done', label: 'Done' },
  { value: 'pending', label: 'Pending' },
];

const PRIORITY_OPTIONS = [
  { value: 'all', label: 'All Priorities' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

/* ------------------------------------------------------------------ */
/*  Dropdown style helper                                               */
/* ------------------------------------------------------------------ */

const selectSx = {
  minWidth: 150,
  '& .MuiOutlinedInput-root': {
    borderRadius: 2,
    fontSize: '0.8rem',
  },
  '& .MuiInputLabel-root': {
    fontSize: '0.8rem',
  },
  '& .MuiSelect-select': {
    py: 1,
    fontSize: '0.8rem',
  },
};

/* ------------------------------------------------------------------ */
/*  TaskFilters                                                         */
/* ------------------------------------------------------------------ */

export function TaskFilters({ filters, onFilterChange, projects, employees }) {
  const currentStatus = filters?.status || 'all';
  const currentPriority = filters?.priority || 'all';
  const currentProjectId = filters?.projectId || 'all';
  const currentAssigneeId = filters?.assigneeId || 'all';

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        p: 2,
        borderRadius: 2,
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      {/* Label row */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <FilterListIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Filters
        </Typography>
      </Box>

      {/* Status chip toggles */}
      <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
        {STATUS_OPTIONS.map((opt) => {
          const isActive = currentStatus === opt.value;
          return (
            <Chip
              key={opt.value}
              label={opt.label}
              size="small"
              variant={isActive ? 'filled' : 'outlined'}
              onClick={() => onFilterChange('status', opt.value)}
              sx={{
                fontWeight: isActive ? 600 : 400,
                backgroundColor: isActive ? 'rgba(74, 144, 217, 0.15)' : 'transparent',
                borderColor: isActive ? 'primary.main' : 'rgba(255, 255, 255, 0.15)',
                color: isActive ? 'primary.light' : 'text.secondary',
                '&:hover': {
                  backgroundColor: isActive
                    ? 'rgba(74, 144, 217, 0.2)'
                    : 'rgba(255, 255, 255, 0.06)',
                },
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            />
          );
        })}
      </Box>

      {/* Dropdowns row */}
      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
        {/* Priority dropdown */}
        <FormControl size="small" sx={selectSx}>
          <InputLabel>Priority</InputLabel>
          <Select
            value={currentPriority}
            label="Priority"
            onChange={(e) => onFilterChange('priority', e.target.value)}
          >
            {PRIORITY_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Project dropdown */}
        <FormControl size="small" sx={selectSx}>
          <InputLabel>Project</InputLabel>
          <Select
            value={currentProjectId}
            label="Project"
            onChange={(e) => onFilterChange('projectId', e.target.value)}
          >
            <MenuItem value="all">All Projects</MenuItem>
            {(projects || []).map((proj) => (
              <MenuItem key={proj.id} value={proj.id}>
                {proj.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Assignee dropdown */}
        <FormControl size="small" sx={selectSx}>
          <InputLabel>Assignee</InputLabel>
          <Select
            value={currentAssigneeId}
            label="Assignee"
            onChange={(e) => onFilterChange('assigneeId', e.target.value)}
          >
            <MenuItem value="all">All Assignees</MenuItem>
            {(employees || []).map((emp) => (
              <MenuItem key={emp.id} value={emp.id}>
                {emp.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
    </Box>
  );
}

export default TaskFilters;
