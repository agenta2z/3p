import React, { useState, useEffect, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BoltIcon from '@mui/icons-material/Bolt';
import { useApiData } from '../../hooks/useApiData';
import { LoadingIndicator, EmptyState } from '../../shared';
import { ProjectCard } from '../projects/ProjectCard';
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
/*  ProjectsView — main view component                                 */
/* ------------------------------------------------------------------ */

export default function ProjectsView() {
  const { data: projects, loading: projectsLoading, error: projectsError } = useApiData('/projects');
  const { data: suggestedActions, loading: actionsLoading } = useApiData(
    '/intelligence/suggested-actions?context=projects'
  );

  // State for detailed project data (resolved agents, humans, tasks)
  const [detailedProjects, setDetailedProjects] = useState([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  // Fetch full details for each project once the project list arrives
  const fetchProjectDetails = useCallback(async (projectList) => {
    if (!projectList?.length) {
      setDetailedProjects([]);
      return;
    }

    setDetailsLoading(true);
    setDetailsError(null);

    try {
      const detailPromises = projectList.map(async (proj) => {
        try {
          const detail = await fetchJson(`/projects/${proj.id}`);
          return { ...proj, ...detail };
        } catch (err) {
          // If a single project detail fails, use the summary data
          console.warn(`Failed to fetch details for project ${proj.id}:`, err);
          return proj;
        }
      });

      const results = await Promise.all(detailPromises);
      setDetailedProjects(results);
    } catch (err) {
      console.error('Failed to fetch project details:', err);
      setDetailsError(err);
      // Fall back to summary data
      setDetailedProjects(projectList);
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (projects?.length) {
      fetchProjectDetails(projects);
    }
  }, [projects, fetchProjectDetails]);

  // Loading state
  if (projectsLoading) return <LoadingIndicator />;

  // Error state
  if (projectsError) {
    return (
      <Typography color="error">
        Failed to load projects: {projectsError.message}
      </Typography>
    );
  }

  // Empty state
  if (!projects?.length) return <EmptyState message="No projects found" />;

  // Determine which data to render — prefer detailed, fall back to summary
  const projectsToRender = detailedProjects.length > 0 ? detailedProjects : projects;

  return (
    <Box>
      {/* Page header */}
      <Typography variant="h5" sx={{ mb: 0.5, fontWeight: 600 }}>
        My Projects
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
        AI agents actively managing {projects.length} project{projects.length !== 1 ? 's' : ''}
      </Typography>

      {/* Suggested actions banner */}
      <SuggestedActionsBanner actions={suggestedActions} loading={actionsLoading} />

      {/* Loading indicator for details fetch */}
      {detailsLoading && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <CircularProgress size={14} />
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Loading project details...
          </Typography>
        </Box>
      )}

      {/* Details error (non-fatal) */}
      {detailsError && (
        <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mb: 2 }}>
          Some project details could not be loaded. Showing available data.
        </Typography>
      )}

      {/* Project cards */}
      <Box sx={{
        display: 'grid',
        gap: 3,
        gridTemplateColumns: {
          xs: '1fr',
          lg: 'repeat(2, 1fr)',
          xl: 'repeat(3, 1fr)',
        },
        alignItems: 'start',
      }}>
        {projectsToRender.map((project) => (
          <ProjectCard key={project.id} project={project} />
        ))}
      </Box>

      {/* Add new project button */}
      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          size="large"
          sx={{
            borderColor: 'rgba(255, 255, 255, 0.15)',
            color: 'text.secondary',
            borderStyle: 'dashed',
            borderRadius: 3,
            px: 4,
            py: 1.5,
            textTransform: 'none',
            fontSize: '0.9rem',
            '&:hover': {
              borderColor: 'primary.main',
              color: 'primary.light',
              backgroundColor: 'rgba(74, 144, 217, 0.08)',
              borderStyle: 'dashed',
            },
          }}
        >
          Add New AI-Powered Project!
        </Button>
      </Box>
    </Box>
  );
}
