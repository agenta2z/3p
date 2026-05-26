import React, { useState, useEffect, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Button from '@mui/material/Button';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BoltIcon from '@mui/icons-material/Bolt';
import { useApiData } from '../../hooks/useApiData';
import { LoadingIndicator, EmptyState } from '../../shared';
import { TeamCard } from '../teams/TeamCard';
import { fetchJson } from '../../utils/api';

/* ------------------------------------------------------------------ */
/*  SuggestedActionsBanner — inline component for AI suggested actions */
/* ------------------------------------------------------------------ */

function SuggestedActionsBanner({ actions, loading }) {
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          p: 1.5,
          mb: 2,
          borderRadius: 2,
          backgroundColor: 'rgba(74, 144, 217, 0.06)',
          border: '1px solid rgba(74, 144, 217, 0.15)',
        }}
      >
        <CircularProgress size={14} sx={{ color: 'primary.light' }} />
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Loading AI suggestions...
        </Typography>
      </Box>
    );
  }

  if (!actions?.length) return null;

  return (
    <Box
      sx={{
        p: 2,
        mb: 3,
        borderRadius: 2,
        backgroundColor: 'rgba(74, 144, 217, 0.06)',
        border: '1px solid rgba(74, 144, 217, 0.15)',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
        <AutoAwesomeIcon sx={{ fontSize: 16, color: 'primary.light' }} />
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            color: 'primary.light',
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          AI Suggested Actions
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {actions.map((action, idx) => (
          <Box
            key={action.id || idx}
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 1,
              p: 1,
              borderRadius: 1,
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.04)' },
              transition: 'background-color 0.15s',
            }}
          >
            <BoltIcon sx={{ fontSize: 14, color: 'warning.main', mt: 0.25, flexShrink: 0 }} />
            <Box sx={{ minWidth: 0, flexGrow: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 500, lineHeight: 1.4 }}>
                {action.title || action.message}
              </Typography>
              {action.description && (
                <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.4 }}>
                  {action.description}
                </Typography>
              )}
            </Box>
            {action.action_label && (
              <Button
                size="small"
                variant="outlined"
                sx={{
                  fontSize: '0.65rem',
                  flexShrink: 0,
                  borderColor: 'rgba(255, 255, 255, 0.15)',
                  color: 'text.secondary',
                  textTransform: 'none',
                  whiteSpace: 'nowrap',
                }}
              >
                {action.action_label}
              </Button>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  TeamOverviewView — main view component                             */
/* ------------------------------------------------------------------ */

export default function TeamOverviewView() {
  const { data: teams, loading: teamsLoading, error: teamsError } = useApiData('/teams');
  const { data: suggestedActions, loading: actionsLoading } = useApiData(
    '/intelligence/suggested-actions?context=team'
  );

  // State for detailed team data (resolved members, projects)
  const [detailedTeams, setDetailedTeams] = useState([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  // Fetch full details for each team once the team list arrives
  const fetchTeamDetails = useCallback(async (teamList) => {
    if (!teamList?.length) {
      setDetailedTeams([]);
      return;
    }

    setDetailsLoading(true);
    setDetailsError(null);

    try {
      const detailPromises = teamList.map(async (team) => {
        try {
          const detail = await fetchJson(`/teams/${team.id}?resolve=members,projects`);
          return { ...team, ...detail };
        } catch (err) {
          // If a single team detail fails, use the summary data
          console.warn(`Failed to fetch details for team ${team.id}:`, err);
          return team;
        }
      });

      const results = await Promise.all(detailPromises);
      setDetailedTeams(results);
    } catch (err) {
      console.error('Failed to fetch team details:', err);
      setDetailsError(err);
      // Fall back to summary data
      setDetailedTeams(teamList);
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (teams?.length) {
      fetchTeamDetails(teams);
    }
  }, [teams, fetchTeamDetails]);

  // Loading state
  if (teamsLoading) return <LoadingIndicator text="Loading teams..." />;

  // Error state
  if (teamsError) {
    return (
      <Typography color="error">
        Failed to load teams: {teamsError.message}
      </Typography>
    );
  }

  // Empty state
  if (!teams?.length) return <EmptyState message="No teams found" />;

  // Determine which data to render — prefer detailed, fall back to summary
  const teamsToRender = detailedTeams.length > 0 ? detailedTeams : teams;

  return (
    <Box>
      {/* Page header */}
      <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 600 }}>
        My Teams — AI-Powered Team Orchestration
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
        {teams.length} team{teams.length !== 1 ? 's' : ''} actively managed
      </Typography>

      {/* Suggested actions banner */}
      <SuggestedActionsBanner actions={suggestedActions} loading={actionsLoading} />

      {/* Loading indicator for details fetch */}
      {detailsLoading && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <CircularProgress size={14} />
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Loading team details...
          </Typography>
        </Box>
      )}

      {/* Details error (non-fatal) */}
      {detailsError && (
        <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mb: 2 }}>
          Some team details could not be loaded. Showing available data.
        </Typography>
      )}

      {/* Team cards */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {teamsToRender.map((team) => (
          <TeamCard key={team.id} team={team} />
        ))}
      </Box>
    </Box>
  );
}
