"""Tests for dict__ _obj_cache stale entry bug caused by Python id() reuse.

When dict__ processes multiple attrs objects in a list, the _obj_cache uses
id(obj) as the key. Intermediate dicts created by attr.asdict() can be
garbage-collected and their memory addresses reused by subsequent attr.asdict()
calls. This causes _obj_cache to return stale results for new objects that
happen to share the same memory address as a previously-cached (and now-GC'd)
intermediate object.

This test reproduces the exact scenario from the WebAgent action processing
pipeline where [InputText, Click] becomes [InputText, InputText].
"""
import gc
import sys
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import attr
import pytest

from python_utils.common_utils.map_helper import dict__


# --- Attrs classes simulating the WebAgent's AgentAction ---

@attr.s
class AgentAction:
    """Simulates the action object from the WebAgent pipeline."""
    reasoning = attr.ib(type=str)
    target = attr.ib(type=str)
    type = attr.ib(type=str)
    is_follow_up = attr.ib(type=bool, default=False)
    memory_target = attr.ib(default=None)
    args = attr.ib(default=None)
    source = attr.ib(default=None)
    result = attr.ib(default=None)


def test_dict_obj_cache_stale_entry_with_attrs_list():
    """Reproduce: dict__ on a list of different attrs objects should
    produce distinct dicts for each, not duplicates.

    This simulates the exact WebAgent scenario:
    next_actions = [[InputText_action], [Click_action]]
    After dict__(), the Click should NOT become a copy of InputText.
    """
    action1 = AgentAction(
        reasoning="Enter email into input field",
        target="76",
        type="ElementInteraction.InputText",
        args={"Text": "tzchen86@gmail.com"},
    )
    action2 = AgentAction(
        reasoning="Click the Next button to proceed",
        target="131",
        type="ElementInteraction.Click",
    )

    # Structure mirrors the actual next_actions: [[action1], [action2]]
    next_actions = [[action1], [action2]]

    result = dict__(next_actions, recursive=True, fallback='skip')

    # Verify action1 is correct
    assert result[0][0]["type"] == "ElementInteraction.InputText", (
        f"First action type should be InputText, got {result[0][0]['type']}"
    )
    assert result[0][0]["target"] == "76", (
        f"First action target should be '76', got {result[0][0]['target']}"
    )

    # Verify action2 is correct - THIS IS WHERE THE BUG MANIFESTS
    assert result[1][0]["type"] == "ElementInteraction.Click", (
        f"Second action type should be Click, got {result[1][0]['type']}. "
        f"BUG: dict__ returned a stale cached copy of the first action!"
    )
    assert result[1][0]["target"] == "131", (
        f"Second action target should be '131', got {result[1][0]['target']}. "
        f"BUG: dict__ returned a stale cached copy of the first action!"
    )


def test_dict_obj_cache_stale_entry_with_gc_pressure():
    """Same test but with explicit GC to increase likelihood of id() reuse.

    Python's id() returns the memory address. When objects are garbage-
    collected, their addresses can be reused. By forcing GC between
    iterations, we increase the chance of triggering the stale cache bug.
    """
    action1 = AgentAction(
        reasoning="Enter email into input field",
        target="76",
        type="ElementInteraction.InputText",
        args={"Text": "user@example.com"},
    )
    action2 = AgentAction(
        reasoning="Click the Next button",
        target="131",
        type="ElementInteraction.Click",
    )
    action3 = AgentAction(
        reasoning="Wait for page load",
        target="200",
        type="Navigation.WaitForPageLoad",
    )

    next_actions = [[action1], [action2], [action3]]

    # Force GC to free any lingering objects and make address reuse more likely
    gc.collect()

    result = dict__(next_actions, recursive=True, fallback='skip')

    # Each action in the result should preserve its own distinct data
    assert result[0][0]["type"] == "ElementInteraction.InputText"
    assert result[0][0]["target"] == "76"

    assert result[1][0]["type"] == "ElementInteraction.Click", (
        f"Second action corrupted: got type={result[1][0]['type']}, target={result[1][0]['target']}"
    )
    assert result[1][0]["target"] == "131"

    assert result[2][0]["type"] == "Navigation.WaitForPageLoad", (
        f"Third action corrupted: got type={result[2][0]['type']}, target={result[2][0]['target']}"
    )
    assert result[2][0]["target"] == "200"


