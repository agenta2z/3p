# Plan — Complex Graph Visualization for Composing WorkGraphs

> ## ⏸️ STATUS: ON HOLD (decided 2026-04-19 18:11)
>
> **Wait for `plan_role_setup_real_command_test_and_fixes.md` to
> complete first.** Implementation of THIS plan does NOT start
> until the other plan ships.
>
> **Why on hold:**
> - The other plan refactors `src/.../role_setup/executor.py` from
>   1203-line programmatic code into a yaml-driven BTA (Phase B,
>   ~Medium-High risk). That refactor includes adding
>   `WebSocketGraphReporter` attachment in the new executor (their
>   plan lines 171–176) — exactly the wiring this plan's v0 item #3
>   would add. Building this plan first means rewriting that wiring
>   when the other plan refactors.
> - The other plan also touches `breakdown_then_aggregate_inferencer.py`
>   (Issues 2 + 4) — same file this plan adds `child_reporter`
>   propagation and `flush()` calls to. Sequencing them avoids a
>   merge dance.
> - Issues 2 (`group_max_concurrency`) and 4 (conflict-aware
>   aggregator) need to land first so the visualization shows
>   correct, deterministic behaviour rather than masking real bugs.
>
> **What "the other plan completes" means as a green-light:**
> 1. Phase A1–A6 done — `/create_role` true E2E test passing
>    against src/ yaml.
> 2. Phase B1–B5 done — `/role_setup` yaml-driven executor in src/,
>    `WebSocketGraphReporter` attached in the refactored
>    `executor.execute()`, `test_role_setup_through_yaml.py` invokes
>    `execute()` directly.
> 3. Issue 2 fixed — `group_max_concurrency` honoured at runtime
>    (so the graph visualization will show the correct concurrency
>    pattern, not 17-workers-at-once).
> 4. Issue 4 fixed — conflict-aware aggregator promoted; aggregator
>    `_finalize_response` rewrite stable.
>
> **When green-lit, restart at:** §READ-FIRST R-14 (canonical effort
> table). v0 critical path is **5.05 d** to first iterable demo.
>
> **What to do meanwhile:** nothing on this plan. The 14 verified
> issues, the architecture (NamespacedGraphReporter +
> `parent_node_id`), the v0/v1/v2 staging, and the codebase
> verification all stand — no rework needed when we resume.

---


> **Scope**: Make the real-time graph visualization correctly handle *any*
> WorkGraph composition — including nested BTAs (BTA-of-BTAs), 20+ workers,
> and sustained high-frequency status/stream events — while remaining
> human-friendly.
>
> **Driving test**: `test/openteam/resources/tools/role_setup/test_role_setup.py`
> (outer BTA → ~5 inner BTAs → ~17 leaf workers).
>
> ## Reading guide
>
> | Reader | Sections |
> |---|---|
> | Implementer (Python) | READ-FIRST, §0, §3 Phase 1, §3.5.18.5–6, §3.6.3, §3.6.6 |
> | Implementer (React) | READ-FIRST, §0, §3.5.18 (full), §3.7.3 |
> | Architect / reviewer | Full document |
> | Project manager | READ-FIRST R-14 (effort) |
>
> ## Revision history
>
> - **r1–r5** (2026-04-19): Initial plan → drill-in UX → mock_task → MHF integration.
> - **r6–r9** (2026-04-19): Four feedback rounds — corrections folded in-place.
>   Key fixes: Phase 4.3 dropped (non-BTA inferencers use Workflow not WorkGraph),
>   §3.5.10 obsoleted (BTA already routes streams), `namespace` field removed,
>   mock `.emit()` bug fixed, stream observer `flush()` added.
>   Full correction details archived in
>   [`plan_complex_graph_visualization_audit_history.md`](plan_complex_graph_visualization_audit_history.md).
> - **r10** (2026-04-20, current): Codebase re-verification. Issue #1 (role_setup
>   wiring) confirmed RESOLVED. Line numbers updated. §11-§16 archived to
>   separate file. Document consolidated from 4585 → ~3020 lines.

---

## READ-FIRST — canonical truth (r8+r9+r10; use this; ignore older sections that disagree)

> If anything below conflicts with earlier sections, **this block
> wins**. The older sections are kept for audit history but the
> implementer should rely on this block for the authoritative answer
> on three things: **effort, dropped tasks, and event/data shape**.

### R-1. Single canonical effort table

> **⚠️ STALE — see R-14 below for the latest canonical numbers (post r10
> verification: v0 6.65 d, v1 3.0 d, v2 1.35 d, total 11.0 d).**
> Item #3 (role_setup wiring) is DONE — saves 0.10 d; r9 added 0.50 d.

| | Effort | What's in it |
|---|---|---|
| **v0 — drill-in works for any composition** | **6.65 d** | Phase 1 (excl. 1.5 — done) + `/mock_task` + `useGraphState` + Breadcrumb + GraphFlowView additions + drill-down state + RAF batching + bounded streams + race buffer + WS slash intercept + circuit breaker + transport try/except + Protocol + GC + tests |
| **v1 — polished single-canvas zoom UX** | **3.0 d** | React Flow + dagre migration + `setViewport` zoom + ghost outer context + minimap + live token bubbles + a11y + perf tuning |
| **v2 — generic + audit + polish** | **1.35 d** | Items 26 (search / layout toggle / jump-to-running / per-group badge) + 27 (`--assert-event-parity`) + cross-repo coordination |
| **TOTAL** | **11.0 d** | — |
| **Critical path to first iterable demo** | **4.55 d** | Phase 1 + role_setup wiring + `/mock_task` (flat) + race buffer + slash intercept + Breadcrumb + GraphFlowView additions |

> Older effort numbers in §7.1, §7.2, §7.3, §7.4, §7.5 are
> **STALE** — keep them for audit but read this table.

### R-2. Tasks DROPPED (do not implement)

The following items appear in §7.3 / §3.7.6 / §7.5 but were dropped
during r6 corrections and **must not be implemented**:

- ❌ **Item #22**: "§3.5.10 Python: route breakdown/aggregator streams
  to graph_reporter under `__breakdown__` / `__aggregator__` synthetic
  ids". **REASON**: BTA already routes these under `"breakdown"` /
  `"aggregator"` (verified
  `AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/flow_inferencers/breakdown_then_aggregate_inferencer.py:1501-1503`
  and `:1031`; line numbers shifted from original 1339/855). My §3.5.10 proposal would create duplicate streams.
- ❌ **Item #25**: "Phase 4.3 wire `graph_reporter` into Linear / Dual
  / PlanThenImplement / Reflective inferencers". **REASON**: these
  inherit `Workflow`, NOT `WorkGraph` (verified
  `PythonUtils/src/python_utils/common_objects/workflow/workflow.py:31`
  `class Workflow(WorkNodeBase, ABC)`). Setting `graph_reporter` on
  them would have zero effect — `Workflow` has no DAG nodes to fire
  callbacks on. A `WorkflowVisualizationAdapter` (see audit history §13.1)
  could be built later as a separate plan.

### R-3. Authoritative event / data shape (server → client)

```ts
// graph_topology
{ type: "graph_topology", task_id: string, parent_node_id: "" | string,
  version: number, layout: "horizontal", nodes: Node[], edges: Edge[] }

// node_status — server sends ONE timestamp; UI derives startedAt/completedAt
{ type: "node_status", task_id: string, node_id: string,
  status: "pending"|"running"|"completed"|"error",
  timestamp: number,        // unix epoch seconds
  error?: string, output_path?: string }

// node_stream
{ type: "node_stream", task_id: string, node_id: string,
  content: string, is_final?: boolean }

// Node (shape inside a topology event)
{ id: string, label?: string, group?: string|null,
  is_container?: boolean, _viz_label?: string|null,
  next?: string[], previous?: string[] }
```

**Implementation note**: in `_applyStatusToTask` the implementer must
derive `startedAt` / `completedAt` from `evt.status` + `evt.timestamp`
(matching the existing pattern in `useManagerChat.js:174-175`):

```js
const ts = evt.timestamp ?? Date.now() / 1000;
const startedAt   = evt.status === 'running'
                       ? ts : oldNode.startedAt;
const completedAt = (evt.status === 'completed' || evt.status === 'error')
                       ? ts : oldNode.completedAt;
```

### R-4. `maxColSize` is computed CLIENT-SIDE

`maxColSize` is **NOT** a field on the topology event. It is computed
inside `GraphFlowView.computeLayout()` from the BFS column assignment:

```js
const columns = bfsColumns(graph.nodes, graph.edges);
const maxColSize = Math.max(...columns.map(c => c.length));
const compact = userCompactToggle || maxColSize > 8;
```

The compact prop on `<GraphFlowView>` should be derived inside the
component (or returned from a `useGraphLayout` hook), not read from
`currentGraph.maxColSize`.

### R-5. Node-id matching: NO leaf-id fallback

`_applyStatusToTask` must match nodes by **fully-qualified id only**:

```js
// CORRECT
const idx = graph.nodes.findIndex(n => n.id === evt.node_id);

// WRONG — would route worker_0 in inner_bta_2 sub-graph to outer worker_0
const idx = graph.nodes.findIndex(n => n.id === evt.node_id || n.id === leaf);
```

The leaf-fallback breaks the very namespacing scheme the plan
designs. With two inner BTAs (each with `worker_0`), the fallback
delivers a status to the wrong node.

### R-6. RAF-batched topology resets must batch the navigation reset too

`handleGraphTopology` calls `setGraphPath([])` and
`setSelectedLeafId(null)` synchronously, but `setTasks` is RAF-deferred.
For one frame, `graphPath=[]` against the OLD `tasks`. Fix by either:

**(A) Synchronous setTasks for root topology** (preferred):

```js
const handleGraphTopology = useCallback((tid, evt) => {
  if (!evt.parent_node_id) {
    // Root: apply IMMEDIATELY (atomic with navigation reset)
    setTasks(prev => applyRootTopology(prev, tid, evt));
    setGraphPath([]);
    setSelectedLeafId(null);
    pendingStatusByParentRef.current = {};
    return;
  }
  // Sub-graph: defer via RAF batching as before
  enqueueTaskUpdate((prev) => spliceSubgraph(prev, tid, evt));
  _replayPendingStatusFor(tid, evt.parent_node_id);
}, [setTasks, setGraphPath, setSelectedLeafId, enqueueTaskUpdate, _replayPendingStatusFor]);
```

This makes the root reset atomic and avoids the 1-frame stale flash.
Sub-graph topology arrivals are not race-prone (no navigation reset).

### R-7. Where to call `_StreamObserver.flush()` in BTA

The §13.11 fix says "BTA flushes breakdown/aggregator on completion."
Specific insertion points (verified file path):

`AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/flow_inferencers/breakdown_then_aggregate_inferencer.py`:

- After `await self.breakdown_inferencer.ainfer(...)` returns (around
  line 1505 today — was 1346, shifted by code additions).
  **Before patching**: verify no existing `finally` clause with
  `grep -A 5 'await self.breakdown_inferencer.ainfer'` — if one
  exists, augment it rather than adding a new one.
  In a `finally` block — flush the breakdown
  observer:
  ```python
  finally:
      obs = getattr(self.breakdown_inferencer, 'stream_observer', None)
      if obs is not None and hasattr(obs, 'flush'):
          await obs.flush()
  ```
- Same pattern after `await agg_inf.ainfer(...)` (around line 1035 — was 855).
- Also for each worker: after `await async_execute_with_retry(node.value, ...)`
  succeeds OR fails (the existing `is_final=True` post-emit covers
  this, but adding a defensive flush of the worker's observer is
  safe).

### R-8. Canonical file path conventions

| Symbol | Canonical path |
|---|---|
| BTA | `AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/flow_inferencers/breakdown_then_aggregate_inferencer.py` |
| Graph events | `AgentFoundation/src/agent_foundation/common/inferencers/graph_events.py` |
| Reporter | `AgentFoundation/src/agent_foundation/ui/graph_interactive_adapter.py` |
| WorkGraph | `PythonUtils/src/python_utils/common_objects/workflow/workgraph.py` |
| Workflow | `PythonUtils/src/python_utils/common_objects/workflow/workflow.py` |
| `agent_enabled` filter | `AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/conversational/conversational_inferencer.py:506-507` (NOT `formatters/markdown.py`) |
| `agent_enabled` declaration | `AgentFoundation/src/agent_foundation/resources/tools/models.py:111` |

> The plan in older sections cites `bta_inferencer.py` — that file
> does NOT exist. Use `breakdown_then_aggregate_inferencer.py`
> everywhere.

### R-9. PythonUtils vs rankevolve disambiguation

`WorkGraphNode` and `WorkGraph` exist in **two** locations:

- ✅ **CANONICAL**: `PythonUtils/src/python_utils/common_objects/workflow/workgraph.py`
  — this is what AgentFoundation imports.
- ⚠️ DUPLICATE: `atlassian-packages/rankevolve/src/utils/common_objects/workflow/workgraph.py`
  — independent fork (per current state). **DO NOT EDIT** for this
  plan; changes here would have no effect on the BTA visualization
  pipeline.

If the team needs to reconcile the two copies, that is a separate
plan. For this plan, `PythonUtils` is the only one we touch.

### R-10. Receive-side recovery (NEW capability, suggested for v0)

Add a one-shot client → server message:

```ts
{ type: "request_full_topology", task_id: string }
```

Server responds by re-emitting the root `graph_topology` and every
known sub-graph `graph_topology` (in dependency order). Used by the
UI when:
- WebSocket reconnects after a brief drop.
- User opens an existing task tab (was backgrounded during emission).

Implementation cost: ~0.20 d (one server handler, one client trigger
in the WS-reconnect callback). Add as item #14b in v0.

**Revised v0 total (R-10 included): 5.85 + 0.20 = 6.05 d.**

### R-11. Per-task `graphPath` / `selectedLeafId` (architectural — applied in v0)

