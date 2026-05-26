import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { useTheme, alpha } from '@mui/material/styles';

const PERIOD_ORDER = ['24h', '7d', '14d', '30d', '6m', 'all'];

const PERIOD_LABELS = {
  '24h': '24h',
  '7d': '7d',
  '14d': '14d',
  '30d': '30d',
  '6m': '6m',
  'all': 'All',
};

const cellSx = {
  fontSize: '0.7rem',
  py: 0.5,
  px: 1,
  borderBottom: '1px solid',
  borderBottomColor: 'divider',
  lineHeight: 1.3,
};

export default function PeriodComparisonTable({
  timeSeries = {},
  metricKeys = [],
  labels = [],
  activePeriod,
}) {
  const theme = useTheme();

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell
              sx={{
                ...cellSx,
                fontWeight: 600,
                color: 'text.secondary',
                fontSize: '0.65rem',
                textTransform: 'uppercase',
                letterSpacing: 0.3,
              }}
            >
              Period
            </TableCell>
            {labels.map((label, i) => (
              <TableCell
                key={metricKeys[i]}
                align="right"
                sx={{
                  ...cellSx,
                  fontWeight: 600,
                  color: 'text.secondary',
                  fontSize: '0.65rem',
                  textTransform: 'uppercase',
                  letterSpacing: 0.3,
                }}
              >
                {label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {PERIOD_ORDER.map((periodKey) => {
            const periodData = timeSeries[periodKey] || {};
            const isActive = periodKey === activePeriod;

            return (
              <TableRow
                key={periodKey}
                sx={{
                  backgroundColor: isActive
                    ? alpha(theme.palette.primary.main, 0.08)
                    : 'transparent',
                  '&:hover': {
                    backgroundColor: isActive
                      ? alpha(theme.palette.primary.main, 0.12)
                      : 'action.hover',
                  },
                }}
              >
                <TableCell
                  sx={{
                    ...cellSx,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? 'primary.light' : 'text.primary',
                  }}
                >
                  {PERIOD_LABELS[periodKey] || periodKey}
                </TableCell>
                {metricKeys.map((key) => {
                  const val = periodData[key];
                  return (
                    <TableCell
                      key={key}
                      align="right"
                      sx={{
                        ...cellSx,
                        fontWeight: isActive ? 600 : 400,
                        color: isActive ? 'text.primary' : 'text.secondary',
                      }}
                    >
                      <Typography
                        component="span"
                        sx={{ fontSize: '0.7rem' }}
                      >
                        {val != null ? val : '\u2014'}
                      </Typography>
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
