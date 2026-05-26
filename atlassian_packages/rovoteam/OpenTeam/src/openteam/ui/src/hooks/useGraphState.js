/**
 * useGraphState — manages graph visualization state for composing WorkGraphs.
 *
 * Extracted from useManagerChat to handle:
 * - Sub-graph topology splicing (parent_node_id routing)
 * - RAF-batched status/stream updates (reduces re-renders from 85/s to 60fps max)
 * - Bounded stream buffers (200KB cap per node)
 * - Sticky selection (no auto-switch within 5s of manual click)
 * - Recursive allComplete (traverses subGraphs)
 * - Per-task navigation state (graphPath, selectedLeafId, containerView)
 * - Race buffer for status events arriving before their sub-graph topology
 */

import { useState, useRef, useCallback, useMemo } from 'react';

const MAX_STREAM_SIZE = 200_000;
const TRIM_SIZE = 50_000;
const STICKY_DURATION_MS = 5_000;
const RACE_BUFFER_MAX_PER_PARENT = 200;
const MAX_TOTAL_STREAMS = 10_000_000;
const CLEANUP_KEEP_SIZE = 2_000;

/**
 * Check if all nodes across root graph and all sub-graphs are in a terminal state.
 */
function isAllComplete(graph, subGraphs) {
  if (!graph?.nodes?.length) return false;
  const terminal = ['completed', 'error', 'skipped'];
  if (!graph.nodes.every(n => terminal.includes(n.status))) return false;
  if (subGraphs) {
    for (const sg of Object.values(subGraphs)) {
      if (sg?.nodes && !sg.nodes.every(n => terminal.includes(n.status))) return false;
    }
  }
  return true;
}

/**
 * Apply a node_status event to the correct graph (root or sub-graph).
 * Returns updated task object.
 */
function applyStatusToTask(task, evt) {
  if (!task) return task;

  const nodeId = evt.node_id;
  const slashIdx = nodeId.indexOf('/');
  const ts = evt.timestamp ?? Date.now() / 1000;

  const updateNode = (n) => {
    if (n.id !== nodeId) return n;
    return {
      ...n,
      status: evt.status,
      label: evt.label || n.label,
      error: evt.error || '',
      startedAt: evt.status === 'running' ? ts : n.startedAt,
      completedAt: (evt.status === 'completed' || evt.status === 'error') ? ts : n.completedAt,
      outputPath: evt.output_path || n.outputPath || '',
    };
  };

  if (slashIdx > 0) {
    // Inner node — route to subGraphs
    const parentId = nodeId.substring(0, slashIdx);
    const subGraph = task.subGraphs?.[parentId];
    if (!subGraph) return null; // signal: buffer this event
    const nodes = subGraph.nodes.map(updateNode);
    const updatedSubGraphs = { ...task.subGraphs, [parentId]: { ...subGraph, nodes } };
    const update = { ...task, subGraphs: updatedSubGraphs };
    if (evt.status === 'running') update.autoSelectedNodeId = nodeId;
    return update;
  }

  // Root node
  if (!task.graph) return task;
  const nodes = task.graph.nodes.map(updateNode);
  const update = { ...task, graph: { ...task.graph, nodes } };
  if (evt.status === 'running' && !task._stickyUntil) {
    update.autoSelectedNodeId = nodeId;
  }
  return update;
}

/**
 * Apply a node_stream event — append content with bounded buffer.
 */
function applyStreamToTask(task, evt) {
  if (!task) return task;
  const nodeStreams = { ...(task.nodeStreams || {}) };
  let content = (nodeStreams[evt.node_id] || '') + evt.content;
  if (content.length > MAX_STREAM_SIZE) {
    content = content.slice(TRIM_SIZE);
  }
  nodeStreams[evt.node_id] = content;

  // Global cap: if total nodeStreams size exceeds limit, purge completed nodes
  let totalSize = 0;
  for (const v of Object.values(nodeStreams)) totalSize += v.length;
  if (totalSize > MAX_TOTAL_STREAMS) {
    const terminal = new Set(['completed', 'error', 'skipped']);
    const allNodes = [
      ...(task.graph?.nodes || []),
      ...Object.values(task.subGraphs || {}).flatMap(sg => sg?.nodes || []),
    ];
    for (const n of allNodes) {
      if (terminal.has(n.status) && nodeStreams[n.id] && nodeStreams[n.id].length > CLEANUP_KEEP_SIZE) {
        totalSize -= nodeStreams[n.id].length;
        nodeStreams[n.id] = '';
        if (totalSize <= MAX_TOTAL_STREAMS * 0.7) break;
      }
    }
  }

  const updated = { ...task, nodeStreams };

  // Auto-correct: a node receiving stream data is clearly running.
  // If its status is still "pending" (the RUNNING event was lost due to
  // RAF batching race with topology), infer the correct status.
  if (updated.graph?.nodes) {
    const nodeId = evt.node_id;
    const slashIdx = nodeId.indexOf('/');
    if (slashIdx < 0) {
      const node = updated.graph.nodes.find(n => n.id === nodeId);
      if (node && node.status === 'pending') {
        updated.graph = {
          ...updated.graph,
          nodes: updated.graph.nodes.map(n =>
            n.id === nodeId ? { ...n, status: 'running' } : n
          ),
        };
      }
    }
  }
  return updated;
}

