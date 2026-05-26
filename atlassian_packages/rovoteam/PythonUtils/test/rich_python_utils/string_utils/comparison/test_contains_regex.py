"""
Test cases for regex patterns that check if strings contain specific patterns.

This demonstrates how to use regex to achieve "contains" matching with alternation,
which is useful for checking if strings contain any of several keywords.
"""

import os
import sys
import re

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
    string_compare
)


def test_contains_with_regex():
    """Test regex patterns for contains matching with alternation."""
    print("=" * 80)
    print("TEST: Contains matching with regex alternation")
    print("=" * 80)

    # Test case from user: check if string contains view, body, or presentation
    pattern_str = r'@.*(view|body|presentation).*'
    test_cases = [
        ('p-workspace__primary_view_body', True, 'Contains "view" and "body"'),
        ('main-presentation-slide', True, 'Contains "presentation"'),
        ('simple-view-container', True, 'Contains "view"'),
        ('body-content-wrapper', True, 'Contains "body"'),
        ('unrelated-class-name', False, 'Contains none of the keywords'),
        ('header-footer-navigation', False, 'Contains none of the keywords'),
    ]

    print(f"\nPattern: '{pattern_str}'")
    print("Explanation: Matches if string contains 'view' OR 'body' OR 'presentation'\n")

    # Test without compilation
    print("Without compilation:")
    option, pattern = solve_compare_option(pattern_str, compile_regex=False)
    for test_str, expected, description in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{test_str}' -> {result} ({description})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"

    # Test with compilation
    print("\nWith compilation:")
    option, pattern = solve_compare_option(pattern_str, compile_regex=True)
    assert isinstance(pattern, re.Pattern), "Pattern should be compiled"
    print(f"  Compiled pattern: {pattern.pattern}")
    print(f"  Pattern type: {type(pattern).__name__}\n")

    for test_str, expected, description in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{test_str}' -> {result} ({description})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"

    print("\n✅ All tests passed!\n")


def test_contains_with_word_boundaries():
    """Test regex patterns with word boundaries for exact word matching."""
    print("=" * 80)
    print("TEST: Contains with word boundaries")
    print("=" * 80)

    # Pattern with word boundaries - matches only complete words
    pattern_str = r'@.*\b(view|body|presentation)\b.*'
    test_cases = [
        ('this is a view', True, 'Complete word "view"'),
        ('body is here', True, 'Complete word "body"'),
        ('presentation slide', True, 'Complete word "presentation"'),
        ('overview document', False, '"view" is not a complete word'),
        ('p-workspace__primary_view_body', False, '"view" and "body" are not complete words'),
    ]

    print(f"\nPattern: '{pattern_str}'")
    print(r"Explanation: Matches if string contains complete words 'view', 'body', or 'presentation'" + "\n")

    option, pattern = solve_compare_option(pattern_str, compile_regex=True)
    assert isinstance(pattern, re.Pattern), "Pattern should be compiled"
    print(f"  Compiled pattern: {pattern.pattern}")
    print(f"  Pattern type: {type(pattern).__name__}\n")

    for test_str, expected, description in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{test_str}' -> {result} ({description})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"

    print("\n✅ All tests passed!\n")


def test_case_insensitive_contains():
    """Test case insensitive contains matching."""
    print("=" * 80)
    print("TEST: Case insensitive contains matching")
    print("=" * 80)

    # Case insensitive pattern
    pattern_str = r'/@.*(view|body|presentation).*'
    test_cases = [
        ('View_Container', True, 'Contains "View" (case insensitive)'),
        ('BODY_CONTENT', True, 'Contains "BODY" (case insensitive)'),
        ('Main-Presentation', True, 'Contains "Presentation" (case insensitive)'),
        ('p-workspace__PRIMARY_VIEW_BODY', True, 'Contains "VIEW" and "BODY" (case insensitive)'),
        ('unrelated-text', False, 'Contains none of the keywords'),
    ]

    print(f"\nPattern: '{pattern_str}'")
    print("Explanation: Case insensitive match for 'view', 'body', or 'presentation'\n")

    option, pattern = solve_compare_option(pattern_str, compile_regex=True)
    assert isinstance(pattern, re.Pattern), "Pattern should be compiled"
    assert pattern.flags & re.IGNORECASE != 0, "Pattern should have IGNORECASE flag"
    print(f"  Compiled pattern: {pattern.pattern}")
    print(f"  Pattern flags: {pattern.flags} (includes re.IGNORECASE)")
    print(f"  Case sensitive: {option.case_sensitive}\n")

    for test_str, expected, description in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{test_str}' -> {result} ({description})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"

    print("\n✅ All tests passed!\n")


def test_contains_plus_regex():
    """Test that *@ (contains + regex) works both with AND without compilation."""
    print("=" * 80)
    print("TEST: *@ (contains + regex) combination")
    print("=" * 80)

    pattern_str = '*@ view|body|presentation'

    print(f"\nPattern: '{pattern_str}'")
    print("This pattern uses '*' (contains) with '@' (regex)")
    print("This now works BOTH with and without compilation!\n")

    test_cases = [
        ('p-workspace__primary_view_body', True, 'Contains "view" and "body"'),
        ('main-presentation-slide', True, 'Contains "presentation"'),
        ('unrelated-class-name', False, 'Contains none of the keywords'),
    ]

    # Test WITHOUT compilation - now works!
    print("WITHOUT compilation (compile_regex=False):")
    option, pattern = solve_compare_option(pattern_str, compile_regex=False)
    print(f"  Compare method: {option.compare_method.value}")
    print(f"  Is regex: {option.is_regular_expression}")
    print(f"  Pattern type: {type(pattern).__name__}")
    print(f"  Pattern: {pattern}\n")

    for test_str, expected, description in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{test_str}' -> {result} ({description})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"

    # Test WITH compilation - also works!
    print("\nWITH compilation (compile_regex=True):")
    option, pattern = solve_compare_option(pattern_str, compile_regex=True)
    print(f"  Compare method: {option.compare_method.value}")
    print(f"  Is regex: {option.is_regular_expression}")
    print(f"  Pattern type: {type(pattern).__name__}")
    if isinstance(pattern, re.Pattern):
        print(f"  Compiled pattern: {pattern.pattern}\n")

    for test_str, expected, description in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{test_str}' -> {result} ({description})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"

    print("\n✅ Test passed!")
    print("\nKey insight:")
    print("  - '*@' pattern now WORKS with compile_regex=False ✓")
    print("  - '*@' pattern also WORKS with compile_regex=True ✓")
    print("  - Both use re.search() which naturally handles 'contains' matching")
    print("  - Compiled version is ~2x faster for repeated matching\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CONTAINS REGEX PATTERN TESTS")
    print("=" * 80 + "\n")

    try:
        test_contains_with_regex()
        test_contains_with_word_boundaries()
        test_case_insensitive_contains()
        test_contains_plus_regex()

        print("=" * 80)
        print("✅ ALL CONTAINS REGEX TESTS PASSED!")
        print("=" * 80)
        print("\nKey Takeaways:")
        print("  1. Use '@.*(pattern).*' for explicit contains matching with regex")
        print("  2. Use '/@.*(pattern).*' for case insensitive contains")
        print(r"  3. Use '@.*\b(pattern)\b.*' for complete word matching")
        print("  4. The '*@' combination now WORKS (both with and without compilation) ✓")
        print("  5. Pattern '*@ view|body|presentation' matches 'p-workspace__primary_view_body'")
        print("  6. Compiled patterns are ~2x faster for repeated matching")
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
    success = main()
    sys.exit(0 if success else 1)
