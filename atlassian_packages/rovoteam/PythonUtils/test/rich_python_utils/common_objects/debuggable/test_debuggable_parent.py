"""
Test passing Debuggable instance as parent_log_group_id.

This test verifies that parent_log_group_id can accept both string IDs
and Debuggable instances, with automatic conversion to full hierarchical ID.
"""
import pytest
from python_utils.common_objects.debuggable import Debuggable


class Agent(Debuggable):
    """Test agent class."""
    pass


class WorkGraphNode(Debuggable):
    """Test node class."""
    pass


class TestDebuggableParentObject:
    """Test suite for passing Debuggable instances as parent_log_group_id."""

    def test_string_parent_vs_object_parent(self):
        """Test that string ID and Debuggable object produce same hierarchy."""
        parent = Agent(log_group_id="MainAgent", log_time=False, log_group_hierarchy_separator=' > ')

        # Method 1: Using string ID
        child_with_string = WorkGraphNode(
            parent_log_group_id="MainAgent",
            log_group_id="Node1",
            log_time=False,
            log_group_hierarchy_separator=' > '
        )

        # Method 2: Using Debuggable instance
        child_with_object = WorkGraphNode(
            parent_log_group_id=parent,
            log_group_id="Node2",
            log_time=False
        )

        # Both should have same parent in hierarchy
        assert child_with_string.full_log_group_id == "MainAgent > Node1"
        assert child_with_object.full_log_group_id == "MainAgent > Node2"
        assert child_with_string.parent_log_group_id == child_with_object.parent_log_group_id

    def test_deep_hierarchy_with_object_parents(self):
        """Test deep hierarchy using Debuggable parent objects."""
        level1 = Agent(log_group_id="L1", log_time=False, log_group_hierarchy_separator=' > ')
        level2 = WorkGraphNode(parent_log_group_id=level1, log_group_id="L2", log_time=False)
        level3 = Agent(parent_log_group_id=level2, log_group_id="L3", log_time=False)

        assert level1.full_log_group_id == "L1"
        assert level2.full_log_group_id == "L1 > L2"
        assert level3.full_log_group_id == "L1 > L2 > L3"

        # Verify parent IDs are strings
        assert isinstance(level2.parent_log_group_id, str)
        assert isinstance(level3.parent_log_group_id, str)

    def test_complex_parent_hierarchy(self):
        """Test parent with existing hierarchy."""
        # Parent already has a hierarchy
        complex_parent = Agent(
            parent_log_group_id="Root",
            log_group_id="MiddleAgent",
            log_time=False,
            log_group_hierarchy_separator=' > '
        )
        assert complex_parent.full_log_group_id == "Root > MiddleAgent"

        # Pass the complex parent as an object
        child = WorkGraphNode(
            parent_log_group_id=complex_parent,  # Automatically gets "Root > MiddleAgent"
            log_group_id="LeafNode",
            log_time=False
        )

        assert child.full_log_group_id == "Root > MiddleAgent > LeafNode"
        assert child.parent_log_group_id == "Root > MiddleAgent"

    def test_parent_converted_to_string(self):
        """Test that parent_log_group_id is converted to string after init."""
        parent_obj = Agent(log_group_id="ParentAgent", log_time=False)
        child_obj = WorkGraphNode(
            parent_log_group_id=parent_obj,
            log_group_id="ChildNode",
            log_time=False
        )

        # After init, parent_log_group_id should be a string
        assert isinstance(child_obj.parent_log_group_id, str)
        assert child_obj.parent_log_group_id == "ParentAgent"

    def test_mix_string_and_object_parents(self):
        """Test mix of string and object parents in same hierarchy."""
        root = Agent(log_group_id="Root", log_time=False, log_group_hierarchy_separator=' > ')

        # Child 1: uses string
        child1 = WorkGraphNode(
            parent_log_group_id="Root",
            log_group_id="Child1",
            log_time=False,
            log_group_hierarchy_separator=' > '
        )

        # Child 2: uses object
        child2 = WorkGraphNode(
            parent_log_group_id=root,
            log_group_id="Child2",
            log_time=False
        )

        # Grandchild of child1: uses object
        grandchild1 = Agent(
            parent_log_group_id=child1,
            log_group_id="GrandChild1",
            log_time=False
        )

        # Grandchild of child2: uses string
        grandchild2 = Agent(
            parent_log_group_id=child2.full_log_group_id,
            log_group_id="GrandChild2",
            log_time=False,
            log_group_hierarchy_separator=' > '
        )

        assert child1.full_log_group_id == "Root > Child1"
        assert child2.full_log_group_id == "Root > Child2"
        assert grandchild1.full_log_group_id == "Root > Child1 > GrandChild1"
        assert grandchild2.full_log_group_id == "Root > Child2 > GrandChild2"

    def test_none_parent_still_works(self):
        """Test that None parent (root level) still works."""
        root_obj = Agent(
            parent_log_group_id=None,
            log_group_id="RootAgent",
            log_time=False
        )

        assert root_obj.full_log_group_id == "RootAgent"
        assert root_obj.parent_log_group_id is None

    def test_object_parent_with_create_child_debuggable(self):
        """Test that create_child_debuggable works with object parents."""
        parent = Agent(log_group_id="Parent", log_time=False, log_group_hierarchy_separator=' > ')
        child = parent.create_child_debuggable(WorkGraphNode, log_group_id="Child")

        # create_child_debuggable uses parent.full_log_group_id internally
        assert child.full_log_group_id == "Parent > Child"
        assert child.parent_log_group_id == "Parent"

    def test_object_parent_captures_full_path(self):
        """Test that object parent captures full hierarchical path, not just log_group_id."""
        # Create a parent with hierarchy
        grandparent = Agent(log_group_id="GrandParent", log_time=False, log_group_hierarchy_separator=' > ')
        parent = Agent(parent_log_group_id=grandparent, log_group_id="Parent", log_time=False)

        # Using object parent (CORRECT - gets full path)
        child_with_object = WorkGraphNode(
            parent_log_group_id=parent,  # Uses parent.full_log_group_id = "GrandParent > Parent"
            log_group_id="Child",
            log_time=False
        )

        # Using just the log_group_id (WRONG - loses GrandParent)
        child_with_string = WorkGraphNode(
            parent_log_group_id=parent.log_group_id,  # Only "Parent"
            log_group_id="Child2",
            log_time=False,
            log_group_hierarchy_separator=' > '
        )

        # Object parent should capture full hierarchy
        assert child_with_object.full_log_group_id == "GrandParent > Parent > Child"

        # String using just log_group_id loses grandparent
        assert child_with_string.full_log_group_id == "Parent > Child2"

        # Verify the difference
        assert child_with_object.parent_log_group_id == "GrandParent > Parent"
        assert child_with_string.parent_log_group_id == "Parent"

    def test_type_checking_parent_log_group_id(self):
        """Test that parent_log_group_id accepts Union[str, Debuggable]."""
        # Test with string
        child1 = Agent(parent_log_group_id="StringParent", log_group_id="Child1", log_time=False)
        assert isinstance(child1.parent_log_group_id, str)

        # Test with Debuggable object
        parent_obj = Agent(log_group_id="ObjectParent", log_time=False)
        child2 = Agent(parent_log_group_id=parent_obj, log_group_id="Child2", log_time=False)
        assert isinstance(child2.parent_log_group_id, str)

        # Test with None
        child3 = Agent(parent_log_group_id=None, log_group_id="Child3", log_time=False)
        assert child3.parent_log_group_id is None


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