After the r7 architectural concern (#12), `useGraphState` is built
**per-task from the start**. The hook stores:

```js
// instead of:  const [graphPath, _setGraphPath] = useState([])
// use:
const [graphPathByTid, setGraphPathByTid] = useState({});
const [selectedLeafByTid, setSelectedLeafByTid] = useState({});
const [containerViewByTid, setContainerViewByTid] = useState({});

// helpers:
const setGraphPath = (tid, p) => setGraphPathByTid(s => ({ ...s, [tid]: p }));
// ...etc
```

Consumers (`TaskPanel`) pass `tid` to the helpers. This is a minor
upfront cost (≈0.10 d) that avoids a much bigger v2 retrofit. Folded
into v0 effort.

### R-12. ID separator escape (defensive)

`/` separator is safe today (BTA names workers `worker_{i}`), but a
generic mechanism should escape it:

```python
def _qualify(self, node_id: str) -> str:
    safe = node_id.replace("/", "%2F")
    return f"{self._ns}/{safe}" if self._ns else safe
```

UI splits on un-encoded `/`, then `decodeURIComponent`-equivalents
each segment (use a small `safeSplit(qualifiedId)` helper).

Cost: ~0.10 d. Add as item #15a in v0.

**Revised v0 total (R-10 + R-11 + R-12 all in): 6.25 d.**

### R-13. Items 23–24 deferral (architectural)

Items 23 (`to_serializable_obj` extra fields) and 24 (`_emit_topology`
in WorkGraph base) are premature without a second `WorkGraph`
consumer in flight. **Move from v2 to "Future Work"** until a
concrete second consumer materializes. Saves 0.5 d in v2.

**Revised v2 total: 1.85 − 0.5 = 1.35 d.**

### R-14. Final canonical totals (after all revisions through r10)

> Incorporates: R-1 base + R-10/R-11/R-12/R-13 adjustments + r9 §16.99
> (+0.50d Protocol/GC/tests) + r10 (−0.10d item #3 done).

| | Effort |
|---|---|
| v0 | **6.65 d** (R-8 base 6.25 + r9 0.50 − r10 0.10) |
| v1 | 3.0 d |
| v2 | **1.35 d** |
| **TOTAL** | **11.0 d** |
| **Critical path to first iterable demo** | **5.05 d** (R-8 base 4.65 + r9 0.50 − r10 0.10) |

> **THESE ARE THE NUMBERS TO QUOTE.** Older numbers in §7 are stale.
> Per-revision effort deltas archived in audit history file.

---

## 0. Problem Statement (verified against the codebase, not assumed)

### What works today (post-implementation of the original plan)
- Single-BTA `create_role` flow visualizes correctly:
  `breakdown` → `worker_0..N` → `aggregator` diamond, with live status,
  per-node streaming, and on-completion file fetching via `/api/view/{path}`.
- `_graph_topology_emitted` is correctly reset at the top of
  `_build_diamond_graph` (`breakdown_then_aggregate_inferencer.py:474`),
  so re-runs of the same BTA instance work.
- `_pending_topology` uses `getattr(..., None)` (line 380), avoiding the
  fragile `hasattr` pattern.
- `WorkGraphNode._graph_event_callback` checks `iscoroutinefunction` to bridge
  sync/async correctly.

### What is broken or missing for complex compositions

| # | Issue | Where | Impact |
|---|---|---|---|
| 1 | ~~`role_setup/executor.py` has **zero** `graph_reporter` references~~ — **RESOLVED (r10)**: `WebSocketGraphReporter` is now wired at `executor.py:1215-1216`. | `OpenTeam/server/resources/tools/role_setup/executor.py` | ~~The 2-BTA composition test produces NO graph at all.~~ Outer graph now renders. |
| 2 | Outer BTA's `worker_factory` does not propagate `graph_reporter` to inner BTAs. | `breakdown_then_aggregate_inferencer.py:567–573` (`worker = factory(...)`) | Even if outer reporter is attached, inner BTAs run blind. |
| 3 | Both BTAs would emit `worker_0..N` ids → **id collisions** in the UI's `nodes.find(n => n.id === ...)`. | `useManagerChat.js:175` | Node updates routed to wrong nodes. |
| 4 | Topology is emitted only **once per BTA** (`_graph_topology_emitted` guard) — inner BTAs have no path to merge their topology into the parent's. | `breakdown_then_aggregate_inferencer.py:894` (see §READ-FIRST R-8 for canonical paths) | UI never learns the inner structure. |
| 5 | UI has **no nested-graph rendering** — `node.group` is plumbed through the event but ignored by `GraphFlowView`. | `GraphFlowView.js:43–110` | Workers cannot be visually grouped by `task_type` or by parent BTA. |
| 6 | 20-worker column = ~1500 px in a 300 px viewport. No pan/zoom/fit-to-view/minimap. | `GraphFlowView.js:73–88` (column layout) | Users see ~4 of 17 workers at once. |
| 7 | `node_stream` accumulator is unbounded (`stream + chunk` forever). | `useManagerChat.js:194–198` | OOM / React stalls on long-running CLI workers (megabytes of output). |
| 8 | Auto-switch selected node fires for *every* `running` node. With 17 concurrent workers, panel flips every few hundred ms. | `useManagerChat.js:184` | Panel is unreadable during fan-out. |
| 9 | Auto-collapse fires when `allComplete` of currently-known nodes — outer-only topology may be "complete" before inner workers start. | `TaskPanel.js:54–68` | Graph hides itself prematurely. |
| 10 | `ElapsedTimer` mixes `Date.now()/1000` (browser) with server `time.time()`. | `NodeDetailPanel.js:60–82` | Wrong elapsed time on clock skew. |
| 11 | No throttling/batching on UI-side `setTasks` for `node_stream` — 17 workers × 200 ms flush = ~85 events/s, each a full state update. | `graph_interactive_adapter.py:148–192`, `useManagerChat.js:188–199` | UI lag. |
| 12 | `send_graph_event` has no try/except around `await self._send(msg)` — closed WS aborts the BTA mid-run. | `websocket_interactive.py:39–85` | Visualization failure crashes computation (violates the design comment in `graph_events.py:9`). |
| 13 | `_viz_label` is BTA-specific. `LinearWorkflowInferencer`, `DualInferencer`, `PlanThenImplementInferencer`, `ReflectiveInferencer` build **`Workflow`s, NOT `WorkGraph`s** — `Workflow(WorkNodeBase, ABC)` (verified `workflow.py:31`). They have no DAG nodes, no edges, no `_graph_event_callback` hook. | `flow_inferencers/*.py`, `workflow.py` | **Phase 4's earlier proposal to "wire `graph_reporter` into them" was based on an incorrect assumption.** They cannot be visualized as DAGs without a separate adapter that synthesizes graph nodes from their step chains. See audit history §13.1 for analysis. |
| 14 | `breakdown` is a **virtual** node manually injected by BTA — no equivalent generic mechanism for "phase" nodes in other inferencers. | `bta_inferencer.py:444+` (virtual node) | Hard to extend to non-BTA flows. |


---

## 1. Design Principles

1. **Generic over BTA-specific.** The visualization protocol must work for
   any `WorkGraph`/`Workflow` subclass. BTA's diamond shape is a special
   case, not the protocol.
2. **Composition is first-class.** A node's value can be another graph-bearing
   inferencer. The UI must render these as **nested groups** that can be
   expanded/collapsed, not flattened with id collisions.
3. **Hierarchical, namespaced node ids.** Use `parent_id/child_id` paths
   (e.g. `inner_bta_2/worker_3`) so events from any depth are unambiguous.
4. **Streaming-safe by default.** Visualization MUST NOT crash compute.
   Every send wrapped in try/except. Every accumulator bounded.
5. **Human-friendly at scale.** Pan, zoom, fit-to-view, group collapse,
   search, minimap. Default behaviour must remain readable for 50+ nodes.
6. **Backwards compatible.** Existing single-BTA `create_role` flow continues
   to work without changes to its executor.

---

## 2. Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│  PythonUtils (generic)                                         │
│    WorkGraph._graph_event_callback                                 │
│    + new: WorkGraph.subgraph_callback (for composition)            │
│    + new: WorkGraphNode.to_serializable_obj() includes 'group'     │
└────────────────────────────────────────────────────────────────────┘
              │ generic events: NODE_STARTED / DONE / ERROR / SUBGRAPH
              ▼
┌────────────────────────────────────────────────────────────────────┐
│  AgentFoundation (transport-agnostic reporter protocol)            │
│    GraphReporter (Protocol)                                        │
│      .on_graph_topology(event, *, parent_node_id="")               │
│      .on_node_status(...)                                          │
│      .on_node_stream(...)                                          │
│      .child_reporter(parent_node_id) -> GraphReporter   (NEW)      │
│    WebSocketGraphReporter implements with throttling/batching      │
│    NodeNamespacedReporter wraps a parent reporter with id prefix   │
└────────────────────────────────────────────────────────────────────┘
              │ JSON over WebSocket
              ▼
┌────────────────────────────────────────────────────────────────────┐
│  OpenTeam React UI                                              │
│    useGraphState (NEW hook — replaces inline switch in             │
│                   useManagerChat for graph events)                 │
│    GraphFlowView (rewritten with React Flow OR upgraded custom)    │
│      - Hierarchical groups (sub-graphs as parent nodes)            │
│      - Pan/zoom/fit-view/minimap                                   │
│      - Status-based re-layout w/ memoization                       │
│    NodeDetailPanel (bounded stream buffer, sticky selection)       │
└────────────────────────────────────────────────────────────────────┘
```

### 2.1 Hierarchical Node ID Scheme

| Level | Example id | Notes |
|---|---|---|
| Root (outer BTA) | `breakdown`, `worker_0`, `aggregator` | unchanged |
| Nested (inner BTA) | `worker_0/breakdown`, `worker_0/worker_3`, `worker_0/aggregator` | parent path prefix |
| Deeper composition | `worker_0/worker_2/worker_1` | recursive |

This is a pure **convention**: ids are strings. Servers prepend the parent
namespace; the UI splits on `/` for grouping. No id collision possible.

### 2.2 New Event: `SubgraphTopologyEvent`

A composing parent does not know its children's topology until they build
themselves. Solution: when a child graph is built (e.g., the inner BTA's
`_build_diamond_graph` runs), it emits its own `GraphTopologyEvent` —
**but with a `parent_node_id` field** so the UI knows where to splice it.

```python
@dataclass
class GraphTopologyEvent:
    nodes: list[dict]
    edges: list[dict]
    layout: str = "horizontal"
    parent_node_id: str = ""    # NEW — non-empty: this is a sub-graph
                                # whose nodes should be spliced under
                                # the node identified by parent_node_id
                                # in the parent graph. Also IS the namespace
                                # — child node ids are reported qualified
                                # already (e.g. "worker_2/worker_0").
    version: int = 0            # NEW — incremented per emission for
                                # change detection (see §2.5).
    # NOTE r6 / §13.4: an earlier draft also had a separate `namespace`
    # field. Removed — `parent_node_id` IS the namespace; they were
    # always equal in NamespacedGraphReporter construction.
```

The UI:
1. On root topology (parent_node_id=""): replace `task.graph` entirely.
2. On child topology (parent_node_id="worker_0"): mark `worker_0` as a
   container and store its sub-graph at `task.graph.subgraphs["worker_0"]`.
3. Render container nodes as group boxes (collapsed by default beyond
   a depth threshold).


---

## 3. Implementation Phases

Each phase is independently shippable. Phases 1–3 unblock the
`role_setup` test scenario (the immediate goal). Phases 4–5 generalise
to other inferencers and polish the UX.

### Phase 1 — Hierarchical reporter & namespaced ids (Python, ~1 day)

**Goal**: A composing BTA propagates a *child* reporter to its inner BTAs;
all events from inner BTAs use prefixed node ids; outer topology is augmented
with `SubgraphTopologyEvent`s.

**Files to change**

#### 1.1 `AgentFoundation/.../graph_events.py` (extend protocol)

- Add `parent_node_id: str = ""` and `version: int = 0` to
  `GraphTopologyEvent` (back-compat: defaults are empty/0).
  **§READ-FIRST R-3 / §13.4 supersede this**: a `namespace` field
  was originally proposed alongside `parent_node_id` but was
  removed — `parent_node_id` IS the namespace.
- Add `is_container: bool = False` to the per-node dict in topology.
  `from_work_graph()` sets it to `True` if a node's `value` is itself a
  `WorkGraph` instance — detect via `isinstance(real_node.value, WorkGraph)`
  *or* via a duck-typed `has_subgraph` attribute set by the parent BTA at
  worker-creation time. Prefer the explicit attribute (less coupling to
  PythonUtils internals).

#### 1.2 `AgentFoundation/.../graph_interactive_adapter.py`

Add a new class:

```python
class NamespacedGraphReporter:
    """Wraps a parent reporter; prefixes all node_ids with `parent_node_id/`.

    Used to give inner BTAs their own reporter that automatically scopes
    events into a sub-graph identified by `parent_node_id`.

    NOTE (§13.4): `parent_node_id` IS the namespace — no separate field.
    """
    def __init__(self, parent: "GraphReporter", parent_node_id: str):
        self._parent = parent
        self._parent_node_id = parent_node_id

    def _qualify(self, node_id: str) -> str:
        return f"{self._parent_node_id}/{node_id}" if self._parent_node_id else node_id

    async def on_graph_topology(self, event):
        from dataclasses import replace
        nodes = [{**n, "id": self._qualify(n["id"])} for n in event.nodes]
        edges = [{"source": self._qualify(e["source"]),
                  "target": self._qualify(e["target"])} for e in event.edges]
        new_evt = replace(event, nodes=nodes, edges=edges,
                          parent_node_id=self._parent_node_id)
        await self._parent.on_graph_topology(new_evt)

    async def on_node_status(self, node_id, *a, **kw):
        await self._parent.on_node_status(self._qualify(node_id), *a, **kw)

    async def on_node_stream(self, node_id, *a, **kw):
        await self._parent.on_node_stream(self._qualify(node_id), *a, **kw)

    def node_interactive(self, node_id):
        return self._parent.node_interactive(self._qualify(node_id))

    def node_stream_observer(self, node_id, **kw):
        return self._parent.node_stream_observer(self._qualify(node_id), **kw)

    def child_reporter(self, parent_node_id: str) -> "NamespacedGraphReporter":
        return NamespacedGraphReporter(self._parent, self._qualify(parent_node_id))
```

Add `child_reporter(parent_node_id)` on `WebSocketGraphReporter` that returns
a `NamespacedGraphReporter(self, namespace=parent_node_id, parent_node_id=parent_node_id)`.

#### 1.3 `AgentFoundation/.../breakdown_then_aggregate_inferencer.py`

> **⚠️ CRITICAL INTERACTION: `_bta_prefix` vs `NamespacedGraphReporter`**
>
> BTA already has a dot-based namespacing mechanism at line 701:
> `_bta_prefix = f"{self.name}." if getattr(self, "name", None) else ""`
> which produces node names like `outer_bta.worker_0`. When a nested
> BTA gets `worker.name = _node_name` (line 775), its own workers
> become `outer_bta.worker_0.worker_0`.
>
> If `NamespacedGraphReporter` ALSO adds `worker_0/` prefix, the
> result is **double-prefixed**: `worker_0/outer_bta.worker_0.worker_0`.
>
> **Fix**: When attaching a child reporter, clear the inner BTA's
> `_bta_prefix` by unsetting its name. The reporter handles
> namespacing; `_bta_prefix` must not also prefix. Workspace
> isolation is handled separately by `self._workspace.child()` and
> is not affected by clearing the name.

In `_build_diamond_graph`, after constructing `worker` (around line 773),
**before** assigning `worker.interactive`:

```python
# If this worker is itself a graph-bearing inferencer (composition),
# give it a child reporter so its own _build_diamond_graph emits a
# sub-graph topology that the UI can splice under this node.
if self.graph_reporter is not None and hasattr(worker, "graph_reporter"):
    if getattr(worker, "graph_reporter", None) is None:
        worker.graph_reporter = self.graph_reporter.child_reporter(_node_name)
        # Disable _bta_prefix on inner BTA — NamespacedGraphReporter
        # handles namespacing. Without this, node IDs get double-prefixed
        # (e.g. "worker_0/outer_bta.worker_0.worker_0" instead of
        # "worker_0/worker_0").
        if isinstance(worker, BreakdownThenAggregateInferencer):
            worker.name = None
        # Mark this node as a container — UI renders as a group/cluster
        node._is_container = True
```

Then update `GraphTopologyEvent.from_work_graph()` to set
`"is_container": getattr(real_node, "_is_container", False)` per node.

#### 1.4 `AgentFoundation/.../websocket_interactive.py` (server send safety — Issue #12)

Wrap `await self._send(msg)` in `send_graph_event` with try/except logging
and swallowing — never propagate to the BTA. Also add a per-task
**circuit breaker**: after N consecutive WS send failures, set a flag and
short-circuit further `send_graph_event` calls until reset.

#### 1.5 `OpenTeam/.../role_setup/executor.py` (the missing wiring)

> **✅ DONE (verified r10)**: `WebSocketGraphReporter` is now wired at
> `role_setup/executor.py:1215-1216`. No further action needed for this
> item. The outer BTA graph renders correctly.

~~After `inferencer = instantiate(cfg)` ...~~ (see above — already implemented).

Phase 1 acceptance: running `test_role_setup.py` with the WebSocket UI
produces a topology containing `worker_*` nodes (containers), and child
topologies arrive with `parent_node_id` set.

### Phase 2 — UI: nested groups & scalable layout (React, ~1 day base + see §3.5)

**Goal**: render hierarchical sub-graphs, support 50+ nodes with
pan/zoom/fit/minimap, and bounded stream buffers.

> **IMPORTANT**: §3.5 (Drill-in UX for Composing Graphs) below
> **supersedes** the "inline expand/collapse" model originally proposed
> here in Phase 2.1. The default UX is now **Overview (compact
> containers) → click drills in with animated zoom**, *not* inline
> expand. Read §3.5 before implementing this phase.

**Decision: React Flow vs. extend custom?**

Recommendation: **migrate to [`reactflow`](https://reactflow.dev/)** (now
`@xyflow/react`). Reasons:
- Native parent-node / sub-graph support ("sub-flow" feature) — exactly
  what we need for nested BTAs.
- Built-in pan/zoom, minimap (`<MiniMap/>`), controls (`<Controls/>`),
  fit-view, edge bundling, node memoization.
- ~25 KB gzip; we already have MUI etc.
- Layout: pair with `dagre` (10 KB) for column-DAG auto-layout — handles
  20+ workers without overlap.

If we want to avoid the dep, the **custom** GraphFlowView can be extended,
but pan/zoom/minimap implementations alone are several hundred lines —
React Flow pays for itself.

**Files to change**

#### 2.1 `OpenTeam/.../components/chat/GraphFlowView.js` — rewrite

Use `<ReactFlow>` with:
- `nodeTypes`: `default`, `group` (for containers), `phase` (for the virtual
  breakdown node, styled differently).
- `dagre` for layout: TB direction by default, LR for narrow viewports.
- `<MiniMap />`, `<Controls />`, `<Background />` standard.
- `fitView` on prop change (new topology arrives → fit). Use a key on the
  ReactFlow instance based on graph version to force re-fit.
- Container nodes (`is_container=true`) rendered as **collapsible group
  boxes**. Default state: collapsed if depth > 1 OR if expanding would push
  total node count beyond a threshold (e.g., 30).

Render contract:
```js
// Input task.graph:
//   { nodes: [...root nodes...], edges: [...],
//     subgraphs: { "worker_0": { nodes: [...], edges: [...] }, ... } }
// Flatten for React Flow with parentNode field set per nested node.
```

#### 2.2 `OpenTeam/.../hooks/useGraphState.js` — NEW (extracted from `useManagerChat`)

Extract the `graph_topology`, `node_status`, `node_stream` cases from
`useManagerChat.js` into a dedicated hook. Responsibilities:

1. **Topology splicing**: on receiving a `graph_topology` with non-empty
   `parent_node_id`, store it under `task.graph.subgraphs[parent_node_id]`
   instead of replacing the root.
2. **Status routing by qualified id**: walk the appropriate sub-graph using
   the `/`-split path of `node_id`.
3. **Bounded stream buffers** (Issue #7): cap each `nodeStreams[id]` at e.g.
   200 KB. Above that, drop oldest 50 KB chunks (keep tail).
4. **Status update batching** (Issue #11): coalesce `node_status` and
   `node_stream` events with `requestAnimationFrame` — accumulate in a ref,
   flush once per frame. Reduces re-renders from 85/s to 60/s max and
   batches multiple node updates into one `setTasks` call.
5. **Sticky selection** (Issue #8): only auto-switch if the user has not
   manually clicked a node (track `userSelectedAt` timestamp; if within
   last 5s, do not auto-switch).
6. **Don't auto-collapse with active subgraphs** (Issue #9): `allComplete`
   must traverse all sub-graphs recursively.

#### 2.3 `OpenTeam/.../components/chat/NodeDetailPanel.js`

- Fix `ElapsedTimer` (Issue #10): receive a `serverNow` offset (computed
  once when topology arrives: `clientNow - serverNow`). Use offset-corrected
  `Date.now() / 1000 - offset - startedAt`. Or simpler: server sends
  `elapsed_ms` along with running events when it can; UI just displays.
- Show breadcrumb path for nested nodes: `inner_bta_2 / worker_3 → label`.
- "Open in new tab" link for `outputPath` (we already fetch via `/api/view/`).

#### 2.4 `OpenTeam/.../components/chat/TaskPanel.js`

- Replace `allComplete = nodes.every(...)` with a recursive helper that
  walks `subgraphs`.
- Remove auto-collapse on completion for tasks that have sub-graphs (let
  the user decide; complex graphs are useful as a post-mortem).
- The `userSelectedNodeId` reset key should be the `task.graph.version`
  (see 2.5) instead of `nodes.length`, which is unreliable.

#### 2.5 Topology version field

Server adds `version: int` (incremented per topology emission) so the UI
can detect changes deterministically rather than via `nodes.length` proxy.

Phase 2 acceptance: 17-worker `role_setup` run renders as outer BTA with
5 expandable inner-BTA group boxes; each inner box can be opened to reveal
its breakdown→workers→aggregator sub-diamond. Pan/zoom/fit-view work.
No React stalls during sustained streaming.

### Phase 3 — Resilience & throughput (~0.5 day)

#### 3.1 Server-side stream throttling

`graph_interactive_adapter.py` `node_stream_observer` already has
`flush_interval_ms=200`. For composing BTAs with N concurrent leaf workers,
this is N × 5 events/sec. Add **max_msg_per_sec** at the
`WebSocketGraphReporter` level (default 30/s/task) — drop or coalesce
excess `node_stream` events (status events are never dropped). Use
`asyncio.Queue` with `maxsize=1` per node for the stream observer (latest
chunk wins; status sequence preserved via separate path).

#### 3.2 WebSocket back-pressure handling

`websocket_interactive.send_graph_event`: if `_send` raises (closed socket,
buffer full), increment a per-task error counter; after 3 consecutive
failures, log once and short-circuit further sends until the next
`graph_topology`. Compute remains unaffected.

#### 3.3 Memory caps (UI)

Already covered by 2.2 #3 (bounded `nodeStreams`). Also: when
`task.status === 'completed' && allComplete`, garbage-collect
`task.nodeStreams` after 60 seconds (the file content is on disk and
served via `/api/view/`).

### Phase 4 — Generalise beyond BTA (~1 day)

**Goal**: `LinearWorkflowInferencer`, `DualInferencer`,
`PlanThenImplementInferencer`, `ReflectiveInferencer` can also produce
graph events.

#### 4.1 Move topology emission into the WorkGraph base layer

In `PythonUtils/.../workgraph.py`, add an optional
`graph_reporter` attribute (None by default) and a method
`async def _emit_topology(self, *, parent_node_id="")` that builds a
`GraphTopologyEvent.from_work_graph(self, parent_node_id=parent_node_id)`
and forwards it. Inferencers in AgentFoundation simply set
`self.graph_reporter` and the base class handles the rest.

This avoids duplicating the BTA-specific `_emit_pending_graph_topology`
machinery in every flow inferencer.

#### 4.2 Include `group` in `WorkGraphNode.to_serializable_obj()`

Currently `group` is read from the live node via the `node_map` workaround
in `from_work_graph()`. Promote it to a first-class serialized field so the
event-construction code is uniform across all WorkGraph users.

```python
# WorkGraphNode.to_serializable_obj — add:
"group": self.group,
"_viz_label": getattr(self, "_viz_label", None),
"_is_container": getattr(self, "_is_container", False),
```

`from_work_graph` is then a simple list-comprehension; no `node_map` lookup.

#### 4.3 Wire reporters in non-BTA inferencers

For each of `LinearWorkflowInferencer`, `DualInferencer`,
`PlanThenImplementInferencer`, `ReflectiveInferencer`: add the standard
graph_reporter attribute (kw-only, default None). Each calls
`await self._emit_topology()` once after building its graph, before
running. No further changes needed — `_graph_event_callback` on
`WorkGraphNode` (already in PythonUtils) emits status events.

Phase 4 acceptance: a `PlanThenImplementInferencer` invocation through the
UI shows a 2-node `plan` → `implement` graph with live status and streaming.

### Phase 5 — UX polish (~1 day)

- **Search/filter** (`Ctrl-F`): highlight nodes whose label matches a query.
  Useful with 50+ nodes.
- **Status legend** in the corner.
- **Layout direction toggle** (TB/LR) — TB is better when fanout is wide;
  LR is better for deep diamond chains.
- **"Jump to running"**: click a button to fit-view all currently `running`
  nodes (helpful when most workers are pending/done and the action is in
  one cluster).
- **Per-group concurrency hint**: if BTA has `group_max_concurrency` set,
  show "3/5 running" badge per group container.
- **Persist UI state** (collapsed/expanded sub-graphs) across topology
  re-emissions so a re-run doesn't blow away the user's layout.


---

## 4. Testing Strategy

### 4.1 Python unit tests (AgentFoundation)

| Test | Purpose |
|---|---|
| `test_namespaced_reporter_qualifies_ids` | `NamespacedGraphReporter.on_node_status("worker_1")` produces `worker_0/worker_1` for a child reporter rooted at `worker_0`. |
| `test_child_reporter_recursive_namespacing` | `parent.child_reporter("a").child_reporter("b").on_node_status("c")` → `a/b/c`. |
| `test_topology_event_includes_is_container` | A WorkGraphNode whose `value` is a WorkGraph (or with `_is_container=True`) is marked accordingly in the emitted event. |
| `test_send_graph_event_swallows_send_errors` | Closed WS does not raise to the BTA. After 3 failures, subsequent calls short-circuit. |
| `test_workgraph_node_serializes_group` | Phase 4: `to_serializable_obj()` includes `group`, `_viz_label`, `_is_container`. |

### 4.2 Python integration test (OpenTeam)

`test/openteam/resources/tools/role_setup/test_role_setup_graph_events.py` —
new test that:
1. Builds the full nested BTA with a mock `GraphReporter` that records all events.
2. Runs with a tiny breakdown (mocked LLM returning 2 outer subtasks × 2 inner facets each).
3. Asserts that the recorded events include:
   - 1 root `GraphTopologyEvent` with 2 `worker_*` container nodes.
   - 2 child `GraphTopologyEvent`s with `parent_node_id=worker_0` / `worker_1`.
   - All `node_status` events have qualified ids matching the namespaces.
   - No id collision (set of all node_ids has size = total node count).

### 4.3 React UI tests (OpenTeam)

| Test (jest + react-testing-library) | Purpose |
|---|---|
| `useGraphState.subgraph_splicing` | Receiving a topology with `parent_node_id="worker_0"` stores it under `subgraphs["worker_0"]`, leaves root graph intact. |
| `useGraphState.bounded_streams` | Pushing 1 MB of stream chunks for one node leaves `nodeStreams[id].length <= 200_000`. |
| `useGraphState.batched_setTasks` | 100 status events in one frame produce 1 React state update (use `act()` and a render counter). |
| `useGraphState.sticky_selection` | Manual click within last 5s prevents auto-switch on subsequent `running` events. |
| `GraphFlowView.large_graph_layout` | A graph with 50 nodes renders without overlap (assert no two nodes share bounding box). |
| `GraphFlowView.container_collapse` | Container node defaults collapsed; click expands; nested graph appears. |

### 4.4 Manual e2e checklist

Run `test_role_setup.py` end-to-end against the live UI. Verify:
- [ ] Outer topology arrives with 5 `worker_*` container nodes.
- [ ] Each container shows `▶ N children` collapsed badge.
- [ ] Click expand: inner graph fades in inside the container.
- [ ] Status updates fire on inner nodes correctly (no flicker on outer).
- [ ] Pan, zoom, fit-view, minimap all work.
- [ ] No console errors during 5-minute sustained run.
- [ ] Memory profiler shows `tasks` state size stable after 10 minutes.

---

## 5. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| React Flow adds 25 KB + dependency | Med | Low | Tree-shake; only `Background`, `Controls`, `MiniMap` modules. |
| `parentNode` field of React Flow requires absolute positions inside parent — dagre layout needs to be run per-subgraph then offset. | Med | Med | Implement a `layoutGraph(graph, subgraphs)` helper that recursively dagre-lays out each subgraph and assigns parent-relative positions. Unit-tested with synthetic graphs. |
| Namespacing scheme breaks existing single-BTA UI (root-level ids previously had no `/`). | Low | High | Default namespace is empty → root ids unchanged. Pre-merge: run existing `create_role` test in CI. |
| Rate-limiting `node_stream` could drop important final chunks. | Low | Med | Always pass `is_final=True` chunks unconditionally. |
| Inner BTAs may share `worker_0` ids with outer if namespacing misconfigured. | Med | High | Assert in `NamespacedGraphReporter.__init__` that `parent_node_id` is non-empty. Add Python-side test. |
| Group nodes from `worker_factory: dict` (e.g. `skill_tool_creation_research`) may visually conflict with **container** nodes (composing BTAs). | Low | Low | Render distinctly: containers are double-bordered group boxes; group-tagged workers get a colored left border. |
| Auto-fit-view on every new sub-topology resets the user's pan/zoom. | High | Low | Only `fitView` on the very first topology of a task. Subsequent topologies preserve viewport. |

---

## 6. Open Questions (need user input or design-time decision)

1. **React Flow vs custom?** This plan recommends React Flow (and §3.5
   essentially requires it for the focus-zoom and parent-node features).
   If the team rejects new deps, §3.5 must be substantially rewritten.
2. **Auto-collapse policy for deep graphs.** Superseded by §3.5: the
   default model is **Overview shows containers as compact cards**
   (effectively "collapsed"), and click drills in. Inline expand is
   not the default.
3. **Should aggregator nodes show streaming token-by-token?** Yes — the
   BTA already routes breakdown and aggregator streams under their
   existing node IDs. The "Container Output" toggle (§3.5.4) displays
   them. ~~(§3.5.10 is OBSOLETE — no synthetic IDs needed.)~~
4. **Do we want a "graph DAG" mini-visualization in the conversation
   bubble** (next to TaskCard) for at-a-glance progress, separate from the
   full TaskPanel view?
5. **Persistence**: should completed task graphs be persisted server-side
   (JSON snapshot) so reopening the task later shows the historical graph
   without needing to re-run? Out-of-scope for this plan unless desired.
6. **Drill-in UX deferred decisions** (see §3.5.15 for a 5-row table):
   picture-in-picture vs ghost outlines + minimap; persistence of the
   "Container Output" toggle; intermediate-stop vs direct zoom; auto
   compact mode for completed leaves; Comparison Mode (3.5.11) in v1
   or post-v1.

---

## 7. Effort Estimate & Sequencing — v0 / v1 / v2 Staged Shipping

After integrating MHF (§3.7), the plan is restructured into three
independently-shippable versions. Each version is end-to-end useful;
later versions add capability without regressing earlier ones.

### 7.1 v0 — "Visualization works for any composition; no library deps" (~5.5 days)

> **⚠️ STALE — see §READ-FIRST R-1 / R-14 for the canonical effort
> totals.** This sub-section's totals (5.5 d) are pre-r6/r7/r8
> corrections. Item-level breakdown below remains useful for
> understanding the work; the per-version total is wrong.

**Outcome**: User runs `test_role_setup.py` in the live UI and sees a
working drill-in graph with breadcrumb navigation, status updates,
streaming, compact mode, and `/mock_task` for fast iteration. Built on
the existing custom SVG `GraphFlowView` — **no React Flow yet**.

| # | Item | Owner | Effort | Depends on |
|---|---|---|---|---|
| 1 | Phase 1: hierarchical reporter + `parent_node_id` + namespacing (1.1–1.5) | Python | 0.75 d | — |
| 2 | Phase 1.4: `send_graph_event` try/except + circuit breaker | Python | 0.25 d | 1 |
| 3 | ~~role_setup/executor.py — wire `WebSocketGraphReporter`~~ **✅ DONE (r10)**: already at `executor.py:1215-1216` | — | 0 d | — |
| 4 | §3.6 mock components (`MockBreakdownInferencer`, `MockWorker`, `MockAggregator`) + register targets | Python | 0.5 d | 1 |
| 5 | §3.6 mock_task tool.json + executor + 5 profile YAMLs (default, huge, flat, error, slow) | Python | 0.5 d | 4 |
| 6 | §3.7.3.5 WS slash-command intercept gated by `OPENTEAM_DEV_MODE` + `agent_enabled:false` | Python | 0.25 d | 5 |
| 7 | §3.5.18.1 `useGraphState` hook — full RAF batching, bounded streams, orphan cleanup | React | 0.75 d | 1 (event shape) |
| 8 | §3.5.18.2 TaskPanel drill-in wiring + §3.5.18.3 Breadcrumb component | React | 0.5 d | 7 |
| 9 | §3.5.18.4 GraphFlowView additions (expand indicator, compact mode, fit-to-view, zoom/pan) | React | 0.75 d | 8 |
| 10 | §3.7.3.7 Dynamic graph panel height ladder | React | 0.10 d | 8 |
| 11 | §3.5.9 keyboard shortcuts (Esc/Space/arrows) + ChatInput slash autocomplete | React | 0.5 d | 6, 8 |
| 12 | §3.5.7 side-panel rules refactor (orthogonal to focus) | React | 0.25 d | 8 |
| 13 | Phase 3.1/3.2 server-side stream throttle + WS back-pressure | Python | 0.25 d | 1 |
| 14 | v0 acceptance tests (Python + React) | Both | 0.50 d | all of v0 |

**v0 total: 5.5 days** (≈ 1 week of dev time). At end of v0 the user
sees `test_role_setup.py` rendered with working drill-in for the first
time, and can iterate on UI tweaks via `/mock_task --workers 20 --inner 5`
in seconds rather than 3-minute LLM runs.

### 7.2 v1 — "Polished single-canvas zoom UX" (+3 days)

> **⚠️ Item totals OK, but read §READ-FIRST R-14 for the canonical
> grand total.**

**Outcome**: Drill-in feels modern — single canvas, animated zoom,
ghost outer context, minimap, live token bubbles. Adds React Flow as
a dep but the UI behaviour (`graphPath` state model, breadcrumb,
side-panel orthogonality) is unchanged from v0.

| # | Item | Owner | Effort | Depends on |
|---|---|---|---|---|
| 15 | Migrate `GraphFlowView.js` to `@xyflow/react` + `dagre` | React | 1.0 d | v0 |
| 16 | §3.5.2 focus-zoom animation via `setViewport({duration: 600})` + opacity fade | React | 0.5 d | 15 |
| 17 | §3.5.6 ghost outer-context outlines + `<MiniMap/>` integration | React | 0.5 d | 15 |
| 18 | §3.5.5 live-token bubbles + edge traversal shimmer + status pulse halos | React | 0.5 d | 15 |
| 19 | §3.5.13 a11y pass + `prefers-reduced-motion` opt-out paths | React | 0.25 d | 15–18 |
| 20 | §3.5.14 perf budget verification — profile under `/mock_task --profile huge` | React | 0.25 d | 15–18 |

**v1 total: 3.0 days**.

### 7.3 v2 — "Generalisation + Container Output" (+2 days)

> **⚠️ STALE — items #22 (§3.5.10) and #25 (Phase 4.3) below are
> DROPPED per §READ-FIRST R-2.** Items #23 and #24 are also DEFERRED
> per §READ-FIRST R-13. The canonical v2 effort is 1.35 d, not 2.25 d.

**Outcome** (updated r10): ~~Visualization works for non-BTA inferencers~~
— **non-BTA inferencer support DROPPED** (they use `Workflow`, not
`WorkGraph`). v2 now covers: Container Output toggle UI, UX polish
(search/filter/layout/jump-to-running), and `--assert-event-parity`.

| # | Item | Owner | Effort | Depends on |
|---|---|---|---|---|
| 21 | §3.5.4 Container Output toggle UI (floating pill + content swap) | React | 0.25 d | v1 |
| ~~22~~ | ~~§3.5.10 Python: route breakdown/aggregator streams to synthetic ids~~ — **DROPPED** (R-2): BTA already routes under `"breakdown"` / `"aggregator"` (verified `breakdown_then_aggregate_inferencer.py:1501-1503`/`:1031`). | — | 0 d | — |
| 23 | ~~Phase 4.2 promote `group` / `_viz_label` / `_is_container` to first-class fields~~ — **DEFERRED** (R-13): premature without a 2nd consumer | Python | 0 d (was 0.25) | — |
| 24 | ~~Phase 4.1 promote `_emit_topology` into the WorkGraph base layer~~ — **DEFERRED** (R-13): premature without a 2nd consumer | Python | 0 d (was 0.25) | — |
| ~~25~~ | ~~Phase 4.3 wire `graph_reporter` into Linear / Dual / PlanThenImplement / Reflective inferencers~~ — **DROPPED** (R-2): these inherit `Workflow`, NOT `WorkGraph`; setting `graph_reporter` has zero effect. Path B (`WorkflowVisualizationAdapter`) is a separate plan. | — | 0 d | — |
| 26 | Phase 5 polish — search/filter, layout direction toggle, "Jump to running", per-group concurrency badge | React | 0.5 d | v1 |
| 27 | §3.7.2.2 `/mock_task --assert-event-parity` flag (regression test for event protocol) | Python | 0.25 d | v0 |

**v2 total: 2.25 days**.

### 7.4 Grand total & critical path

> **⚠️ STALE — see §READ-FIRST R-14 for canonical totals (v0 6.65d,
> v1 3.0d, v2 1.35d, total 11.0d, critical path 5.05d).**

| | Effort | Cumulative |
|---|---|---|
| v0 (works for any composition; no library) | 5.5 d | 5.5 d |
| v1 (polished single-canvas zoom UX) | 3.0 d | 8.5 d |
| v2 (generalised + Container Output) | 2.25 d | 10.75 d |

**Critical path to demo `test_role_setup.py` working**: items 1–2
(Phase 1; item 3 DONE) + items 7–9 (useGraphState + TaskPanel +
GraphFlowView) = **~3.0 days**, after which the test scenario produces
a working (if visually basic) drill-in graph in the UI.

### 7.5 Recommended 2-developer parallel sequencing

**Dev A (Python)**:
- Day 1: items 1, 2 → Phase 1 lands (item 3 DONE — role_setup already wired).
- Day 2: items 4, 5, 6 → /mock_task is shippable.
- Day 3: items 13 → reliability (item 22 DROPPED — already implemented).
- Day 4: ~~items 23, 24, 25~~ → items 23, 24 DEFERRED; item 25 DROPPED. Use for acceptance tests.
- Day 5: items 27 + acceptance tests → event-parity assertions.

**Dev B (React)**:
- Day 1: scaffold `useGraphState` against mock event JSON (item 7 can
  start before Dev A finishes Phase 1 — only needs the event shape).
- Day 2: items 8, 10, 12 → TaskPanel + Breadcrumb + side-panel rules.
- Day 3: items 9, 11 → GraphFlowView additions + keyboard.
- Day 4: item 15 → React Flow migration.
- Day 5: items 16, 17 → focus-zoom animation + ghost context + minimap.
- Day 6: items 18, 19, 20 → live overlays + a11y + perf.
- Day 7: items 21, 26 → Container Output UI + Phase 5 polish.

With this split, **end of day 3** = `test_role_setup.py` is visualizable
end-to-end at v0; **end of day 5** = both devs are building v1 in
parallel; **end of day 7** = v2 complete with all 27 items shipped.

### 7.6 Sequencing rationale (why mock-first; why v0 before React Flow)

- **Mock first** (item 4–6 before items 8–9): UI iteration is the
  bottleneck. Without `/mock_task`, every render tweak costs 3 min +
  $1–3 of LLM calls. `/mock_task` with flat profile is shippable in
  ~0.85 day (items 4+5+6) and unblocks all subsequent UI work.
- **v0 before React Flow**: ships drill-in working against the existing
  custom SVG using MHF's `key`-remount + CSS keyframe animation
  (§3.7.2.1). Avoids the React Flow migration risk on the critical
  path. Once v0 is in users' hands and the UX is validated, v1 swaps
  the rendering layer transparently.
- **Python and React deeply parallel**: the only real cross-team
  blocker is the event shape (item 7 needs the event spec from item 1
  — but the event shape is already pinned in §3.5.18.1 / §3.7).

### 7.7 Stop conditions / "we shipped enough" checkpoints

- **v0 acceptance**: `/mock_task --workers 20 --inner 5` renders a
  working drill-in graph; `test_role_setup.py` end-to-end shows
  topology + status + streaming for both outer and inner BTAs.
  Production-deployable.
- **v1 acceptance**: §3.5.16 acceptance criteria pass; smooth animated
  zoom; ghost context preserved; perf budgets met under `/mock_task
  --profile huge`.
- **v2 acceptance**: ~~A non-BTA inferencer renders~~ (DROPPED — they
  use `Workflow`, not `WorkGraph`). `Container Output` toggle shows
  live breakdown/aggregator for an inner BTA; UX polish features
  (search, layout toggle, jump-to-running) work.

If user feedback after v0 is "this is enough", v1/v2 can be deferred
indefinitely without leaving anything in a half-done state.

---

## 8. Out of Scope

- Visualization of conversation flow (existing chat UI handles this).
- DAGs with cycles (WorkGraph is acyclic by definition — `DirectedAcyclicGraph` base class).
- Real-time edit / pause / resume of running graphs (read-only viz).
- Cost/token consumption overlay per node (separate plan if desired).
- Replay / time-scrubber UI (interesting future work; out of scope here).

---

## 9. Backwards-Compatibility & Rollout

- All new event fields default to empty/None → old clients ignore them.
- New reporter methods (`child_reporter`) are additive — old reporters work
  unchanged for non-composing BTAs.
- ~~Roll out behind a feature flag `OPENTEAM_HIERARCHICAL_GRAPH=1` for the~~ **DROPPED** (§13.9): no existing UI behaviour to A/B against (today nested BTAs render NOTHING). The flag would add code complexity for zero value. Rolling out unconditionally.

<!-- Original text retained for audit:
- Roll out behind a feature flag `OPENTEAM_HIERARCHICAL_GRAPH=1` for the
  first week to allow A/B comparison.
-->
- After Phase 4, `create_role/executor.py` and any future tool needs only
  the standard 4-line attach-reporter snippet — fully generic.

---

## 10. Specific Bug Fixes Bundled In

While we're in this code, fix the residual issues from the original plan
review (now confirmed against the live implementation):

- **#10 (cross-system timestamps)** — Phase 2.3.
- **#7 (unbounded stream)** — Phase 2.2 #3 (also reinforced by §3.5.14
  perf budget).
- **#8 (frantic auto-switch)** — Phase 2.2 #5 + §3.5.7 (side panel only
  opens on explicit leaf click; no auto-switch).
- **#9 (premature auto-collapse)** — Phase 2.2 #6 + §3.5.8 (focus state
  is preserved across topology re-emissions).
- **#11 (no batching)** — Phase 2.2 #4.
- **#12 (no try/except in send)** — Phase 1.4.
- **`group` not in serialized dict** — Phase 4.2 (promote to first-class field).
- **Container nodes have nothing to show in side panel** — §3.5.4
  introduces "Container Output" toggle. BTA already routes breakdown
  and aggregator streams; no additional Python work needed (§3.5.10 OBSOLETE).

---

## Appendix A — File Inventory (complete list of files touched)

### PythonUtils
- `src/python_utils/common_objects/workflow/workgraph.py`
  - `WorkGraphNode.to_serializable_obj`: add `group`, `_viz_label`,
    `_is_container` (Phase 4.2).
  - `WorkGraph`: optional `graph_reporter` attribute + `_emit_topology`
    helper (Phase 4.1). [Decision required: do this in PythonUtils
    or keep in AgentFoundation?]

### AgentFoundation
- `src/agent_foundation/common/inferencers/graph_events.py`
  - Add `parent_node_id` and `version` to `GraphTopologyEvent`. (The
    earlier `namespace` field was removed per §READ-FIRST R-3 / §13.4
    — `parent_node_id` IS the namespace.)
  - Add `is_container` to per-node dict.
- `src/agent_foundation/ui/graph_interactive_adapter.py`
  - Add `NamespacedGraphReporter`.
  - Add `child_reporter()` method on `WebSocketGraphReporter`.
  - Throttle / circuit-breaker (Phase 3.1).
- `src/agent_foundation/common/inferencers/agentic_inferencers/flow_inferencers/breakdown_then_aggregate_inferencer.py`
  - Propagate `child_reporter` to nested workers (Phase 1.3).
  - Mark container nodes (`node._is_container = True`).
  - ~~Route breakdown/aggregator streams to synthetic ids (§3.5.10)~~
    **OBSOLETE**: BTA already routes these under `"breakdown"` /
    `"aggregator"` node IDs. No additional work needed.
- ~~`linear_workflow_inferencer.py`, `dual_inferencer.py`,
  `plan_then_implement_inferencer.py`, `reflective_inferencer.py`
  — Add `graph_reporter` (Phase 4.3)~~ **DROPPED**: these inherit
  `Workflow`, not `WorkGraph`. See R-2.

### OpenTeam
- `src/openteam/server/services/websocket_interactive.py`
  - try/except around `_send` (Phase 1.4).
- `src/openteam/server/resources/tools/role_setup/executor.py`
  - ~~**Attach `WebSocketGraphReporter`** (Phase 1.5) — currently absent.~~ **✅ DONE (r10)**: wired at lines 1215-1216.
- `src/openteam/server/resources/tools/create_role/executor.py`
  - No change required; uses generic Phase 1 machinery automatically.
- `src/openteam/ui/src/hooks/useGraphState.js` — NEW (Phase 2.2).
  - Manages `task.graph.subgraphs`, `focusPath`, `selectedLeafId`,
    `containerView` (§3.5.8), batched setTasks, bounded streams.
- `src/openteam/ui/src/hooks/useManagerChat.js`
  - Delegate graph cases to `useGraphState`.
- `src/openteam/ui/src/components/chat/GraphFlowView.js` — rewrite (Phase 2.1).
  - React Flow + dagre + nested groups + minimap + controls.
  - Focus-zoom animation handler, ghost-outline rendering, edge
    traversal shimmer, status-pulse halo (§3.5.2, §3.5.5, §3.5.6).
- `src/openteam/ui/src/components/chat/NodeDetailPanel.js`
  - Server-time offset for elapsed (Phase 2.3).
  - Breadcrumb path for nested ids.
  - Strict open-only-on-leaf-click rule (§3.5.7).
- `src/openteam/ui/src/components/chat/TaskPanel.js`
  - Recursive `allComplete` (Phase 2.4).
  - Use topology `version` as reset key (Phase 2.5).
  - Hosts the breadcrumb bar and keyboard-shortcut handler (§3.5.3, §3.5.9).
- `src/openteam/ui/src/components/chat/Breadcrumb.js` — NEW (§3.5.3).
- `src/openteam/ui/src/components/chat/ContainerOutputToggle.js` — NEW
  (§3.5.4); switches focused container view between Graph and Output.
- `src/openteam/ui/src/components/chat/GhostOutline.js` — NEW (§3.5.6);
  edge-pinned ghost markers for non-focused outer-context nodes.
- `src/openteam/ui/src/components/chat/LiveTokenBubble.js` — NEW (§3.5.5);
  fade-in/out floating preview of latest stream tokens above leaf nodes.
- `src/openteam/ui/src/components/chat/NodeKeyboardShortcuts.js` — NEW
  (§3.5.9); thin hook (`useGraphKeyboard`) attached at TaskPanel level.
- `src/openteam/ui/src/components/chat/KeyboardHelpOverlay.js` — NEW
  (§3.5.9, `?` key).
- `package.json` — add `@xyflow/react`, `dagre` (required for §3.5).

### OpenTeam — §3.6 `/mock_task` developer tool (NEW)

- `src/openteam/server/resources/tools/mock_task/tool.json` — NEW
  (`agent_enabled: false` to hide from LLM prompt).
- `src/openteam/server/resources/tools/mock_task/executor.py` — NEW
  (loads profile YAML, registers mock targets, instantiates BTA, wires
  `WebSocketGraphReporter` exactly as `create_role/executor.py:546–548`).
- `src/openteam/server/resources/tools/mock_task/profiles/default.yaml` — NEW
- `src/openteam/server/resources/tools/mock_task/profiles/default_inner.yaml` — NEW
- `src/openteam/server/resources/tools/mock_task/profiles/huge.yaml` — NEW
- `src/openteam/server/resources/tools/mock_task/profiles/flat.yaml` — NEW
- `src/openteam/server/resources/tools/mock_task/profiles/error.yaml` — NEW
- `src/openteam/server/resources/tools/mock_task/profiles/slow.yaml` — NEW
- `src/openteam/server/api/dev_tools_routes.py` — NEW
  (`GET /api/dev_tools/list`, `POST /api/dev_tools/{name}`; gated by
  `OPENTEAM_DEV_MODE`).
- `src/openteam/ui/src/components/chat/ChatInput.js`
  - Slash-command parsing on submit (intercepts `/<name>` lines).
  - Autocomplete popover for developer tools.
- `src/openteam/ui/src/hooks/useDevTools.js` — NEW
  (fetches `/api/dev_tools/list`, exposes `invokeDevTool(name, args)`).
- `src/openteam/ui/src/components/chat/DevToolBubble.js` — NEW
  (distinctly styled chat bubble for developer-tool invocations).

### AgentFoundation — §3.6 mock inferencer components (NEW)

- `src/agent_foundation/common/inferencers/mock_inferencers/mock_bta_components.py` — NEW
  (`MockBreakdownInferencer`, `MockWorker`, `MockAggregator`).
- `src/agent_foundation/common/inferencers/mock_inferencers/__init__.py`
  - Export the new mock components.
- `src/agent_foundation/common/configs/registered_targets.py`
  - Register `MockBreakdownInferencer`, `MockWorker`, `MockAggregator` so
    YAML `_target_:` resolution works.


---

## 3.5 Drill-in UX for Composing Graphs (NEW — supersedes parts of §3 Phase 2)

This section was added after a UX-focused review. It refines the earlier
"inline expand/collapse" model into a **single-canvas, animated drill-in**
experience suited for deeply composed graphs (BTA-of-BTAs with 17+ leaf
workers). It replaces or extends specific items in Phase 2.1 / 2.3 / 2.4.

### 3.5.0 Why the original "inline expand" is not enough

The original Phase 2.1 says container nodes render as collapsible group
boxes that expand inline. Verified problems with that approach for the
`test_role_setup` scenario:

- **Spatial blow-up.** Outer BTA has 5 inner BTAs. Each inner BTA has
  ~5 workers. Inline-expanding all 5 containers produces a graph with
  5 + 5×(2+5+1) = 45 visible nodes laid out in a single canvas. With
  16-wide leaf rows per container, total layout area exceeds 4000×3000
  px. Pan/zoom is necessary but the structural visual hierarchy gets
  lost — everything is at the same visual weight.
- **Loss of context vs. focus tradeoff.** Either you see the whole forest
  (and can't read any tree) or one tree at a time (and lose the forest).
- **Cluttered detail panel routing.** The current `NodeDetailPanel` is a
  side pane that expects a single "selected leaf" to show streaming
  output. Container nodes have nothing meaningful to put there today
  (the BTA doesn't stream).

### 3.5.1 Interaction Model — the 3 modes

The canvas operates in one of three modes at any moment:

| Mode | Trigger | Visual | Side panel content |
|---|---|---|---|
| **Overview** | Default; or `Esc` from any depth | Root graph fits viewport. Container nodes shown as compact "card" nodes with `▶ N children · X/Y ✓` badge. Outer edges fully visible. | Hidden (or shows minimal task summary) |
| **Focused** | Click a *container* node | Smooth-animated zoom into that container; canvas occupies same on-screen area but viewport now shows the sub-graph. Outer-context shown as faint **ghost outlines** at canvas edges. | Hidden by default; floating "Container output" toggle pill appears in top-right of focused area |
| **Inspecting** | Click a *leaf* node (any depth) | No zoom change. Clicked node gets selection ring + dim others slightly. | Slides in from right; shows live streaming output, status, label, output file links (current behaviour) |

Key invariant: **Overview ↔ Focused** uses canvas zoom only; **Inspecting**
is orthogonal and uses the side panel only. They can compose:
e.g. *Focused on `inner_bta_2`, Inspecting `inner_bta_2/worker_3`*.

### 3.5.2 Drill-in animation

Use React Flow's `setViewport({x, y, zoom}, {duration: 600})`. On
container click:

1. Compute the bounding box of the target container's sub-graph
   (recursively flatten its children's positions).
2. Compute target viewport: center on that bbox, zoom = `min(2.0,
   viewportWidth / bboxWidth * 0.9)`.
3. Begin the viewport animation (600 ms `cubic-bezier(0.4, 0, 0.2, 1)`).
4. Concurrently fade outer-context nodes' opacity 1.0 → 0.15 over 300 ms.
5. After animation completes, render ghost outlines for the outer-context
   nodes around the canvas perimeter (CSS-only, fixed-position pseudo-
   elements at viewport edges).
6. Show the floating breadcrumb bar slide-down from top.

Reverse on `Esc` or breadcrumb-click: invert in 400 ms (faster zoom-out
feels more natural).

**Performance**: viewport animation is GPU-driven (CSS transforms in React
Flow). Opacity fades use `transition: opacity 300ms` on a single CSS class
toggled via React state. No per-frame React re-renders.

### 3.5.3 Breadcrumb navigation

Always-visible at top of canvas (replaces the existing static `🔄 Pipeline
— N nodes` header):

```
┌─────────────────────────────────────────────────────────────┐
│ Task ▸ inner_bta_2 (Backend) ▸ worker_3 (Auth API)   [Esc]  │
└─────────────────────────────────────────────────────────────┘
```

- Each segment is the human-readable `_viz_label` (truncated to 24 chars)
  with the qualified id as a tooltip.
- Clicking a segment focuses to that depth (zoom to its sub-graph).
- Clicking "Task" returns to Overview.
- `Esc` pops one level.
- Persists across topology re-emissions (see 3.5.8).

### 3.5.4 Container "Container Output" toggle

When focused on a container, a floating pill appears in the top-right of
the focused area:

```
   ┌──────────────────┐
   │ ◐ Graph │ Output │   ← toggle, default = Graph
   └──────────────────┘
```

- **Graph** mode: shows the children sub-graph (default).
- **Output** mode: shows the container's own breakdown reasoning and
  aggregator output as a streaming text view, **inside** the focused
  area — not the side panel. This is the "single canvas" experience the
  user asked for.

**No additional Python work needed** (§3.5.10 is OBSOLETE — the BTA
already routes breakdown and aggregator streams under the existing
`"breakdown"` / `"aggregator"` node IDs via `node_stream_observer`).
When nested, `ChildGraphReporter` namespaces these to
`worker_2/breakdown` and `worker_2/aggregator`. When the user toggles
to "Output" for container `worker_2`, the UI reads
`nodeStreams["worker_2/breakdown"]` and `nodeStreams["worker_2/aggregator"]`
and displays them concatenated as markdown.

### 3.5.5 Live preview overlays — the "alive" feeling

To address the user's "single visualization" goal, give every node enough
live information that the user often does not need to open the side panel:

**Overview mode (zoomed out)**:
- Container nodes show animated **mini progress badge**:
  `▶ 3/5 ✓ · 2 ⚙` where `⚙` icon spins for currently running children.
- Container nodes show a **micro-sparkline** of their children's
  cumulative completion percentage over time (last 30 s).
- Leaf nodes show a 1-line **last token preview** (e.g.
  `…analyzing endpoint /auth`) updated max 2× per second, fading after
  5 s of inactivity.

**Focused mode**:
- Each running child node shows a **floating live tokens bubble** above
  it: a tiny CSS-clipped 3-line preview of the most recent stream
  output, with auto-fade. Updates throttled to 4 Hz.
- Edges from a just-completed parent to newly eligible children get a
  brief **traversal animation** (120 ms shimmer along the edge path)
  via SVG `stroke-dashoffset` animation. Visual cue that data flowed.
- Status transitions (pending → running) trigger a **2-pulse halo**
  around the node (no permanent animation cost).

All animations are CSS-only and respect `prefers-reduced-motion: reduce`.

### 3.5.6 Ghost outer context

When focused 1+ levels deep, the parent's siblings are not entirely hidden
— they appear as **ghost outlines** along canvas edges:

- Each ghost is a 32×32 px translucent box pinned to the viewport edge in
  the direction the original node lies.
- Hovering a ghost shows a tooltip with the node's label & status.
- Clicking a ghost focuses *back to the parent level* and re-focuses on
  the clicked sibling (one navigation step).
- A small **mini-overview** in the bottom-right corner (40×30 px) shows
  the entire root graph with a viewport-rectangle indicating current
  focus. Uses React Flow's `<MiniMap>` component already.

This achieves "you can drill in without losing where you are."

### 3.5.7 Side panel rules — strict and predictable

The `NodeDetailPanel` displays content *if and only if* a **leaf** node
is currently selected (Inspecting mode). Specifically:

| Click target | Result |
|---|---|
| Leaf node, currently in Overview/Focused | Side panel opens, shows that leaf's stream/details. Mode (zoom level) does not change. |
| Container node, currently in Overview | Switch to Focused on that container. Side panel does NOT open. |
| Container node, currently Focused on it | Toggle "Output ↔ Graph" (3.5.4). Side panel still does not open. |
| Container node, currently Focused on a *different* container | Re-focus to the new container. Side panel preserves its current selection only if the new focus contains it; else closes. |
| Background click | Close side panel; do not change focus. |
| `Esc` | If side panel open, close side panel; else pop focus level. |

This separates *spatial navigation* (canvas focus) from *information
inspection* (side panel) as two orthogonal concerns. Users can have both
or either independently.

### 3.5.8 Persisted UI state

Track per-task in React state (and optionally `sessionStorage`):

- `focusPath: string[]` — the qualified id segments of the current focus
  (`["inner_bta_2"]` for 1-level focus; `[]` for Overview).
- `selectedLeafId: string | null` — for the side panel.
- `containerView: { [containerId]: "graph" | "output" }` — per-container
  toggle state.

On topology re-emission (e.g., the inner BTA finally builds its sub-graph
and arrives a few seconds after the outer):

- If `focusPath` still resolves (its container id still exists), keep
  it.
- If the current `selectedLeafId` no longer exists, close the side panel.
- Apply the new sub-graph **without animation** to avoid jarring re-fits.
  Run a new `setViewport(currentFocusBbox)` only if focus is on the
  newly-arrived container's parent (so users *see* the children appear).

### 3.5.9 Keyboard shortcuts

| Key | Action |
|---|---|
| `Esc` | Close side panel; or pop focus one level |
| `Space` | Fit-view current focus (or root if Overview) |
| `→` / `←` | Step through siblings at current focus depth |
| `↑` / `↓` | Step through children of focused container |
| `/` | Focus search box |
| `R` | "Run-tour": auto-focus to the first running node, then sequentially the next |
| `?` | Show keyboard help overlay |

### 3.5.10 Python-side work needed for "Container Output" mode

> **⛔ OBSOLETE (r6/r10)**: BTA already routes breakdown and aggregator
> streams via `node_stream_observer("breakdown")` (line 1501-1503) and
> `node_stream_observer("aggregator")` (line 1031). The synthetic
> `__breakdown__`/`__aggregator__` IDs proposed below would create
> duplicate streams. Container Output toggle should use the existing
> `"breakdown"` / `"aggregator"` node IDs directly (namespaced by
> `ChildGraphReporter` when nested). **DO NOT IMPLEMENT THIS SECTION.**

~~This is **new** beyond the original Phase 1 plan. Adds ~half day.~~

~~Today, BTA's `breakdown_inferencer` and `aggregator_inferencer` have
their own `stream_observer` attributes but **the BTA does not route
their output to the graph_reporter** as `node_stream` events.~~ (INCORRECT — see above.) The virtual
`breakdown` *node* fires only a `completed` status (no streaming). **(This claim is also incorrect — breakdown fires stream events via its observer.)**

Add to `breakdown_then_aggregate_inferencer.py`:

```python
# In _ainfer, after self.graph_reporter is set and BEFORE breakdown runs:
if self.graph_reporter is not None and self.breakdown_inferencer is not None:
    # Route breakdown reasoning into the BTA's own container stream
    # under a synthetic "__breakdown__" sub-id so the UI can show it
    # in the Container Output toggle.
    self.breakdown_inferencer.stream_observer = (
        self.graph_reporter.node_stream_observer(
            f"__breakdown__"  # qualified by NamespacedGraphReporter
        )
    )

# Similarly before aggregator runs:
if self.graph_reporter is not None and self.aggregator_inferencer is not None:
    self.aggregator_inferencer.stream_observer = (
        self.graph_reporter.node_stream_observer(f"__aggregator__")
    )
```

When this BTA runs nested under a parent (its `graph_reporter` is a
`NamespacedGraphReporter` with namespace `inner_bta_2`), the qualified
ids become `inner_bta_2/__breakdown__` and `inner_bta_2/__aggregator__`.

UI side: when the user toggles "Output" for container `inner_bta_2`, the
panel concatenates `nodeStreams["inner_bta_2/__breakdown__"]` (with a
"## Breakdown" heading) and `nodeStreams["inner_bta_2/__aggregator__"]`
(with a "## Aggregation" heading) and shows them in a scrollable
markdown view.

### 3.5.11 Comparison Mode (optional, opt-in)

Hold `Shift` and click a second container while focused on one:

- The focused area splits 50/50 horizontally.
- Each side shows one focused sub-graph, independently scrollable.
- Useful for comparing two parallel workers (e.g., two competing approaches).
- `Esc` exits comparison; closing one side promotes the other to full focus.

This is opt-in and adds modest implementation cost; suggest deferring
until §3.5.1–3.5.10 ship and we have user feedback.

### 3.5.12 Library implications

The drill-in UX requires:

- **React Flow** (`@xyflow/react`) — viewport API, parentNode, MiniMap,
  Controls, Background. ~25 KB gzip.
- **dagre** for sub-graph auto-layout. ~10 KB gzip.
- *No* `framer-motion` needed — viewport transitions use React Flow's
  built-in animation; opacity / pulse / shimmer use CSS.

Custom alternative is possible but the viewport animation alone (smooth
zoom + pan with composed easing) is ~200 lines and the parent-node
absolute-positioning math is fiddly. Recommendation stands: adopt
React Flow.

### 3.5.13 Accessibility

- All drill-in actions available via keyboard (3.5.9).
- Focus management: when canvas focus changes, move DOM focus to the
  breadcrumb's last segment so screen readers announce the new context.
- ARIA: container nodes get `role="button" aria-expanded="true|false"
  aria-label="Inner BTA 2: Backend, 3 of 5 children complete"`.
- `prefers-reduced-motion`: replace animations with instant transitions;
  ghost outlines remain (non-animated).
- Color is never the sole status indicator (icons + text labels).

### 3.5.14 Performance budget for the drill-in UX

Targets at 17 leaf workers, 1 outer + 5 inner BTAs, sustained streaming:

- Frame time during idle drill-in: < 16 ms (60 fps).
- Frame time during status flurry (5 status events / 100 ms): < 33 ms (30 fps).
- React reconciliation per status event: < 2 ms (use `React.memo` on
  every node component, key by qualified id).
- Layout recompute (dagre) per topology emission: < 50 ms; offload to a
  Web Worker if exceeded for graphs > 100 nodes.
- Memory ceiling per task: < 50 MB JS heap including all stream buffers
  (enforced by 200 KB cap per node × ~50 nodes = 10 MB worst case).

### 3.5.15 Open UX questions (deferred decisions)

| # | Question | Default if no decision |
|---|---|---|
| A | Picture-in-picture overlay (focused + outer overview) vs. ghost outlines + minimap? | **Ghost + minimap** (simpler, less screen real estate) |
| B | Should "Container Output" toggle persist per container across re-runs? | Yes; stored in `sessionStorage` under task id |
| C | When zooming into a deep container, transit through intermediate levels (waypoint stop) or jump direct? | **Direct jump** (faster); intermediate stops feel slow at depth ≥ 3 |
| D | Should completed leaf nodes auto-collapse to half size to give running ones more visual weight? | **No** by default; opt-in via "compact mode" toggle in toolbar |
| E | Comparison Mode (3.5.11) in v1 or defer? | **Defer**; ship after user feedback on basic drill-in |

### 3.5.16 Acceptance criteria for §3.5

- [ ] Click on `inner_bta_2` container → smooth 600 ms zoom into its
  sub-graph, breadcrumb updates, side panel does not open.
- [ ] `Esc` returns to Overview in 400 ms with no flicker.
- [ ] Click a leaf node at any depth → side panel opens, focus unchanged.
- [ ] "Container Output" toggle on `worker_2` shows live breakdown +
  aggregator streams (BTA already routes these — no §3.5.10 work needed).
- [ ] At 60 fps with 17 workers running, sustained for 30 s.
- [ ] Ghost outlines for non-focused root nodes appear on viewport edges
  when focused 1+ levels deep.
- [ ] Mini-overview minimap reflects current focus rectangle.
- [ ] Keyboard nav: `Esc` / `Space` / `→` / `←` / `/` all work.
- [ ] `prefers-reduced-motion`: animations replaced with instant
  transitions; functional behavior identical.
- [ ] Re-emission of inner topology while focused on outer container:
  children appear in place; viewport stays on outer container.

### 3.5.17 Effort revision

Original Phase 2 was estimated 2 days. With §3.5 the UI work expands:

| Sub-area | Days |
|---|---|
| 2.1 React Flow base + dagre layout + nested groups | 1.0 |
| 3.5.2 Focus zoom animation + ghost context | 0.5 |
| 3.5.3 Breadcrumb navigation | 0.25 |
| 3.5.4 Container Output toggle (UI) | 0.25 |
| 3.5.5 Live preview overlays + edge animations | 0.75 |
| 3.5.7 Side panel rules refactor | 0.25 |
| 3.5.8 Persisted UI state | 0.25 |
| 3.5.9 Keyboard shortcuts | 0.25 |
| ~~3.5.10 Python: route breakdown/aggregator streams~~ **OBSOLETE** | 0 |
| 3.5.13 A11y pass | 0.25 |
| 3.5.14 Perf testing & tuning | 0.5 |
| **Total UI + Python additions** | **4.75 days** |

Revised total plan effort: **~8 dev-days** (was ~5.5).

Critical path for `test_role_setup.py` to be visualizable AND drill-in-able:
Phase 1 (1 d) + revised Phase 2 incl. §3.5 minimum (3.5 d for items 2.1,
3.5.2, 3.5.3, 3.5.7) = **~4.5 days** to first usable demo.


---

## 3.6 `/mock_task` Developer Tool — Mock Composing Inferencer for UI Iteration

This section adds a development-only tool that constructs a fully-mocked
BTA-of-BTAs (mirroring the `role_setup.yaml` shape — outer breakdown →
inner BTAs → leaf workers → aggregators) and **drives it without any LLM
calls**. Its purpose is to let the UI team iterate on §3.5's drill-in
visualization without paying the cost (latency, $, network flakiness) of
running a real `role_setup` invocation.

### 3.6.0 Why this is necessary

Verified facts about the current state:

- A real `role_setup` run takes ~3 minutes and ~$1–3 of LLM calls
  (`monitor_run_3min.sh` exists in the test directory).
- It depends on Atlassian Rovo / network / file IO.
- The graph topology is **non-deterministic** — breakdown count varies
  per run, making reproducibility hard for UI bug reports.
- An iterative UI session needs ~50 runs/day → infeasible without mocking.
- An existing `MockClarificationInferencer` (verified at
  `agent_foundation/.../mock_inferencers/mock_clarification_inferencer.py`)
  proves the pattern; we extend it to BTA composition.

### 3.6.1 User-facing behaviour

- Available as a **slash command** in the chat input: typing `/mock_task`
  triggers the tool.
- Optional args control complexity:
  - `/mock_task` → default profile (1 outer BTA × 5 inner BTAs × ~3
    leaf workers each = ~17 leaf nodes, mirrors `role_setup` average).
  - `/mock_task --profile huge` → 1 outer × 8 inner × 8 = 64 leaves.
  - `/mock_task --profile flat` → 1 outer BTA × 0 inner × 12 leaves
    (single-level, no composition; useful baseline).
  - `/mock_task --profile error` → injects a worker that errors out
    (test error styling).
  - `/mock_task --profile slow` → 60 s total runtime with 2 s per
    transition (test sustained streaming).
  - `/mock_task --seed 42` → deterministic topology + timing.
  - `/mock_task --yaml ./path/to/some.yaml` → load real
    `role_setup`-style YAML, replace every `_target_` with its mock
    equivalent, and run that exact topology.
- **Hidden from the LLM conversational prompt** by setting
  `agent_enabled: false` in `tool.json` (this flag *already exists*
  in `ToolDefinition`, verified at `models.py:111` — see §READ-FIRST R-8). The LLM never sees
  `mock_task` as an available tool, so it cannot trigger it accidentally.
- **Behaves identically to `role_setup` on the wire** — emits the same
  `graph_topology`, `node_status`, `node_stream` events through
  `WebSocketGraphReporter`, so the UI cannot tell the difference.

### 3.6.2 Architecture

```
ChatInput (UI)                 server/
   ↓ "/mock_task --profile huge"  resources/tools/mock_task/
   ↓                                  tool.json   (agent_enabled=false)
ChatInput slash parser              executor.py  (entry point)
   ↓                                  profiles/
WebSocket → tool_dispatcher           ├── default.yaml
   ↓                                  ├── huge.yaml
mock_task.executor:execute()           ├── flat.yaml
   ↓                                   ├── error.yaml
MockBTA(outer_yaml)                   └── slow.yaml
   ↓ uses MockBreakdownInferencer
   ↓ uses MockWorkerFactory
   ↓ uses MockAggregatorInferencer
   ↓ wires WebSocketGraphReporter (same as create_role/role_setup)
   ↓ kicks off async ainfer()
WebSocket emits graph_topology, node_status, node_stream
   ↓
React UI renders exactly as for a real BTA run
```

### 3.6.3 Mock Inferencer Library (Python, AgentFoundation)

Create `agent_foundation/common/inferencers/mock_inferencers/mock_bta_components.py`:

```python
class MockBreakdownInferencer:
    """Returns a pre-canned JSON list of N subtasks instantly (or with delay)."""
    def __init__(self, *, subtasks: list[dict], delay_s: float = 0.0,
                 stream_chunks: list[str] | None = None):
        self.subtasks = subtasks      # list of {task_preamble, description, ...}
        self.delay_s = delay_s
        self.stream_chunks = stream_chunks or [
            "Analyzing role document…\n",
            "Identifying required capabilities…\n",
            f"Found {len(subtasks)} subtasks.\n",
        ]
        self.stream_observer = None   # set by parent BTA — emits chunks live

    async def ainfer(self, *args, **kwargs):
        for chunk in self.stream_chunks:
            if self.stream_observer:
                # §READ-FIRST R-3 / §13.3: observer is a CALLABLE, not .emit()
                await self.stream_observer(chunk)
            await asyncio.sleep(self.delay_s / max(1, len(self.stream_chunks)))
        # §READ-FIRST R-7: flush trailing batch so the last chunk is not
        # silently dropped by the observer's 200 ms coalescing buffer.
        if self.stream_observer and hasattr(self.stream_observer, 'flush'):
            await self.stream_observer.flush()
        return json.dumps(self.subtasks)


class MockWorker:
    """Mocks a single leaf worker — sleeps + emits stream chunks + returns text.

    Critically: respects `_graph_event_callback` so RUNNING / COMPLETED
    transitions are emitted normally by the parent WorkGraph machinery.
    """
    def __init__(self, *, label: str, duration_s: float = 1.0,
                 stream_chunks: list[str] | None = None,
                 should_error: bool = False, output: str = ""):
        self.label = label
        self.duration_s = duration_s
        self.stream_chunks = stream_chunks or _default_chunks_for(label)
        self.should_error = should_error
        self.output = output or f"[mock output for {label}]"
        self.stream_observer = None
        self.interactive = None       # set by parent BTA
        self._graph_event_callback = None  # set by WorkGraphNode

    async def ainfer(self, *args, **kwargs):
        per_chunk = self.duration_s / max(1, len(self.stream_chunks) + 1)
        for chunk in self.stream_chunks:
            await asyncio.sleep(per_chunk)
            if self.stream_observer:
                await self.stream_observer(chunk)   # §READ-FIRST R-3 / §13.3
        await asyncio.sleep(per_chunk)
        if self.should_error:
            raise RuntimeError(f"[mock error in {self.label}]")
        # §READ-FIRST R-7: flush before the worker returns; BTA's post-emit
        # `is_final=True` is also redundant-safe.
        if self.stream_observer and hasattr(self.stream_observer, 'flush'):
            await self.stream_observer.flush()
        return self.output


class MockAggregator:
    """Mocks the aggregator — emits chunks reflecting per-worker outputs."""
    # Same shape as MockBreakdownInferencer, but receives worker outputs
    # in __call__ args and synthesizes a result string.
```

These plug into the **real** `BreakdownThenAggregateInferencer` — they
satisfy its `breakdown_inferencer`, `worker_factory`, `aggregator_inferencer`
interface contracts. The real BTA does the graph construction, status
emission, and reporter wiring exactly as it does for a real run. **No
visualization code paths are mocked or bypassed.**

### 3.6.4 Mock Profiles (YAML)

Profiles live in `openteam/server/resources/tools/mock_task/profiles/`.
Each is a real `BTA` YAML (loadable via the same `instantiate(cfg)` flow
that `create_role/role_setup` use), but with `_target_` set to mock
classes:

```yaml
# profiles/default.yaml — mirrors role_setup composition
_target_: BTA
name: mock_outer_bta

breakdown_inferencer:
  _target_: MockBreakdownInferencer
  delay_s: 1.5
  subtasks:
    - {task_preamble: skill_tool_creation, description: "Auth API skill"}
    - {task_preamble: skill_tool_creation, description: "DB query skill"}
    - {task_preamble: skill_tool_creation, description: "Logging skill"}
    - {task_preamble: skill_tool_creation, description: "Metrics skill"}
    - {task_preamble: skill_tool_association, description: "Wire existing skills"}

worker_factory:
  skill_tool_creation:
    # Inner BTA — full composing scenario
    _import_: "default_inner.yaml"
  skill_tool_association:
    _target_: MockWorker
    label: "Associate existing skills"
    duration_s: 4.0

aggregator_inferencer:
  _target_: MockAggregator
  delay_s: 2.0
  output_template: "Mock role setup report (5 subtasks completed)"
```

```yaml
# profiles/default_inner.yaml — inner BTA (3 leaf workers)
_target_: BTA
name: mock_inner_bta

breakdown_inferencer:
  _target_: MockBreakdownInferencer
  delay_s: 0.8
  subtasks:
    - {description: "Research existing implementations"}
    - {description: "Identify gaps"}
    - {description: "Define new SOP"}

worker_factory:
  __default__:
    _target_: MockWorker
    duration_s: 3.0  # parameterized per worker via factory args

aggregator_inferencer:
  _target_: MockAggregator
  delay_s: 1.2
```

This achieves the user's stated goal: a mock that exactly mirrors the
`role_setup.yaml` *structural shape* (outer-BTA → inner-BTAs →
leaf-workers → aggregators) so the UI is exercised under the real
composition pattern.

Other profiles override delays/counts/error injection.

### 3.6.5 Tool Registration (`tool.json`)

Create `openteam/server/resources/tools/mock_task/tool.json`:

```json
{
  "name": "mock_task",
  "asynchronous": true,
  "is_bridge": true,
  "executor": "openteam.server.resources.tools.mock_task.executor:execute",
  "description": "[DEVELOPER] Run a mocked composing-BTA pipeline to exercise the graph visualization without real LLM calls.",
  "tool_type": "Action",
  "category": "utility",
  "agent_enabled": false,
  "parameters": [
    {"name": "--profile", "type": "string", "default": "default",
     "description": "default | huge | flat | error | slow"},
    {"name": "--seed", "type": "int", "default": 0,
     "description": "Deterministic seed for topology + timing variation."},
    {"name": "--yaml", "type": "path",
     "description": "Override: load arbitrary BTA YAML and mock its inferencers."},
    {"name": "--speed", "type": "float", "default": 1.0,
     "description": "Multiplier on all delays (0.5 = 2x faster, 2.0 = 2x slower)."}
  ],
  "returns": "Mock report (no real artifacts produced)."
}
```

`agent_enabled: false` makes this **invisible to the LLM** (verified
at `models.py:111` and the conversational filter at `conversational_inferencer.py:506-507` —
`_format_conversation_tools` filters by `agent_enabled`).

### 3.6.6 Executor (`executor.py`)

```python
async def execute(arguments: dict, session_context: dict) -> ToolExecutionResult:
    profile = arguments.get("profile", "default")
    seed = int(arguments.get("seed", 0))
    yaml_override = arguments.get("yaml")
    speed = float(arguments.get("speed", 1.0))

    # Load profile YAML (or user-provided)
    if yaml_override:
        cfg_path = Path(yaml_override)
    else:
        cfg_path = _PROFILES_DIR / f"{profile}.yaml"

    # Optionally apply speed multiplier by post-processing config
    cfg = load_config(cfg_path)
    if speed != 1.0:
        cfg = _apply_speed(cfg, speed)
    if seed:
        random.seed(seed)
        cfg = _apply_seed_jitter(cfg, seed)

    # IMPORTANT: register mock targets so instantiate() resolves them.
    import agent_foundation.common.configs.registered_targets  # noqa
    import agent_foundation.common.inferencers.mock_inferencers.mock_bta_components  # noqa: register MockBreakdownInferencer, MockWorker, MockAggregator

    bta = instantiate(cfg)

    # Wire graph reporter — IDENTICAL to create_role/executor.py:546–548
    interactive = session_context.get("interactive")
    task_id = session_context.get("task_id", "")
    if interactive is not None and task_id:
        from agent_foundation.ui.graph_interactive_adapter import WebSocketGraphReporter
        bta.graph_reporter = WebSocketGraphReporter(interactive, task_id)

    # Run
    try:
        result = await bta.ainfer("__mock_input__")
        return ToolExecutionResult(success=True, output=str(result))
    except Exception as e:
        return ToolExecutionResult(success=False, output=str(e))
```

### 3.6.7 UI: Slash Command Support (NEW)

> **⛔ OBSOLETE (r6/§13.10)**: The HTTP-route design below (dev_tools_routes.py,
> useDevTools.js, DevToolBubble.js) is superseded by the simpler WS
> slash-command intercept in §3.5.18.5 / §3.7.3.5. Use that instead.

~~Currently `ChatInput.js` is a plain `<TextField>`. Add a minimal slash
command parser:~~

#### 3.6.7.1 `ChatInput.js` enhancement

- When input starts with `/`, intercept submit:
  - Match `/mock_task( --profile=X)?( --seed=N)?...` against tool registry.
  - If match and `agent_enabled === false` (developer tool), call a
    new endpoint `POST /api/dev_tools/{name}` with parsed args directly
    (bypassing the conversation/LLM path entirely).
  - If no match, allow normal submission (LLM handles the message).
- Show an autocomplete popover when user types `/`:
  - List all developer tools (those with `agent_enabled: false`) and
    standard tools the user might want to invoke directly.
  - Renders inline below the input. Fetch list from
    `GET /api/dev_tools/list`.

#### 3.6.7.2 New backend endpoint

`server/api/dev_tools_routes.py`:

```python
@router.get("/api/dev_tools/list")
async def list_dev_tools():
    return [t.to_dict() for t in tool_registry.values() if not t.agent_enabled]

@router.post("/api/dev_tools/{name}")
async def invoke_dev_tool(name: str, body: InvokeBody, ws: WebSocket = ...):
    tool = tool_registry.get(name)
    if not tool or tool.agent_enabled:
        raise HTTPException(404)
    # Reuse the same dispatch path as conversation tools
    result = await tool_dispatcher(name, body.arguments)
    return result.to_dict()
```

This **does NOT bypass** the existing tool dispatch / WebSocket /
graph reporter pipeline — it merely lets the user *originate* the call
without an LLM in the loop.

#### 3.6.7.3 Visual treatment in conversation

- Developer-tool invocations render in the chat as a distinctly-styled
  "system" bubble with a small wrench icon and gray background, e.g.:

  ```
  🔧 [DEV] /mock_task --profile huge   ⏱ running…
  ```

- Same TaskPanel pops out for the result — so the user sees the
  drill-in graph visualization exactly as for a real `role_setup`.

### 3.6.8 What the mock guarantees (test contract)

The mock reproduces the following for parity with real runs:

| Real BTA emits | Mock BTA emits | Same? |
|---|---|---|
| `graph_topology` with namespaced ids per `NamespacedGraphReporter` | ✅ same path through `bta.graph_reporter.child_reporter(...)` | yes |
| `node_status` RUNNING / COMPLETED / ERROR | ✅ via `WorkGraphNode._graph_event_callback` — unchanged | yes |
| `node_stream` chunks every ~200 ms | ✅ via `await MockWorker.stream_observer(chunk)` (callable; §READ-FIRST R-3) | yes |
| ~~`__breakdown__` / `__aggregator__` streams (§3.5.10)~~ DROPPED — see §READ-FIRST R-2; BTA already routes under `"breakdown"` / `"aggregator"`. Mock uses the existing ids. | ✅ via `await MockBreakdownInferencer.stream_observer(chunk)` | yes |
| Graph re-emission when inner BTA builds itself | ✅ same `_build_diamond_graph` codepath | yes |
| Variable-fanout topologies | ✅ subtask count from profile YAML | yes |
| Errors mid-run | ✅ `--profile error` raises `RuntimeError` in one worker | yes |

### 3.6.9 Anti-patterns to avoid (verified pitfalls)

1. **DO NOT bypass the real `BreakdownThenAggregateInferencer`** — using
   a `MockBTA` class that fakes the events directly defeats the purpose.
   The point is to exercise the same code path the user sees.
2. **DO NOT register `mock_task` with `agent_enabled: true`** — even
   transiently. Once committed, the LLM may try to call it ("user said
   they want a quick test → I'll run mock_task!"). Verified that
   `_format_conversation_tools` filters by `agent_enabled` (formatters/
   `conversational_inferencer.py:506-507` — NOT `formatters/markdown.py:167`).
3. **DO NOT bind `mock_task` to a global keyboard shortcut** — only
   the `/mock_task` slash command. Otherwise users in production
   could trigger it accidentally.
4. **DO mark mock outputs visually as `[MOCK]`** in any rendered text
   to prevent confusion in screenshots/recordings shared in PRs.
5. **DO ship `mock_task` only when `OPENTEAM_DEV_MODE=1`** — gate the
   `/api/dev_tools/*` routes behind an env flag so production builds
   cannot expose them. Belt-and-braces with `agent_enabled: false`.

### 3.6.10 Acceptance criteria

- [ ] `/mock_task` typed in chat → autocomplete popover shows the
  command + its profiles.
- [ ] `/mock_task --profile default` → TaskPanel opens, graph topology
  arrives within 2 s, status updates flow, run completes in ~10 s.
- [ ] Identical graph rendering codepath as real `role_setup` (verified
  by feature flag: real `role_setup` emits identical event types/names).
- [ ] `/mock_task --profile huge` → 64-node graph renders without
  layout overlap, drill-in works.
- [ ] `/mock_task --profile error` → one worker shows ERROR styling
  (red halo); aggregator still runs (or fails gracefully — test both).
- [ ] LLM never sees `mock_task` in its conversation prompt (assert
  `agent_enabled=false` in `tool.json`; assert
  `_format_conversation_tools` output does not contain "mock_task" via
  unit test).
- [ ] `/mock_task --seed 42` produces byte-identical graph topology
  and timing across runs.
- [ ] Production build (`OPENTEAM_DEV_MODE` unset) returns 404 from
  `/api/dev_tools/*`.
- [ ] Bonus: `/mock_task --yaml ./test_role_setup.yaml` runs the
  exact `role_setup.yaml` topology with mocked inferencers.

### 3.6.11 Effort

| Item | Days |
|---|---|
| `MockBreakdownInferencer`, `MockWorker`, `MockAggregator` + register targets | 0.5 |
| 5 profile YAMLs (default, huge, flat, error, slow) + speed/seed support | 0.25 |
| `mock_task/tool.json` + `executor.py` + tests | 0.25 |
| Slash-command parser + autocomplete popover in `ChatInput.js` | 0.5 |
| `/api/dev_tools/*` routes + `OPENTEAM_DEV_MODE` gating | 0.25 |
| Visual treatment for dev-tool messages in chat | 0.25 |
| Tests (unit + e2e for hidden-from-LLM, dev-mode gating, profile parity) | 0.5 |
| **Total** | **2.5 days** |

This is **net-additive** to the §3.5 effort. Crucially, §3.6 unblocks
fast iteration on §3.5 — once §3.6 ships, §3.5 development gets ~10×
faster because every UI tweak can be tested against `/mock_task --profile
huge` instead of running real `role_setup`. **Recommend building §3.6
in parallel with Phase 1**, before starting Phase 2 / §3.5.

### 3.6.12 Dependency on rest of plan

- Requires **Phase 1** (namespaced reporter) to be complete so child
  reporters work for the inner-BTA mock.
- Requires the `agent_enabled: false` filter to actually be honored by
  the conversation prompt formatter — this is **already implemented**
  (verified at `models.py:111` and the agent_enabled filter at
  `conversational_inferencer.py:506-507`). Good news: no foundation
  work needed. NOTE: `_format_conversation_tools` lives in
  `formatters/markdown.py:167` but does NOT itself filter — the
  filter is applied upstream in `conversational_inferencer.py`.
- Slash-command parser is independent of §3.5 — it can ship before the
  React Flow rewrite. Initial version can render the existing custom
  `GraphFlowView` while §3.5 is in development.

### 3.6.13 Open Questions

| # | Question | Default if no decision |
|---|---|---|
| F | Should `/mock_task` be available to *all* users in dev mode, or only when an `?dev=1` query param is set in the URL? | All users in `OPENTEAM_DEV_MODE` builds. Belt-and-braces with `agent_enabled: false`. |
| G | Should the autocomplete popover ALSO list real tools (`/role_setup`, `/create_role`) even though they're LLM-driven? Could be useful for power users. | Out of scope; this is the dev-tool palette, not a general command palette. |
| H | Do we want a `--record` flag that captures all WebSocket events to a JSON file for replay? Useful for golden-file UI tests. | Defer; nice-to-have. Phase 2 of mock_task. |
| I | Should `/mock_task` automatically launch with `--profile huge --speed 0.5` if `Shift` is held during submission? Quick stress-test shortcut. | No; explicit args only. Avoids hidden surprises. |


---

## 3.7 Plan Integration — best-of-both from `memoized-hugging-firefly.md` (MHF)

A second design plan ("MHF") was independently produced. Side-by-side
review (see archived comparison in §11) shows MHF's Phase 1 architecture
is **identical** to ours (independent convergence on `parent_node_id` +
`ChildGraphReporter`/`NamespacedGraphReporter`) — strong validation of
the core design. MHF wins on **pragmatism, decisiveness, no-new-deps
shipability**; ours wins on **breadth, reliability, generality**. This
section folds the best of MHF into our plan as concrete deltas, ordered
by ROI.

### 3.7.0 Adopt-from-MHF list (priority-ordered)

| # | Idea from MHF | What it changes here | ROI |
|---|---|---|---|
| 1 | **Build `/mock_task` first**, even before Phase 1 namespacing | Reorder §7 (see §3.7.6 v0/v1 schedule). Initial version: flat-only `--workers N --inner 0` to unblock UI iteration immediately. | ★★★★★ |
| 2 | **Slash command via WebSocket message intercept** instead of `/api/dev_tools/*` HTTP route | §3.6.7.2 is replaced. Implementation lands in `manager_websocket_routes.py:process_message`. **Still gated by `OPENTEAM_DEV_MODE` + `agent_enabled:false` defense-in-depth.** | ★★★★★ |
| 3 | **`graphPath: string[]` as the single canvas-navigation primitive** | Replaces `focusPath` everywhere in §3.5. `selectedLeafId` and `containerView` remain orthogonal additional state. | ★★★★ |
| 4 | **`expandableNodeIds` derivation pattern** (see §3.5.x rewrite) | Adopt verbatim into `useGraphState`; cleanest way to discover which nodes have sub-graphs at a given depth. | ★★★★ |
| 5 | **CSS-keyframe + `key`-remount animation** as v0 fallback | Lets v0 ship drill-in without React Flow. Upgrade to React Flow `setViewport` zoom in v1. | ★★★★ |
| 6 | **Numeric args for `/mock_task`** (`--workers`, `--inner`, `--delay`) alongside `--profile` YAML | Both pathways — numeric for quick parameter sweeps, YAML for `role_setup`-shape mirroring. | ★★★★ |
| 7 | **Compact mode** as a discrete on/off toggle (hide leaf labels above `nodes > N`) — independent of drill-in | Standalone graceful-degradation feature usable with or without React Flow. | ★★★ |
| 8 | **Dynamic graph panel height ladder** (5 → 30%; 10 → 40%; 20 → 50%; >20 → 55%) | Pragmatic 4-line solution to the 20-worker overflow problem. | ★★★ |
| 9 | **MHF's edge-case list** (race conditions on drill-down before inner topology arrives, zoom/pan reset on `graphPath` change, deep nesting) | Copy near-verbatim into §4 testing, **with the addition** of "Rerun also clears `nodeStreams` for orphaned ids" (MHF miss). | ★★★ |
| 10 | **`/mock_task` `--assert-event-parity` flag** (NEW idea surfaced by the merge) | Mock becomes a regression test for the event protocol, not just a UI exercise. | ★★ |

### 3.7.1 Reject-from-MHF list (with reasons)

| MHF idea | Why we don't adopt it |
|---|---|
| Replace whole canvas on drill-down (`key`-remount only) | Loses outer context for 2+ deep compositions. We keep this as a **v0 fallback** but the v1 target is single-canvas zoom + ghost outer context + minimap (§3.5.6). |
| WS-intercept `/mock_task` ungated | Dev tool exposed in production via literal substring match. We add `OPENTEAM_DEV_MODE` env gate (defense-in-depth alongside `agent_enabled:false`). |
| `transitionDirection` state set imperatively before navigation | Race-prone on rapid clicks. We derive direction via `useRef(prevPath)` + `useEffect` instead. |
| `fitToView` capped at zoom 1.0 (small graph cannot magnify) | Off-by-design. We remove the cap (use min(cW/totalW, cH/totalH); separate sanity bound at 2.0 for max). |
| No `OPENTEAM_DEV_MODE` gate | Production safety. Required. |
| No `prefers-reduced-motion` | A11y. Required. |
| No `node_stream` accumulator cap | Real OOM risk on long-running CLI workers. We keep §3.5.14 perf budget + §3.3 enforced caps. |
| No `LinearWorkflowInferencer` / `DualInferencer` / etc. generalisation | Stated user goal: "generic and able to handle complex case". We keep Phase 4. |
| No "Container Output" mode | Container nodes have nothing meaningful to show today. We keep §3.5.4 (UI toggle reads existing `breakdown`/`aggregator` streams — no §3.5.10 Python work needed). |

### 3.7.2 Genuinely new ideas the merge surfaces

#### 3.7.2.1 Two-phase animation strategy (v0 → v1 upgrade path)

- **v0** uses MHF's `<Box key={graphPath.join('/') || 'root'}>` CSS-keyframe
  remount animation. **No React Flow needed.** Ships drill-in against the
  current custom GraphFlowView.
- **v1** upgrades to React Flow's `setViewport({duration: 600})` for true
  zoom-into-sub-graph. Outer context preserved as ghost outlines + minimap
  (§3.5.6).
- The `useGraphState` hook is **identical** for both — only the rendering
  layer changes. v0 → v1 is a localised swap of `<GraphFlowView>` impl.

This means we can ship a working drill-in UX **before** committing to the
React Flow migration risk.

#### 3.7.2.2 `/mock_task` event-parity assertion mode

`--assert-event-parity ./reference_run.jsonl` flag:
- Loads a captured `WebSocket` event stream from a real `role_setup` run
  (see also `--record` flag, §3.6.13.H).
- Mock emits the structurally-equivalent sequence (modulo timing).
- Asserts (in dev mode) that every event type/field/relationship matches.
- Fails the run if drift detected.

Now `/mock_task` is **a regression test for the event protocol**, not
just an interactive UI exercise tool. Deeply useful when iterating on
graph event routing — confirms the on-wire shape is stable.

Implementation: ~0.25 day. Add to §3.6.11.

#### 3.7.2.3 `graphPath`-driven derivation of EVERYTHING

Adopting MHF's elegance: derive *all* downstream state from `graphPath`
via `useMemo`:

```js
// Single source of truth for canvas navigation
const [graphPath, setGraphPath] = useState([]);    // [] = root

// Everything else derives from it:
const currentGraph = useMemo(() => {
  if (graphPath.length === 0) return task.graph;
  return task.subGraphs?.[graphPath.join('/')] || null;
}, [task.graph, task.subGraphs, graphPath]);

const breadcrumb = useMemo(() => buildBreadcrumb(task, graphPath), [task, graphPath]);
const expandableNodeIds = useMemo(() => deriveExpandable(task.subGraphs, graphPath), [task.subGraphs, graphPath]);
const isContainer = (nodeId) => expandableNodeIds.has(nodeId);

// Side-panel selection is orthogonal:
const [selectedLeafId, setSelectedLeafId] = useState(null);

// Per-container view-mode (graph vs output) is orthogonal:
const [containerView, setContainerView] = useState({});  // {[containerId]: 'graph'|'output'}
```

Three pieces of state, each with a clear semantic, each independently
debuggable. Replaces my earlier `focusPath` + ad hoc derivations.

### 3.7.3 Concrete deltas to existing sections

#### 3.7.3.1 §3.5.1 — three modes table — replace "Focused: animated zoom into that container..." with:

> **Focused** (v0): drill into that container — current canvas is
> remounted to render the sub-graph (CSS keyframe animation,
> 0.3 s ease-out, scale 1.05→1.0 + 8 px translate-Y).
> **Focused** (v1): canvas zooms into the container's bbox via React
> Flow `setViewport({duration: 600})`; outer context fades to opacity
> 0.15 and is shown as ghost outlines on the viewport perimeter.
> The `useGraphState` hook is identical for both — only `<GraphFlowView>`
> differs.

#### 3.7.3.2 §3.5.7 side-panel rules — clarify v0 behaviour

For v0 (canvas-replacement drill-in), "Inspecting" mode is fully
orthogonal to "Focused". Selection of a leaf at any depth opens the
side panel; the side panel's `nodeStreamKey` is derived from
`graphPath.join('/') + '/' + selectedLeafId` so it works at any depth
without further changes.

#### 3.7.3.3 §3.5.8 persisted state — adopt MHF's edge case 6 with addition

On topology re-emission for the **root** graph (rerun):
1. Replace `task.graph`.
2. Clear `task.subGraphs` entirely.
3. Reset `graphPath = []`.
4. Reset `selectedLeafId = null`.
5. **NEW**: Clear `task.nodeStreams[k]` for every `k` that does not
   appear in the new root graph (orphaned-stream cleanup — MHF miss).

On topology arrival for a **sub-graph** (`parent_node_id != ""`):
1. Splice into `task.subGraphs[parent_node_id]`.
2. Do NOT reset `graphPath` (user may already be elsewhere).
3. Do NOT change `selectedLeafId`.
4. If `graphPath` ends with `parent_node_id` (user is currently looking
   at this newly-arrived sub-graph), trigger a fit-view on the new
   nodes (no animation — would be jarring).

#### 3.7.3.4 §3.5.9 keyboard shortcuts — `Esc` semantics

Refined after merge:
- `Esc` priority: (1) close help overlay if open; (2) close side panel
  if open and selection is at current `graphPath` depth; (3) pop
  `graphPath` one level. So pressing `Esc` repeatedly: dismisses help,
  closes side panel, then walks back up the breadcrumb.

#### 3.7.3.5 §3.6.7.1 — slash command intercept moves to WebSocket

REPLACES the prior `/api/dev_tools/*` HTTP-route design. New design:

```python
# server/routes/manager_websocket_routes.py: in process_message
async def process_message(sid: str, text: str) -> None:
    text = text.strip()
    if text.startswith("/") and os.environ.get("OPENTEAM_DEV_MODE") == "1":
        cmd, *rest = text[1:].split(maxsplit=1)
        args_str = rest[0] if rest else ""
        tool = tool_registry.get(cmd)
        if tool is not None and tool.agent_enabled is False:
            # Defense in depth: tool.json must explicitly opt in
            args = parse_cli_args(args_str, tool.parameters)
            task_id = f"dev-{cmd}-{uuid.uuid4().hex[:8]}"
            await send_safe({"type": "task_status", "task_id": task_id,
                             "tool_name": cmd, "status": "running",
                             "label": f"[DEV] {cmd}"})
            # Reuse the SAME tool dispatcher as conversational tools
            asyncio.create_task(
                tool_dispatcher.execute(cmd, args,
                                        session_context={"interactive": ...,
                                                         "task_id": task_id})
            )
            return
    # ... existing conversation flow ...
```

Two-flag safety:
1. `OPENTEAM_DEV_MODE=1` env (production builds will not set this).
2. `tool.json` has `agent_enabled: false` (LLM never sees it; substring
   intercept won't fire either if flag is missing).

Critically, we **route through the existing tool_dispatcher** (MHF's
miss) so the mock exercises the same execution wrapper as real tools.

#### 3.7.3.6 Compact mode toggle (NEW, §3.7 addition)

Add to `GraphFlowView.js` toolbar:
```jsx
<IconButton size="small" onClick={() => setCompact(!compact)}>
  <UnfoldLessIcon fontSize="small" />
</IconButton>
```

When `compact` is on, or when **`maxColSize > 8`** (MHF v2 §4H —
column-height heuristic; better signal than total-node count because
visual overflow depends on the tallest column, not the graph size),
leaf nodes render as 32×32 px squares with status icon only (no label,
no sparkline, no live-token bubble). Hover reveals a tooltip with full
label. Saves ~50% vertical space for high-N graphs. Independent of
drill-in.

Concrete formula in `computeLayout()`:

```javascript
const maxColSize = Math.max(...columns.map(c => c.length));
const compact = userCompactToggle || maxColSize > 8;
const nodeH = compact ? 38 : 64;
const nodeW = compact ? 140 : 160;
const rowGap = compact ?  6 : 12;
```

This is materially better than `nodes.length > 15`: a 50-node graph
shaped 10 wide × 5 deep stays roomy in non-compact mode; a 12-node
graph stacked 12-deep correctly triggers compact mode.

#### 3.7.3.7 Dynamic panel height (NEW, §3.7 addition)

Replace `maxHeight: '40%'` in `TaskPanel.js` with MHF's ladder:
```js
const graphMaxHeight = useMemo(() => {
  if (graphCollapsed) return 40;
  const count = currentGraph?.nodes?.length || 0;
  if (count <= 5) return '30%';
  if (count <= 10) return '40%';
  if (count <= 20) return '50%';
  return '55%';
}, [graphCollapsed, currentGraph?.nodes?.length]);
```

### 3.7.4 New file changes (delta on top of Appendix A)

- `src/openteam/server/routes/manager_websocket_routes.py`
  - Add `/`-prefix slash-command intercept gated by `OPENTEAM_DEV_MODE`
    + `agent_enabled:false` (3.7.3.5).
- DELETE planned `src/openteam/server/api/dev_tools_routes.py` from
  Appendix A — superseded by 3.7.3.5.
- DELETE planned `src/openteam/ui/src/hooks/useDevTools.js` from
  Appendix A — slash autocomplete handled directly in `ChatInput.js`
  using a tool-registry list fetched once at session start (or hard-coded
  for the dev-only commands).

### 3.7.5 Anti-patterns (added to §3.6.9)

11. **DO NOT skip `OPENTEAM_DEV_MODE` env gate** even though
    `agent_enabled:false` exists. The substring intercept fires before
    tool registry is consulted; without the env gate, a user typing
    `/mock_task` in production triggers the parser, which is wasted CPU
    and a vector for log/error noise.
12. **DO NOT track animation direction in imperative state** — derive
    via `useRef(previousGraphPath)` + `useEffect`. Imperative-state
    approach (MHF 197–209) is racy on fast clicks.

### 3.7.6 v0 / v1 shipping schedule (replaces §7 — see also §7 update)

**v0 — "Visualization works for compositions, no library deps" (5.5 days)**

- Phase 1 (Python: hierarchical reporter + namespacing + role_setup wiring) — 1 day
- Phase 1.4 (WS error handling) — included
- §3.6 mock_task FIRST (flat-only initial; nested after Phase 1 lands; WS-intercept slash command gated by OPENTEAM_DEV_MODE) — 2 days
- §3.7.3.5 slash-command intercept + autocomplete — 0.25 day
- v0 drill-in UX (MHF-style canvas-remount with CSS keyframe) — 1 day
- §3.5.7 strict side-panel rules — 0.25 day
- §3.7.3.6 compact mode + §3.7.3.7 dynamic height — 0.25 day
- §3.5.8 persisted state with orphan cleanup — 0.25 day
- §3.5.9 keyboard shortcuts (Esc/Space/arrows/?) — 0.25 day
- Phase 3 throttle + bounded buffers + batching — 0.25 day

**v1 — "Polished single-canvas zoom UX" (+3 days, on top of v0)**

- Migrate `<GraphFlowView>` to React Flow + dagre — 1 day
- §3.5.2 focus-zoom animation via `setViewport` — 0.5 day
- §3.5.6 ghost outer context + minimap — 0.5 day
- §3.5.5 live-token bubbles + edge traversal shimmer — 0.5 day
- §3.5.13 a11y pass + `prefers-reduced-motion` — 0.25 day
- §3.5.14 perf budget verification + tuning — 0.25 day

**v2 — "Generalisation + Container Output" (+2 days, on top of v1)**

- §3.5.4 Container Output toggle UI — 0.25 day
- ~~§3.5.10 Python stream routing~~ — **0 d (OBSOLETE — already implemented)**
- ~~Phase 4 non-BTA inferencer wiring~~ — **DROPPED (they use Workflow, not WorkGraph)**
- Phase 5 polish (search, layout direction toggle, jump-to-running, per-group concurrency badge) — 0.5 day
- `--assert-event-parity` flag — 0.25 day

**Total spread**: v0 ships in ~1 week of dev time and gives the user
working drill-in for `test_role_setup.py`. v1 polishes the UX. v2
generalises and adds the deeper functionality. Each version is
independently shippable.


---

## 3.5.18 Concrete Code Reference (v0 implementation)

This subsection provides copy-pasteable code for the v0 drill-in
implementation (no React Flow), inspired by MHF's concrete-snippet
style but folding in the §3.5/§3.7 design corrections (orthogonal modes,
orphan cleanup, race-safe direction tracking, side-panel rules,
keyboard handling).

### 3.5.18.1 `useGraphState.js` — full hook (NEW file)

```js
// src/openteam/ui/src/hooks/useGraphState.js
import { useState, useMemo, useRef, useCallback, useEffect } from 'react';

const STREAM_CAP_BYTES = 200_000;     // §3.7 + Phase 2.2 #3
const STREAM_TRIM_BYTES = 50_000;     // drop oldest 50 KB when over cap
const RAF_BATCH_MS = 16;              // batch state updates per frame

/**
 * Centralised graph navigation + event-handling state.
 * Drop-in replacement for the inline graph cases in useManagerChat.
 *
 * Returns:
 *   {tasks, setTasks, graphPath, setGraphPath, navUp, navTo,
 *    selectedLeafId, selectLeaf, currentGraph, breadcrumb,
 *    expandableNodeIds, isContainer, containerView, setContainerView,
 *    transitionDirection, handleGraphEvent}
 */
export function useGraphState() {
  const [tasks, setTasks] = useState({});
  const [graphPath, _setGraphPath] = useState([]);
  const [selectedLeafId, setSelectedLeafId] = useState(null);
  const [containerView, setContainerView] = useState({});  // {[containerId]: 'graph'|'output'}

  // §3.7.5 anti-pattern #12: derive direction via ref, not imperative state
  const prevPathRef = useRef([]);
  const [transitionDirection, setTransitionDirection] = useState('in');

  const setGraphPath = useCallback((newPath) => {
    const prev = prevPathRef.current;
    setTransitionDirection(newPath.length > prev.length ? 'in' : 'out');
    prevPathRef.current = newPath;
    _setGraphPath(newPath);
  }, []);

  const navUp = useCallback(() => {
    if (graphPath.length > 0) setGraphPath(graphPath.slice(0, -1));
  }, [graphPath, setGraphPath]);

  const navTo = useCallback((depth) => {
    setGraphPath(graphPath.slice(0, depth));
  }, [graphPath, setGraphPath]);

  // §3.5.7: leaf click opens side panel; orthogonal to canvas focus
  const selectLeaf = useCallback((nodeId) => {
    setSelectedLeafId((cur) => (cur === nodeId ? null : nodeId));
  }, []);

  // RAF-batched setTasks (§3.5/§3.7 reliability — Phase 2.2 #4)
  const pendingUpdatesRef = useRef([]);
  const rafRef = useRef(null);
  const enqueueTaskUpdate = useCallback((updater) => {
    pendingUpdatesRef.current.push(updater);
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      const updates = pendingUpdatesRef.current;
      pendingUpdatesRef.current = [];
      rafRef.current = null;
      setTasks((prev) => updates.reduce((acc, u) => u(acc), prev));
    });
  }, []);

  // ---- Event handlers (called by useManagerChat for each WS message) ----

  // §13-r7-#5 race buffer (declared FIRST so handleGraphTopology can
  // reference _replayPendingStatusFor in its closure / deps).
  const pendingStatusByParentRef = useRef({});
  const PENDING_CAP = 200;

  const _applyStatusToTask = useCallback((task, evt) => {
    if (!task) return null;
    // §READ-FIRST R-3: server sends ONE timestamp; derive started/completed
    // §READ-FIRST R-5: NO leaf-id fallback — would cause collisions across BTAs
    const ts = evt.timestamp ?? Date.now() / 1000;
    const updateInGraph = (graph) => {
      if (!graph) return graph;
      // The graph stores nodes with their LOCAL id (e.g. "worker_3"),
      // not the qualified id ("worker_2/worker_3"). Strip the parent
      // prefix to find the right node within this specific sub-graph.
      const segments = evt.node_id.split('/');
      const localId = segments[segments.length - 1];
      const idx = graph.nodes.findIndex(n => n.id === localId);
      if (idx < 0) return graph;
      const oldNode = graph.nodes[idx];
      const newNodes = [...graph.nodes];
      newNodes[idx] = {
        ...oldNode,
        status: evt.status,
        startedAt: evt.status === 'running'
                   ? (oldNode.startedAt ?? ts)
                   : oldNode.startedAt,
        completedAt: (evt.status === 'completed' || evt.status === 'error')
                   ? ts
                   : oldNode.completedAt,
        error: evt.error,
        outputPath: evt.output_path,
      };
      return { ...graph, nodes: newNodes };
    };
    const segments = evt.node_id.split('/');
    if (segments.length === 1) {
      // Root-graph node — apply to task.graph
      return { ...task, graph: updateInGraph(task.graph) };
    }
    // Sub-graph node — find the exact owning sub-graph by full parent path
    const parentKey = segments.slice(0, -1).join('/');
    const subGraphs = { ...(task.subGraphs || {}) };
    if (subGraphs[parentKey]) {
      subGraphs[parentKey] = updateInGraph(subGraphs[parentKey]);
      return { ...task, subGraphs };
    }
    return null;     // sub-graph topology not yet arrived; caller buffers
  }, []);

  const _replayPendingStatusFor = useCallback((tid, parentKey) => {
    const bucketKey = `${tid}::${parentKey}`;
    const bucket = pendingStatusByParentRef.current[bucketKey];
    if (!bucket || bucket.length === 0) return;
    delete pendingStatusByParentRef.current[bucketKey];
    enqueueTaskUpdate((prev) => {
      let task = prev[tid];
      for (const evt of bucket) {
        const updated = _applyStatusToTask(task, evt);
        if (updated) task = updated;
      }
      return { ...prev, [tid]: task };
    });
  }, [enqueueTaskUpdate, _applyStatusToTask]);

  /**
   * Handle graph_topology event.
   * Branches on parent_node_id (empty = root, non-empty = sub-graph).
   *
   * §3.7.3.3 / §13-r7-#2 — On a ROOT topology emission (rerun), we
   * MUST reset:
   *   1) tasks[tid].graph + subGraphs (inside enqueueTaskUpdate)
   *   2) graphPath = []                 (separate hook)
   *   3) selectedLeafId = null          (separate hook)
   * The hook resets cannot live inside enqueueTaskUpdate because
   * `setGraphPath` and `setSelectedLeafId` are different React state
   * hooks. Without resetting, the UI remains focused on stale
   * subgraph paths after a rerun.
   */
  const handleGraphTopology = useCallback((tid, evt) => {
    const isRoot = !evt.parent_node_id;

    if (isRoot) {
      // §READ-FIRST R-6: ROOT topology must be applied SYNCHRONOUSLY
      // (not via RAF batching) so that graphPath/selectedLeafId resets
      // are atomic with the new graph data. Otherwise there's a 1-frame
      // window where graphPath=[] applies to the OLD tasks state and
      // any derived selectors (breadcrumb, expandableNodeIds) flash
      // incorrect values.
      setTasks((prev) => {
        const task = prev[tid] || {};
        const validIds = new Set(evt.nodes.map(n => n.id));
        const cleanedStreams = Object.fromEntries(
          Object.entries(task.nodeStreams || {})
            .filter(([k]) => validIds.has(k.split('/')[0]))
        );
        return {
          ...prev,
          [tid]: {
            ...task,
            graph: {
              nodes: evt.nodes,
              edges: evt.edges,
              layout: evt.layout || 'horizontal',
              version: (task.graph?.version || 0) + 1,
            },
            subGraphs: {},
            nodeStreams: cleanedStreams,
          },
        };
      });
      // R-11 per-task state: pass tid into the helpers
      setGraphPath(tid, []);
      setSelectedLeafId(tid, null);
      // Drop ALL buffered status events for this task — they're for the old graph
      Object.keys(pendingStatusByParentRef.current).forEach((k) => {
        if (k.startsWith(`${tid}::`)) delete pendingStatusByParentRef.current[k];
      });
      return;
    }

    // Sub-graph topology: defer via RAF batching (no navigation reset
    // → no atomicity concern with the navigation hooks).
    enqueueTaskUpdate((prev) => {
      const task = prev[tid] || {};
      const subGraphs = { ...(task.subGraphs || {}) };
      subGraphs[evt.parent_node_id] = {
        nodes: evt.nodes,
        edges: evt.edges,
        layout: evt.layout || 'horizontal',
      };
      return { ...prev, [tid]: { ...task, subGraphs } };
    });
    // §13-r7-#5: replay buffered status events for this sub-graph now
    // that its topology has arrived.
    _replayPendingStatusFor(tid, evt.parent_node_id);
  }, [setTasks, enqueueTaskUpdate, setGraphPath, setSelectedLeafId, _replayPendingStatusFor]);

  const handleNodeStatus = useCallback((tid, evt) => {
    enqueueTaskUpdate((prev) => {
      const task = prev[tid];
      const updated = _applyStatusToTask(task, evt);
      if (updated) return { ...prev, [tid]: updated };
      // §13-r7-#5: sub-graph not yet present → buffer for replay when
      // the sub-graph topology arrives. Capped at 200 per bucket.
      const segments = evt.node_id.split('/');
      const parentKey = segments.slice(0, -1).join('/');
      const bucketKey = `${tid}::${parentKey}`;
      const bucket = pendingStatusByParentRef.current[bucketKey] || [];
      if (bucket.length < PENDING_CAP) {
        pendingStatusByParentRef.current[bucketKey] = [...bucket, evt];
      }
      return prev;
    });
  }, [enqueueTaskUpdate, _applyStatusToTask]);

  const handleNodeStream = useCallback((tid, evt) => {
    enqueueTaskUpdate((prev) => {
      const task = prev[tid] || {};
      const streams = { ...(task.nodeStreams || {}) };
      const cur = streams[evt.node_id] || '';
      let next = cur + evt.content;
      // Bounded buffer (§3.5/§3.7)
      if (next.length > STREAM_CAP_BYTES) {
        next = next.slice(next.length - (STREAM_CAP_BYTES - STREAM_TRIM_BYTES));
      }
      streams[evt.node_id] = next;
      return { ...prev, [tid]: { ...task, nodeStreams: streams } };
    });
  }, [enqueueTaskUpdate]);

  /** Single dispatch used by useManagerChat. */
  const handleGraphEvent = useCallback((tid, msg) => {
    switch (msg.type) {
      case 'graph_topology': handleGraphTopology(tid, msg); break;
      case 'node_status':    handleNodeStatus(tid, msg);    break;
      case 'node_stream':    handleNodeStream(tid, msg);    break;
    }
  }, [handleGraphTopology, handleNodeStatus, handleNodeStream]);

  // ---- Derived state (§3.7.2.3 — derive everything from graphPath) ----

  // Pick the active task — caller passes tid; we expose helpers
  const getDerivedFor = useCallback((tid) => {
    const task = tasks[tid];
    if (!task) return null;
    const currentGraph = graphPath.length === 0
      ? task.graph
      : (task.subGraphs?.[graphPath.join('/')] || null);

    const breadcrumb = (() => {
      const labels = [{ label: 'Pipeline', depth: 0 }];
      let g = task.graph;
      for (let i = 0; i < graphPath.length; i++) {
        const id = graphPath[i];
        const node = g?.nodes?.find(n => n.id === id);
        labels.push({ label: node?.label || node?._viz_label || id, depth: i + 1 });
        const key = graphPath.slice(0, i + 1).join('/');
        g = task.subGraphs?.[key] || null;
      }
      return labels;
    })();

    // §3.7 idea #4: derive expandableNodeIds from subGraphs keys
    const expandableNodeIds = (() => {
      const out = new Set();
      const prefix = graphPath.length > 0 ? graphPath.join('/') + '/' : '';
      for (const key of Object.keys(task.subGraphs || {})) {
        if (key.startsWith(prefix)) {
          const remainder = key.substring(prefix.length);
          if (remainder && !remainder.includes('/')) out.add(remainder);
        }
      }
      return out;
    })();

    // Stream key for side panel (any depth)
    const nodeStreamKey = selectedLeafId
      ? (graphPath.length > 0 ? graphPath.join('/') + '/' + selectedLeafId : selectedLeafId)
      : null;

    return {
      task, currentGraph, breadcrumb, expandableNodeIds,
      isContainer: (id) => expandableNodeIds.has(id),
      nodeContent: nodeStreamKey ? (task.nodeStreams?.[nodeStreamKey] || '') : '',
      nodeStreamKey,
    };
  }, [tasks, graphPath, selectedLeafId]);

  return {
    tasks, setTasks,
    graphPath, setGraphPath, navUp, navTo,
    selectedLeafId, selectLeaf, setSelectedLeafId,
    containerView, setContainerView,
    transitionDirection,
    handleGraphEvent,
    getDerivedFor,
  };
}
```

### 3.5.18.2 `TaskPanel.js` — drill-in & breadcrumb wiring

```jsx
// src/openteam/ui/src/components/chat/TaskPanel.js (relevant additions)
import { useEffect } from 'react';

