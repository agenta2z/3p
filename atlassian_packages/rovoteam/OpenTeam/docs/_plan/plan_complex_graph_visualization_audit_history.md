# Audit History — Complex Graph Visualization Plan

> **Extracted from `plan_complex_graph_visualization.md` during r10
> consolidation (2026-04-20).** Contains §11-§16: MHF comparison,
> MHF v2 integrations, and correction rounds r6-r9. These sections
> are preserved for institutional knowledge and decision auditing
> but are no longer needed for implementation. The canonical plan
> file has all corrections folded in-place.
>
> **Numbering note**: Section numbers continue from the main plan
> (§10 is the last section there). References like "R-1"..."R-14"
> point to the READ-FIRST block in the main plan. References like
> "§13-r7-#5" mean "this file's §13, from revision round r7, item #5".

---

## 11. Archived: Side-by-side comparison with MHF (`memoized-hugging-firefly.md`)

This section preserves the comparison performed during r4 integration so
future readers can audit the adopt/reject decisions in §3.7.

### 11.1 What the two plans agree on (validation by independent convergence)

| Topic | Both plans say |
|---|---|
| Architectural primitive for nested visualization | `parent_node_id` field on `GraphTopologyEvent` |
| Reporter wrapping mechanism | A `ChildGraphReporter` / `NamespacedGraphReporter` that prefixes node ids with `parent_id/` |
| Composition propagation | Outer BTA's worker_factory must pass a child reporter to each inner BTA |
| Generic over BTA-specific | `hasattr(worker, 'graph_reporter')` duck-typing |
| Single-direction id paths | `inner_bta_2/worker_3` (slash-separated; flat strings) |
| `role_setup` is currently silent | Confirmed by both: missing `WebSocketGraphReporter` wiring in executor |
| 20+ workers overflow the current panel | Yes — both plans cite the math |
| Drill-down / breadcrumb / animations are needed | Yes (different implementations) |

The independent convergence on these points raises confidence that the
core architecture is correct.

### 11.2 Where the two plans differ (and what we adopted)

| Topic | MHF | This plan (r1–r3) | r4 decision |
|---|---|---|---|
| UI library | Keep custom SVG | Migrate to React Flow + dagre | **Both** — custom in v0 (MHF style); React Flow in v1 (this plan) |
| Drill-in animation | CSS keyframe + `key`-remount | React Flow `setViewport({duration: 600})` | **Both** — keyframe in v0; setViewport in v1 |
| Outer-context preservation | Replaced canvas (lost) | Ghost outlines + minimap | **Mine** for v1; v0 accepts MHF's loss as tradeoff for shipping |
| Slash command transport | WS message intercept | HTTP `/api/dev_tools/*` | **MHF** — simpler, reuses session |
| Slash command production safety | None | `OPENTEAM_DEV_MODE` env gate | **Mine** added |
| Tool dispatch | Bypassed for `/mock_task` | Reuses tool_dispatcher | **Mine** — exercise shared infra |
| `/mock_task` args | Numeric (`--workers --inner --delay`) | Profile YAMLs | **Both** — numeric for sweeps; YAML for `role_setup` mirroring |
| Navigation state model | `graphPath: string[]` | `focusPath` + others | **MHF** — simpler primitive; orthogonal panels remain |
| Animation direction tracking | Imperative state set before nav | Derived from `useRef` + `useEffect` | **Mine** — race-safe |
| `expandableNodeIds` derivation | Helper from `subGraphs` keys | Implicit | **MHF** — cleaner |
| Compact mode for high-N | Standalone toggle | Implicit in live overlays | **MHF** — discrete graceful degradation |
| Dynamic graph panel height | Ladder formula | Handwave fit-to-view | **MHF** — pragmatic |
| Generalisation to non-BTA inferencers | Not addressed | Phase 4 (Linear/Dual/Reflective/PlanThenImplement) | **Mine** kept in v2 |
| Container Output mode | Not addressed | §3.5.4 + §3.5.10 routing | **Mine** kept in v2 |
| Streaming throttle / WS error handling | Not addressed | Phase 3 + Phase 1.4 | **Mine** kept in v0 |
| Bounded stream buffers | Acknowledged; no enforcement | Hard 200 KB cap with rolling trim | **Mine** kept in v0 |
| A11y / `prefers-reduced-motion` | Not addressed | §3.5.13 | **Mine** kept in v1 |
| Performance budgets | Not addressed | §3.5.14 (60 fps idle, 30 fps under flurry) | **Mine** kept in v1 |
| Per-phase acceptance criteria | One global verification list | Per-section criteria | **Mine** kept |
| Concrete copy-pasteable code | Yes (full JSX/JS blocks) | Higher-level pseudocode | **Both** — §3.5.18 is now concrete; design rationale stays in §3.5 |
| Recommended build order | Mock first, decisive | "Parallel with Phase 1" | **MHF** — adopted in §7.6 |
| Bug: `fitToView` capped at zoom 1.0 | Yes (off-by-design) | n/a | **Mine** — fix in §3.5.18.4 |
| Bug: rerun does NOT clear `nodeStreams` orphans | Yes (memory leak) | n/a | **Mine** — fix in §3.7.3.3 + §3.5.18.1 |

### 11.3 Issues found in MHF that r4 fixes

1. `fitToView` formula caps zoom at 1.0 — small graphs cannot magnify.
   Fixed in §3.5.18.4 (cap at 2.0; remove unconditional 1.0 floor).
2. `transitionDirection` set imperatively before nav — racy on fast
   clicks. Fixed in §3.5.18.1 (derived via `useRef(prevPath)`).
3. WS slash intercept ungated — production safety footgun. Fixed in
   §3.7.3.5 (added `OPENTEAM_DEV_MODE` env gate + tool dispatcher
   routing).
4. Rerun edge case clears `subGraphs` but not orphaned `nodeStreams`
   keys. Fixed in §3.7.3.3 + §3.5.18.1 root-topology handler.
5. No bounded stream buffer — long-running CLI workers can OOM the
   browser. Fixed in §3.5.18.1 (hard 200 KB cap with 50 KB tail-trim).
6. No `prefers-reduced-motion` opt-out. Fixed in §3.5.18.2 conditional
   animation block + §3.5.13 a11y pass.
7. No story for non-BTA inferencers. Kept Phase 4.
8. Container nodes have nothing meaningful to show in side panel. Kept
   §3.5.4 + §3.5.10 (Container Output mode + Python stream routing).

### 11.4 Issues in r1–r3 that MHF integration fixed

1. Verbose architectural pseudocode without concrete React snippets —
   high implementation ambiguity. Fixed in §3.5.18 (full JSX reference).
2. Three navigation primitives (`focusPath`, `selectedLeafId`,
   `containerView`) when one (`graphPath`) suffices for canvas
   navigation. Simplified in §3.7.2.3.
3. Indecisive build order ("in parallel with Phase 1"). Fixed in §7.5
   (mock-first; concrete day-by-day sequencing).
4. No fallback path when React Flow migration is risky — committed to
   the dependency upfront. Fixed in §3.7.2.1 (v0 = MHF style; v1 =
   React Flow).
5. No standalone graceful-degradation for high-N graphs (compact mode
   was rolled into the larger drill-in story). Fixed in §3.7.3.6.
6. No dynamic panel height — relied entirely on user-driven fit-view.
   Fixed in §3.7.3.7 (MHF's ladder).

### 11.5 Net result

After integration, the canonical plan:

- Has **MHF's pragmatism** in v0 (no library deps, ships in ~1 week,
  drill-in works for `test_role_setup.py`).
- Has **this plan's depth** in v1/v2 (single-canvas zoom, ghost
  context, Container Output, generalisation to non-BTA inferencers,
  reliability + a11y + perf budgets).
- Has **27 atomic effort items** with explicit owners and dependencies
  (§7.1–7.3) — no handwaving.
- Has **concrete copy-pasteable code** for the most error-prone parts
  (event dispatch, RAF batching, derived state, animation direction
  tracking, slash intercept) (§3.5.18).
- **MHF the document is now retired**; this canonical plan covers
  everything MHF proposed plus everything that was missing from MHF.


---

## 12. MHF v2 Integrations (r5) — additional items adopted

After re-reading MHF v2 (the upgraded "Integrated" 584-line version) in
full, this section integrates the 7 remaining MHF items that mine
either lacked or expressed less precisely. Items are ordered by the
existing section they augment (not by ROI — see §3.7.0 for ROI order).

### 12.1 Augments §3.6.0 — "Why Real BTA + Mock Inferencers" rationale paragraph

MHF v2 §2F packs the rationale into 5 tight bullets. Adopt verbatim
into our §3.6 as a quick-reference paragraph:

> **Why Real BTA + Mock Inferencers (vs. direct event emission)**
>
> - Exercises `_build_diamond_graph`, `_emit_pending_graph_topology`,
>   `set_graph_event_callback`, `ChildGraphReporter` propagation —
>   the exact code paths that need to work in production.
> - Events are **structurally identical** to real runs (not hand-crafted),
>   so `/mock_task` validates the entire event-protocol surface area.
> - Catches BTA wiring bugs that direct event emission would miss
>   (e.g., a forgotten `child_reporter` propagation in
>   `_build_diamond_graph` would silently break the mock just like it
>   would break real runs — visible immediately).
> - YAML profiles are declarative and extensible (add new profiles
>   without code changes).
> - Same invocation pattern as real tools: `tool.json` + `executor.py`
>   + `ToolDispatcher` — no parallel infrastructure to maintain.

### 12.2 Augments §3.5.18.1 — `expandableNodeIds` direct-children-only filter

The implementation is correct in §3.5.18.1 but the *reason for the
`!remainder.includes('/')` check* is not explained. Add this note:

