"""
Test the full_log_group_id property getter.

This test verifies that the property getter provides a clean, read-only
interface to the hierarchical log group ID.
"""
import pytest
from python_utils.common_objects.debuggable import Debuggable


class TestFullLogGroupIdProperty:
    """Test suite for full_log_group_id property getter."""

    def test_simple_property_access(self):
        """Test simple property access."""
        obj = Debuggable(log_group_id="TestObject", log_time=False, log_group_hierarchy_separator=' > ')

        assert obj.full_log_group_id == "TestObject"
        assert isinstance(obj.full_log_group_id, str)

    def test_property_with_parent_hierarchy(self):
        """Test property with parent hierarchy."""
        parent = Debuggable(log_group_id="Parent", log_time=False, log_group_hierarchy_separator=' > ')
        child = Debuggable(
            parent_log_group_id="Parent",
            log_group_id="Child",
            log_time=False,
            log_group_hierarchy_separator=' > '
        )

        assert parent.full_log_group_id == "Parent"
        assert child.full_log_group_id == "Parent > Child"

    def test_deep_hierarchy_property(self):
        """Test property in deep hierarchy (3 levels)."""
        l1 = Debuggable(log_group_id="L1", log_time=False, log_group_hierarchy_separator=' > ')
        l2 = l1.create_child_debuggable(Debuggable, log_group_id="L2")
        l3 = l2.create_child_debuggable(Debuggable, log_group_id="L3")

        assert l1.full_log_group_id == "L1"
        assert l2.full_log_group_id == "L1 > L2"
        assert l3.full_log_group_id == "L1 > L2 > L3"

    def test_property_in_string_formatting(self):
        """Test using property in string formatting."""
        obj = Debuggable(log_group_id="Agent", log_time=False, log_group_hierarchy_separator=' > ')
        child = obj.create_child_debuggable(Debuggable, log_group_id="Node")

        message = f"Logging from {child.full_log_group_id}"

        assert message == "Logging from Agent > Node"

    def test_property_is_read_only(self):
        """Test that property is read-only (cannot be set)."""
        obj = Debuggable(log_group_id="TestObject", log_time=False)

        with pytest.raises(AttributeError, match="property.*has no setter"):
            obj.full_log_group_id = "NewValue"

    def test_property_equals_private_attribute(self):
        """Test that property returns same value as private attribute."""
        obj = Debuggable(log_group_id="TestObject", log_time=False)

        assert obj.full_log_group_id == obj._full_log_group_id

    def test_property_with_custom_separator(self):
        """Test property with custom hierarchy separator."""
        parent = Debuggable(
            log_group_id="Root",
            log_group_hierarchy_separator=" :: ",
            log_time=False
        )
        # Child needs explicit separator (not auto-inherited by create_child_debuggable)
        child = parent.create_child_debuggable(
            Debuggable,
            log_group_id="Child",
            log_group_hierarchy_separator=" :: "
        )

        assert child.full_log_group_id == "Root :: Child"

    def test_property_with_disabled_hierarchy(self):
        """Test property when hierarchy is disabled."""
        child = Debuggable(
            parent_log_group_id="Parent",
            log_group_id="Child",
            full_log_group_id_include_hierarchy=False,
            log_time=False
        )

        # When hierarchy is disabled, should just be log_group_id
        assert child.full_log_group_id == "Child"

    def test_property_with_auto_generated_id(self):
        """Test property with auto-generated log_group_id."""
        obj = Debuggable(log_time=False)

        # Should have auto-generated ID
        assert obj.full_log_group_id.startswith("Debuggable_")
        assert len(obj.full_log_group_id) > len("Debuggable_")

    def test_property_used_in_create_child_debuggable(self):
        """Test that create_child_debuggable uses the property internally."""
        parent = Debuggable(log_group_id="Parent", log_time=False, log_group_hierarchy_separator=' > ')
        child = parent.create_child_debuggable(Debuggable, log_group_id="Child")

        # The child should have parent's full_log_group_id as parent_log_group_id
        assert child.parent_log_group_id == parent.full_log_group_id
        assert child.full_log_group_id == "Parent > Child"

    def test_property_consistency_across_hierarchy(self):
        """Test property consistency in complex hierarchy."""
        root = Debuggable(log_group_id="Root", log_time=False, log_group_hierarchy_separator=' > ')
        middle = root.create_child_debuggable(Debuggable, log_group_id="Middle")
        leaf = middle.create_child_debuggable(Debuggable, log_group_id="Leaf")

        # Verify each level
        assert root.full_log_group_id == "Root"
        assert middle.full_log_group_id == "Root > Middle"
        assert leaf.full_log_group_id == "Root > Middle > Leaf"

        # Verify parent_log_group_id uses property
        assert middle.parent_log_group_id == root.full_log_group_id
        assert leaf.parent_log_group_id == middle.full_log_group_id

    def test_property_type_hint(self):
        """Test that property returns string type."""
        obj = Debuggable(log_group_id="Test", log_time=False)

        # Property should always return string
        result = obj.full_log_group_id
        assert isinstance(result, str)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