export function TaskPanel({ tid, derived, graphState }) {
  const { task, currentGraph, breadcrumb, expandableNodeIds, isContainer,
          nodeContent, nodeStreamKey } = derived;
  const { graphPath, setGraphPath, navUp, navTo,
          selectedLeafId, selectLeaf, transitionDirection } = graphState;

  // §3.5.9 Esc handling — derived priority chain
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (helpOpen) { setHelpOpen(false); return; }
        if (selectedLeafId) { selectLeaf(null); return; }
        if (graphPath.length > 0) { navUp(); return; }
      }
      if (e.key === ' ' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault(); fitToView();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [helpOpen, selectedLeafId, graphPath, navUp, selectLeaf]);

  // Node click router
  const onNodeClick = (id) => {
    if (isContainer(id)) {
      // §3.5.1 / §3.5.7: container click = drill in (focus zoom)
      setGraphPath([...graphPath, id]);
    } else {
      // Leaf click = side panel selection (orthogonal)
      selectLeaf(id);
    }
  };

  // §3.7.3.7 Dynamic graph panel height
  const graphMaxHeight = useMemo(() => {
    const count = currentGraph?.nodes?.length || 0;
    if (graphCollapsed) return 40;
    if (count <= 5)  return '30%';
    if (count <= 10) return '40%';
    if (count <= 20) return '50%';
    return '55%';
  }, [graphCollapsed, currentGraph?.nodes?.length]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* §3.5.3 Breadcrumb (always visible) */}
      <Breadcrumb crumbs={breadcrumb} onNavigate={(depth) => navTo(depth)} />

      {/* Animated drill-in container (v0: CSS keyframe; v1: React Flow setViewport) */}
      <Box
        key={graphPath.join('/') || 'root'}
        sx={{
          maxHeight: graphMaxHeight,
          flexShrink: 0,
          // §3.7.2.1 v0 animation strategy
          animation: !prefersReducedMotion
            ? `${transitionDirection === 'in' ? 'graphDrillIn' : 'graphZoomOut'} 0.3s cubic-bezier(0.4, 0, 0.2, 1)`
            : 'none',
          '@keyframes graphDrillIn': {
            from: { opacity: 0, transform: 'scale(1.05) translateY(-8px)' },
            to:   { opacity: 1, transform: 'scale(1) translateY(0)' },
          },
          '@keyframes graphZoomOut': {
            from: { opacity: 0, transform: 'scale(0.92) translateY(8px)' },
            to:   { opacity: 1, transform: 'scale(1) translateY(0)' },
          },
        }}
      >
        {currentGraph ? (
          <GraphFlowView
            graph={currentGraph}
            expandableNodeIds={expandableNodeIds}
            selectedNodeId={selectedLeafId}
            /* §READ-FIRST R-4: compact mode is decided INSIDE GraphFlowView
             * (or its useGraphLayout hook), based on column-height of the
             * BFS layout — not from a server field. TaskPanel just passes
             * the user toggle and lets the component compute the rest. */
            userCompact={userCompactToggle}
            onNodeClick={onNodeClick}
          />
        ) : (
          <Placeholder text="Waiting for inner pipeline..." />
        )}
      </Box>

      {/* Side panel (§3.5.7 orthogonal) */}
      {selectedLeafId && !isContainer(selectedLeafId) && (
        <NodeDetailPanel
          nodeId={selectedLeafId}
          streamKey={nodeStreamKey}
          content={nodeContent}
          onClose={() => selectLeaf(null)}
        />
      )}
    </Box>
  );
}
```

### 3.5.18.3 `Breadcrumb.js` — clickable hierarchy (NEW file)

```jsx
// src/openteam/ui/src/components/chat/Breadcrumb.js
import { Breadcrumbs, Link, Typography } from '@mui/material';