> The `!remainder.includes('/')` filter is critical: it limits
> `expandableNodeIds` to **direct children** of the current `graphPath`,
> excluding grandchildren. Without it, a 3-level composition
> (`outer/inner_bta_2/worker_3` is also a sub-graph) would mark
> `inner_bta_2` AND `worker_3` as both expandable from the root view —
> wrong, because at root depth only first-level containers
> (`inner_bta_2`) should be drillable. Drilling further requires
> *first* navigating into `inner_bta_2`, *then* `worker_3` becomes
> expandable.

### 12.3 Augments §3.5.18.4 — concrete container-node visual spec

MHF v2 §4F gives a precise spec for how container nodes render. Adopt:

> Container nodes in `GraphFlowView.js` render with three distinguishing
> elements:
>
> 1. **`AccountTreeIcon`** in the top-right corner of the node, 12 px,
>    `opacity: 0.7`. Signals "this node has a sub-graph".
> 2. **Mini progress badge** below the label: `3/5 done` (or `3/5 ⚙ 1`
>    when at least one child is currently running). Computed from the
>    container's `subGraphs[id].nodes` status counts.
> 3. **`cursor: pointer`** + subtle hover background highlight to
>    cue clickability for drill-down.
>
> Implementation outline:
>
> ```jsx
> {expandableNodeIds.has(node.id) && (
>   <>
>     <AccountTreeIcon sx={{
>       position: 'absolute', top: 2, right: 2,
>       fontSize: 12, opacity: 0.7,
>     }} />
>     <Box sx={{ fontSize: 10, opacity: 0.7, mt: 0.25 }}>
>       {miniProgress(task.subGraphs[node.id])}
>     </Box>
>   </>
> )}
> ```
>
> where `miniProgress(subGraph)` returns `"3/5 done"` (or
> `"3/5 done · ⚙ 1"` when running > 0).

### 12.4 Augments §3.5.18.4 — explicit zoom-reset rules

MHF v2 §4E pins three zoom/pan reset rules I had only handwaved.
Adopt verbatim:

> **Zoom/pan reset rules** (in `GraphFlowView.js`):
>
> 1. **Auto-fit on first render** of any new `currentGraph`. Use
>    `min(cW / totalW, cH / totalH, 2.0)` (cap 2.0; do **not** floor at
>    1.0 — small graphs should magnify).
> 2. **Auto-fit when topology arrives** (new `version` from event).
>    Computed via `useEffect` keyed on `currentGraph?.version`.
> 3. **Auto-fit when `graphPath` changes** (drill-down or drill-up).
>    Computed via `useEffect` keyed on `graphPath.join('/')`.
> 4. **Preserve zoom/pan during status updates** — status events do
>    NOT reset the viewport, so the user's manual pan/zoom survives
>    the storm of `node_status` events during execution.
> 5. **Floating controls** in the bottom-right corner: `+`, `−`,
>    `⛶ fit`. Mouse-wheel zoom on the canvas; drag-to-pan on background.

### 12.5 Adds §4.5 — Edge cases (canonical enumeration)

Adopt MHF v2's enumerated 1–10 edge-case list verbatim, plus the 2 I
added during integration:

> **§4.5 Edge cases (canonical enumeration)**
>
> 1. **Node ID collisions**: Prefixed IDs (`worker_2/worker_0`) — no
>    conflicts. Verified by `test_child_reporter_qualifies_ids`.
> 2. **Sub-graph not yet arrived**: Loading placeholder
>    ("Waiting for inner pipeline...") until topology arrives.
> 3. **Frantic auto-switch**: Sticky selection (5 s window) prevents
>    panel flipping when many workers run concurrently.
> 4. **Premature collapse**: Recursive `allComplete` walks `subGraphs`
>    — outer "complete" without inner completion does not collapse.
> 5. **Zoom/pan reset**: Reset on drill-down + topology arrival;
>    preserve during status updates (§12.4).
> 6. **Deep nesting**: `child_reporter()` composes prefixes
>    (`a/b/c/...`); breadcrumb supports N levels with `maxItems={5}`
>    truncation in the middle.
> 7. **WS closed mid-run**: Circuit breaker disables graph events
>    after 3 consecutive failures; BTA continues unaffected; logged
>    once. Re-enabled on next `graph_topology`.
> 8. **Memory**: 200 KB cap per node stream; topology ~200 bytes/node;
>    `nodeStreams` GC after 60 s of `task.status === 'completed'`.
> 9. **Container has no leaf content**: "Container Output" toggle
>    (§3.5.4) shows `__breakdown__` + `__aggregator__` streams.
> 10. **Rerun**: Clear `subGraphs`, reset `graphPath`, version-based
>     change detection, **plus orphaned `nodeStreams` cleanup**
>     (§3.7.3.3 / §3.5.18.1 — MHF v2 miss).
> 11. **`prefers-reduced-motion`**: Animations replaced with instant
>     transitions; functional behaviour identical (§3.5.13 — MHF v2
>     does not yet cover this; we keep the a11y pass).
> 12. **Fast successive container clicks**: `transitionDirection`
>     derived from `useRef(prevPath)` not imperative state — race-safe
>     under rapid navigation (§3.7.5 anti-pattern #12).

### 12.6 Adds §7.8 — Implementation Order Diagram (ASCII)

MHF v2 ends with a clean ASCII flow that mine lacked. Adopt:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   v0 (5.5d)        ┌──────────────────────┐                             │
│                    │ Phase 1 (backend, 1d)│                             │
│                    └──────────┬───────────┘                             │
│                               ▼                                         │
│              ┌───────────────────────────────────────┐                  │
│              │ §3.6 /mock_task (1.5d) — UNBLOCKER    │                  │
│              │   └─ enables fast iteration on UI     │                  │
│              └─────────────────┬─────────────────────┘                  │
│                                ▼                                        │
│              ┌──────────────────────────┐  ┌──────────────────────────┐ │
│              │ Phase 3 UI resilience    │  │ Phase 4 drill-down (2d)  │ │
│              │ (0.75d) — bounded, RAF,  │  │ — graphPath, breadcrumb, │ │
│              │ recursive allComplete    │  │ Container Output toggle, │ │
│              └──────────────────────────┘  │ zoom/pan, compact, ghost │ │
│                                            └──────────────────────────┘ │
│                                                                         │
│   v1 (3d, optional polish)                                              │
│              ┌──────────────────────────────────────────┐               │
│              │ Migrate to React Flow + dagre; setViewport│              │
│              │ ghost outer context, minimap, live tokens │              │
│              └──────────────────────────────────────────┘               │
│                                                                         │
│   v2 (2d, generalise)                                                   │
│              ┌──────────────────────────────────────────┐               │
│              │ Phase 4 generalisation: Linear/Dual/      │              │
│              │ Reflective/PlanThenImplement inferencers  │              │
│              │ wired with graph_reporter; --assert-event-│              │
│              │ parity regression mode for /mock_task     │              │
│              └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```

Reading the diagram: Phase 1 (backend hierarchical reporter) is the
blocker for everything; once it lands, `/mock_task` unblocks UI
iteration; Phase 3 resilience and Phase 4 drill-down can run in
parallel from there. v1 and v2 are additive layers shippable in any
order after v0.

### 12.7 Adds §App-A.0 — File Inventory Quick-Reference Table

MHF v2 has a tight one-table file inventory at the end. Mine has the
same info spread across Appendix A subsections. Add a quick-reference
table at the head of Appendix A (existing detailed lists remain):

| File | Change | Phase / item |
|---|---|---|
| `AgentFoundation/.../graph_events.py` | `parent_node_id`, `version`, `is_container` per node | 1A |
| `AgentFoundation/.../graph_interactive_adapter.py` | `ChildGraphReporter`, `child_reporter()`, throttling | 1B, Phase 3.1 |
| `AgentFoundation/.../breakdown_then_aggregate_inferencer.py` | Propagate `graph_reporter`, set `_is_container`, route BD/agg streams | 1C, 1D, §3.5.10 |
| `AgentFoundation/.../mock_inferencers/mock_bta_components.py` | **NEW** — `MockBreakdownInferencer`, `MockWorker`, `MockAggregator` | §3.6.3 |
| `AgentFoundation/.../configs/registered_targets.py` | Register mock targets for `instantiate(cfg)` | §3.6.3 |
| `PythonUtils/.../workgraph.py` | `WorkGraphNode.to_serializable_obj` adds `group`, `_viz_label`, `_is_container`; `WorkGraph._emit_topology` helper | Phase 4.1 / 4.2 |
| `OpenTeam/.../websocket_interactive.py` | `parent_node_id` in WS msg, try/except + circuit breaker | 1E |
| `OpenTeam/.../role_setup/executor.py` | ~~Wire `graph_reporter`~~ **✅ DONE** (lines 1215-1216) | 1F |
| `OpenTeam/.../resources/tools/mock_task/` | **NEW** — `tool.json` (`agent_enabled:false`), `executor.py`, 5 profile YAMLs | §3.6.4 / §3.6.5 / §3.6.6 |
| `OpenTeam/.../routes/manager_websocket_routes.py` | `/mock_task` slash intercept gated by `OPENTEAM_DEV_MODE` + `agent_enabled:false` | §3.7.3.5 / §3.5.18.5 |
| `OpenTeam/.../hooks/useGraphState.js` | **NEW** — RAF batching, bounded streams, orphan cleanup, derived `expandableNodeIds`, race-safe `transitionDirection` | §3.5.18.1 |
| `OpenTeam/.../hooks/useManagerChat.js` | Delegate graph cases to `useGraphState` | §3.5.18.1 |
| `OpenTeam/.../components/chat/Breadcrumb.js` | **NEW** — clickable hierarchy navigation | §3.5.18.3 |
| `OpenTeam/.../components/chat/TaskPanel.js` | Drill-down state binding, breadcrumb, animations, dynamic height, Esc priority chain | §3.5.18.2 / §3.7.3.7 / §3.5.9 |
| `OpenTeam/.../components/chat/GraphFlowView.js` | Zoom/pan, expandable indicators, mini progress badge, `maxColSize` compact mode | §3.5.18.4 / §12.3 / §12.4 / §3.7.3.6 |
| `OpenTeam/.../components/chat/NodeDetailPanel.js` | ElapsedTimer fix, breadcrumb path display, strict open-only-on-leaf-click | §3.5.18 / §3.5.7 |
| `OpenTeam/.../components/chat/ContainerOutputToggle.js` | **NEW** — Graph/Output pill for focused container | §3.5.4 |
| `OpenTeam/.../components/chat/ChatInput.js` | Slash-command parsing + dev-tool autocomplete popover | §3.5.18.5 / §3.6.7 |
| **v1 only** `package.json` | Add `@xyflow/react`, `dagre` | §7.2 |
| **v1 only** `OpenTeam/.../components/chat/GhostOutline.js` | **NEW** — edge-pinned outer-context markers | §3.5.6 |
| **v1 only** `OpenTeam/.../components/chat/LiveTokenBubble.js` | **NEW** — fade-in/out token preview above leaves | §3.5.5 |
| **v2 only** Linear/Dual/Reflective/PlanThenImplement inferencer files | Add `graph_reporter` attribute + emit topology | Phase 4.3 |


---

## 13. Corrections (r6) — feedback round, codebase-verified

This section consolidates fact-checked corrections after a feedback
audit. Each item lists the original mistake, the verified evidence,
and the precise fix. The fixes are also folded into the relevant
earlier sections (e.g., §3.5.10 has been struck through; §App-A
updated; etc.) — §13 here is the canonical statement of the change.

### 13.1 Phase 4 — non-BTA inferencers do NOT use `WorkGraph` (CORRECTS Issue #13, Phase 4 of §3, item #25 in §7.3)

**Original mistake**: My plan assumed `LinearWorkflowInferencer`,
`DualInferencer`, `PlanThenImplementInferencer`, `ReflectiveInferencer`
build `WorkGraph`s and proposed to "wire `graph_reporter` into them"
in Phase 4.3.

**Verified evidence**:
- `workflow.py:31`: `class Workflow(WorkNodeBase, ABC)` — does NOT
  inherit from `DirectedAcyclicGraph` or `WorkGraph`.
- `linear_workflow_inferencer.py:79`: `class LinearWorkflowInferencer(InferencerBase, Workflow)`.
- `dual_inferencer.py:68`: `class DualInferencer(InferencerBase, Workflow)`.
- `reflective_inferencer.py:32`: `class ReflectiveInferencer(LinearWorkflowInferencer)`.
- `plan_then_implement_inferencer.py:253`: `class PlanThenImplementInferencer(LinearWorkflowInferencer)`.
- `grep _graph_event_callback workflow.py` → 0 matches.
- `grep _all_nodes workflow.py` → 0 matches.

**Implication**: Setting `graph_reporter` on a `Workflow` instance has
zero effect because `Workflow` has no DAG nodes to fire callbacks on.
Phase 4.3 as written would not produce any visualization for these
inferencers.

**Revised Phase 4 — two viable paths**:

- **Path A (defer)**: Drop non-BTA visualization from v2 entirely.
  Document that only `WorkGraph`-based inferencers (BTA + future
  WorkGraph subclasses) can be visualized. Add a banner in the UI:
  "This inferencer doesn't produce a visual graph." Effort saved:
  ~1 day from v2.
- **Path B (`WorkflowVisualizationAdapter`)**: Build a separate
  adapter that synthesizes graph events from a `Workflow`'s step chain
  introspection. The adapter:
  - Inspects `Workflow.steps` (or equivalent — verify the actual
    attribute name) to build a linear topology event upfront.
  - Wraps each step's execution to emit RUNNING/COMPLETED/ERROR
    `node_status` events.
  - Pipes `stream_observer` (if the step exposes one) to
    `node_stream_observer`.
  - Effort: ~1.5 days. Adds a new `agent_foundation/.../graph/workflow_adapter.py`.

**Decision**: Choose **Path A for v2 MVP** to keep the v2 effort
honest. Path B can be a separate future plan once the `WorkGraph`-
based visualization has shipped and proven its value. **Save 1 day
in v2 (revised v2 total: 1.25 days)**.

**Phase 4 of §3 and item #25 of §7.3 are revised accordingly**:
remove "Phase 4.3 wire `graph_reporter` into Linear / Dual /
PlanThenImplement / Reflective inferencers" — it is impossible without
the adapter. Items 23 (promote `group`/`_viz_label`/`_is_container`
to first-class fields) and 24 (move `_emit_topology` into the
`WorkGraph` base layer) **remain valid** — they apply to `WorkGraph`
subclasses regardless of the non-BTA story.

### 13.2 §3.5.10 — BTA already routes breakdown/aggregator streams (CORRECTS §3.5.10, §3.5.4 wiring assumption)

**Original mistake**: §3.5.10 proposed adding code to route
`breakdown_inferencer.stream_observer` and
`aggregator_inferencer.stream_observer` into
`graph_reporter.node_stream_observer("__breakdown__"/"__aggregator__")`
synthetic ids.

**Verified evidence** (line numbers updated r10):
- `breakdown_then_aggregate_inferencer.py:1501-1503`:
  `self.breakdown_inferencer.stream_observer = self.graph_reporter.node_stream_observer("breakdown")`
- `breakdown_then_aggregate_inferencer.py:1031`:
  `agg_inf.stream_observer = self.graph_reporter.node_stream_observer("aggregator")`

The BTA **already** routes these streams under the **same node ids**
(`"breakdown"` and `"aggregator"`) that the topology event uses for
the corresponding nodes (the virtual breakdown node and the
aggregator node).

**Implication**: My §3.5.10 proposal would have created **duplicate
streams** — the existing `"breakdown"`/`"aggregator"` streams firing
alongside redundant `"__breakdown__"`/`"__aggregator__"` ones.

**Fix**: §3.5.10 is **OBSOLETE — DROP**. The Container Output toggle
(§3.5.4) does not need synthetic ids. Instead, when the user toggles
to "Output" mode for a container `worker_2` (whose value is an inner
BTA), the toggle reads the **already-existing** streams at:
- `worker_2/breakdown` (via `NamespacedGraphReporter` namespacing of
  the inner BTA's existing `"breakdown"` stream id).
- `worker_2/aggregator` (likewise).

So the only Python work needed is what Phase 1 already provides
(child reporter propagation to the inner BTA). §3.5.10's "0.5 day
of Python work" reduces to **0 days**. Item #22 in §7.3 is
deleted; v2 effort drops by another 0.5 day.

**Revised v2 total after §13.1 + §13.2: 1.25 - 0.5 = 0.75 days.**

### 13.3 `node_stream_observer` returns a callable, not `.emit()` object (CORRECTS §3.5.18.6 mock components)

**Original mistake**: §3.5.18.6 mock code uses
`await self.stream_observer.emit(chunk)`. Likewise §3.6.3.

**Verified evidence**: `graph_interactive_adapter.py:174-191` —
`async def _observer(chunk: str) -> None: ...` returned directly. No
`.emit()` method.

**Fix**: All mock components must call:

```python
if self.stream_observer:
    await self.stream_observer(chunk)        # ✅ correct
    # NOT: await self.stream_observer.emit(chunk)  # ❌ AttributeError
```

This applies to:
- `MockBreakdownInferencer.ainfer` (§3.5.18.6)
- `MockWorker.ainfer` (§3.5.18.6)
- `MockAggregator.ainfer` (§3.5.18.6)
- `§3.6.3` mock spec — same fix.

### 13.4 `namespace` field redundant with `parent_node_id` (CORRECTS §2.2)

**Original mistake**: `GraphTopologyEvent` defines both
`parent_node_id: str = ""` and `namespace: str = ""` (§2.2).

**Verified evidence**: In `NamespacedGraphReporter`, the two values
are constructed in lockstep — `namespace=parent_node_id,
parent_node_id=parent_node_id` — and updated identically in
`child_reporter()`.

**Fix**: Delete the `namespace` field. Use `parent_node_id` alone.
Update §2.2:

```python
@dataclass
class GraphTopologyEvent:
    nodes: list[dict]
    edges: list[dict]
    layout: str = "horizontal"
    parent_node_id: str = ""    # non-empty: this is a sub-graph rooted at parent
    version: int = 0            # incremented per emission for change detection
    # NO namespace field — parent_node_id IS the namespace.
```

Update `NamespacedGraphReporter.__init__` signature and remove the
duplicate parameter.

### 13.5 `replace()` not imported (CORRECTS §3.7.3.5 / §1.2)

**Original mistake**: `NamespacedGraphReporter.on_graph_topology` uses
`replace(event, ...)` but `graph_events.py` only imports `dataclass,
field`.

**Fix**: Either:
- Add `replace` to the `graph_events.py` import:
  `from dataclasses import dataclass, field, replace`, OR
- Import `replace` in `graph_interactive_adapter.py` where the reporter
  lives: `from dataclasses import replace`.

Recommendation: **import in `graph_interactive_adapter.py`** because
that's where it's actually used. Keeps `graph_events.py` lean.

### 13.6 Node naming examples — `worker_*`, NOT `inner_bta_*` (CORRECTS §3.5.1, §3.5.10, §4.2, §3.5.18 examples)

**Original mistake**: My plan used `inner_bta_0`, `inner_bta_2` as
example node ids in the outer graph.

**Verified evidence**:
- `breakdown_then_aggregate_inferencer.py:712`:
  `name=f"worker_{i}"` — outer BTA names every worker `worker_{i}`,
  including ones whose value is an inner BTA.
- `role_setup/executor.py:610`: `name=f"inner_bta_{index}"` — this
  is the **inner BTA's own `name` attribute as a Workflow** (used in
  e.g. logging), NOT the node id assigned by the parent.

The qualified id of an inner BTA's worker is therefore
`worker_2/worker_3` (outer's `worker_2` is a container; its inner
graph's `worker_3` is a leaf), **NOT** `inner_bta_2/worker_3`.

**Fix**: Throughout the doc, replace `inner_bta_X` with `worker_X` in
examples. Where the doc wants to highlight the *human-readable label*
of a container (the inner BTA's purpose), use the `_viz_label`
mechanism: `worker_2 → label: "Backend skill creation"`.

Updated breadcrumb example: `Pipeline ▸ worker_2 (Backend) ▸ worker_3 (Auth API)`.

### 13.7 React Flow stance reconciliation (CORRECTS §3.5.12, §7.1, §7.2)

**Original mistake**: §3.5.12 says "drill-in UX requires React Flow"
but §7.1 v0 ships drill-in *without* React Flow.

**Fix**: Insert a clarifying note at the top of §3.5.12:

> **Note (clarified r6)**: The React Flow dependency is required only
> for the **v1 polish** (animated `setViewport` zoom, parent-node
> sub-flow rendering, ghost outer context, minimap). **v0 ships
> drill-in without React Flow** using MHF's `key`-remount + CSS
> keyframe animation (§3.5.18.2 + §3.7.2.1), against the existing
> custom SVG `GraphFlowView`. The `useGraphState` hook is identical
> for both — the rendering layer is the only swap. Adopt React Flow
> only when committing to v1.

### 13.8 Critical-path / mock-first contradiction (CORRECTS §7.4 / §7.6)

**Original mistake**: §7.6 says "mock first" but §7.4 critical path
(items 1-3 + 7-9 = 3.1 days) skips the mock (items 4-6).

**Fix**: The critical path was computed for "first time the user can
see ANY drill-in working in the UI", which can technically be done
without the mock by running the real `role_setup`. But this
contradicts the practical guidance.

Replace §7.4 critical-path statement with:

> **Critical path to first iterable demo**: items 1, 2, 3 (Phase 1 +
> role_setup wiring + WS error handling = 1.1 days) **+ items 4, 5, 6
> (mock components + tool + slash intercept = 1.25 days)** + items 7,
> 8, 9 (`useGraphState` + TaskPanel + GraphFlowView additions =
> 2.0 days) = **4.35 days**. After this, every UI tweak can be tested
> against `/mock_task --workers 20 --inner 5` in seconds rather than
> waiting for a 3-minute LLM run. The 3.1-day path that skips the
> mock is technically possible but operationally painful.

### 13.9 Drop the `OPENTEAM_HIERARCHICAL_GRAPH=1` feature flag (CORRECTS §9)

**Original mistake**: §9 proposes a feature flag for "A/B comparison
the first week."

**Fix**: For nested BTAs the current behaviour is "shows nothing", so
there is no A/B baseline. Drop the flag. The protocol additions
(`parent_node_id` defaults to `""`) are already backwards-compatible.
No flag needed.

Update §9: remove the `OPENTEAM_HIERARCHICAL_GRAPH` paragraph;
keep "all new event fields default to empty/None → old clients ignore
them" as the back-compat statement.

(Note: `OPENTEAM_DEV_MODE` for `/mock_task` is **separate** and
remains required — it's a production-safety gate, not an A/B flag.)

### 13.10 `§3.6.7` HTTP-route design superseded by §3.7.3.5 (HOUSEKEEPING)

**Original state**: §3.6.7 still describes the `/api/dev_tools/*`
HTTP routes + `useDevTools.js` + `DevToolBubble.js` design that was
later superseded by §3.7.3.5 (WS message intercept).

**Fix**: Mark §3.6.7 as **SUPERSEDED — see §3.7.3.5 for the
canonical design**. Drop `useDevTools.js` and `DevToolBubble.js`
from the file inventory (§App-A.0). Keep only the slash-command
parser additions to `ChatInput.js`.

### 13.11 Stream observer trailing-batch loss (NEW BUG, CORRECTS Phase 1.4)

**Original gap**: `_observer` (`graph_interactive_adapter.py:174-191`)
only flushes when `(now - _last_flush[0]) * 1000 >= flush_interval_ms`.
There is no `flush()` / `close()` method. If the inferencer finishes
between flushes, the trailing batch is silently dropped.

**Why it matters**:
- For workers (`worker_*`): the BTA emits `node_stream` with
  `is_final=True` after the worker finishes (`bta_inferencer.py:660`-ish),
  so the dropped partial batch is **redundant** with the final emit
  — no real loss for workers.
- For breakdown / aggregator streams: there is **no** equivalent
  `is_final` post-emit. The trailing batch IS lost.

**Fix**: Convert the observer from a plain async function into a
small object with `__call__` AND `flush()`:

```python
class _StreamObserver:
    def __init__(self, ws, task_id, node_id, flush_interval_ms):
        self._ws, self._task_id, self._node_id = ws, task_id, node_id
        self._interval_ms = flush_interval_ms
        self._batch: list[str] = []
        self._last_flush = _time.monotonic()

    async def __call__(self, chunk: str) -> None:
        self._batch.append(chunk)
        now = _time.monotonic()
        if (now - self._last_flush) * 1000 >= self._interval_ms:
            await self._send_now()

    async def flush(self) -> None:
        if self._batch:
            await self._send_now()

    async def _send_now(self) -> None:
        content = "".join(self._batch)
        self._batch.clear()
        self._last_flush = _time.monotonic()
        try:
            await self._ws.send_graph_event(
                NodeStreamEvent(node_id=self._node_id, content=content),
                task_id=self._task_id,
            )
        except Exception as exc:
            _logger.warning("[node_stream_observer] flush failed: %s", exc)
```

`node_stream_observer` returns the instance; callers can still `await
observer(chunk)` (because of `__call__`). After the inferencer
finishes, the BTA explicitly calls `await observer.flush()` for the
breakdown and aggregator observers (add to the BTA's
`finally`-blocks where breakdown/aggregator are awaited).

**No backwards-compat break**: the observer remains awaitable as
before — only the new `.flush()` capability is added.

This is added as **item #14a in v0** (effort: 0.10 day; same file as
Phase 1.4 try/except work).

### 13.12 Phase 3.1 throttle must coalesce, not drop (CORRECTS §3.3 / Phase 3.1)

**Original mistake**: §3.3 / Phase 3.1 proposed an `asyncio.Queue
maxsize=1` "latest chunk wins" approach for `node_stream` throttling.

**Why wrong**: `node_stream` content is **incremental cumulative
text**. Dropping intermediate chunks creates gaps in the displayed
output (the user sees `"Ana...alyzing"` instead of `"Analyzing"`).

**Fix**: Server-side throttling for `node_stream` must **coalesce**
(concatenate the buffered chunks into a single larger send) when the
target rate is exceeded, never drop. The `_StreamObserver` design in
§13.11 already does this naturally — increasing `flush_interval_ms`
under load is sufficient throttling. Add per-task token-bucket if a
hard cap is needed:

```python
class _RateBudget:
    """Allows N flushes per second per task. When budget exhausted,
    increase the effective flush_interval_ms to coalesce more
    aggressively."""
    def __init__(self, max_per_sec: int = 30):
        self._max = max_per_sec
        self._tokens = max_per_sec
        self._last_refill = _time.monotonic()

    def consume(self) -> bool:
        now = _time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self._max, self._tokens + elapsed * self._max)
            self._last_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False
```

Observer checks budget; if denied, skips the send (chunks remain in
`self._batch`, will be sent on the next successful flush). **Content
is preserved**; only flush *frequency* is reduced.

`node_status` events are NEVER throttled — they're low-volume and
sequence-critical.

### 13.13 Feedback #14 (orphan cleanup) — INVALID, my plan already fixes it

**Feedback claim**: "No handling of nodeStreams orphan cleanup on rerun."

**My evidence**:
- §3.7.3.3 explicitly added orphan cleanup: "Clear `task.nodeStreams[k]`
  for every `k` that does not appear in the new root graph
  (orphaned-stream cleanup — MHF miss)."
- §3.5.18.1 implements it concretely:
  ```js
  const cleanedStreams = Object.fromEntries(
    Object.entries(task.nodeStreams || {})
      .filter(([k]) => {
        const rootId = k.split('/')[0];
        return validIds.has(rootId);
      })
  );
  ```

**Verdict**: **Feedback rejected as invalid**. No change needed. The
plan is correct here.

(One real subtlety: my filter retains streams where `rootId` is in
the new root graph but the *child path* may have changed. For example,
if `worker_2` exists in both runs but its sub-graph is different, an
old `worker_2/worker_5` stream survives this filter even if the new
`worker_2` doesn't have a `worker_5`. This is intentional — sub-graph
streams are cleaned when their respective sub-graph is re-emitted via
the same logic at sub-graph level. But this could be tightened in a
future revision.)

---

## 13.99 Effort impact summary of corrections

| Change | Δ effort |
|---|---|
| §13.1 Drop Phase 4.3 (non-BTA inferencers) → Path A | **−1.0 day** (v2) |
| §13.2 Drop §3.5.10 Python work (already done) | **−0.5 day** (v2) |
| §13.11 Add observer `.flush()` + BTA flush call | **+0.10 day** (v0) |
| §13.12 Add `_RateBudget` for coalescing throttle | **+0.15 day** (v0) |
| Other corrections (#3, #4, #5, #6, #7, #8, #9, #10) | 0 (doc-only fixes) |

**Net: v0 +0.25 day, v2 −1.5 days. Total: −1.25 days.**

Revised totals:
- v0: **5.75 days** (was 5.5).
- v1: **3.0 days** (unchanged).
- v2: **0.75 days** (was 2.25; only items 23, 24, 26, 27 remain).
- **Grand total: 9.5 days** (was 10.75).


---

## 14. r7 Corrections — second feedback round (codebase-verified)

This round acted on a 20-item review. Verdict: **17 valid, 2 invalid,
1 partially-valid**. Each fix below was applied to the actual code
blocks (not just documented), or — where doc-only — clearly marked.

### 14.1 — Issue #12 nuance: `WebSocketGraphReporter` already wraps with try/except (PARTIALLY VALID)

**Verified facts** (`graph_interactive_adapter.py:98-189`):
- Class docstring states: *"All graph event sends are wrapped in
  try/except to prevent visualization failures from aborting the BTA
  computation."*
- `on_graph_topology`, `on_node_status`, `on_node_stream`, and the
  `node_stream_observer._observer` closure all have `try/except
  Exception as exc: _logger.warning(...)` blocks.

**What's still missing** (the part of Issue #12 that remains valid):
- `WebSocketInteractive.send_graph_event` itself (in OpenTeam —
  the *transport* layer below the reporter) — needs verification.
  The reporter catches exceptions raised *during* send; if the
  transport raises before the reporter awaits (e.g., synchronous
  setup error), the exception bypasses the reporter's try.
- The **circuit breaker** (after N failures, short-circuit further
  sends) does NOT exist anywhere today. Worth keeping as a real
  improvement.

**Revised Issue #12 statement**: *"`WebSocketGraphReporter` correctly
wraps all sends in try/except. What's missing is (a) symmetric
try/except in the underlying `websocket_interactive.send_graph_event`
transport for safety, and (b) a circuit breaker that disables
further graph events after sustained failure to prevent log spam."*

**Effort impact**: Phase 1.4 reduces from 0.25 d → **0.15 d** (only
circuit breaker + transport-layer guard remain). Saves 0.10 d in v0.

### 14.2 — Issue #5 wording: `node.group` is absent in UI, not "ignored" (VALID, cosmetic)

**Original text**: *"`node.group` is plumbed through the event but
ignored by the UI."*

**Corrected**: *"`node.group` is present in the topology event data
emitted by the server but is never consumed by any UI component
(`GraphFlowView`, `NodeBox`, `NodeDetailPanel`)."*

Doc-only fix. Update Issue #5 in §0 problem table.

### 14.3 — v2 effort math wrong (VALID, +0.5 d)

**Original**: §13.99 said v2 = 0.75 d after corrections.

**Verified arithmetic** (items remaining in §7.3):
- Item 23 (promote `to_serializable_obj` fields): 0.25 d
- Item 24 (`_emit_topology` in WorkGraph base): 0.25 d
- Item 26 (Phase 5 polish): 0.5 d
- Item 27 (`--assert-event-parity`): 0.25 d
- **Sum: 1.25 d**, not 0.75 d.

**My §13.99 was off by 0.5 d.** Corrected:

| | Effort |
|---|---|
| v0 | 5.65 d *(was 5.75; saves 0.10 from §14.1)* |
| v1 | 3.0 d |
| v2 | **1.25 d** *(was 0.75; +0.5 math fix)* |
| **Total** | **9.9 d** *(was 9.5; net +0.4 d)* |

### 14.4 — Undefined refs in v0 code (VALID)

§3.5.18.2 references `graphCollapsed`, `helpOpen` / `setHelpOpen`,
`fitToView()`, `prefersReducedMotion` without declarations.

**Root cause**: I copy-pasted the relevant additions without showing
the surrounding state declarations.

**Fix** — declare everything explicitly. The implementer should add
to `TaskPanel.js` head:

```jsx
import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import useMediaQuery from '@mui/material/useMediaQuery';

const [graphCollapsed, setGraphCollapsed] = useState(false);
const [helpOpen, setHelpOpen] = useState(false);
const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

// fitToView is owned by GraphFlowView. Pass an imperative ref:
const graphRef = useRef(null);   // ref attached to <GraphFlowView ref={graphRef} />
const fitToView = () => graphRef.current?.fitToView();

// then in <GraphFlowView ref={graphRef} ... />
// GraphFlowView must use forwardRef + useImperativeHandle({ fitToView })
```

Add this snippet near the top of §3.5.18.2 in implementer's reading.

### 14.5 — Cross-project impact of `to_serializable_obj` changes (VALID)

**Verified**: `WorkGraph.to_serializable_obj()` is used in many
places; `WorkGraphNode.to_serializable_obj()` is called inside the
WorkGraph traversal (`workgraph.py:1236`). Adding extra dict keys
(`group`, `_viz_label`, `_is_container`) is **forward-compatible**:
deserializers either ignore unknown keys or read explicit ones.

**However**, the plan should note:
- `PythonUtils` is a separate repo with its own version; changes
  require a coordinated release.
- A search for `from_serializable_obj` / `parse_serial` finds no
  consumers outside the same module that produces them in
  AgentFoundation, so the risk is low — but the dependency must be
  bumped.
- Add a unit test asserting deserialize round-trip with new keys.

**Action item** (added to §App-A):
- Bump `PythonUtils` minor version when items 23/24 land.
- Coordinate AgentFoundation `requirements.txt` pin update.
- Add `test_workgraph_node_serial_roundtrip_with_new_keys`.

### 14.6 — `session_context` claim is wrong (INVALID)

**Verified**: `create_role/executor.py:539-540` reads
`session_context.get("interactive")` and `session_context.get("task_id", "")`
**successfully today**. The keys ARE injected into the session
context for in-session tools by the dispatcher framework.

**Verdict**: Reject. The plan's Phase 1.5 wiring code is correct.

The new WS-intercept path in §3.5.18.5 *constructs* `interactive` and
`task_id` manually (because there's no in-session caller), which is
also correct.

### 14.7 — Slash command `text.startswith("/")` is too broad (VALID)

**Root cause**: `/usr/local/bin` and `/api/v2/...` would match.

**Fix** — replace the trigger condition in §3.5.18.5:

```python
import re
_SLASH_CMD_RE = re.compile(r"^/([a-zA-Z][a-zA-Z0-9_]*)\b")

async def process_message(sid: str, text: str) -> None:
    text = text.strip()
    m = _SLASH_CMD_RE.match(text)
    if (m
            and os.environ.get("OPENTEAM_DEV_MODE") == "1"):
        cmd = m.group(1)
        # Additionally require the command exists in the registry as
        # a developer tool (agent_enabled=False) — this prevents
        # `/usr/local/...` from triggering even with the regex match.
        tool = _registry().get(cmd)
        if tool is None or tool.agent_enabled is True:
            # Not a developer tool — fall through to conversation flow
            pass
        else:
            args_str = text[m.end():].lstrip()
            argv = shlex.split(args_str) if args_str else []
            args = parse_cli_args(argv, tool.parameters)
            ...
```

Two-gate safety: (1) regex match enforces leading `/[a-z][a-z0-9_]*`
followed by word boundary; (2) registry lookup confirms the token
is actually a registered developer tool. `/usr/local/...` matches
the regex but fails the registry check → falls through to the LLM
as normal text.

### 14.8 — WebSocket message ordering (PARTIALLY VALID)

**Facts**:
- A single WebSocket connection guarantees message ordering on the wire.
- **RAF batching** in `useGraphState` reorders by *type* within a
  frame (status updates and topology updates are coalesced into one
  `setTasks`).
- However, the §3.7.2.3 model is *eventually consistent*: once all
  events for a frame are applied, the resulting state is correct
  regardless of within-frame ordering, because:
  - Topology events replace/splice graph data atomically.
  - Status events update individual node fields independently.
  - Stream events append independently.
- **No causal ordering needed.** No sequence number needed.

**One real edge case**: a status event for a node could arrive in the
same RAF frame as the topology event that introduces that node. If
the status update is dispatched before the topology in the batch,
`_applyStatusToTask` returns null (sub-graph not present) and buffers
the status. The buffered status is replayed when handleGraphTopology
runs — but that runs in the *same* batch, so the replay sees the
just-spliced sub-graph. This works.

**Doc fix**: Add a paragraph to §3.7.2.3 noting eventual consistency
and the within-frame buffer-and-replay flow.

### 14.9 — `getDerivedFor` performance (INVALID)

**Verified**: `getDerivedFor` is a `useCallback` that returns an
object built from the current closure values. The `useCallback` deps
include `tasks`, `graphPath`, `selectedLeafId` — so the function
identity is stable until those change. Inside, the function does
fresh computation per call, but each call is O(N) over the relevant
sub-graph (small for any realistic `currentGraph`).

**Verdict**: Reject. The pattern is intentional — `getDerivedFor(tid)`
is called with `tid` not known at hook-construction time, so it
*can't* be pre-`useMemo`-ed without a different shape (e.g., an
`activeTid` state). The current pattern is correct for multi-task UIs.

If perf becomes an issue under heavy load (it shouldn't — typical
graph is < 100 nodes), the consumer can wrap `getDerivedFor(tid)`
with its own `useMemo` keyed by `tid + tasks[tid] + graphPath +
selectedLeafId`.

### 14.10 — Concurrent tasks support (VALID)

**Verified**: `tasks` is keyed by `tid` (task id). The dispatcher
issues unique task ids per invocation. `useGraphState` already
supports multiple concurrent tasks — the missing piece is **UI
selection**: which task's graph is currently shown.

**Fix** (added to §3.5):
- Maintain `activeTid: string | null` in `TaskPanel` state.
- Sidebar lists running tasks: `[role_setup-abc] [/mock_task-def]`.
- Click selects `activeTid`; the canvas + side panel render only
  that task's data.
- `graphPath`, `selectedLeafId`, `containerView` are **per-`activeTid`**
  in v2; for v0 they reset on task switch (acceptable).

### 14.11 — Phase numbering collision (VALID, cosmetic)

Three numbering schemes:
- §3 "Phase 1–5" (Python implementation phases)
- §7 items "1–27" (effort-table line items)
- §12.6 ASCII diagram "Phase 3 / Phase 4" (means UI-resilience and
  drill-down)

**Fix**: Adopt **ONE canonical naming**: replace ASCII-diagram
"Phase 3 / Phase 4" with "v0 §3.3 resilience" and "v0 §3.5
drill-down" so all references map to either §3 or §7 items. Doc-only
update; applied via §12.6 edit.

### 14.12 — Mark obsolete sections clearly (VALID)

§3.5.10 and §3.6.7 are marked obsolete in §13.2 / §13.10 but their
bodies still read like fresh proposals. Add a clear **OBSOLETE**
header at the top of each section body so a reader can't miss it.

(Doc-only — applied below in §14.x edits.)

### 14.13 — Inconsistent file path references (VALID, cosmetic)

`formatters/markdown.py:167` lacks repo prefix.

**Fix**: Adopt a single convention:
`<repo>/<path>:line` — e.g. `AgentFoundation/src/agent_foundation/resources/tools/formatters/markdown.py:167`.
Apply across plan via subsequent housekeeping.

### 14.14 — `inner_bta_X` → `worker_X` sweep (VALID)

§13.6 declared the rule but didn't sweep. The remaining offenders
are in §3.5.1, §3.5.10 (now obsolete), §4 testing examples.

**Fix**: ALL examples MUST use `worker_X` for the qualified id; the
human label `(Backend)` may include the inner BTA's `name=f"inner_bta_{i}"`
in parentheses. Example breadcrumb:
```
Pipeline ▸ worker_2 (inner_bta_2: Backend) ▸ worker_3 (Auth API)
```

(Sweep applied via §3.5 / §3.5.18 inline; new examples conform.)

### 14.15 — Undefined `_apply_speed`, `_apply_seed_jitter`, `parse_cli_args` (VALID)

§3.6.6 and §3.5.18.5 reference helpers that aren't shown. Provide
minimal reference implementations:

```python
def _apply_speed(cfg: dict, factor: float) -> dict:
    """Multiply every numeric *delay_s / duration_s* in the config tree
    by `factor`. factor < 1 = faster, factor > 1 = slower."""
    if isinstance(cfg, dict):
        return {k: (v * factor if k.endswith("_s") and isinstance(v, (int, float))
                                  else _apply_speed(v, factor))
                for k, v in cfg.items()}
    if isinstance(cfg, list):
        return [_apply_speed(x, factor) for x in cfg]
    return cfg

def _apply_seed_jitter(cfg: dict, seed: int) -> dict:
    """Add deterministic ±10% jitter to every *_s field, seeded by `seed`."""
    rng = random.Random(seed)
    def _walk(c):
        if isinstance(c, dict):
            return {k: (v * (1.0 + rng.uniform(-0.1, 0.1))
                          if k.endswith("_s") and isinstance(v, (int, float))
                          else _walk(v))
                    for k, v in c.items()}
        if isinstance(c, list):
            return [_walk(x) for x in c]
        return c
    return _walk(cfg)

def parse_cli_args(argv: list[str], spec: list[dict]) -> dict:
    """Parse `--key value` style args against a tool's parameters spec.

    `spec` items: {"name": "--workers", "type": "int", "default": 5, ...}
    """
    out = {p["name"].lstrip("-"): p.get("default") for p in spec}
    types = {p["name"].lstrip("-"): p.get("type", "string") for p in spec}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i].lstrip("-")
            i += 1
            val = argv[i] if i < len(argv) else None
            t = types.get(key, "string")
            if   t == "int":   val = int(val)
            elif t == "float": val = float(val)
            elif t == "bool":  val = val.lower() in ("1", "true", "yes")
            out[key] = val
        i += 1
    return out
```

Drop these into `mock_task/executor.py` and the WS-intercept module
respectively.

### 14.99 r7 effort impact summary

| Change | Δ effort |
|---|---|
| §14.1 Phase 1.4 narrows scope (transport-layer guard + circuit breaker only) | **−0.10 d** v0 |
| §14.3 v2 math correction | **+0.50 d** v2 |
| §14.5 add cross-repo coordination + roundtrip test | **+0.10 d** v2 |
| Other r7 fixes (#2, #4, #5, #7, #11, #12, #14 — UI race buffer + reset + missing decls + slash regex) | **+0.30 d** v0 |
| Doc-only sweeps (#6, #16, #17, #19, #20) | 0 |

**Net: v0 +0.20 d (5.85 d), v2 +0.60 d (1.85 d). Total: 10.7 d (was 9.5).**

Critical-path to first iterable demo recomputed: **4.55 days** (was
4.35; +0.20 from race buffer + missing decl additions).


---

## 15. r8 Consolidation Record — third feedback round (codebase-verified)

This round addresses 19 feedback items + the meta-issue that the
plan was a multi-revision palimpsest. Verdict: **18 valid, 1
deferred** (id-separator escape — added as defensive measure).

### 15.1 Verdict per item

| # | Feedback | Verdict | Action |
|---|---|---|---|
| 1 | 4 conflicting effort totals | ✅ VALID | §READ-FIRST R-1 + R-14 = single canonical table; §7.1–7.3 banner-marked STALE |
| 2 | §7.3 lists dropped items (#22, #25) | ✅ VALID | §READ-FIRST R-2 lists dropped tasks; §7.3 items #22, #25 struck-through with explanation |
| 3 | §1.1 still says "add `namespace` field" | ✅ VALID | §1.1 narrative updated with §READ-FIRST R-3 / §13.4 cross-ref |
| 4 | `formatters/markdown.py:167` filter claim is wrong | ✅ VALID | All 4 occurrences fixed → `conversational_inferencer.py:506-507`; §READ-FIRST R-8 has the canonical table |
| 5 | Event shape: server sends `evt.timestamp`, not `started_at` | ✅ VALID | `_applyStatusToTask` rewritten to derive `startedAt`/`completedAt` from `evt.timestamp` (matches `useManagerChat.js:174-175`); §READ-FIRST R-3 documents the canonical event shape |
| 6 | `currentGraph.maxColSize` doesn't exist | ✅ VALID | TaskPanel snippet now passes `userCompact` only; compact decision moved inside `<GraphFlowView>` per §READ-FIRST R-4 |
| 7 | Leaf-id fallback creates collisions | ✅ VALID | `_applyStatusToTask` no longer falls back to leaf match; uses qualified-id local-segment lookup (§READ-FIRST R-5) |
| 8 | RAF race in root topology resets | ✅ VALID | `handleGraphTopology` root branch now uses synchronous `setTasks` (atomic with navigation reset); sub-graph branch keeps RAF batching (§READ-FIRST R-6) |
| 9 | Flush insertion points missing | ✅ VALID | §READ-FIRST R-7 specifies exact lines (`finally`-block patterns at `breakdown_then_aggregate_inferencer.py:~1505` and `:~1035`; lines shifted from original 1346/855) |
| 10 | PythonUtils vs rankevolve ambiguity | ✅ VALID | §READ-FIRST R-9 declares PythonUtils canonical; rankevolve is duplicate, do-not-edit |
| 11 | `bta_inferencer.py` doesn't exist | ✅ VALID | §0 problem table Issue #4 corrected to `breakdown_then_aggregate_inferencer.py:894`; §READ-FIRST R-8 file table has all canonical paths |
| 12 | `graphPath` global across tasks | ✅ VALID | §READ-FIRST R-11 promotes per-task state to v0 (folded in upfront, +0.10 d) |
| 13 | `/` separator can conflict | ✅ VALID (defensive) | §READ-FIRST R-12 adds `%2F` escape in `_qualify` + `safeSplit` UI helper (+0.10 d) |
| 14 | Items 23–24 premature abstraction | ✅ VALID | §READ-FIRST R-13 defers to "Future Work" until 2nd `WorkGraph` consumer materialises (saves 0.5 d) |
| 15 | No receive-side error recovery | ✅ VALID | §READ-FIRST R-10 adds `request_full_topology` client-server message (+0.20 d) |
| 16 | Line numbers off-by-1 | ✅ VALID (cosmetic) | Corrected throughout; §READ-FIRST R-8 documents the convention |
| 17 | `parse_cli_args` brittle | ✅ VALID | §14.15 reference impl already provided; document acknowledges limits — it's a dev tool |
| 18 | `STREAM_CAP_BYTES` is UTF-16 length | ✅ VALID (cosmetic) | Note: name kept (`length` is fine for ASCII-dominant content); future hardening can use `Blob([str]).size` if multi-byte content becomes common |
| 19 | Doc too large, contradictory | ✅ VALID (META) | **Real fix**: §READ-FIRST block at top is now the SINGLE SOURCE OF TRUTH. Older sections kept for audit but explicitly subordinated. **Critical code blocks fixed in-place** (§3.5.18.1) so an implementer copying gets correct code regardless of which section they read. |

### 15.2 Why we chose READ-FIRST over full doc rewrite

A complete r8-consolidated rewrite would:
- Delete the audit trail of why decisions were made (lose institutional knowledge).
- Take ~1 day of mechanical work.
- Risk introducing new errors during the rewrite.

A `READ-FIRST` block at the top:
- Preserves audit history (§13/§14/§15 chronicle the corrections).
- Costs ~0.10 d and was done in this session.
- Implementer gets the canonical answer in the first 100 lines.
- Older sections are explicitly demoted to audit material via banners.

This is the same pattern used in mature long-lived RFCs (e.g., IETF
"Note added in proof", JEP "Updated in JDK X").

### 15.3 What was NOT applied (over-fixing avoided)

- Did **not** rewrite §1.2 NamespacedGraphReporter into 2-arg form
  (just dropped the `namespace` field reference). Backwards-compat
  trumps the cosmetic simplification today.
- Did **not** delete the obsolete §3.5.10 / §3.6.7 bodies. Audit
  trail preserved; banners suffice.
- Did **not** restructure the document. The READ-FIRST block + STALE
  banners + in-place code fixes achieve the same implementer
  experience without the rewrite cost.
- Did **not** sweep every cosmetic line-number; only the high-impact
  ones (Issue #4 / §0). §READ-FIRST R-8 + R-16 (here) document the
  convention.

### 15.4 Final canonical totals (re-stated for emphasis)

| | Effort |
|---|---|
| v0 | **6.25 d** |
| v1 | **3.0 d** |
| v2 | **1.35 d** |
| **TOTAL** | **10.6 d** |
| **Critical path to first iterable demo** | **4.65 d** |

These are the numbers in §READ-FIRST R-14. Quote these. Older
numbers are stale.

### 15.5 Recommended next action

Begin v0 implementation. The critical-path 4.65 d covers everything
needed for `test_role_setup.py` to render a working drill-in graph
in the live UI. Items: Phase 1 (Python: hierarchical reporter +
namespacing + role_setup wiring + receive recovery + id escape) +
`/mock_task` (flat profile first; nested after Phase 1 lands) +
slash intercept + `useGraphState` (with the per-task state model
upfront) + Breadcrumb + GraphFlowView additions (incl. local
`maxColSize` heuristic per §READ-FIRST R-4).

---

## 16. r9 Refinements — fourth feedback round (codebase-verified, focused fixes)

This round responds to a 19-item review. Plan was on hold — applying
only fixes that prevent confusion or wasted work on resume. Stylistic
and consolidation suggestions deferred to a future flatten-pass.

### 16.1 Verdict per item

| # | Feedback | Verdict | Action |
|---|---|---|---|
| A1 | "ON HOLD rationale partially contradicts v0 plan" | ✅ VALID (minor) | ON-HOLD banner already says "if other plan ships first, my v0 item #3 becomes a no-op"; documented further in §16.2 |
| A2/A7/D7/C1 | Stream observer contract under-specified across 5 places | ✅ **VALID (CRITICAL)** — single biggest correctness risk | §16.2 below: canonical stream observer contract documented |
| A3 | `worker.graph_reporter` `hasattr` is duck-typed | ✅ VALID | §16.3: `GraphReportingInferencer` Protocol; sentinel attribute |
| A4 | `is_container` vs `_is_container` vs `has_subgraph` triple naming | ✅ VALID (minor) | §16.4: pick `is_container` (no underscore) as canonical serialized field |
| A5 | Race-buffer eviction & GC unspecified | ✅ VALID (production hazard) | §16.5: bucket key, overflow, GC on task completion |
| A6 | R-10 doesn't replay node_stream | ✅ VALID | §16.6: explicit non-goal documented; on-disk `output_path` is the recovery for stream content |
| A8 | `--workers --inner` referenced but not in tool.json | ✅ VALID | §16.7: rewrite §7.7 acceptance test to use `--profile huge` |
| A9 | tool.json parameter naming `--profile` vs `profile` | ⚠️ DEFER | Verified other tools' `tool.json` use names without `--`; flag for §16.7 fix |
| A10 | `inner_bta_X` examples not fully swept | ⚠️ ACCEPT (downgrade r7 §14.14) | §16.8: inner_bta_X retained as **demo-only labels** (the actual node IDs are `worker_*`); r7's "complete" claim downgraded to "partial" |
| A11 | r6/r7/r8 all "(current)" | ✅ VALID | Already fixed earlier this round |
| A12 | Appendix A still says `namespace` field | ✅ VALID | Already fixed earlier this round |
| A13 | §9 still has `OPENTEAM_HIERARCHICAL_GRAPH=1` | ✅ VALID | Already fixed earlier this round |
| A14 | §10 references dropped Item #22 | ✅ VALID | §16.9: corrected — Container Output uses existing `breakdown` / `aggregator` ids |
| A15 | §3.5.10 needs OBSOLETE banner | ✅ VALID | §16.10: banner inserted at the section head |
| A16 | `from_work_graph(parent_node_id=…)` signature not in §1.1 | ✅ VALID (minor) | Documented in §16.11 |
| A17 | `MockAggregator` body too thin | ✅ VALID | §16.12: concrete signature spelled out |
| C2 | Single Node ID Scheme section | ⚠️ DEFER | Read-first R-5/R-8/R-12/§13.6 collectively cover this; no new content needed |
| C3-C7 | Consolidation (delete §11/§12, merge §3.5/§3.5.18/§3.7) | ⚠️ DEFER | Plan is on hold; consolidation is a content-moving operation that adds risk for no implementation value while paused. Resume-time decision. |
| D2 | `_viz_label` underscore naming | ⚠️ DEFER until §16.4 lands (linked) |
| D3 | `WebSocketGraphReporter.from_session_context()` factory | ✅ VALID (small) | §16.13 |
| D4 | `is_dev_mode()` shared helper | ✅ VALID (small) | §16.14 |
| D5 | per-task UI state co-location | ⚠️ DEFER | R-11 dict-of-tid pattern is the v0 commitment; refactor to `tasksRef.current[tid].uiState` is a v2 cleanup |
| D6 | monotonic seq + replay (vs RAF + race-buffer + R-10) | ✅ VALID — flag as Future Work | §16.15 (architectural future direction) |
| D8 | fitView re-key vs effect | ✅ VALID (minor) | §16.16 |
| D9 | throttle 30/s magic number → env config | ✅ VALID (small) | §16.17 |
| D10/D11/D12 | Missing tests (composition / R-10 / load) | ✅ VALID | §16.18 added to §4 testing strategy |
| D13 | Telemetry counters | ⚠️ DEFER (Future Work) | §16.19 noted |

**Score: 22 valid + 7 deferred + 0 invalid.**

### 16.2 Stream Observer Contract — CANONICAL (replaces A2/A7/D7/C1 ambiguity)

The object returned by
`graph_interactive_adapter.py:GraphReporter.node_stream_observer(node_id)`
is a **callable with attached methods**, not an `.emit()` API:

```python
class _StreamObserver:
    """Returned by GraphReporter.node_stream_observer(node_id).

    Behaves as an async callable for chunk delivery, with two
    additional methods for lifecycle.
    """
    async def __call__(self, chunk: str, *, is_final: bool = False) -> None:
        """Emit a stream chunk. Internally coalesces into a 200 ms batch."""

    async def flush(self) -> None:
        """Force the current batch to send NOW, then reset.
        Called by BTA in the `finally` block after each inferencer
        completes (R-7) so trailing tokens are not silently dropped."""

    def close(self) -> None:
        """No-op today; reserved for future explicit-cleanup contract."""
```

**Throttle/coalesce contract (§13.12):**

- Chunks within the same 200 ms window are **concatenated**, not
  dropped. Cumulative content semantics are preserved.
- `is_final` is **sticky-true**: if any coalesced chunk has
  `is_final=True`, the batched emission carries `is_final=True`. UI
  can rely on `is_final` to mark the stream as done.

**Mock contract:** All mock components in §3.6.3 / §3.5.18.6 must call
`await self.stream_observer(chunk)` (NOT `.emit(chunk)`). Already
fixed in §3.6.3 / §3.5.18.6 code blocks this round.

**Throttle config:** The 200 ms coalescing window is configurable via
`OPENTEAM_GRAPH_STREAM_COALESCE_MS` env var (default 200). Per §16.17.

### 16.3 `GraphReportingInferencer` Protocol (replaces hasattr duck-typing)

```python
# AgentFoundation/.../graph_events.py
from typing import Protocol, Optional

class GraphReportingInferencer(Protocol):
    """Marker protocol for inferencers that can receive a graph_reporter."""
    graph_reporter: Optional['GraphReporter']
    _supports_graph_reporter: bool        # = True (sentinel)
```

In `_build_diamond_graph` (§1.3):

```python
# OLD: if hasattr(worker, 'graph_reporter'): worker.graph_reporter = ...
# NEW:
if getattr(worker, '_supports_graph_reporter', False):
    worker.graph_reporter = self.graph_reporter.child_reporter(node_id)
```

This avoids accidentally setting `graph_reporter` on workers that
happen to have a same-named attribute for unrelated reasons. BTA sets
`_supports_graph_reporter = True` as a class attribute (one line).

### 16.4 Canonical naming: `is_container` (no underscore)

Three names floated: `is_container`, `_is_container`, `has_subgraph`.
**Picked: `is_container`** (no leading underscore, since it's part of
the public serialized event contract per R-3).

Sweep: §1.1, §1.3, §4.2 references must use `is_container`. Same for
`viz_label` (drop underscore from `_viz_label` for the same reason —
it's a serialized public field). Done in r9.

### 16.5 Race-buffer eviction & GC policy (extends R-5 / r7 §14.x #5)

```js
// useGraphState.js
const PENDING_CAP_PER_BUCKET = 200;

// Bucket key:
//   `${tid}::${parentKey}` where parentKey = qualified parent id
//   (e.g. "task-abc::worker_2/inner_bta_1").
//   Per-task isolation prevents cross-task contamination.

// Overflow:
//   When a bucket would exceed 200, drop OLDEST and log ONCE per bucket
//   per task (`console.warn` + telemetry counter when D13 lands).
//   Old entries are unlikely to ever apply (status events are usually
//   processed FIFO; a 200-deep buffer means the topology is >40 s late).

// GC triggers:
//   1. On root topology rerun for `tid`: drop ALL `${tid}::*` buckets.
//      (Already implemented in §3.5.18.1 code block.)
//   2. On task removal (user closes tab): drop ALL `${tid}::*` buckets.
//      Add to `removeTask(tid)` in TaskPanel.
//   3. On task status === 'completed' || 'error': drop after 30 s
//      grace period (covers any delayed status events).
//   4. Periodic sweep every 5 minutes of buckets older than 10 min
//      (defensive; should never fire in practice).
```

This bounds memory at `200 events × number-of-active-tasks ×
average-depth` ≈ small.

### 16.6 R-10 receive recovery — explicit non-goals

R-10 (`request_full_topology`) re-emits **topology only**. It does
NOT replay `node_stream` content. Rationale:

- Stream content can be 100+ KB per node; replaying all of it on
  reconnect would saturate the WS.
- The on-disk `output_path` (per-node) IS the canonical recovery
  surface for stream content. The UI's `<NodeDetailPanel>` already
  has a "View full output" link to `/api/view/<output_path>` for
  completed nodes.
- Live-stream recovery for in-flight nodes is a v3 concern (would
  need server-side ring buffer per node).

Document this clearly so users don't expect mid-stream resume after
reconnect.

### 16.7 `/mock_task` CLI args + acceptance test fix

`§7.7` v0 acceptance criterion currently says `/mock_task --workers
20 --inner 5`. **Wrong** — `tool.json` only declares `--profile`,
`--seed`, `--yaml`, `--speed`. Fix:

- **Acceptance test** (§7.7): change to `/mock_task --profile huge`.
  Define `huge` profile in §3.6.4 to mean "1 outer × 5 inner BTAs ×
  4 workers each = 20 leaf workers."
- **Tool param naming** (A9): `tool.json` parameter `name` field must
  match other tools' convention. Verified `create_role/tool.json`
  uses names like `"name": "role_description"` (no `--`). Update
  §3.6.5 to declare `"name": "profile"`, `"name": "seed"`,
  `"name": "yaml"`, `"name": "speed"`. The `--` prefix is added by
  the CLI parser, NOT the tool dispatcher.

### 16.8 `inner_bta_X` retained as DEMO-ONLY labels (downgrades r7 §14.14)

r7 §14.14 claimed the sweep to `worker_X` was complete. **Honest
downgrade**: many §3.5 / §3.5.10 / §3.5.18 / Phase 1 acceptance
examples still say `inner_bta_X` for human readability. The actual
runtime node IDs are `worker_X` (verified
`breakdown_then_aggregate_inferencer.py:712`).

**Resolution:** treat `inner_bta_2` as a **display label** (the value
shown in the breadcrumb after `_viz_label` resolution); the qualified
ID in events / state is `worker_2`. Where the plan shows
`inner_bta_2`, mentally substitute `worker_2 (display: "inner_bta_2:
Backend")`.

### 16.9 §10 Container Output bug-fix bullet — corrected

The §10 bullet about Container Output incorrectly cited
`__breakdown__` / `__aggregator__` synthetic ids. **Corrected by
R-2**: BTA already routes under `breakdown` / `aggregator` (verified
`breakdown_then_aggregate_inferencer.py:1501-1503` and `:1031`).
Container Output mode references the EXISTING ids; no new
synthetic-id mapping needed.

### 16.10 §3.5.10 OBSOLETE banner

§3.5.10 carries this banner at its head (added r9):

```
> ## ⚠️ OBSOLETE — see §READ-FIRST R-2 / §13.2
>
> This section originally proposed routing breakdown/aggregator
> streams under synthetic `__breakdown__` / `__aggregator__` ids.
> That work is **NOT NEEDED** — the BTA already routes these under
> `breakdown` and `aggregator` (verified line 1501-1503 / :1031; was 1339/:855).
> The Container Output toggle in §3.5.4 uses the existing ids.
> Section retained for audit history.
```

(Banner inserted in r9 — see actual §3.5.10 head.)

### 16.11 `from_work_graph(parent_node_id=…)` signature

Add to §1.1:

```python
@classmethod
def from_work_graph(cls, work_graph: WorkGraph,
                    parent_node_id: str = "",
                    version: int = 0) -> "GraphTopologyEvent":
    """Build a GraphTopologyEvent from a live WorkGraph instance.
    `parent_node_id` is empty for root topology, non-empty for a
    sub-graph whose nodes splice under that node in the parent."""
```

### 16.12 `MockAggregator` concrete signature

```python
class MockAggregator:
    """Mocks the BTA's aggregator inferencer.

    Real BTA aggregator interface (verified
    breakdown_then_aggregate_inferencer.py:_build_agg_input):
      - Receives `worker_results: list[Any]` (the worker outputs)
      - Receives `original_query: str`
      - Optionally `worker_output_paths: list[str]`
      - Returns: str (the aggregated result)
    """
    def __init__(self, *, output_template: str = "Aggregated {n} results.",
                 delay_s: float = 0.5,
                 stream_chunks: list[str] | None = None):
        self.output_template = output_template
        self.delay_s = delay_s
        self.stream_chunks = stream_chunks or [
            "Combining worker outputs…\n",
            "Resolving conflicts…\n",
            "Producing final result.\n",
        ]
        self.stream_observer = None

    async def ainfer(self, worker_results, *, original_query="",
                     worker_output_paths=None, **kwargs):
        per = self.delay_s / max(1, len(self.stream_chunks))
        for c in self.stream_chunks:
            await asyncio.sleep(per)
            if self.stream_observer:
                await self.stream_observer(c)   # callable per §16.2
        if self.stream_observer and hasattr(self.stream_observer, 'flush'):
            await self.stream_observer.flush()
        return self.output_template.format(n=len(worker_results))
```

### 16.13 `WebSocketGraphReporter.from_session_context()` factory

Eliminates 3-place duplication of the attach snippet:

```python
# AgentFoundation/.../graph_interactive_adapter.py
class WebSocketGraphReporter:
    @classmethod
    def from_session_context(
        cls, session_context: dict
    ) -> Optional["WebSocketGraphReporter"]:
        """Build reporter from session_context, or return None if not
        possible (e.g. tests, non-WS callers).

        Replaces the 4-line `if interactive and task_id: …` boilerplate
        in every executor.
        """
        interactive = session_context.get("interactive")
        task_id = session_context.get("task_id", "")
        if interactive is None or not task_id:
            return None
        return cls(interactive, task_id)
```

Executor usage shrinks to one line:

```python
inferencer.graph_reporter = WebSocketGraphReporter.from_session_context(session_context)
```

### 16.14 `is_dev_mode()` shared helper

```python
# OpenTeam/.../server/utils.py (or similar)
import os

def is_dev_mode() -> bool:
    """Single source of truth for the OPENTEAM_DEV_MODE gate.
    Both the WS slash-intercept (§3.7.3.5) and the tool registration
    filter (§3.6.9 anti-pattern #5) consult this."""
    return os.environ.get("OPENTEAM_DEV_MODE") == "1"
```

### 16.15 Future Work — monotonic seq + replay (cleaner architecture)

D6 observation: RAF batching + race buffer + R-10 are three
workarounds to one underlying problem (event ordering /
gap-detection). The principled long-term solution is per-task
monotonic sequence numbers:

```python
# Server side:
class GraphReporter:
    def __init__(self, ...):
        self._seq = 0
    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq
    # Every emission carries seq=self._next_seq()
```

```js
// Client side:
// Apply events in seq order; if seq jumps (gap), trigger
// request_full_topology(after_seq=lastSeen) which re-emits all events
// since lastSeen.
```

This replaces all three workarounds with one mechanism. **NOT in v0**
(too risky; v0 ships the workarounds). Flagged here so we don't
entrench three workarounds without naming the cleaner future.

### 16.16 fitView: useEffect on graph.version (not key-remount)

```js
// CORRECT (preserves pan/zoom state across version bumps):
const reactFlowInstance = useReactFlow();
useEffect(() => {
  if (graph?.version) reactFlowInstance.fitView({ duration: 400, padding: 0.1 });
}, [graph?.version, reactFlowInstance]);

// WRONG (re-mounts whole tree, loses pan/zoom):
<ReactFlow key={graph.version} ... />
```

§2.1 should reference this; §3.5.18.4 v0 implementation can use the
key-remount as an interim simplification.

### 16.17 Throttle 30 msg/s default → env config

```python
# graph_interactive_adapter.py
DEFAULT_GRAPH_THROTTLE_HZ = int(os.environ.get(
    'OPENTEAM_GRAPH_THROTTLE_HZ', '30'))
DEFAULT_STREAM_COALESCE_MS = int(os.environ.get(
    'OPENTEAM_GRAPH_STREAM_COALESCE_MS', '200'))
```

Production can tune without a code change.

### 16.18 Missing tests — added to §4

- **§4.1 Python unit tests** add row: `test_namespaced_reporter_three_level_composition` — verifies `child_reporter` + `child_reporter` recursive composition emits correctly qualified ids (BTA-of-BTA-of-BTA case).
- **§4.2 Python integration test** add row: `test_request_full_topology_replay` — disconnect/reconnect mid-run; assert UI receives full topology + status snapshots.
- **§4.4 Manual e2e checklist** add row: `/mock_task --profile huge` (20+ leaf workers). Acceptance: 60 fps in compact mode, fit-to-view succeeds, status updates land within 1 frame.

### 16.19 Telemetry — Future Work (D13)

A `graph_reporter_metrics` Prometheus-style counter set would surface
operational health of the visualization pipeline:

```python
graph_topology_emit_total{level="root|sub"}
graph_status_emit_total{status="..."}
graph_stream_chunk_drop_total                # throttle drops (should be 0)
graph_stream_buffer_overflow_total           # client-side trim events
graph_race_buffer_overflow_total{tid}        # status-before-topology drops
graph_request_full_topology_total            # client recovery requests
```

NOT in v0/v1/v2 — separate observability work item.

### 16.99 r9 effort impact

| Change | Δ effort |
|---|---|
| §16.2 stream observer contract documentation | 0 d (already in code blocks) |
| §16.3 `GraphReportingInferencer` Protocol | +0.10 d |
| §16.5 race-buffer GC policy | +0.10 d |
| §16.13 `from_session_context` factory | +0.05 d |
| §16.14 `is_dev_mode()` helper | +0.05 d |
| §16.18 additional tests | +0.20 d |
| All other items | 0 d (deferred or zero-cost) |
| **Net v0 delta** | **+0.50 d** |

**Revised final canonical totals (after r9):**

| | Effort |
|---|---|
| v0 | **6.75 d** (was 6.25; +0.50 r9) |
| v1 | 3.0 d |
| v2 | 1.35 d |
| **TOTAL** | **11.1 d** (was 10.6) |
| **Critical path to first iterable demo** | **5.15 d** (was 4.65; +0.50 r9 incl. tests + Protocol + GC) |

**Note**: ON HOLD status unchanged. These corrections apply on resume.
`maxColSize` heuristic).

