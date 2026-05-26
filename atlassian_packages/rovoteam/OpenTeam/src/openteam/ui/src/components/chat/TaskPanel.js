/**
 * TaskPanel — full-panel streaming view for a background async task.
 *
 * Two view modes:
 *   page-switch:    replaces graph on container click (breadcrumb navigation)
 *   focus-context:  unified canvas with viewport zoom + ghost outlines (§3.5)
 *
 * Props:
 *   task       - task object from useManagerChat's `tasks` state
 *   onBack     - called when user clicks the Back button
 *   graphState - from useGraphState hook
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { useTheme } from '@mui/material/styles';
import { MarkdownRenderer } from './MarkdownRenderer';
import { GraphFlowView } from './GraphFlowView';
import { NodeDetailPanel } from './NodeDetailPanel';
import { Breadcrumb } from './Breadcrumb';

const STATUS_CONFIG = {
  starting:  { label: 'Starting…', color: 'warning', showSpinner: true },
  running:   { label: 'Running',   color: 'info',    showSpinner: true },
  completed: { label: 'Complete',  color: 'success',  showSpinner: false },
  error:     { label: 'Error',     color: 'error',   showSpinner: false },
};

export function TaskPanel({ task, onBack, graphState }) {
  const theme = useTheme();
  const bottomRef = useRef(null);
  const tid = task?.id;

  // --- View mode ---
  const [viewMode, setViewMode] = useState('focus-context');
  const [focusedPath, setFocusedPath] = useState([]);
  const [containerOutputView, setContainerOutputView] = useState({});

  // Graph state from useGraphState (used for page-switch mode)
  const derived = useMemo(
    () => graphState?.getDerivedFor(tid, task) || {},
    [graphState, tid, task]
  );
  const {
    graphPath = [],
    selectedLeafId,
    currentGraph,
    expandableNodeIds = new Set(),
    nodeStreamKey: getNodeStreamKey,
    allComplete,
  } = derived;

  // For focus-context mode, the "active graph" is always the root graph
  const activeGraph = viewMode === 'focus-context' ? task?.graph : currentGraph;
  const activePath = viewMode === 'focus-context' ? focusedPath : graphPath;

  // Local UI state
  const [userSelectedNodeId, setUserSelectedNodeId] = useState(null);
  const [graphCollapsed, setGraphCollapsed] = useState(false);
  const [transitionDirection, setTransitionDirection] = useState('in');

  // Effective selected node
  const effectiveNodeId = userSelectedNodeId
    || selectedLeafId
    || task?.autoSelectedNodeId
    || activeGraph?.nodes?.[0]?.id;

  // For focus-context: find selected node across all graphs
  const selectedNode = useMemo(() => {
    if (!effectiveNodeId) return null;
    if (viewMode === 'focus-context') {
      // Search root graph and sub-graphs
      const rootNode = task?.graph?.nodes?.find(n => n.id === effectiveNodeId);
      if (rootNode) return rootNode;
      if (task?.subGraphs) {
        for (const sg of Object.values(task.subGraphs)) {
          const qid = effectiveNodeId.includes('/') ? effectiveNodeId.split('/').pop() : effectiveNodeId;
          const found = sg?.nodes?.find(n => n.id === qid || `${Object.keys(task.subGraphs).find(k => sg === task.subGraphs[k])}/${n.id}` === effectiveNodeId);
          if (found) return found;
        }
      }
    }
    return currentGraph?.nodes?.find(n => n.id === effectiveNodeId);
  }, [effectiveNodeId, viewMode, task, currentGraph]);

  // Node content for detail panel
  const nodeStreamKeyStr = useMemo(() => {
    if (!effectiveNodeId) return '';
    if (viewMode === 'focus-context') return effectiveNodeId;
    return getNodeStreamKey ? getNodeStreamKey(effectiveNodeId) : effectiveNodeId;
  }, [effectiveNodeId, viewMode, getNodeStreamKey]);
  const nodeContent = task?.nodeStreams?.[nodeStreamKeyStr] || '';
  const isNodeStreaming = selectedNode?.status === 'running';

  // Container output content (§3.5.4)
  const focusedContainerId = focusedPath.length > 0 ? focusedPath.join('/') : null;
  const showContainerOutput = focusedContainerId && containerOutputView[focusedContainerId] === 'output';
  const containerOutputContent = useMemo(() => {
    if (!showContainerOutput || !focusedContainerId) return '';
    const bd = task?.nodeStreams?.[`${focusedContainerId}/breakdown`] || '';
    const ag = task?.nodeStreams?.[`${focusedContainerId}/aggregator`] || '';
    const parts = [];
    if (bd) parts.push(`## Breakdown\n\n${bd}`);
    if (ag) parts.push(`## Aggregation\n\n${ag}`);
    return parts.join('\n\n---\n\n') || '*No container output yet.*';
  }, [showContainerOutput, focusedContainerId, task?.nodeStreams]);

  // Status counts
  const statusCounts = useMemo(() => {
    if (!activeGraph?.nodes) return null;
    const c = { completed: 0, running: 0, pending: 0, error: 0 };
    activeGraph.nodes.forEach(n => { c[n.status] = (c[n.status] || 0) + 1; });
    return c;
  }, [activeGraph?.nodes]);

  // Resizable split between graph and detail panel
  const [splitRatio, setSplitRatio] = useState(0.45);
  const splitDragRef = useRef({ dragging: false, startY: 0, startRatio: 0 });
  const contentRef = useRef(null);

  const handleSplitMouseDown = useCallback((e) => {
    e.preventDefault();
    splitDragRef.current = { dragging: true, startY: e.clientY, startRatio: splitRatio };
    const onMove = (me) => {
      if (!splitDragRef.current.dragging || !contentRef.current) return;
      const rect = contentRef.current.getBoundingClientRect();
      const dy = me.clientY - splitDragRef.current.startY;
      const newRatio = splitDragRef.current.startRatio + dy / rect.height;
      setSplitRatio(Math.max(0.15, Math.min(0.85, newRatio)));
    };
    const onUp = () => {
      splitDragRef.current.dragging = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [splitRatio]);

  // Auto-collapse when all complete
  useEffect(() => {
    if (allComplete && activeGraph?.nodes?.length) {
      const timer = setTimeout(() => setGraphCollapsed(true), 1500);
      return () => clearTimeout(timer);
    } else if (activeGraph?.nodes?.length) {
      setGraphCollapsed(false);
    }
  }, [allComplete, activeGraph?.nodes?.length]);

  // Reset selections on topology change
  const graphVersion = activeGraph?.version ?? activeGraph?.nodes?.length ?? 0;
  useEffect(() => { setUserSelectedNodeId(null); }, [graphVersion, activePath.length]);

  // Auto-scroll simple streaming view
  useEffect(() => {
    if (!task?.graph) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [task?.streamContent, task?.graph]);

  // --- Navigation handlers ---

  const handleNodeClick = useCallback((nodeId) => {
    if (viewMode === 'focus-context') {
      const hasSubGraph = task?.subGraphs?.[nodeId];
      if (hasSubGraph) {
        setFocusedPath(prev => {
          if (prev.length === 1 && prev[0] === nodeId) return [];
          return [nodeId];
        });
        setUserSelectedNodeId(null);
      } else {
        setUserSelectedNodeId(nodeId === userSelectedNodeId ? null : nodeId);
        graphState?.setStickySelection(tid);
      }
    } else {
      if (expandableNodeIds.has(nodeId)) {
        setTransitionDirection('in');
        graphState?.setGraphPath(tid, [...graphPath, nodeId]);
        setUserSelectedNodeId(null);
      } else {
        setUserSelectedNodeId(nodeId === userSelectedNodeId ? null : nodeId);
        graphState?.setStickySelection(tid);
      }
    }
  }, [viewMode, task?.subGraphs, expandableNodeIds, graphState, tid, graphPath, userSelectedNodeId]);

  const handleFocusChange = useCallback((path) => {
    setFocusedPath(path);
    setUserSelectedNodeId(null);
  }, []);

  const handleBreadcrumbNavigate = useCallback((depth) => {
    if (viewMode === 'focus-context') {
      setFocusedPath(prev => prev.slice(0, depth));
    } else {
      setTransitionDirection('out');
      graphState?.setGraphPath(tid, graphPath.slice(0, depth));
    }
    setUserSelectedNodeId(null);
  }, [viewMode, graphState, tid, graphPath]);

  // Keyboard: Esc chain, Space fit, arrows
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        if (userSelectedNodeId) {
          setUserSelectedNodeId(null);
        } else if (viewMode === 'focus-context' && focusedPath.length > 0) {
          setFocusedPath([]);
        } else if (viewMode === 'page-switch' && graphPath.length > 0) {
          handleBreadcrumbNavigate(graphPath.length - 1);
        }
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        if (!activeGraph?.nodes?.length || !effectiveNodeId) return;
        e.preventDefault();
        const siblings = activeGraph.nodes;
        const idx = siblings.findIndex(n => n.id === effectiveNodeId || `${focusedPath[0]}/${n.id}` === effectiveNodeId);
        if (idx < 0) return;
        const next = e.key === 'ArrowRight' ? (idx + 1) % siblings.length : (idx - 1 + siblings.length) % siblings.length;
        const nextId = viewMode === 'focus-context' && focusedPath.length > 0
          ? `${focusedPath[0]}/${siblings[next].id}`
          : siblings[next].id;
        setUserSelectedNodeId(nextId);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewMode, focusedPath, graphPath, handleBreadcrumbNavigate, userSelectedNodeId, activeGraph, effectiveNodeId]);

  if (!task) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>Task not found.</Typography>
      </Box>
    );
  }

  const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.starting;
  const summaryText = statusCounts
    ? (allComplete
        ? `Pipeline complete — ${activeGraph.nodes.length} nodes`
        : `Pipeline — ${statusCounts.completed}/${activeGraph.nodes.length} done${statusCounts.running ? `, ${statusCounts.running} running` : ''}${statusCounts.error ? `, ${statusCounts.error} errors` : ''}`)
    : `Pipeline — ${activeGraph?.nodes?.length || 0} nodes`;

  const hasSubGraphs = task?.subGraphs && Object.keys(task.subGraphs).length > 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', mx: -3, mt: -3, mb: -3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5, borderBottom: '1px solid rgba(255,255,255,0.06)', backgroundColor: 'background.paper', flexShrink: 0 }}>
        <IconButton onClick={onBack} size="small" sx={{ color: 'text.secondary' }}>
          <ArrowBackIcon fontSize="small" />
        </IconButton>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {task.label || task.toolName || task.id}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{task.toolName || 'Background Task'}</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
          {cfg.showSpinner && <CircularProgress size={14} color={cfg.color} />}
          {!cfg.showSpinner && task.status === 'completed' && <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main' }} />}
          {!cfg.showSpinner && task.status === 'error' && <ErrorIcon sx={{ fontSize: 16, color: 'error.main' }} />}
          <Chip label={cfg.label} color={cfg.color} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.72rem' }} />
        </Box>
      </Box>

      {/* Graph content */}
      {activeGraph ? (
        <Box ref={contentRef} sx={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          {/* Breadcrumb */}
          <Breadcrumb graphPath={activePath} task={task} onNavigate={handleBreadcrumbNavigate} />

          {/* Graph section — resizable via drag handle */}
          <Box sx={{ flexShrink: 0, height: graphCollapsed ? 40 : `${splitRatio * 100}%`, transition: graphCollapsed ? 'height 0.3s ease' : 'none', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {/* Toggle bar */}
            <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 0.5, cursor: 'pointer', backgroundColor: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.04)', '&:hover': { backgroundColor: 'rgba(255,255,255,0.05)' } }}>
              <Box onClick={() => setGraphCollapsed(c => !c)} sx={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                <Typography variant="caption" sx={{ color: 'text.disabled', flex: 1, fontSize: '0.68rem' }}>
                  {allComplete ? '✅' : '🔄'} {summaryText}
                </Typography>
                {graphCollapsed ? <ExpandMoreIcon sx={{ fontSize: 16, color: 'text.disabled' }} /> : <ExpandLessIcon sx={{ fontSize: 16, color: 'text.disabled' }} />}
              </Box>

              {/* View mode toggle */}
              {hasSubGraphs && (
                <Box sx={{ display: 'flex', ml: 1, gap: 0.25, borderLeft: '1px solid rgba(255,255,255,0.08)', pl: 0.5 }}>
                  <IconButton size="small" onClick={() => setViewMode('focus-context')} title="Focus+Context zoom"
                    sx={{ p: 0.25, color: viewMode === 'focus-context' ? 'primary.main' : 'text.disabled' }}>
                    <AccountTreeIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                  <IconButton size="small" onClick={() => setViewMode('page-switch')} title="Page switch"
                    sx={{ p: 0.25, color: viewMode === 'page-switch' ? 'primary.main' : 'text.disabled' }}>
                    <ViewModuleIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Box>
              )}

              {/* Container Output toggle (§3.5.4) */}
              {viewMode === 'focus-context' && focusedContainerId && (
                <Box sx={{ display: 'flex', ml: 1, gap: 0, borderLeft: '1px solid rgba(255,255,255,0.08)', pl: 0.5 }}>
                  <Chip label="Graph" size="small" variant={showContainerOutput ? 'outlined' : 'filled'}
                    onClick={() => setContainerOutputView(prev => ({ ...prev, [focusedContainerId]: 'graph' }))}
                    sx={{ height: 18, fontSize: '0.6rem', borderRadius: '4px 0 0 4px' }} />
                  <Chip label="Output" size="small" variant={showContainerOutput ? 'filled' : 'outlined'}
                    onClick={() => setContainerOutputView(prev => ({ ...prev, [focusedContainerId]: 'output' }))}
                    sx={{ height: 18, fontSize: '0.6rem', borderRadius: '0 4px 4px 0' }} />
                </Box>
              )}
            </Box>

            {/* Graph or Container Output */}
            {!graphCollapsed && (
              showContainerOutput ? (
                <Box sx={{ overflow: 'auto', p: 2, maxHeight: 400 }}>
                  <MarkdownRenderer content={containerOutputContent} />
                </Box>
              ) : (
                <Box
                  key={viewMode === 'focus-context' ? 'unified' : (graphPath.join('/') || 'root')}
                  sx={{
                    overflow: viewMode === 'focus-context' ? 'hidden' : 'auto',
                    p: 1.5, flex: 1, minHeight: 0,
                    ...(viewMode === 'page-switch' ? {
                      animation: transitionDirection === 'in' ? 'graphDrillDown 0.3s ease-out' : 'graphZoomOut 0.3s ease-out',
                      '@keyframes graphDrillDown': { from: { opacity: 0, transform: 'scale(1.05) translateY(-8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
                      '@keyframes graphZoomOut': { from: { opacity: 0, transform: 'scale(0.92) translateY(8px)' }, to: { opacity: 1, transform: 'scale(1) translateY(0)' } },
                    } : {}),
                  }}
                >
                  <GraphFlowView
                    nodes={activeGraph.nodes}
                    edges={activeGraph.edges}
                    selectedNodeId={effectiveNodeId}
                    expandableNodeIds={expandableNodeIds}
                    onNodeClick={handleNodeClick}
                    viewMode={viewMode}
                    subGraphs={viewMode === 'focus-context' ? task?.subGraphs : undefined}
                    focusedPath={viewMode === 'focus-context' ? focusedPath : undefined}
                    onFocusChange={viewMode === 'focus-context' ? handleFocusChange : undefined}
                  />
                </Box>
              )
            )}
          </Box>

          {/* Drag handle */}
          {!graphCollapsed && (
            <Box
              onMouseDown={handleSplitMouseDown}
              sx={{
                height: 6, flexShrink: 0, cursor: 'row-resize',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                backgroundColor: 'transparent',
                borderTop: '1px solid rgba(255,255,255,0.08)',
                '&:hover': { backgroundColor: 'rgba(74, 144, 217, 0.15)' },
                '&:hover > div': { backgroundColor: 'primary.main' },
              }}
            >
              <Box sx={{ width: 32, height: 3, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.15)', transition: 'background-color 0.15s' }} />
            </Box>
          )}

          {/* Node detail panel */}
          <Box sx={{ flex: 1, overflow: 'hidden' }}>
            <NodeDetailPanel node={selectedNode} content={nodeContent} isStreaming={isNodeStreaming} />
          </Box>
        </Box>
      ) : (
        /* Simple streaming view */
        <Box sx={{ flexGrow: 1, overflow: 'auto', px: 3, py: 2 }}>
          {task.streamContent ? (
            <Box sx={{ '& p': { m: 0 }, '& pre': { overflow: 'auto' } }}><MarkdownRenderer content={task.streamContent} /></Box>
          ) : task.status === 'starting' || task.status === 'running' ? (
            <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', animation: 'pulse 1.5s ease-in-out infinite', '@keyframes pulse': { '0%, 100%': { opacity: 0.4 }, '50%': { opacity: 1 } } }}>
              {task.toolName || 'Task'} is running…
            </Typography>
          ) : task.error ? (
            <Typography variant="body2" sx={{ color: 'error.main' }}>Error: {task.error}</Typography>
          ) : (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>Task completed.</Typography>
          )}
          <div ref={bottomRef} />
        </Box>
      )}
    </Box>
  );
}

export default TaskPanel;