export function Breadcrumb({ crumbs, onNavigate }) {
  return (
    <Breadcrumbs sx={{ px: 2, py: 1, fontSize: 13 }} separator="›" maxItems={5}>
      {crumbs.map((c, i) =>
        i === crumbs.length - 1
          ? <Typography key={i} fontSize={13}>{truncate(c.label, 24)}</Typography>
          : <Link key={i} component="button" onClick={() => onNavigate(c.depth)}
                  underline="hover" fontSize={13}>{truncate(c.label, 24)}</Link>
      )}
    </Breadcrumbs>
  );
}
const truncate = (s, n) => s.length > n ? s.slice(0, n - 1) + '…' : s;
```

### 3.5.18.4 `GraphFlowView.js` — incremental v0 changes (no library swap)

Keep the existing custom SVG layout. Add only:

```jsx
// 1. expandable node indicator (small AccountTreeIcon top-right)
{expandableNodeIds.has(node.id) && (
  <AccountTreeIcon sx={{ position: 'absolute', top: 2, right: 2, fontSize: 12, opacity: 0.7 }} />
)}

// 2. compact mode (32×32 squares, status icon only)
const renderNodeBody = compact
  ? <StatusDot status={node.status} sx={{ width: 16, height: 16 }} />
  : <FullNodeBody node={node} />;

