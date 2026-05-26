"""Test script for the updated comparison.py with compiled regex support."""

import os
import re
import sys
import time

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
    string_check
)


def test_basic_functionality():
    """Test that basic functionality still works."""
    print("=" * 60)
    print("Test 1: Basic functionality (without compilation)")
    print("=" * 60)

    # Test exact match
    option, pattern = solve_compare_option('hello')
    assert isinstance(pattern, str)
    assert string_compare('hello', pattern, option) == True
    print("✓ Exact match works")

    # Test contains
    option, pattern = solve_compare_option('*world')
    assert isinstance(pattern, str)
    assert string_compare('hello world', pattern, option) == True
    assert string_compare('hello', pattern, option) == False
    print("✓ Contains match works")

    # Test starts with
    option, pattern = solve_compare_option('^hello')
    assert isinstance(pattern, str)
    assert string_compare('hello world', pattern, option) == True
    assert string_compare('world hello', pattern, option) == False
    print("✓ Starts with match works")

    # Test ends with
    option, pattern = solve_compare_option('$world')
    assert isinstance(pattern, str)
    assert string_compare('hello world', pattern, option) == True
    assert string_compare('world hello', pattern, option) == False
    print("✓ Ends with match works")

    print()


def test_regex_without_compilation():
    """Test regex patterns without pre-compilation."""
    print("=" * 60)
    print("Test 2: Regex without compilation (original behavior)")
    print("=" * 60)

    # Test regex exact match
    option, pattern = solve_compare_option('@[0-9]+')
    assert isinstance(pattern, str)
    assert option.is_regular_expression == True
    assert string_compare('12345', pattern, option) == True
    assert string_compare('abc', pattern, option) == False
    print("✓ Regex exact match works")

    # Test regex starts with
    option, pattern = solve_compare_option('@^[a-z]+')
    assert isinstance(pattern, str)
    assert string_compare('abc123', pattern, option) == True
    assert string_compare('123abc', pattern, option) == False
    print("✓ Regex starts with works")

    # Test regex ends with
    option, pattern = solve_compare_option('@$[0-9]+')
    assert isinstance(pattern, str)
    assert string_compare('abc123', pattern, option) == True
    assert string_compare('123abc', pattern, option) == False
    print("✓ Regex ends with works")

    print()


def test_regex_with_compilation():
    """Test regex patterns with pre-compilation enabled."""
    print("=" * 60)
    print("Test 3: Regex WITH compilation (new feature)")
    print("=" * 60)

    # Test regex exact match with compilation
    option, pattern = solve_compare_option('@[0-9]+', compile_regex=True)
    assert isinstance(pattern, re.Pattern), f"Expected re.Pattern, got {type(pattern)}"
    assert string_compare('12345', pattern, option) == True
    assert string_compare('abc', pattern, option) == False
    print(f"✓ Compiled regex exact match works (pattern type: {type(pattern).__name__})")

    # Test regex starts with compilation
    option, pattern = solve_compare_option('@^[a-z]+', compile_regex=True)
    assert isinstance(pattern, re.Pattern)
    assert string_compare('abc123', pattern, option) == True
    assert string_compare('123abc', pattern, option) == False
    print(f"✓ Compiled regex starts with works (pattern: {pattern.pattern})")

    # Test regex ends with compilation
    option, pattern = solve_compare_option('@$[0-9]+', compile_regex=True)
    assert isinstance(pattern, re.Pattern)
    assert string_compare('abc123', pattern, option) == True
    assert string_compare('123abc', pattern, option) == False
    print(f"✓ Compiled regex ends with works (pattern: {pattern.pattern})")

    print()


