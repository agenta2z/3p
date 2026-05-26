

"""StateGraph — a DAG state machine for workflow tracking.

Unlike WorkGraph/Workflow (which are DAG executors that own the execution loop),
a StateGraph only defines states and transitions. A StateGraphTracker tracks
runtime position in the graph and computes which states are available next.

Components:
  - StateNode(Node): extends the graph Node with state machine semantics
    (dependencies, gates, goto, foreach). Inherits BFS, tree printing.
  - StateGraph: collection of StateNodes. Links Node.next/previous from
    depends_on at construction time.
  - StateGraphTracker: runtime tracking — current state, completed states,
    output variables, goto counts, foreach iteration state. Provides
    start/complete/fail transitions and get_available_next() evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from attr import attrib, attrs

from python_utils.algorithms.graph.node import Node

logger = logging.getLogger(__name__)


@dataclass
class ThreadSpawnRequest:
    """A deferred thread spawn from a __goto__ ... __afterwards__ directive."""
    target_phase: str
    source_phase: str
    wait_duration: str | None = None


# ---------------------------------------------------------------------------
# StateNode
# ---------------------------------------------------------------------------


@attrs(slots=False, eq=False, hash=False)
class StateNode(Node):
    """A node in a state graph — extends Node with state machine semantics.

    The ``id`` field is the primary identifier. ``Node.value`` is set to ``id``
    for display in tree printing / BFS.

    Graph connectivity (``Node.next`` / ``Node.previous``) is built from
    ``depends_on`` by ``StateGraph._link_nodes()`` at construction time.
    """

    id: str = attrib(default="")
    depends_on: list = attrib(factory=list)
    outputs: list = attrib(factory=list)
    # __if__ `var` [__is__ `value`]
    gate_var: str = attrib(default=None)
    gate_value: str = attrib(default=None)  # None = truthy check
    # __go to__ Phase X [__if__ `var` [__is__ `value`]]
    goto_target: str = attrib(default=None)
    goto_condition_var: str = attrib(default=None)
    goto_condition_value: str = attrib(default=None)
    # __for each__ `item` __in__ `collection` [__sequentially__]
    foreach_item_var: str = attrib(default=None)
    foreach_collection_var: str = attrib(default=None)
    foreach_sequential: bool = attrib(default=False)
    # __goto__ Phase X __afterwards__ [__wait__ duration]
    goto_afterwards: bool = attrib(default=False)
    goto_wait_duration: str = attrib(default=None)
    # __branch__ [`var`]
    branch: bool = attrib(default=False)
    branch_source_var: str = attrib(default=None)
    # != polarity inversion for conditions
    goto_condition_negate: bool = attrib(default=False)
    gate_negate: bool = attrib(default=False)

    def __attrs_post_init__(self) -> None:
        if self.value is None:
            self.value = self.id
        super().__attrs_post_init__()

    def __str__(self) -> str:
        return self.id


# ---------------------------------------------------------------------------
# StateGraph
# ---------------------------------------------------------------------------


class StateGraph:
    """Collection of StateNodes with dependency-based linking.

    At construction, builds ``Node.next``/``Node.previous`` edges from
    each node's ``depends_on`` list, so the graph is traversable via
    ``Node.bfs()``, ``Node.str_all_descendants()``, etc.
    """

    def __init__(self, nodes: list[StateNode] | None = None) -> None:
        self.nodes: list[StateNode] = nodes or []
        if self.nodes:
            self._link_nodes()

    def _link_nodes(self) -> None:
        """Build Node.next/previous edges from depends_on IDs."""
        node_map = {n.id: n for n in self.nodes}
        for node in self.nodes:
            for dep_id in node.depends_on:
                dep_node = node_map.get(dep_id)
                if dep_node is not None:
                    dep_node.add_next(node)

    def get_node(self, node_id: str) -> StateNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    @property
    def node_ids(self) -> list[str]:
        return [n.id for n in self.nodes]


# ---------------------------------------------------------------------------
# StateGraphTracker
# ---------------------------------------------------------------------------


@dataclass
class StateGraphTracker:
    """Runtime state tracking for a StateGraph.

    Tracks which states have completed, what outputs are set, and computes
    which states are available next. Provides start/complete/fail transitions.
    """

    graph: StateGraph
    current_state: str | None = None
    state_status: str = "idle"  # idle/running/completed/error
    completed_states: list[str] = field(default_factory=list)
    state_outputs: dict[str, Any] = field(default_factory=dict)
    goto_counts: dict[str, int] = field(default_factory=dict)
    foreach_state: dict[str, dict] = field(default_factory=dict)
    max_goto_iterations: int = 10

    # -- Transitions -------------------------------------------------------

    def start(self, state_id: str) -> None:
        """Mark a state as running."""
        self.current_state = state_id
        self.state_status = "running"
        logger.debug("StateGraphTracker: started %s", state_id)

    def complete(self, state_id: str, **outputs: Any) -> None:
        """Mark a state as completed and record outputs."""
        self.state_status = "completed"
        if state_id not in self.completed_states:
            self.completed_states.append(state_id)
        self.state_outputs.update(outputs)
        logger.debug(
            "StateGraphTracker: completed %s, outputs=%s",
            state_id, list(outputs.keys()),
        )

    def fail(self, state_id: str, error: str = "") -> None:
        """Mark a state as failed."""
        self.state_status = "error"
        logger.debug("StateGraphTracker: failed %s: %s", state_id, error)

    # -- Evaluation --------------------------------------------------------

    def get_available_next(self) -> list[StateNode]:
        """Compute which states are available to run next."""
        truly_completed = self._get_truly_completed()

        # Process __go to__: re-enable target states
        # Skip goto_afterwards nodes — those spawn separate threads via
        # get_pending_thread_spawns(), not inline re-enabling.
        for node in self.graph.nodes:
            if node.id not in truly_completed:
                continue
            if not node.goto_target:
                continue
            if getattr(node, "goto_afterwards", False):
                continue
            if not self._check_condition(
                node.goto_condition_var, node.goto_condition_value,
                negate=getattr(node, "goto_condition_negate", False),
            ):
                continue
            goto_key = f"{node.id}->{node.goto_target}"
            if self.goto_counts.get(goto_key, 0) >= self.max_goto_iterations:
                continue
            truly_completed.discard(node.goto_target)

        # Find available states
        available: list[StateNode] = []
        for node in self.graph.nodes:
            if node.id in truly_completed:
                continue
            if self.current_state == node.id:
                continue
            if not all(d in truly_completed for d in node.depends_on):
                continue
            if node.gate_var and not self._check_condition(
                node.gate_var, node.gate_value,
                negate=getattr(node, "gate_negate", False),
            ):
                continue
            if node.foreach_collection_var:
                collection = self.state_outputs.get(node.foreach_collection_var)
                if collection and not isinstance(collection, list):
                    collection = [collection]
                if not collection:
                    continue
            available.append(node)

        return available

    def get_missing_outputs(self) -> dict[str, list[str]]:
        """Check which completed states have missing outputs."""
        missing: dict[str, list[str]] = {}
        for node in self.graph.nodes:
            if node.id in self.completed_states and node.outputs:
                m = [o for o in node.outputs if o not in self.state_outputs]
                if m:
                    missing[node.id] = m
        return missing

    def get_pending_thread_spawns(self) -> list[ThreadSpawnRequest]:
        """Return deferred thread spawns from completed nodes with goto_afterwards=True."""
        spawns: list[ThreadSpawnRequest] = []
        truly_completed = self._get_truly_completed()
        for node in self.graph.nodes:
            if node.id not in truly_completed:
                continue
            if not getattr(node, "goto_afterwards", False):
                continue
            if not node.goto_target:
                continue
            if not self._check_condition(
                node.goto_condition_var, node.goto_condition_value,
                negate=getattr(node, "goto_condition_negate", False),
            ):
                continue
            goto_key = f"{node.id}->{node.goto_target}"
            if self.goto_counts.get(goto_key, 0) >= self.max_goto_iterations:
                continue
            spawns.append(ThreadSpawnRequest(
                target_phase=node.goto_target,
                source_phase=node.id,
                wait_duration=getattr(node, "goto_wait_duration", None),
            ))
        return spawns

    def get_branch_items(self, node_id: str) -> list[Any] | None:
        """For branch nodes, look up the source variable in state_outputs."""
        node = self.graph.get_node(node_id)
        if node is None:
            return None
        source_var = getattr(node, "branch_source_var", None)
        if source_var:
            items = self.state_outputs.get(source_var)
            if items is not None and not isinstance(items, list):
                items = [items]
            return items
        if getattr(node, "branch", False):
            for dep_id in node.depends_on:
                dep_node = self.graph.get_node(dep_id)
                if dep_node and dep_node.outputs:
                    for out_name in dep_node.outputs:
                        val = self.state_outputs.get(out_name)
                        if isinstance(val, list):
                            return val
        return None

    @property
    def status(self) -> str:
        """Overall status: idle, running, completed, or error."""
        if self.state_status == "running":
            return "running"
        if self.state_status == "error":
            return "error"
        if not self.completed_states and self.current_state is None:
            return "idle"
        if not self.get_available_next() and self.current_state is None:
            return "completed"
        return "idle"

    # -- Serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_state": self.current_state,
            "state_status": self.state_status,
            "completed_states": list(self.completed_states),
            "state_outputs": dict(self.state_outputs),
            "goto_counts": dict(self.goto_counts),
            "foreach_state": dict(self.foreach_state),
            "max_goto_iterations": self.max_goto_iterations,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], graph: StateGraph
    ) -> StateGraphTracker:
        return cls(
            graph=graph,
            current_state=data.get("current_state"),
            state_status=data.get("state_status", "idle"),
            completed_states=data.get("completed_states", []),
            state_outputs=data.get("state_outputs", {}),
            goto_counts=data.get("goto_counts", {}),
            foreach_state=data.get("foreach_state", {}),
            max_goto_iterations=data.get("max_goto_iterations", 10),
        )

    # -- Internal helpers --------------------------------------------------

    def _get_truly_completed(self) -> set[str]:
        """States that are completed AND have all declared outputs set."""
        truly: set[str] = set()
        for node in self.graph.nodes:
            if node.id in self.completed_states:
                if not node.outputs or all(
                    o in self.state_outputs for o in node.outputs
                ):
                    truly.add(node.id)
        return truly

    def _check_condition(
        self, var: str | None, value: str | None, negate: bool = False,
    ) -> bool:
        """Check a gate/goto condition against state_outputs."""
        if not var:
            return True
        actual = self.state_outputs.get(var)
        if value is not None:
            result = str(actual) == value
        else:
            result = bool(actual)
        return (not result) if negate else result