// 3. fit-to-view button (toolbar)
const fitToView = useCallback(() => {
  const cW = containerRef.current?.clientWidth || 800;
  const cH = containerRef.current?.clientHeight || 400;
  // §3.7.1 reject MHF's 1.0 cap; allow zoom in
  const fitZoom = Math.min(cW / totalW, cH / totalH, 2.0);
  setZoom(fitZoom);
  setPan({ x: 0, y: 0 });
}, [totalW, totalH]);

// 4. zoom/pan via wheel + drag (MHF 2E pattern, kept intact)
```

### 3.5.18.5 Server: WS slash-command intercept (§3.7.3.5)

```python
# src/openteam/server/routes/manager_websocket_routes.py — additions
import os, uuid, asyncio, shlex
from agent_foundation.resources.tools.registry import load_all_tools

_TOOLS = None
def _registry():
    global _TOOLS
    if _TOOLS is None:
        _TOOLS = load_all_tools(extra_dirs=[Path(__file__).parent.parent / "resources" / "tools"])
    return _TOOLS

async def process_message(sid: str, text: str) -> None:
    text = text.strip()
    if (text.startswith("/")
            and os.environ.get("OPENTEAM_DEV_MODE") == "1"):
        cmd_line = text[1:]
        try:
            argv = shlex.split(cmd_line)
        except ValueError:
            argv = cmd_line.split()
        if not argv:
            return
        cmd = argv[0]
        tool = _registry().get(cmd)
        if tool is not None and tool.agent_enabled is False:
            args = parse_cli_args(argv[1:], tool.parameters)
            task_id = f"dev-{cmd}-{uuid.uuid4().hex[:8]}"
            interactive = WebSocketInteractive(send_safe, asyncio.Queue())
            await send_safe({"type": "task_status", "task_id": task_id,
                             "tool_name": cmd, "status": "running",
                             "label": f"[DEV] /{cmd}"})
            asyncio.create_task(
                tool_dispatcher.execute(
                    tool_name=cmd, arguments=args,
                    session_context={"interactive": interactive,
                                     "task_id": task_id})
            )
            return  # DO NOT fall through to conversation flow
    # ... existing conversation flow ...
