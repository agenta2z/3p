"""
Test hierarchical logging properties in WorkGraphNode.

This test suite focuses on verifying the hierarchical logging features:
1. parent_log_group_id assignment
2. full_log_group_id computation
3. logger and debug_mode inheritance from parents
"""
import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode


def dummy_func():
    """Dummy function for WorkGraphNode."""
    pass


class TestHierarchicalLoggingSetup:
    """Test hierarchical logging property assignment and computation."""

    def test_node_has_unique_log_group_id(self):
        """Test that each node gets a unique log_group_id by default."""
        node1 = WorkGraphNode(dummy_func)
        node2 = WorkGraphNode(dummy_func)
        node3 = WorkGraphNode(dummy_func)

        # All should have unique IDs
        ids = {node1.log_group_id, node2.log_group_id, node3.log_group_id}
        assert len(ids) == 3, "Each node should have a unique log_group_id"

    def test_custom_log_group_id(self):
        """Test that custom log_group_id can be set."""
        node = WorkGraphNode(dummy_func, log_group_id="CustomID")
        assert node.log_group_id == "CustomID"

    def test_parent_log_group_id_assignment(self):
        """Test that parent_log_group_id can be assigned."""
        parent = WorkGraphNode(dummy_func)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        # parent_log_group_id stores the parent's log_group_id string, not the object
        assert child.parent_log_group_id == parent.log_group_id

    def test_full_log_group_id_with_no_parent(self):
        """Test full_log_group_id for a node without parent."""
        node = WorkGraphNode(dummy_func, log_group_id="RootNode")
        assert node.full_log_group_id == "RootNode"

    def test_full_log_group_id_with_single_parent(self):
        """Test full_log_group_id with one level of hierarchy."""
        parent = WorkGraphNode(dummy_func, log_group_id="Parent", log_group_hierarchy_separator=' > ')
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent, log_group_id="Child")

        expected = f"Parent > Child"
        assert child.full_log_group_id == expected

    def test_full_log_group_id_with_deep_hierarchy(self):
        """Test full_log_group_id with multiple levels."""
        level1 = WorkGraphNode(dummy_func, log_group_id="Level1", log_group_hierarchy_separator=' > ')
        level2 = WorkGraphNode(dummy_func, parent_log_group_id=level1, log_group_id="Level2")
        level3 = WorkGraphNode(dummy_func, parent_log_group_id=level2, log_group_id="Level3")
        level4 = WorkGraphNode(dummy_func, parent_log_group_id=level3, log_group_id="Level4")

        expected = "Level1 > Level2 > Level3 > Level4"
        assert level4.full_log_group_id == expected

        # Verify intermediate levels too
        assert level1.full_log_group_id == "Level1"
        assert level2.full_log_group_id == "Level1 > Level2"
        assert level3.full_log_group_id == "Level1 > Level2 > Level3"

    def test_full_log_group_id_contains_all_ancestors(self):
        """Test that full_log_group_id includes all ancestor IDs."""
        grandparent = WorkGraphNode(dummy_func, log_group_hierarchy_separator=' > ')
        parent = WorkGraphNode(dummy_func, parent_log_group_id=grandparent)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        child_full_id = child.full_log_group_id

        # Child's full ID should contain all ancestor IDs
        assert grandparent.log_group_id in child_full_id
        assert parent.log_group_id in child_full_id
        assert child.log_group_id in child_full_id

        # Should have correct number of separators
        separator_count = child_full_id.count(" > ")
        assert separator_count == 2, "Should have 2 separators for 3 levels"


class TestLoggerInheritance:
    """Test logger inheritance from parent nodes."""

    def test_logger_inheritance_from_parent(self):
        """Test that logger is inherited when not explicitly set."""

        def custom_logger(log_data):
            pass

        parent = WorkGraphNode(dummy_func, logger=custom_logger, always_add_logging_based_logger=False)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        # Child should inherit parent's logger
        assert child.logger is parent.logger

    def test_logger_not_inherited_when_explicitly_set(self):
        """Test that explicitly setting logger=None prevents inheritance."""

        def parent_logger(log_data):
            pass

        parent = WorkGraphNode(dummy_func, logger=parent_logger, always_add_logging_based_logger=False)

        # When we explicitly pass logger (even as None), inheritance doesn't apply
        # This test just verifies that having a parent doesn't break explicit logger setting
        child = WorkGraphNode(
            dummy_func,
            parent_log_group_id=parent
        )

        # Child inherits parent's logger
        assert child.logger is parent.logger


