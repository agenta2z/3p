import React, { useState, useMemo, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import { useApiData } from '../../hooks/useApiData';
import { LoadingIndicator, EmptyState } from '../../shared';
import { EmployeeCard } from '../employees/EmployeeCard';
import { EmployeeFilters } from '../employees/EmployeeFilters';
import HireAgentCard from '../employees/HireAgentCard';

/* ------------------------------------------------------------------ */
/*  Section header for AI / Human groups                               */
/* ------------------------------------------------------------------ */

function SectionHeader({ icon, title, count }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, mt: 1 }}>
      {icon}
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
        {title}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          color: 'text.secondary',
          backgroundColor: 'rgba(255, 255, 255, 0.06)',
          px: 1,
          py: 0.25,
          borderRadius: 1,
          fontWeight: 500,
        }}
      >
        {count}
      </Typography>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Responsive grid for employee cards                                 */
/* ------------------------------------------------------------------ */

const cardGridSx = {
  display: 'grid',
  gap: 2,
  gridTemplateColumns: {
    xs: '1fr',
    sm: 'repeat(2, 1fr)',
    md: 'repeat(3, 1fr)',
  },
};

/* ------------------------------------------------------------------ */
/*  EmployeesView — main view component                                */
/* ------------------------------------------------------------------ */

export default function EmployeesView() {
  const { data: employees, loading: employeesLoading, error: employeesError } = useApiData('/employees');
  const { data: teams } = useApiData('/teams');
  const { data: roleSkillsMap } = useApiData('/role-skills');
  const { data: roleConfigs } = useApiData('/role-skills/configs');

  // Filter state
  const [filters, setFilters] = useState({
    type: 'all',
    teamId: '',
    status: '',
  });

  const handleFilterChange = useCallback((key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Apply filters client-side
  const filteredEmployees = useMemo(() => {
    if (!employees?.length) return [];

    return employees.filter((emp) => {
      // Type filter
      if (filters.type === 'ai' && emp.type !== 'ai') return false;
      if (filters.type === 'human' && emp.type === 'ai') return false;

      // Team filter
      if (filters.teamId) {
        const empTeamIds = emp.team_ids || [];
        if (!empTeamIds.includes(filters.teamId)) return false;
      }

      // Status filter
      if (filters.status && emp.status !== filters.status) return false;

      return true;
    });
  }, [employees, filters]);

  // Split into AI and human groups
  const aiEmployees = useMemo(
    () => filteredEmployees.filter((e) => e.type === 'ai'),
    [filteredEmployees]
  );
  const humanEmployees = useMemo(
    () => filteredEmployees.filter((e) => e.type !== 'ai'),
    [filteredEmployees]
  );

  // Total counts (unfiltered)
  const totalAI = employees?.filter((e) => e.type === 'ai').length ?? 0;
  const totalHuman = (employees?.length ?? 0) - totalAI;

  // Team options for filter dropdown
  const teamOptions = useMemo(
    () => (teams || []).map((t) => ({ id: t.id, name: t.name })),
    [teams]
  );

  // Loading state
  if (employeesLoading) return <LoadingIndicator text="Loading employees..." />;

  // Error state
  if (employeesError) {
    return (
      <Typography color="error">
        Failed to load employees: {employeesError.message}
      </Typography>
    );
  }

  // Empty state (no data at all)
  if (!employees?.length) return <EmptyState message="No employees found" />;

  return (
    <Box>
      {/* Page header */}
      <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 600 }}>
        Team Members
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
        {employees.length} total — {totalAI} AI employee{totalAI !== 1 ? 's' : ''}, {totalHuman} human{totalHuman !== 1 ? 's' : ''}
      </Typography>

      {/* Filter bar */}
      <EmployeeFilters
        filters={filters}
        onFilterChange={handleFilterChange}
        teams={teamOptions}
      />

      {/* Empty filtered state */}
      {filteredEmployees.length === 0 && (
        <EmptyState message="No employees match the current filters" />
      )}

      {/* AI Employees section */}
      {aiEmployees.length > 0 && (
        <>
          <SectionHeader
            icon={<SmartToyIcon sx={{ fontSize: 20, color: '#4a90d9' }} />}
            title="AI Employees"
            count={aiEmployees.length}
          />
          <Box sx={cardGridSx}>
            {aiEmployees.map((emp) => (
              <EmployeeCard key={emp.id} employee={emp} roleSkillsMap={roleSkillsMap || {}} roleConfigs={roleConfigs || {}} />
            ))}
            <HireAgentCard
              roleSkillsMap={roleSkillsMap || {}}
              teams={teamOptions}
              existingAgentCount={aiEmployees.length}
            />
          </Box>
        </>
      )}

      {/* Humans section */}
      {humanEmployees.length > 0 && (
        <>
          <SectionHeader
            icon={<PersonIcon sx={{ fontSize: 20, color: '#4caf50' }} />}
            title="Humans"
            count={humanEmployees.length}
          />
          <Box sx={cardGridSx}>
            {humanEmployees.map((emp) => (
              <EmployeeCard key={emp.id} employee={emp} roleSkillsMap={roleSkillsMap || {}} roleConfigs={roleConfigs || {}} />
            ))}
          </Box>
        </>
      )}
    </Box>
  );
}