```

### 3.5.18.6 Mock components (§3.6.3 — concrete)

```python
# src/agent_foundation/common/inferencers/mock_inferencers/mock_bta_components.py
import asyncio, json
from typing import Any

class MockBreakdownInferencer:
    def __init__(self, *, subtasks: list[dict], delay_s: float = 1.5,
                 stream_chunks: list[str] | None = None):
        self.subtasks = subtasks
        self.delay_s = delay_s
        self.stream_chunks = stream_chunks or [
            "Analyzing input...\n",
            "Identifying subtasks...\n",
            f"Found {len(subtasks)} subtasks.\n",
        ]
        self.stream_observer = None  # set by parent BTA

    async def ainfer(self, *args, **kwargs):
        per = self.delay_s / max(1, len(self.stream_chunks))
        for c in self.stream_chunks:
            await asyncio.sleep(per)
            if self.stream_observer:
                await self.stream_observer(c)        # §13.3: callable, not .emit()
        # §13.11: flush trailing batch so the last few tokens aren't dropped
        if self.stream_observer and hasattr(self.stream_observer, 'flush'):
            await self.stream_observer.flush()
        return json.dumps(self.subtasks)

class MockWorker:
    def __init__(self, *, label: str = "worker", duration_s: float = 1.5,
                 stream_chunks: list[str] | None = None,
                 should_error: bool = False, output: str = ""):
        self.label = label
        self.duration_s = duration_s
        self.stream_chunks = stream_chunks or [
            f"## {label}\n", "Researching...\n",
            "### Findings\n", f"- Result for {label}\n",
        ]
        self.should_error = should_error
        self.output = output or f"[mock output for {label}]"
        self.stream_observer = None
        self.interactive = None
        self._graph_event_callback = None

    async def ainfer(self, *args, **kwargs):
        per = self.duration_s / max(1, len(self.stream_chunks) + 1)
        for c in self.stream_chunks:
            await asyncio.sleep(per)
            if self.stream_observer:
                await self.stream_observer(c)        # §13.3
        await asyncio.sleep(per)
        if self.stream_observer and hasattr(self.stream_observer, 'flush'):
            await self.stream_observer.flush()      # §13.11
        if self.should_error:
            raise RuntimeError(f"[mock error in {self.label}]")
        return self.output

class MockAggregator:
    def __init__(self, *, delay_s: float = 1.0,
                 output_template: str = "[mock aggregated output]"):
        self.delay_s = delay_s
        self.output_template = output_template
        self.stream_observer = None
    async def ainfer(self, *args, **kwargs):
        chunks = ["Synthesizing...\n", "Compiling final report...\n"]
        per = self.delay_s / len(chunks)
        for c in chunks:
            await asyncio.sleep(per)
            if self.stream_observer:
                await self.stream_observer(c)        # §13.3
        if self.stream_observer and hasattr(self.stream_observer, 'flush'):
            await self.stream_observer.flush()      # §13.11
        return self.output_template
```



---

## Audit History (§11–§16)

> Sections §11 (MHF comparison), §12 (MHF v2 integrations), §13 (r6
> corrections), §14 (r7 corrections), §15 (r8 consolidation record),
> and §16 (r9 refinements) have been extracted to
> [`plan_complex_graph_visualization_audit_history.md`](plan_complex_graph_visualization_audit_history.md)
> during r10 consolidation (2026-04-20).
>
> All corrections from those sections have been folded into the body
> above. The audit file is for decision-tracing only.
