"""
Test hierarchical logging functionality in Debuggable class.

This test demonstrates how hierarchical logging can be used with Agent-like
and WorkGraphNode-like classes to trace execution through task graphs.
"""
import pytest
from python_utils.common_objects.debuggable import Debuggable


class MockAgent(Debuggable):
    """Simplified Agent for testing hierarchical logging."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_group_hierarchy_separator = ' > '


    def create_action_node(self, action_name):
        """Create a WorkGraphNode with hierarchical logging."""
        return self.create_child_debuggable(
            MockWorkGraphNode,
            log_group_id=f"ActionNode_{action_name}"
        )


class MockWorkGraphNode(Debuggable):
    """Simplified WorkGraphNode for testing hierarchical logging."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_log = []
        self.log_group_hierarchy_separator = ' > '

    def execute(self, action_name):
        """Execute the node and log progress."""
        self.log_info(f"Starting execution of {action_name}", "NodeExecution")
        self.execution_log.append(f"start:{action_name}")

        self.log_debug(f"Processing {action_name}...", "NodeProcessing")
        self.execution_log.append(f"process:{action_name}")

        self.log_info(f"Completed execution of {action_name}", "NodeExecution")
        self.execution_log.append(f"complete:{action_name}")


class TestHierarchicalLogging:
    """Test suite for hierarchical logging with Agent and WorkGraphNode patterns."""

    def test_agent_initialization(self):
        """Test that agent can be initialized with log_group_id."""
        agent = MockAgent(
            log_group_id="MainAgent",
            debug_mode=True,
            log_time=False
        )

        assert agent.log_group_id == "MainAgent"
        assert agent.full_log_group_id == "MainAgent"
        assert agent.debug_mode is True

    def test_sequential_action_nodes(self):
        """Test creating sequential action nodes with proper hierarchy."""
        agent = MockAgent(log_group_id="MainAgent", log_time=False)

        search_node = agent.create_action_node("SearchWeb")
        extract_node = agent.create_action_node("ExtractData")
        summarize_node = agent.create_action_node("Summarize")

        # Verify hierarchy
        assert search_node.full_log_group_id == "MainAgent > ActionNode_SearchWeb"
        assert extract_node.full_log_group_id == "MainAgent > ActionNode_ExtractData"
        assert summarize_node.full_log_group_id == "MainAgent > ActionNode_Summarize"

        # Verify parent IDs
        assert search_node.parent_log_group_id == "MainAgent"
        assert extract_node.parent_log_group_id == "MainAgent"
        assert summarize_node.parent_log_group_id == "MainAgent"

    def test_node_execution_logging(self):
        """Test that nodes can execute and log properly."""
        agent = MockAgent(log_group_id="MainAgent", log_time=False, debug_mode=True)
        search_node = agent.create_action_node("SearchWeb")

        search_node.execute("SearchWeb")

        # Verify execution log
        assert search_node.execution_log == [
            "start:SearchWeb",
            "process:SearchWeb",
            "complete:SearchWeb"
        ]

    def test_parallel_branched_agents(self):
        """Test creating parallel branched agents with proper hierarchy."""
        agent = MockAgent(log_group_id="MainAgent", log_time=False)
        compare_action = agent.create_action_node("CompareRecipes")

        # Create branched agents (children of the action node)
        branch1 = compare_action.create_child_debuggable(
            MockAgent,
            log_group_id="BranchedAgent_Starbucks"
        )
        branch2 = compare_action.create_child_debuggable(
            MockAgent,
            log_group_id="BranchedAgent_Local"
        )

        # Verify hierarchy
        expected_branch1 = "MainAgent > ActionNode_CompareRecipes > BranchedAgent_Starbucks"
        expected_branch2 = "MainAgent > ActionNode_CompareRecipes > BranchedAgent_Local"

        assert branch1.full_log_group_id == expected_branch1
        assert branch2.full_log_group_id == expected_branch2

        # Verify they inherit logger and debug_mode
        assert branch1.logger == compare_action.logger
        assert branch2.logger == compare_action.logger

    def test_deep_hierarchy_five_levels(self):
        """Test a 5-level deep hierarchy."""
        agent = MockAgent(log_group_id="MainAgent", log_time=False)
        compare_action = agent.create_action_node("CompareRecipes")
        branch1 = compare_action.create_child_debuggable(
            MockAgent,
            log_group_id="BranchedAgent_Starbucks"
        )
        analyze_node = branch1.create_action_node("AnalyzeStarbucks")
        sub_agent = analyze_node.create_child_debuggable(
            MockAgent,
            log_group_id="SubAgent"
        )

        expected = (
            "MainAgent > ActionNode_CompareRecipes > BranchedAgent_Starbucks > "
            "ActionNode_AnalyzeStarbucks > SubAgent"
        )

        assert sub_agent.full_log_group_id == expected
        assert sub_agent.parent_log_group_id == "MainAgent > ActionNode_CompareRecipes > BranchedAgent_Starbucks > ActionNode_AnalyzeStarbucks"

    def test_custom_separator(self):
        """Test using custom hierarchy separator."""
        agent = MockAgent(
            log_group_id="Root",
            log_group_hierarchy_separator=" :: ",
            log_time=False
        )
        # Child needs explicit separator (not auto-inherited)
        child = MockWorkGraphNode(
            parent_log_group_id="Root",
            log_group_id="Child",
            log_group_hierarchy_separator=" :: ",
            log_time=False
        )

        assert child.full_log_group_id == "Root :: Child"

    def test_disable_hierarchy(self):
        """Test disabling hierarchy display."""
        parent = MockAgent(log_group_id="Parent", log_time=False)
        child = MockWorkGraphNode(
            parent_log_group_id="Parent",
            log_group_id="Child",
            full_log_group_id_include_hierarchy=False,
            log_time=False
        )

        # When hierarchy is disabled, full_log_group_id should just be log_group_id
        assert child.full_log_group_id == "Child"

    def test_auto_generated_ids(self):
        """Test auto-generation of log_group_id."""
        agent = MockAgent(log_time=False)  # No log_group_id provided

        # Should be auto-generated with format: ClassName_uuid
        assert agent.log_group_id.startswith("MockAgent_")
        assert len(agent.log_group_id) > len("MockAgent_")

    def test_logger_inheritance(self):
        """Test that children inherit logger from parent."""
        logged_messages = []

        def custom_logger(log_data):
            logged_messages.append(log_data)

        parent = MockAgent(
            log_group_id="Parent",
            logger=custom_logger,
            always_add_logging_based_logger=False,
            log_time=False
        )

        child = parent.create_child_debuggable(
            MockWorkGraphNode,
            log_group_id="Child"
        )

        child.log_info("Test message", "Test")

        # Verify message was logged
        assert len(logged_messages) == 1
        assert logged_messages[0]['full_log_group_id'] == "Parent > Child"
        assert logged_messages[0]['type'] == "Test"
        assert logged_messages[0]['item'] == "Test message"

    def test_debug_mode_inheritance(self):
        """Test that children inherit debug_mode from parent."""
        parent = MockAgent(
            log_group_id="Parent",
            debug_mode=True,
            log_time=False
        )

        child = parent.create_child_debuggable(
            MockWorkGraphNode,
            log_group_id="Child"
        )

        assert child.debug_mode is True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
