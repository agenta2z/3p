"""
Test script for empty pattern edge cases and wildcard pattern support.

This test suite verifies the fixes for:
1. Empty pattern handling in solve_compare_option (pattern='*', '^', '$', etc.)
2. Empty pattern matching in string_compare
3. Wildcard '*' pattern in string_check
4. Negation with empty patterns ('!*', '!^', '!$')
"""

import os
import sys

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src directory to path
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(test_dir, '..', '..', '..', '..'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

from python_utils.string_utils.comparison import (
    solve_compare_option,
    string_compare,
    string_check,
    CompareOption,
    CompareMethod
)


def test_solve_compare_option_empty_patterns():
    """Test that solve_compare_option correctly handles empty patterns."""
    print("=" * 80)
    print("Test 1: solve_compare_option with empty patterns")
    print("=" * 80)

    # Test single '*' wildcard
    option, pattern = solve_compare_option('*')
    assert pattern == '', f"Expected empty pattern, got: {repr(pattern)}"
    assert option.compare_method == CompareMethod.Contains
    print("✓ Single '*' produces empty pattern with Contains method")

    # Test single '^' (starts with)
    option, pattern = solve_compare_option('^')
    assert pattern == '', f"Expected empty pattern, got: {repr(pattern)}"
    assert option.compare_method == CompareMethod.StartsWith
    print("✓ Single '^' produces empty pattern with StartsWith method")

    # Test single '$' (ends with)
    option, pattern = solve_compare_option('$')
    assert pattern == '', f"Expected empty pattern, got: {repr(pattern)}"
    assert option.compare_method == CompareMethod.EndsWith
    print("✓ Single '$' produces empty pattern with EndsWith method")

    # Test negation with '*'
    option, pattern = solve_compare_option('!*')
    assert pattern == '', f"Expected empty pattern, got: {repr(pattern)}"
    assert option.compare_method == CompareMethod.Contains
    assert option.negation == True
    print("✓ '!*' produces empty pattern with Contains method and negation=True")

    # Test negation with '^'
    option, pattern = solve_compare_option('!^')
    assert pattern == '', f"Expected empty pattern, got: {repr(pattern)}"
    assert option.compare_method == CompareMethod.StartsWith
    assert option.negation == True
    print("✓ '!^' produces empty pattern with StartsWith method and negation=True")

    # Test negation with '$'
    option, pattern = solve_compare_option('!$')
    assert pattern == '', f"Expected empty pattern, got: {repr(pattern)}"
    assert option.compare_method == CompareMethod.EndsWith
    assert option.negation == True
    print("✓ '!$' produces empty pattern with EndsWith method and negation=True")

    print()


def test_string_compare_empty_patterns():
    """Test that string_compare correctly handles empty patterns."""
    print("=" * 80)
    print("Test 2: string_compare with empty patterns")
    print("=" * 80)

    # Test Contains with empty pattern
    opt = CompareOption(compare_method=CompareMethod.Contains)
    assert string_compare('', '', opt) == True, "Empty string should contain empty string"
    assert string_compare('hello', '', opt) == True, "Any string should contain empty string"
    print("✓ Contains method: empty pattern matches any string")

    # Test StartsWith with empty pattern
    opt = CompareOption(compare_method=CompareMethod.StartsWith)
    assert string_compare('', '', opt) == True, "Empty string should start with empty string"
    assert string_compare('hello', '', opt) == True, "Any string should start with empty string"
    print("✓ StartsWith method: empty pattern matches any string")

    # Test EndsWith with empty pattern
    opt = CompareOption(compare_method=CompareMethod.EndsWith)
    assert string_compare('', '', opt) == True, "Empty string should end with empty string"
    assert string_compare('hello', '', opt) == True, "Any string should end with empty string"
    print("✓ EndsWith method: empty pattern matches any string")

    # Test ExactMatch with empty pattern
    opt = CompareOption(compare_method=CompareMethod.ExactMatch)
    assert string_compare('', '', opt) == True, "Empty string should exactly match empty string"
    assert string_compare('hello', '', opt) == False, "Non-empty string should not exactly match empty string"
    print("✓ ExactMatch method: empty pattern only matches empty string")

    # Test negation with empty pattern
    opt = CompareOption(compare_method=CompareMethod.Contains, negation=True)
    assert string_compare('hello', '', opt) == False, "Negation of 'contains empty' should be False"
    assert string_compare('', '', opt) == False, "Negation of 'contains empty' should be False even for empty string"
    print("✓ Negation with empty pattern works correctly")

    print()


def test_string_check_wildcard():
    """Test that string_check correctly handles wildcard patterns."""
    print("=" * 80)
    print("Test 3: string_check with wildcard patterns")
    print("=" * 80)

    # Test single '*' wildcard
    assert string_check('', '*') == True, "Empty string should match '*'"
    assert string_check('hello', '*') == True, "Any string should match '*'"
    assert string_check('12345', '*') == True, "Any string should match '*'"
    print("✓ Single '*' matches any string (including empty)")

    # Test negation of '*'
    assert string_check('hello', '!*') == False, "Negation of '*' should match nothing"
    assert string_check('', '!*') == False, "Negation of '*' should match nothing (even empty)"
    print("✓ Negation '!*' matches nothing")

    # Test empty pattern with '^' (starts with)
    assert string_check('', '^') == True, "Empty string starts with empty string"
    assert string_check('hello', '^') == True, "Any string starts with empty string"
    print("✓ Empty pattern with '^' matches any string")

    # Test empty pattern with '$' (ends with)
    assert string_check('', '$') == True, "Empty string ends with empty string"
    assert string_check('hello', '$') == True, "Any string ends with empty string"
    print("✓ Empty pattern with '$' matches any string")

    # Test negation with '^'
    assert string_check('hello', '!^') == False, "Negation of 'starts with empty' matches nothing"
    print("✓ Negation '!^' matches nothing")

    # Test negation with '$'
    assert string_check('hello', '!$') == False, "Negation of 'ends with empty' matches nothing"
    print("✓ Negation '!$' matches nothing")

    # Test exact match with empty pattern
    assert string_check('', '') == True, "Empty string exactly matches empty string"
    assert string_check('hello', '') == False, "Non-empty string doesn't exactly match empty string"
    print("✓ Empty exact match pattern works correctly")

    print()


def test_boolean_attributes_with_wildcards():
    """Test that wildcard patterns work with boolean HTML attributes (empty values)."""
    print("=" * 80)
    print("Test 4: Boolean attributes (empty values) with wildcard patterns")
    print("=" * 80)

    # Simulate checking if an empty string (like HTML boolean attributes) matches wildcard
    # This is the actual use case that motivated the fix
    boolean_attr_value = ''  # HTML disabled attribute has empty string value

    # Check if disabled attribute (empty string) matches '*' pattern
    assert string_check(boolean_attr_value, '*') == True, "Empty value should match '*' pattern"
    print("✓ Boolean attribute (empty value) matches '*' wildcard")

    # Check with solve_compare_option + string_compare
    option, pattern = solve_compare_option('*')
    assert string_compare(boolean_attr_value, pattern, option) == True, \
        "Empty value should match '*' pattern via string_compare"
    print("✓ Boolean attribute (empty value) matches via solve_compare_option + string_compare")

    print()


def test_integration_with_contains_regex():
    """Test that empty patterns work with regex contains patterns."""
    print("=" * 80)
    print("Test 5: Integration with regex contains patterns")
    print("=" * 80)

    # Test that non-empty patterns still work
    assert string_check('p-workspace__primary_view_body', '*@ view|body|presentation', compile_regex=False) == True
    assert string_check('p-workspace__primary_view_body', '*@ view|body|presentation', compile_regex=True) == True
    assert string_check('unrelated-class-name', '*@ view|body|presentation') == False
    print("✓ Non-empty regex patterns still work correctly")

    # Test that empty patterns take priority
    assert string_check('anything', '*') == True
    print("✓ Empty wildcard '*' takes priority")

    print()


def run_all_tests():
    """Run all test functions."""
    print("\n" + "=" * 80)
    print("EMPTY PATTERNS AND WILDCARDS TEST SUITE")
    print("=" * 80 + "\n")

    test_functions = [
        test_solve_compare_option_empty_patterns,
        test_string_compare_empty_patterns,
        test_string_check_wildcard,
        test_boolean_attributes_with_wildcards,
        test_integration_with_contains_regex,
    ]

    failed_tests = []

    for test_func in test_functions:
        try:
            test_func()
        except AssertionError as e:
            print(f"✗ FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed_tests.append((test_func.__name__, str(e)))
        except Exception as e:
            print(f"✗ ERROR in {test_func.__name__}: {e}")
            failed_tests.append((test_func.__name__, f"Unexpected error: {e}"))

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    if failed_tests:
        print(f"\n❌ {len(failed_tests)} test(s) FAILED:\n")
        for test_name, error in failed_tests:
            print(f"  - {test_name}")
            print(f"    {error}\n")
        return False
    else:
        print("\n✅ All tests PASSED!")
        print(f"\nTotal tests run: {len(test_functions)}")
        return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
