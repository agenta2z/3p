/**
 * FileViewer — right-panel Drawer for viewing documents and browsing folders.
 *
 * Opens from the right side as a slide-in panel. Two modes:
 * 1. **File mode** — renders a single markdown/text document.
 * 2. **Folder mode** — shows a collapsible folder tree at the top;
 *    clicking a file loads its content below.
 *
 * Props:
 *   open             - boolean — drawer open state
 *   onClose          - called when user dismisses
 *   fileName         - display name in header
 *   fileContent      - markdown/text content to render
 *   fileError        - error string if fetch failed
 *   fileLoading      - boolean — shows loading state
 *   isFolderMode     - boolean — enables folder tree header
 *   folderTree       - array of {name, type, path?, children?}
 *   selectedFilePath - currently selected file in folder mode
 *   onFileSelect     - (filePath) => void — called when user clicks a file in tree
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Collapse from '@mui/material/Collapse';
import ButtonBase from '@mui/material/ButtonBase';
import CloseIcon from '@mui/icons-material/Close';
import DescriptionIcon from '@mui/icons-material/Description';
import FolderIcon from '@mui/icons-material/Folder';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import { useTheme } from '@mui/material/styles';
import { MarkdownRenderer } from '../chat/MarkdownRenderer';
import { FolderTree } from './FolderTree';

export function FileViewer({
  open, onClose, fileName, fileContent, fileError, fileLoading,
  isFolderMode, folderTree, selectedFilePath, onFileSelect,
}) {
  const theme = useTheme();
  const [treeExpanded, setTreeExpanded] = useState(true);

  const headerIcon = isFolderMode
    ? <FolderIcon sx={{ color: 'warning.main', fontSize: 20 }} />
    : <DescriptionIcon sx={{ color: 'primary.main', fontSize: 20 }} />;

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: '100%', sm: 560, md: 720 },
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: theme.palette.background.paper,
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 2,
          py: 1.5,
          borderBottom: `1px solid ${theme.palette.divider}`,
          flexShrink: 0,
        }}
      >
        {headerIcon}
        <Typography
          variant="subtitle1"
          sx={{
            fontWeight: 600,
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {fileName || 'Document'}
        </Typography>
        <IconButton onClick={onClose} size="small" sx={{ color: 'text.secondary' }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Folder tree dropdown (folder mode only) */}
      {isFolderMode && folderTree && (
        <>
          <ButtonBase
            onClick={() => setTreeExpanded(prev => !prev)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              px: 2,
              py: 1,
              borderBottom: `1px solid ${theme.palette.divider}`,
              textAlign: 'left',
              '&:hover': {
                backgroundColor: theme.custom?.surfaces?.overlayLight || 'rgba(255,255,255,0.04)',
              },
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 500, color: 'text.secondary', fontSize: '0.82rem' }}>
              Folder Structure
            </Typography>
            {treeExpanded ? <ExpandLess sx={{ fontSize: 18, color: 'text.secondary' }} /> : <ExpandMore sx={{ fontSize: 18, color: 'text.secondary' }} />}
          </ButtonBase>
          <Collapse in={treeExpanded} timeout="auto">
            <Box
              sx={{
                maxHeight: 280,
                overflow: 'auto',
                borderBottom: `1px solid ${theme.palette.divider}`,
              }}
            >
              <FolderTree
                entries={folderTree}
                onFileSelect={onFileSelect}
                selectedPath={selectedFilePath}
              />
            </Box>
          </Collapse>
        </>
      )}

      {/* Content area */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2.5 }}>
        {fileLoading && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 4, justifyContent: 'center' }}>
            <CircularProgress size={20} />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {isFolderMode ? 'Loading…' : 'Loading document…'}
            </Typography>
          </Box>
        )}

        {fileError && !fileLoading && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {fileError}
          </Alert>
        )}

        {fileContent && !fileLoading && (
          <Box
            sx={{
              '& p': { mt: 0, mb: 1.5 },
              '& h1, & h2, & h3': { mt: 2, mb: 1 },
              '& pre': { overflow: 'auto', borderRadius: 1 },
              '& ul, & ol': { pl: 2.5 },
            }}
          >
            <MarkdownRenderer content={fileContent} />
          </Box>
        )}

        {!fileContent && !fileLoading && !fileError && (
          <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
            {isFolderMode && folderTree ? 'Select a file to view its contents.' : 'No content available.'}
          </Typography>
        )}
      </Box>
    </Drawer>
  );
}

export default FileViewer;