def test_dict_obj_cache_deterministic_id_collision():
    """Deterministically demonstrate the _obj_cache id collision mechanism.

    This test directly demonstrates WHY the bug occurs by tracking
    intermediate object ids through dict__'s processing.
    """
    # Create two attrs objects with different data
    action_a = AgentAction(
        reasoning="Action A reasoning",
        target="42",
        type="TypeA",
    )
    action_b = AgentAction(
        reasoning="Action B reasoning",
        target="99",
        type="TypeB",
    )

    # Manually trace what dict__ does internally to show the id collision
    # Step 1: attr.asdict creates a temporary dict for action_a
    temp_dict_a = attr.asdict(action_a)
    addr_a = id(temp_dict_a)

    # Step 2: Process temp_dict_a (simulating dict__'s recursive call)
    # After processing, temp_dict_a can be freed
    processed_a = dict(temp_dict_a)  # This is what dict__ produces
    del temp_dict_a  # Simulate losing the reference
    gc.collect()  # Free the memory

    # Step 3: attr.asdict creates a temporary dict for action_b
    temp_dict_b = attr.asdict(action_b)
    addr_b = id(temp_dict_b)

    # The core question: can addr_b == addr_a?
    # This is non-deterministic but happens frequently in practice
    if addr_a == addr_b:
        print(f"ID COLLISION DETECTED: addr_a={addr_a} == addr_b={addr_b}")
        print("This proves Python reused the memory address.")
        print("In dict__, the _obj_cache would return action_a's result for action_b!")
    else:
        print(f"No collision this run: addr_a={addr_a}, addr_b={addr_b}")
        print("The bug is non-deterministic; it depends on Python's allocator.")

    # Regardless of whether collision happened in THIS run,
    # verify dict__ produces correct results
    result = dict__([action_a, action_b], recursive=True, fallback='skip')
    assert result[0]["type"] == "TypeA", f"First action wrong: {result[0]}"
    assert result[1]["type"] == "TypeB", (
        f"Second action wrong: got {result[1]['type']} instead of TypeB. "
        f"This confirms the _obj_cache stale entry bug!"
    )


def test_dict_obj_cache_many_attrs_objects():
    """Stress test: process many attrs objects to increase collision probability.

    With more objects, the probability of id() reuse increases significantly.
    """
    N = 50
    actions = [
        AgentAction(
            reasoning=f"Action {i} reasoning",
            target=str(i),
            type=f"Type_{i}",
        )
        for i in range(N)
    ]

    # Process as a flat list of attrs objects
    result = dict__(actions, recursive=True, fallback='skip')

    # Verify EVERY action preserved its unique data
    corrupted = []
    for i in range(N):
        if result[i]["type"] != f"Type_{i}" or result[i]["target"] != str(i):
            corrupted.append(
                f"  action[{i}]: expected type=Type_{i}/target={i}, "
                f"got type={result[i]['type']}/target={result[i]['target']}"
            )

    if corrupted:
        msg = (
            f"dict__ corrupted {len(corrupted)}/{N} attrs objects due to "
            f"_obj_cache id() reuse:\n" + "\n".join(corrupted)
        )
        pytest.fail(msg)


