"""Property-based tests for WorkGraph and WorkGraphNode serialization.

This module contains property-based tests using hypothesis to verify
the WorkGraph DAG structure preservation during serialization.

**Feature: serializable-mixin, Property 8: WorkGraph DAG Structure Preservation**
**Validates: Requirements 5.1, 5.3, 5.4**
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from hypothesis import given, strategies as st, settings, assume
import pytest

from python_utils.common_objects.workflow.workgraph import (
    WorkGraphNode,
    WorkGraph,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


# Strategies for generating test data
name_strategy = st.text(
    min_size=1, 
    max_size=20, 
    alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        blacklist_characters='\x00'
    )
)

max_repeat_strategy = st.integers(min_value=1, max_value=10)
wait_time_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def workgraph_node_strategy(draw):
    """Generate WorkGraphNode instances with basic configuration."""
    name = draw(name_strategy)
    max_repeat = draw(max_repeat_strategy)
    min_repeat_wait = draw(wait_time_strategy)
    max_repeat_wait = draw(st.floats(
        min_value=min_repeat_wait, 
        max_value=min_repeat_wait + 1.0,
        allow_nan=False,
        allow_infinity=False
    ))
    
    # Use a simple lambda as value
    node = WorkGraphNode(
        name=name,
        value=lambda x: x,  # Simple identity function
        max_repeat=max_repeat,
        min_repeat_wait=min_repeat_wait,
        max_repeat_wait=max_repeat_wait,
        enable_result_save=False,
    )
    return node


@st.composite
def simple_dag_strategy(draw):
    """Generate a simple DAG with 2-4 nodes in a chain."""
    num_nodes = draw(st.integers(min_value=2, max_value=4))
    
    # Generate unique names
    names = []
    for i in range(num_nodes):
        name = draw(name_strategy)
        # Ensure unique names by appending index
        names.append(f"{name}_{i}")
    
    # Create nodes
    nodes = []
    for i, name in enumerate(names):
        node = WorkGraphNode(
            name=name,
            value=lambda x: x,
            max_repeat=1,
            enable_result_save=False,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        nodes.append(node)
    
    # Connect nodes in a chain
    for i in range(len(nodes) - 1):
        nodes[i].add_next(nodes[i + 1])
    
    return nodes


# **Feature: serializable-mixin, Property 8: WorkGraph DAG Structure Preservation**
# **Validates: Requirements 5.1, 5.3, 5.4**
@settings(max_examples=100)
@given(node=workgraph_node_strategy())
def test_workgraph_node_serialization_preserves_config(node: WorkGraphNode):
    """Property: For any WorkGraphNode, to_serializable_obj() SHALL return
    a dict containing node configuration that preserves name and settings.
    
    This validates that node configuration is properly serialized.
    """
    serializable_obj = node.to_serializable_obj()
    
    # Verify basic structure
    assert '_type' in serializable_obj, "Missing _type field"
    assert '_module' in serializable_obj, "Missing _module field"
    assert 'name' in serializable_obj, "Missing name field"
    assert 'config' in serializable_obj, "Missing config field"
    
    # Verify name is preserved
    assert serializable_obj['name'] == node.name, f"Name mismatch: {serializable_obj['name']} != {node.name}"
    
    # Verify config values are preserved
    config = serializable_obj['config']
    assert config['max_repeat'] == node.max_repeat, f"max_repeat mismatch"
    assert config['min_repeat_wait'] == node.min_repeat_wait, f"min_repeat_wait mismatch"
    assert config['max_repeat_wait'] == node.max_repeat_wait, f"max_repeat_wait mismatch"


# **Feature: serializable-mixin, Property 8: WorkGraph DAG Structure Preservation**
# **Validates: Requirements 5.1, 5.3, 5.4**
@settings(max_examples=100)
@given(nodes=simple_dag_strategy())
def test_workgraph_node_serialization_preserves_connections(nodes: List[WorkGraphNode]):
    """Property: For any WorkGraphNode with connections, to_serializable_obj() SHALL
    preserve the next_names and previous_names lists.
    
    This validates that DAG connections are properly serialized.
    """
    for i, node in enumerate(nodes):
        serializable_obj = node.to_serializable_obj()
        
        # Verify connection lists exist
        assert 'next_names' in serializable_obj, "Missing next_names field"
        assert 'previous_names' in serializable_obj, "Missing previous_names field"
        
        # Verify next connections
        expected_next_names = [n.name for n in (node.next or [])]
        assert serializable_obj['next_names'] == expected_next_names, \
            f"next_names mismatch for node {node.name}: {serializable_obj['next_names']} != {expected_next_names}"
        
        # Verify previous connections
        expected_previous_names = [n.name for n in (node.previous or [])]
        assert serializable_obj['previous_names'] == expected_previous_names, \
            f"previous_names mismatch for node {node.name}: {serializable_obj['previous_names']} != {expected_previous_names}"


# **Feature: serializable-mixin, Property 8: WorkGraph DAG Structure Preservation**
# **Validates: Requirements 5.1, 5.3, 5.4**
@settings(max_examples=100)
@given(nodes=simple_dag_strategy())
def test_workgraph_serialization_preserves_dag_structure(nodes: List[WorkGraphNode]):
    """Property: For any WorkGraph with start nodes and connections, 
    to_serializable_obj() SHALL preserve the DAG structure without infinite loops.
    
    This validates that the entire graph structure is properly serialized.
    """
    # Create a WorkGraph with the first node as start node
    graph = WorkGraph(
        start_nodes=[nodes[0]],
        enable_result_save=False,
    )
    
    serializable_obj = graph.to_serializable_obj()
    
    # Verify basic structure
    assert 'version' in serializable_obj, "Missing version field"
    assert 'start_node_names' in serializable_obj, "Missing start_node_names field"
    assert 'nodes' in serializable_obj, "Missing nodes field"
    
    # Verify start nodes are preserved
    expected_start_names = [n.name for n in graph.start_nodes]
    assert serializable_obj['start_node_names'] == expected_start_names, \
        f"start_node_names mismatch: {serializable_obj['start_node_names']} != {expected_start_names}"
    
    # Verify all nodes are serialized (no infinite loops)
    serialized_node_names = [n['name'] for n in serializable_obj['nodes']]
    expected_node_names = [n.name for n in nodes]
    
    # All nodes should be serialized exactly once
    assert len(serialized_node_names) == len(expected_node_names), \
        f"Node count mismatch: {len(serialized_node_names)} != {len(expected_node_names)}"
    
    # All expected nodes should be present
    for name in expected_node_names:
        assert name in serialized_node_names, f"Missing node: {name}"


# **Feature: serializable-mixin, Property 8: WorkGraph DAG Structure Preservation**
# **Validates: Requirements 5.1, 5.3, 5.4**
@settings(max_examples=100)
@given(node=workgraph_node_strategy())
def test_workgraph_node_value_reference_handling(node: WorkGraphNode):
    """Property: For any WorkGraphNode with a callable value, to_serializable_obj()
    SHALL store a reference identifier or None for non-serializable callables.
    
    This validates that callable values are handled correctly during serialization.
    """
    serializable_obj = node.to_serializable_obj()
    
    # value_ref should be present
    assert 'value_ref' in serializable_obj, "Missing value_ref field"
    
    # For lambda functions, value_ref should be None (lambdas don't have proper __name__)
    # For named functions, it should be a string reference
    value_ref = serializable_obj['value_ref']
    if value_ref is not None:
        assert isinstance(value_ref, str), f"value_ref should be string or None, got {type(value_ref)}"
        assert '.' in value_ref, f"value_ref should be in 'module.name' format, got {value_ref}"


if __name__ == '__main__':
    print("Running property-based tests for WorkGraph serialization...")
    print()
    
    tests = [
        ("WorkGraphNode serialization preserves config",
         test_workgraph_node_serialization_preserves_config),
        ("WorkGraphNode serialization preserves connections",
         test_workgraph_node_serialization_preserves_connections),
        ("WorkGraph serialization preserves DAG structure",
         test_workgraph_serialization_preserves_dag_structure),
        ("WorkGraphNode value reference handling",
         test_workgraph_node_value_reference_handling),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}")
            print(f"  Error: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll property-based tests passed! ✓")