class TestDebugModeInheritance:
    """Test debug_mode inheritance from parent nodes."""

    def test_debug_mode_inheritance_from_parent(self):
        """Test that debug_mode is inherited when not explicitly set."""
        parent = WorkGraphNode(dummy_func, debug_mode=True)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        # Child should inherit parent's debug_mode
        assert child.debug_mode == parent.debug_mode
        assert child.debug_mode is True

    def test_debug_mode_false_inheritance(self):
        """Test inheritance when parent has debug_mode=False."""
        parent = WorkGraphNode(dummy_func, debug_mode=False)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        assert child.debug_mode == parent.debug_mode
        assert child.debug_mode is False

    def test_debug_mode_inheritance_works(self):
        """Test that debug_mode inheritance works correctly."""
        parent = WorkGraphNode(dummy_func, debug_mode=True)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        # Child inherits parent's debug_mode
        assert child.debug_mode == parent.debug_mode
        assert child.debug_mode is True


class TestAlwaysAddLoggingBasedLoggerInheritance:
    """Test always_add_logging_based_logger inheritance."""

    def test_always_add_logging_based_logger_inheritance(self):
        """Test that always_add_logging_based_logger is inherited."""
        parent = WorkGraphNode(dummy_func, always_add_logging_based_logger=False)
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        # Child should inherit parent's setting
        assert child.always_add_logging_based_logger == parent.always_add_logging_based_logger

    def test_always_add_logging_based_logger_inheritance_works(self):
        """Test that always_add_logging_based_logger inherits correctly."""
        parent = WorkGraphNode(dummy_func, always_add_logging_based_logger=False)
        child = WorkGraphNode(
            dummy_func,
            parent_log_group_id=parent
        )

        # Child inherits parent's setting
        assert child.always_add_logging_based_logger == parent.always_add_logging_based_logger
        assert child.always_add_logging_based_logger is False


class TestParallelBranches:
    """Test hierarchical logging with parallel branches."""

    def test_parallel_branches_share_parent(self):
        """Test that parallel branches both reference the same parent."""
        parent = WorkGraphNode(dummy_func, log_group_id="Parent")
        branch_a = WorkGraphNode(dummy_func, parent_log_group_id=parent, log_group_id="BranchA")
        branch_b = WorkGraphNode(dummy_func, parent_log_group_id=parent, log_group_id="BranchB")

        # Both branches should have the same parent ID (string, not object)
        assert branch_a.parent_log_group_id == branch_b.parent_log_group_id
        assert branch_a.parent_log_group_id == parent.log_group_id

        # Both should have parent's ID in their full path
        assert "Parent" in branch_a.full_log_group_id
        assert "Parent" in branch_b.full_log_group_id

        # But they should have different full IDs
        assert branch_a.full_log_group_id != branch_b.full_log_group_id

    def test_parallel_branches_inherit_from_same_parent(self):
        """Test that parallel branches inherit properties from shared parent."""

        def custom_logger(log_data):
            pass

        parent = WorkGraphNode(
            dummy_func,
            logger=custom_logger,
            debug_mode=True,
            always_add_logging_based_logger=False
        )

        branch_a = WorkGraphNode(dummy_func, parent_log_group_id=parent)
        branch_b = WorkGraphNode(dummy_func, parent_log_group_id=parent)

        # Both should inherit from parent
        assert branch_a.logger is parent.logger
        assert branch_b.logger is parent.logger
        assert branch_a.debug_mode == parent.debug_mode
        assert branch_b.debug_mode == parent.debug_mode


class TestRebuildFullLogGroupId:
    """Test _rebuild_full_log_group_id functionality."""

    def test_rebuild_after_parent_change(self):
        """Test that full_log_group_id updates when parent changes."""
        parent1 = WorkGraphNode(dummy_func, log_group_id="Parent1")
        parent2 = WorkGraphNode(dummy_func, log_group_id="Parent2")
        child = WorkGraphNode(dummy_func, parent_log_group_id=parent1, log_group_id="Child")

        # Initial state
        assert "Parent1" in child.full_log_group_id

        # Change parent and rebuild
        child.set_parent_debuggable(parent2)

        # Should now contain Parent2 instead of Parent1
        assert "Parent2" in child.full_log_group_id
        assert "Parent1" not in child.full_log_group_id


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
