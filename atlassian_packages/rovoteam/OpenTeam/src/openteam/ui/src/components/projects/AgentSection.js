import React from 'react';
import Box from '@mui/material/Box';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { SectionCard } from '../../shared';
import { AgentCard } from './AgentCard';

function resolveCurrentTask(agent, tasks) {
  if (!tasks?.length || !agent) return null;
  // Match by agent's current_task_id first
  if (agent.current_task_id) {
    return tasks.find((t) => t.id === agent.current_task_id) || null;
  }
  // Fallback: find a task where this agent is an assignee and task is in-progress
  return (
    tasks.find(
      (t) =>
        t.assignee_ids?.includes(agent.id) &&
        (t.status === 'in-progress' || t.status === 'in_progress')
    ) || null
  );
}

function resolveCorrespondence(agent, correspondences) {
  if (!correspondences?.length || !agent) return null;
  return correspondences.find((c) => c.agent_id === agent.id) || null;
}

function getLastSyncSubtitle(agents) {
  if (!agents?.length) return undefined;
  const syncs = agents
    .filter((a) => a.last_sync)
    .map((a) => new Date(a.last_sync).getTime());
  if (!syncs.length) return undefined;
  const mostRecent = Math.max(...syncs);
  const mins = Math.round((Date.now() - mostRecent) / 60000);
  if (mins < 1) return 'Last sync: just now';
  if (mins < 60) return `Last sync: ${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return `Last sync: ${hrs}h ago`;
}

export function AgentSection({ agents = [], tasks = [], correspondences = [] }) {
  if (!agents.length) return null;

  return (
    <SectionCard
      title="Active AI Dev Agents"
      icon={<SmartToyIcon sx={{ fontSize: 18 }} />}
      subtitle={getLastSyncSubtitle(agents)}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            currentTask={resolveCurrentTask(agent, tasks)}
            correspondence={resolveCorrespondence(agent, correspondences)}
          />
        ))}
      </Box>
    </SectionCard>
  );
}

export default AgentSection;