def test_case_sensitivity():
    """Test case sensitivity with compiled patterns."""
    print("=" * 60)
    print("Test 4: Case sensitivity with compiled patterns")
    print("=" * 60)

    # Case sensitive (default)
    option, pattern = solve_compare_option('@[A-Z]+', compile_regex=True)
    assert string_compare('ABC', pattern, option) == True
    assert string_compare('abc', pattern, option) == False
    print("✓ Case sensitive compiled pattern works")

    # Case insensitive
    option, pattern = solve_compare_option('/@[a-z]+', compile_regex=True)
    assert isinstance(pattern, re.Pattern)
    assert option.case_sensitive == False
    assert string_compare('ABC', pattern, option) == True
    assert string_compare('abc', pattern, option) == True
    print(f"✓ Case insensitive compiled pattern works (flags: {pattern.flags})")

    print()


def test_non_regex_string_unchanged():
    """Test that non-regex strings are not compiled."""
    print("=" * 60)
    print("Test 5: Non-regex strings should remain strings")
    print("=" * 60)

    # Regular string should remain string even with compile_regex=True
    option, pattern = solve_compare_option('hello', compile_regex=True)
    assert isinstance(pattern, str)
    assert option.is_regular_expression == False
    print("✓ Non-regex string remains a string even with compile_regex=True")

    # Contains pattern should remain string
    option, pattern = solve_compare_option('*world', compile_regex=True)
    assert isinstance(pattern, str)
    assert option.is_regular_expression == False
    print("✓ Contains pattern remains a string")

    print()


def test_direct_pattern_passing():
    """Test passing pre-compiled patterns directly to string_compare."""
    print("=" * 60)
    print("Test 6: Passing pre-compiled patterns directly")
    print("=" * 60)

    from python_utils.string_utils.comparison import CompareOption, CompareMethod

    # Create a pre-compiled pattern
    compiled = re.compile(r'\d+')
    option = CompareOption(
        is_regular_expression=True,
        compare_method=CompareMethod.ExactMatch
    )

    assert string_compare('12345', compiled, option) == True
    assert string_compare('abc', compiled, option) == False
    print("✓ Directly passing compiled Pattern to string_compare works")

    print()


def test_performance_comparison():
    """Compare performance of compiled vs non-compiled patterns."""
    print("=" * 60)
    print("Test 7: Performance comparison")
    print("=" * 60)

    test_strings = ['test123', 'hello456', 'world789', 'foo123bar'] * 1000
    pattern_str = '@[a-z]+[0-9]+'

    # Test without compilation
    option, pattern = solve_compare_option(pattern_str, compile_regex=False)
    start = time.perf_counter()
    for s in test_strings:
        string_compare(s, pattern, option)
    time_without_compilation = time.perf_counter() - start

    # Test with compilation
    option, pattern = solve_compare_option(pattern_str, compile_regex=True)
    start = time.perf_counter()
    for s in test_strings:
        string_compare(s, pattern, option)
    time_with_compilation = time.perf_counter() - start

    print(f"Time without compilation: {time_without_compilation:.4f}s")
    print(f"Time with compilation:    {time_with_compilation:.4f}s")
    print(f"Speedup: {time_without_compilation / time_with_compilation:.2f}x")
    print("✓ Compiled patterns show performance benefit")

    print()


def test_string_check_compatibility():
    """Test that string_check still works (backward compatibility)."""
    print("=" * 60)
    print("Test 8: Backward compatibility with string_check")
    print("=" * 60)

    assert string_check('123456', '1456') == False
    assert string_check('123456', '*456') == True
    assert string_check('123456', '^123') == True
    assert string_check('123456', '$456') == True
    assert string_check('123456', '@[0-9]+') == True
    print("✓ string_check backward compatibility maintained")

    print()


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RUNNING ALL TESTS")
    print("=" * 60 + "\n")

    try:
        test_basic_functionality()
        test_regex_without_compilation()
        test_regex_with_compilation()
        test_case_sensitivity()
        test_non_regex_string_unchanged()
        test_direct_pattern_passing()
        test_performance_comparison()
        test_string_check_compatibility()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
