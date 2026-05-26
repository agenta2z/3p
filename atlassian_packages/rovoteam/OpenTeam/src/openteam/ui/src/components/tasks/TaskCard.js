/**
 * TaskCard — expandable card showing task details.
 *
 * Displays title, status, priority, progress, assignees, project,
 * due date, and tags. Expands on click to show description,
 * dependencies, dates, estimated hours, and activity log.
 *
 * Props:
 *   task - object from /api/tasks/{id} with resolved assignees,
 *          dependencies, and project data.
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import FolderIcon from '@mui/icons-material/Folder';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import LinkIcon from '@mui/icons-material/Link';
import EditIcon from '@mui/icons-material/Edit';
import CommentIcon from '@mui/icons-material/Comment';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useTheme } from '@mui/material/styles';
import { StatusBadge, ProgressBar, PersonChip } from '../../shared';

/* ------------------------------------------------------------------ */
/*  Priority helpers                                                    */
/* ------------------------------------------------------------------ */

const PRIORITY_PALETTE = { critical: 'error', high: 'error', medium: 'warning', low: 'success' };
const PRIORITY_LABELS = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };

function PriorityIndicator({ priority }) {
  const theme = useTheme();
  const key = priority?.toLowerCase() || '';
  const paletteKey = PRIORITY_PALETTE[key] || 'neutral';
  const color = theme.palette[paletteKey]?.main || theme.palette.neutral.main;
  const label = PRIORITY_LABELS[key] || priority || 'None';
  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
      <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: color, flexShrink: 0 }} />
      <Typography variant="caption" sx={{ color, fontWeight: 500 }}>{label}</Typography>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Activity icon mapper                                                */
/* ------------------------------------------------------------------ */

const ACTIVITY_ICONS = {
  status_change: <CheckCircleOutlineIcon sx={{ fontSize: 14 }} />,
  comment: <CommentIcon sx={{ fontSize: 14 }} />,
  assignment: <PersonAddIcon sx={{ fontSize: 14 }} />,
  edit: <EditIcon sx={{ fontSize: 14 }} />,
};

function getActivityIcon(type) {
  return ACTIVITY_ICONS[type] || <InfoOutlinedIcon sx={{ fontSize: 14 }} />;
}