def test_dict_obj_cache_nested_attrs_in_list_of_lists():
    """Test the exact structure: list of lists of attrs objects.

    This matches the WebAgent's next_actions = [[action1], [action2], ...]
    """
    N = 20
    next_actions = [
        [AgentAction(
            reasoning=f"Group {i} reasoning",
            target=str(100 + i),
            type=f"ActionType_{i}",
            args={"key": f"value_{i}"},
        )]
        for i in range(N)
    ]

    result = dict__(next_actions, recursive=True, fallback='skip')

    corrupted = []
    for i in range(N):
        action = result[i][0]
        expected_type = f"ActionType_{i}"
        expected_target = str(100 + i)
        if action["type"] != expected_type or action["target"] != expected_target:
            corrupted.append(
                f"  group[{i}]: expected type={expected_type}/target={expected_target}, "
                f"got type={action['type']}/target={action['target']}"
            )

    if corrupted:
        msg = (
            f"dict__ corrupted {len(corrupted)}/{N} action groups due to "
            f"_obj_cache id() reuse:\n" + "\n".join(corrupted)
        )
        pytest.fail(msg)


def test_dict_obj_cache_bug_vs_individual_conversion():
    """Prove the bug is in _obj_cache by comparing dict__ on the whole list
    vs. dict__ on each element individually (fresh cache each time).

    When each element gets its own fresh _obj_cache (no cross-contamination),
    all results are correct. When they share one _obj_cache, some get corrupted.
    """
    N = 20
    next_actions = [
        [AgentAction(
            reasoning=f"Group {i} reasoning",
            target=str(100 + i),
            type=f"ActionType_{i}",
            args={"key": f"value_{i}"},
        )]
        for i in range(N)
    ]

    # Method 1: dict__ on the whole list (shared _obj_cache)
    result_shared = dict__(next_actions, recursive=True, fallback='skip')

    # Method 2: dict__ on each element individually (fresh cache each time)
    result_individual = [
        dict__(group, recursive=True, fallback='skip')
        for group in next_actions
    ]

    # Individual conversion should ALWAYS be correct
    for i in range(N):
        assert result_individual[i][0]["type"] == f"ActionType_{i}", (
            f"Individual conversion should be correct but group[{i}] wrong"
        )
        assert result_individual[i][0]["target"] == str(100 + i)

    # Shared conversion may have corrupted entries
    corrupted_shared = []
    for i in range(N):
        action = result_shared[i][0]
        if action["type"] != f"ActionType_{i}" or action["target"] != str(100 + i):
            corrupted_shared.append(i)

    if corrupted_shared:
        print(f"\nBUG CONFIRMED: Shared _obj_cache corrupted groups {corrupted_shared}")
        print("Individual (fresh cache) conversion was correct for all groups.")
        print("This proves the corruption is caused by _obj_cache id() reuse.")
        for i in corrupted_shared:
            print(
                f"  group[{i}]: shared={result_shared[i][0]['type']}/{result_shared[i][0]['target']}, "
                f"individual={result_individual[i][0]['type']}/{result_individual[i][0]['target']}"
            )
        pytest.fail(
            f"Shared _obj_cache corrupted {len(corrupted_shared)}/{N} groups "
            f"while individual conversion was correct for all."
        )


if __name__ == '__main__':
    print("Running dict__ _obj_cache stale entry tests...")
    print()

    tests = [
        ("Basic two-action scenario (InputText+Click)",
         test_dict_obj_cache_stale_entry_with_attrs_list),
        ("Three-action scenario with GC pressure",
         test_dict_obj_cache_stale_entry_with_gc_pressure),
        ("Deterministic id collision demonstration",
         test_dict_obj_cache_deterministic_id_collision),
        ("Stress test: many attrs objects",
         test_dict_obj_cache_many_attrs_objects),
        ("Nested list of lists structure",
         test_dict_obj_cache_nested_attrs_in_list_of_lists),
        ("Shared vs individual cache comparison",
         test_dict_obj_cache_bug_vs_individual_conversion),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            print(f"  PASS: {test_name}")
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  FAIL: {test_name}")
            print(f"    Error: {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