export function useGraphState(setTasks) {
  // Per-task navigation state
  const [graphPathByTid, setGraphPathByTid] = useState({});
  const [selectedLeafByTid, setSelectedLeafByTid] = useState({});
  const [containerViewByTid, setContainerViewByTid] = useState({});

  // RAF batching
  const pendingUpdates = useRef([]);
  const rafId = useRef(null);

  // Race buffer: status events that arrived before their sub-graph topology
  const raceBuffer = useRef({});

  const enqueueTaskUpdate = useCallback((updater) => {
    pendingUpdates.current.push(updater);
    if (!rafId.current) {
      rafId.current = requestAnimationFrame(() => {
        const updates = pendingUpdates.current;
        setTasks(prev => {
          let state = prev;
          for (const fn of updates) {
            state = fn(state);
          }
          return state;
        });
        pendingUpdates.current = [];
        rafId.current = null;
      });
    }
  }, [setTasks]);

  // --- Event Handlers ---

  const handleGraphTopology = useCallback((tid, evt) => {
    if (!evt.parent_node_id) {
      // Root topology: apply IMMEDIATELY (atomic with navigation reset)
      // Preserve existing nodeStreams — breakdown stream arrives BEFORE topology
      setTasks(prev => ({
        ...prev,
        [tid]: {
          ...prev[tid],
          graph: { nodes: evt.nodes, edges: evt.edges, layout: evt.layout, version: evt.version || 0 },
          nodeStreams: prev[tid]?.nodeStreams || {},
          subGraphs: prev[tid]?.subGraphs || {},
        },
      }));
      setGraphPathByTid(prev => ({ ...prev, [tid]: [] }));
      setSelectedLeafByTid(prev => ({ ...prev, [tid]: null }));
      raceBuffer.current[tid] = {};
    } else {
      // Sub-graph topology: store under parent node, preserve existing data
      enqueueTaskUpdate(prev => {
        const task = prev[tid];
        if (!task?.graph) return prev;
        const subGraphs = { ...(task.subGraphs || {}) };
        subGraphs[evt.parent_node_id] = {
          nodes: evt.nodes, edges: evt.edges, layout: evt.layout,
        };
        return { ...prev, [tid]: { ...task, subGraphs } };
      });
      // Replay any buffered status events for this parent
      const buffered = raceBuffer.current[tid]?.[evt.parent_node_id];
      if (buffered?.length) {
        for (const bufferedEvt of buffered) {
          enqueueTaskUpdate(prev => {
            const task = prev[tid];
            const updated = applyStatusToTask(task, bufferedEvt);
            return updated ? { ...prev, [tid]: updated } : prev;
          });
        }
        delete raceBuffer.current[tid][evt.parent_node_id];
      }
    }
  }, [setTasks, enqueueTaskUpdate]);

  const handleNodeStatus = useCallback((tid, evt) => {
    enqueueTaskUpdate(prev => {
      const task = prev[tid];
      const updated = applyStatusToTask(task, evt);
      if (updated === null) {
        // Sub-graph not yet present — buffer for replay
        const parentId = evt.node_id.substring(0, evt.node_id.indexOf('/'));
        if (!raceBuffer.current[tid]) raceBuffer.current[tid] = {};
        if (!raceBuffer.current[tid][parentId]) raceBuffer.current[tid][parentId] = [];
        if (raceBuffer.current[tid][parentId].length < RACE_BUFFER_MAX_PER_PARENT) {
          raceBuffer.current[tid][parentId].push(evt);
        }
        return prev;
      }
      return { ...prev, [tid]: updated };
    });
  }, [enqueueTaskUpdate]);

  const handleNodeStream = useCallback((tid, evt) => {
    enqueueTaskUpdate(prev => {
      const task = prev[tid];
      const updated = applyStreamToTask(task, evt);
      return { ...prev, [tid]: updated };
    });
  }, [enqueueTaskUpdate]);

  const handleGraphReconcile = useCallback((tid, data) => {
    setTasks(prev => {
      const task = prev[tid];
      if (!task?.graph?.nodes) return prev;
      const updated = { ...task, graph: { ...task.graph, nodes: [...task.graph.nodes] } };
      let corrected = 0;
      for (const node of updated.graph.nodes) {
        const serverStatus = data.nodes?.[node.id];
        if (serverStatus && node.status !== serverStatus) {
          console.warn(
            `[graph_reconcile] Gap detected: node '${node.id}' was '${node.status}' ` +
            `on UI but server reports '${serverStatus}' — auto-correcting`
          );
          node.status = serverStatus;
          corrected++;
        }
      }

      // Free memory: trim nodeStreams for completed graphs.
      // Completed nodes' full output is available via the detail panel's
      // file fetch (outputPath); keeping large stream buffers is wasteful.
      if (isAllComplete(updated.graph, updated.subGraphs) && updated.nodeStreams) {
        const trimmed = {};
        let freed = 0;
        for (const [nodeId, content] of Object.entries(updated.nodeStreams)) {
          if (content.length > CLEANUP_KEEP_SIZE) {
            trimmed[nodeId] = content.slice(0, CLEANUP_KEEP_SIZE);
            freed += content.length - CLEANUP_KEEP_SIZE;
          } else {
            trimmed[nodeId] = content;
          }
        }
        if (freed > 0) {
          updated.nodeStreams = trimmed;
          console.info(`[graph_reconcile] Freed ~${(freed / 1024).toFixed(0)}KB of completed stream data for task ${tid}`);
        }
      }

      if (corrected === 0 && !updated.nodeStreams) return prev;
      return { ...prev, [tid]: updated };
    });
  }, [setTasks]);

  // --- Per-task navigation helpers ---

  const setGraphPath = useCallback((tid, path) => {
    setGraphPathByTid(prev => ({ ...prev, [tid]: path }));
  }, []);

  const setSelectedLeaf = useCallback((tid, leafId) => {
    setSelectedLeafByTid(prev => ({ ...prev, [tid]: leafId }));
  }, []);

  const setStickySelection = useCallback((tid) => {
    setTasks(prev => {
      const task = prev[tid];
      if (!task) return prev;
      return { ...prev, [tid]: { ...task, _stickyUntil: Date.now() + STICKY_DURATION_MS } };
    });
  }, [setTasks]);

  const setContainerView = useCallback((tid, containerId, view) => {
    setContainerViewByTid(prev => ({
      ...prev,
      [tid]: { ...(prev[tid] || {}), [containerId]: view },
    }));
  }, []);

  /**
   * Get derived graph state for a specific task.
   */
  const getDerivedFor = useCallback((tid, task) => {
    const graphPath = graphPathByTid[tid] || [];
    const selectedLeafId = selectedLeafByTid[tid] || null;
    const containerView = containerViewByTid[tid] || {};

    // Current graph at the drill-down depth
    let currentGraph;
    if (graphPath.length === 0) {
      currentGraph = task?.graph || null;
    } else {
      const key = graphPath.join('/');
      currentGraph = task?.subGraphs?.[key] || null;
    }

    // Which nodes at current level are expandable (have sub-graphs)
    const expandableNodeIds = new Set();
    if (task?.subGraphs) {
      const prefix = graphPath.length > 0 ? graphPath.join('/') + '/' : '';
      for (const key of Object.keys(task.subGraphs)) {
        if (key.startsWith(prefix)) {
          const remainder = key.substring(prefix.length);
          if (!remainder.includes('/')) expandableNodeIds.add(remainder);
        }
      }
    }

    // Content key for the detail panel at any depth
    const nodeStreamKey = (nodeId) => {
      return graphPath.length > 0
        ? graphPath.join('/') + '/' + nodeId
        : nodeId;
    };

    const allComplete = isAllComplete(task?.graph, task?.subGraphs);

    return {
      graphPath,
      selectedLeafId,
      containerView,
      currentGraph,
      expandableNodeIds,
      nodeStreamKey,
      allComplete,
    };
  }, [graphPathByTid, selectedLeafByTid, containerViewByTid]);

  return {
    handleGraphTopology,
    handleNodeStatus,
    handleNodeStream,
    handleGraphReconcile,
    setGraphPath,
    setSelectedLeaf,
    setStickySelection,
    setContainerView,
    getDerivedFor,
    isAllComplete,
  };
}

export default useGraphState;
