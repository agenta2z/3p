"""Expansion data types for dynamic Workflow and WorkGraph expansion.

Defines signal types returned by steps/nodes to trigger expansion,
a subgraph specification for WorkGraph expansion, and a serializable
record type for checkpoint persistence.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Set, Union


@dataclass
class ExpansionResult:
    """Return type from a Workflow step to signal dynamic expansion.

    Fields:
        result: The step's actual output (passed downstream, to hooks).
        new_steps: Steps to insert after the current step.
        expansion_id: Optional identifier for checkpoint reconstruction via registry.
        seed: Arbitrary serializable value for seed-based reconstruction (Req 25).
        reconstruct_from_seed: Module-level callable (not lambda/closure) that
            accepts seed and returns identical new_steps. Stored by qualified name.
        mode: 'follow' (default) saves emitter result normally;
              'splice' skips saving emitter result, first expanded step gets
              emitter's original input (Req 26).
    """
    result: Any
    new_steps: Sequence[Callable]
    expansion_id: Optional[str] = None
    seed: Optional[Any] = None
    reconstruct_from_seed: Optional[Callable] = None
    mode: Literal['follow', 'splice'] = 'follow'


@dataclass
class SubgraphSpec:
    """Specification for a subgraph to attach to a WorkGraph node.

    Fields:
        nodes: All nodes in the subgraph (including internal nodes).
        entry_nodes: Nodes that connect to the expanding node's next list.
    """
    nodes: List[Any]  # List[WorkGraphNode] — Any to avoid circular import
    entry_nodes: List[Any]

    def __post_init__(self):
        entry_ids = {id(n) for n in self.entry_nodes}
        node_ids = {id(n) for n in self.nodes}
        if not entry_ids.issubset(node_ids):
            raise ValueError(
                "All entry_nodes must be present in nodes list. "
                f"Missing: {len(entry_ids - node_ids)} entry nodes not in nodes."
            )
        # Validate name uniqueness within the subgraph's own nodes list (Req 17.1)
        # All subgraph nodes must have non-None names for expansion tracking.
        seen_names = set()
        for n in self.nodes:
            if n.name is None:
                raise ValueError(
                    "All subgraph nodes must have non-None names for expansion tracking."
                )
            if n.name in seen_names:
                raise ValueError(f"Duplicate node name in subgraph: {n.name!r}")
            seen_names.add(n.name)

    def to_serializable_obj(self) -> Dict[str, Any]:
        """Produce a dict for observability/debugging.

        Note: This dict is NOT sufficient for reconstructing executable nodes.
        Use seed-based or registry-based reconstruction for resume.
        """
        return {
            'nodes': [n.to_serializable_obj() for n in self.nodes],
            'entry_node_names': [n.name for n in self.entry_nodes],
        }


@dataclass
class GraphExpansionResult:
    """Return type from a WorkGraphNode to signal dynamic expansion.

    Fields:
        result: The node's actual output (passed downstream, to hooks).
        subgraph: The subgraph specification to attach.
        expansion_id: Optional identifier for checkpoint reconstruction.
        seed: Arbitrary serializable value for seed-based reconstruction (Req 25).
        reconstruct_from_seed: Module-level callable for seed-based reconstruction.
        attach_mode: 'insert' rewires non-leaf topology (Req 33).
            On leaf nodes, behavior is unchanged from default.
        include_self: NextNodesSelector-like control for self-loop (Req 23).
        include_others: NextNodesSelector-like control for downstream selection (Req 23).
    """
    result: Any
    subgraph: SubgraphSpec
    expansion_id: Optional[str] = None
    seed: Optional[Any] = None
    reconstruct_from_seed: Optional[Callable] = None
    attach_mode: Literal['insert'] = 'insert'
    include_self: bool = False
    include_others: Union[bool, Set[str]] = True


@dataclass
class ExpansionRecord:
    """Serializable record of an expansion decision for checkpoint persistence.

    Fields:
        after_step_name: Name of the step AFTER which insertion happened.
            Using name instead of index avoids cumulative offset fragility
            during nested expansion reconstruction (S1 fix).
        expansion_id: Registry lookup key.
        num_steps: Number of steps inserted.
        seed: Persisted seed value for seed-based reconstruction (Req 25).
        factory_module: __module__ of reconstruct_from_seed (Req 25).
        factory_qualname: __qualname__ of reconstruct_from_seed (Req 25).
    """
    after_step_name: str
    expansion_id: Optional[str]
    num_steps: int
    seed: Optional[Any] = None
    factory_module: Optional[str] = None
    factory_qualname: Optional[str] = None