/* ------------------------------------------------------------------ */
/*  Date formatter                                                      */
/* ------------------------------------------------------------------ */

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatTimestamp(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

/* ------------------------------------------------------------------ */
/*  TaskCard                                                            */
/* ------------------------------------------------------------------ */

export function TaskCard({ task }) {
  const [expanded, setExpanded] = useState(false);

  if (!task) return null;

  const {
    title,
    status,
    priority,
    progress,
    assignees,
    project,
    project_name,
    due_date,
    tags,
    description,
    dependencies,
    created_at,
    updated_at,
    estimated_hours,
    activity_log,
  } = task;

  const projectLabel = project_name || project?.name || project;
  const dueDateStr = formatDate(due_date);
  const isOverdue =
    due_date && status !== 'done' && status !== 'completed' && new Date(due_date) < new Date();

  return (
    <Paper
      elevation={0}
      sx={{
        p: 0,
        borderRadius: 2,
        border: '1px solid',
        borderColor: expanded ? 'primary.main' : 'divider',
        backgroundColor: 'background.paper',
        transition: 'border-color 0.2s',
        '&:hover': {
          borderColor: 'primary.dark',
        },
      }}
    >
      {/* ---- Collapsed header ---- */}
      <Box
        onClick={() => setExpanded((prev) => !prev)}
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 2,
          p: 2,
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        {/* Left: expand icon + title block */}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          {/* Row 1: title + badges */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75, flexWrap: 'wrap' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
              {title}
            </Typography>
            <StatusBadge status={status} size="small" />
            <PriorityIndicator priority={priority} />
          </Box>

          {/* Row 2: progress bar */}
          {progress != null && (
            <Box sx={{ mb: 1, maxWidth: 280 }}>
              <ProgressBar percent={progress} height={6} showLabel />
            </Box>
          )}

          {/* Row 3: meta chips row */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
            {projectLabel && (
              <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <FolderIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {typeof projectLabel === 'string' ? projectLabel : projectLabel}
                </Typography>
              </Box>
            )}

            {dueDateStr && (
              <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <CalendarTodayIcon
                  sx={{ fontSize: 14, color: isOverdue ? 'error.main' : 'text.secondary' }}
                />
                <Typography
                  variant="caption"
                  sx={{
                    color: isOverdue ? 'error.main' : 'text.secondary',
                    fontWeight: isOverdue ? 600 : 400,
                  }}
                >
                  {dueDateStr}
                  {isOverdue && ' (overdue)'}
                </Typography>
              </Box>
            )}

            {estimated_hours != null && (
              <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <AccessTimeIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {estimated_hours}h est.
                </Typography>
              </Box>
            )}
          </Box>

          {/* Row 4: assignees */}
          {assignees?.length > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1, flexWrap: 'wrap' }}>
              {assignees.map((person, i) => (
                <PersonChip
                  key={person.id || i}
                  name={person.name || person}
                  type={person.type || 'human'}
                  size="small"
                />
              ))}
            </Box>
          )}

          {/* Row 5: tags */}
          {tags?.length > 0 && (
            <Box sx={{ display: 'flex', gap: 0.5, mt: 1, flexWrap: 'wrap' }}>
              {tags.map((tag, i) => (
                <Chip
                  key={tag.id || tag.name || i}
                  label={typeof tag === 'string' ? tag : tag.name}
                  size="small"
                  variant="outlined"
                  sx={{
                    fontSize: '0.65rem',
                    height: 22,
                    borderColor: 'divider',
                    color: 'text.secondary',
                  }}
                />
              ))}
            </Box>
          )}
        </Box>

        {/* Right: expand icon */}
        <IconButton
          size="small"
          sx={{
            mt: 0.25,
            flexShrink: 0,
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.25s',
          }}
        >
          <ExpandMoreIcon sx={{ fontSize: 20 }} />
        </IconButton>
      </Box>

      {/* ---- Expandable detail section ---- */}
      <Collapse in={expanded} timeout={250} unmountOnExit>
        <Divider />
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Description */}
          {description && (
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, mb: 0.5, display: 'block' }}>
                Description
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.primary', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {description}
              </Typography>
            </Box>
          )}

          {/* Dependencies */}
          {dependencies?.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, mb: 0.75, display: 'block' }}>
                Dependencies ({dependencies.length})
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                {dependencies.map((dep, i) => (
                  <Box
                    key={dep.id || i}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      p: 0.75,
                      borderRadius: 1,
                      backgroundColor: 'action.hover',
                    }}
                  >
                    <LinkIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                    <Typography variant="body2" sx={{ flexGrow: 1, minWidth: 0 }}>
                      {dep.title || dep.name || dep}
                    </Typography>
                    {dep.status && <StatusBadge status={dep.status} size="small" variant="outlined" />}
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          {/* Dates and hours */}
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            {created_at && (
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block' }}>
                  Created
                </Typography>
                <Typography variant="body2">{formatDate(created_at)}</Typography>
              </Box>
            )}
            {updated_at && (
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block' }}>
                  Updated
                </Typography>
                <Typography variant="body2">{formatDate(updated_at)}</Typography>
              </Box>
            )}
            {estimated_hours != null && (
              <Box>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block' }}>
                  Estimated Hours
                </Typography>
                <Typography variant="body2">{estimated_hours}h</Typography>
              </Box>
            )}
          </Box>

          {/* Activity log */}
          {activity_log?.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, mb: 0.75, display: 'block' }}>
                Recent Activity
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                {activity_log.map((entry, i) => (
                  <Box
                    key={entry.id || i}
                    sx={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 1,
                      p: 0.75,
                      borderRadius: 1,
                      backgroundColor: 'action.hover',
                    }}
                  >
                    <Box sx={{ color: 'text.secondary', mt: 0.1, flexShrink: 0 }}>
                      {getActivityIcon(entry.type)}
                    </Box>
                    <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                      <Typography variant="body2" sx={{ lineHeight: 1.4 }}>
                        {entry.message}
                      </Typography>
                      {entry.timestamp && (
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {formatTimestamp(entry.timestamp)}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}

export default TaskCard;
