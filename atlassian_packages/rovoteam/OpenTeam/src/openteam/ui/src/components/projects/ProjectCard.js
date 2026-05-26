import React from 'react';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import { ProgressBar } from '../../shared';
import { ProjectHeader } from './ProjectHeader';
import { ProjectMeta } from './ProjectMeta';
import { AgentSection } from './AgentSection';
import { HumanTeamSection } from './HumanTeamSection';
import { AIReportSection } from './AIReportSection';
import { AIRecommendation } from './AIRecommendation';
import { QuickLinksRow } from './QuickLinksRow';
import ProjectTasksSection from './ProjectTasksSection';

/**
 * Resolve each agent's current in-progress task from the project's resolved tasks.
 * An agent is assigned to a task if the task's assignee_ids includes the agent's id.
 */
function buildAgentTaskMap(agents, tasksResolved) {
  if (!agents?.length || !tasksResolved?.length) return {};
  const map = {};
  for (const agent of agents) {
    // Prefer current_task_id if set
    if (agent.current_task_id) {
      const task = tasksResolved.find((t) => t.id === agent.current_task_id);
      if (task) {
        map[agent.id] = task;
        continue;
      }
    }
    // Fallback: find first in-progress task assigned to this agent
    const task = tasksResolved.find(
      (t) =>
        t.assignee_ids?.includes(agent.id) &&
        (t.status === 'in-progress' || t.status === 'in_progress')
    );
    if (task) {
      map[agent.id] = task;
    }
  }
  return map;
}

export function ProjectCard({ project }) {
  if (!project) return null;

  const {
    id,
    name,
    status,
    blockers = 0,
    progress_percent = 0,
    due_date,
    sprint,
    team_composition,
    agents = [],
    humans = [],
    tasks_resolved = [],
    correspondences = [],
    ai_report,
    ai_recommendations = [],
    quick_links = [],
  } = project;

  // Pre-build is not needed — AgentSection resolves internally,
  // but we pass tasks_resolved for it to use.

  return (
    <Paper
      elevation={0}
      sx={{
        backgroundColor: 'background.paper',
        border: '1px solid', borderColor: 'divider',
        borderRadius: 3,
        p: 2.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      {/* Project header: name, status, blockers */}
      <ProjectHeader name={name} status={status} blockers={blockers} tasks={tasks_resolved} />

      {/* Metadata: due date, team composition, sprint */}
      <ProjectMeta
        dueDate={due_date}
        teamComposition={team_composition}
        sprint={sprint}
      />

      {/* Overall project progress */}
      <ProgressBar percent={progress_percent} height={8} showLabel />

      {/* AI Agents section */}
      <AgentSection
        agents={agents}
        tasks={tasks_resolved}
        correspondences={correspondences}
      />

      {/* Task list section */}
      {tasks_resolved?.length > 0 && (
        <ProjectTasksSection tasks={tasks_resolved} />
      )}

      {/* Human team section */}
      <HumanTeamSection humans={humans} />

      {/* AI Report (collapsible) */}
      <AIReportSection report={ai_report} />

      {/* AI Recommendations */}
      {ai_recommendations.length > 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {ai_recommendations.map((rec, idx) => (
            <AIRecommendation key={rec.id || idx} recommendation={rec} />
          ))}
        </Box>
      )}

      {/* Quick links */}
      <QuickLinksRow links={quick_links} />
    </Paper>
  );
}

export default ProjectCard;
