import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import { SectionCard } from '../../shared';

function formatTimeAgo(timestamp) {
  if (!timestamp) return null;
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

export function AIReportSection({ report }) {
  if (!report) return null;

  const { generated_at, summary, highlights, blockers, velocity_trend } = report;

  return (
    <SectionCard
      title="AI-Generated Weekly Report"
      icon={<AnalyticsIcon sx={{ fontSize: 18 }} />}
      collapsible
      defaultExpanded={false}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {/* Summary */}
        {summary && (
          <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.6 }}>
            {summary}
          </Typography>
        )}

        {/* Highlights */}
        {highlights?.length > 0 && (
          <Box>
            <Typography
              variant="caption"
              sx={{ fontWeight: 600, color: 'text.primary', display: 'block', mb: 0.5 }}
            >
              Key Highlights:
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {highlights.map((item, idx) => (
                <Typography
                  key={idx}
                  component="li"
                  variant="caption"
                  sx={{ color: 'text.secondary', lineHeight: 1.6 }}
                >
                  {item}
                </Typography>
              ))}
            </Box>
          </Box>
        )}

        {/* Blockers */}
        {blockers?.length > 0 && (
          <Box>
            <Typography
              variant="caption"
              sx={{ fontWeight: 600, color: 'error.main', display: 'block', mb: 0.5 }}
            >
              Blockers:
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {blockers.map((item, idx) => (
                <Typography
                  key={idx}
                  component="li"
                  variant="caption"
                  sx={{ color: 'error.light', lineHeight: 1.6 }}
                >
                  {item}
                </Typography>
              ))}
            </Box>
          </Box>
        )}

        {/* Velocity trend */}
        {velocity_trend && (
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Velocity trend: {velocity_trend}
          </Typography>
        )}

        {/* Footer */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            pt: 1,
            borderTop: '1px solid', borderTopColor: 'divider',
          }}
        >
          <Typography variant="caption" sx={{ color: 'text.secondary', opacity: 0.7 }}>
            Generated {formatTimeAgo(generated_at)}
          </Typography>
          <Button
            size="small"
            sx={{
              fontSize: '0.7rem',
              color: 'primary.light',
              textTransform: 'none',
              minWidth: 0,
              px: 1,
            }}
          >
            View Full Report →
          </Button>
        </Box>
      </Box>
    </SectionCard>
  );
}

export default AIReportSection;
