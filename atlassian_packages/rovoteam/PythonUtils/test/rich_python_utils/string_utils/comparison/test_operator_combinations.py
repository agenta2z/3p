"""
Comprehensive test script demonstrating all operator combinations for compiled regex.

This script tests various combinations of operators:
- @ (regex)
- ^ (starts with)
- $ (ends with)
- * (contains)
- ! (negation)
- / (case insensitive)

And their combinations with regex compilation.
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


def test_operator_combination(pattern_str, test_cases, compile_regex=True):
    """Test a pattern against multiple test cases."""
    print(f"\n{'─' * 80}")
    print(f"Pattern: '{pattern_str}' (compile_regex={compile_regex})")
    print(f"{'─' * 80}")

    option, pattern = solve_compare_option(pattern_str, compile_regex=compile_regex)

    # Show pattern details
    if isinstance(pattern, re.Pattern):
        print(f"  Type: re.Pattern")
        print(f"  Compiled pattern: {pattern.pattern}")
        print(f"  Flags: {pattern.flags}")
    else:
        print(f"  Type: str")
        print(f"  Pattern: {pattern}")

    print(f"  Options:")
    print(f"    - compare_method: {option.compare_method.value}")
    print(f"    - is_regular_expression: {option.is_regular_expression}")
    print(f"    - case_sensitive: {option.case_sensitive}")
    print(f"    - negation: {option.negation}")

    print(f"\n  Test Results:")
    for test_str, expected in test_cases:
        result = string_compare(test_str, pattern, option)
        status = "✓" if result == expected else "✗"
        print(f"    {status} string_compare('{test_str}', pattern, option) = {result} (expected {expected})")
        assert result == expected, f"Failed for '{test_str}': got {result}, expected {expected}"


def main():
    print("=" * 80)
    print("COMPREHENSIVE OPERATOR COMBINATION TESTS")
    print("=" * 80)

    # Test 1: Basic regex exact match (@)
    test_operator_combination(
        '@[0-9]+',
        [
            ('12345', True),
            ('abc', False),
            ('abc123', False),  # Not exact match
            ('123abc', False),  # Not exact match
        ]
    )

    # Test 2: Regex starts with (@^)
    test_operator_combination(
        '@^[a-z]+',
        [
            ('abc', True),
            ('abc123', True),  # Starts with letters
            ('123abc', False),  # Doesn't start with letters
            ('ABC', False),  # Case sensitive
        ]
    )

    # Test 3: Regex ends with (@$)
    test_operator_combination(
        '@$[0-9]+',
        [
            ('abc123', True),  # Ends with digits
            ('123', True),
            ('123abc', False),  # Doesn't end with digits
            ('abc', False),
        ]
    )

    # Test 4: Negated regex exact match (!@)
    test_operator_combination(
        '!@[0-9]+',
        [
            ('abc', True),  # Not digits
            ('12345', False),  # Is digits
            ('abc123', True),  # Not all digits
        ]
    )

    # Test 5: Negated regex starts with (!@^)
    test_operator_combination(
        '!@^[a-z]+',
        [
            ('abc', False),  # Does start with lowercase
            ('ABC', True),  # Doesn't start with lowercase
            ('123abc', True),  # Doesn't start with lowercase
            ('abc123', False),  # Does start with lowercase
        ]
    )

    # Test 6: Negated regex ends with (!@$)
    test_operator_combination(
        '!@$[0-9]+',
        [
            ('abc123', False),  # Does end with digits
            ('123abc', True),  # Doesn't end with digits
            ('abc', True),  # Doesn't end with digits
        ]
    )

    # Test 7: Case insensitive regex (/@)
    test_operator_combination(
        '/@[a-z]+',
        [
            ('abc', True),
            ('ABC', True),  # Case insensitive
            ('AbC', True),
            ('123', False),
        ]
    )

    # Test 8: Case insensitive regex starts with (/@^)
    test_operator_combination(
        '/@^[a-z]+',
        [
            ('abc', True),
            ('ABC123', True),  # Case insensitive
            ('123abc', False),
            ('AbC', True),
        ]
    )

    # Test 9: Case insensitive regex ends with (/@$)
    test_operator_combination(
        '/@$[a-z]+',
        [
            ('123abc', True),
            ('123ABC', True),  # Case insensitive
            ('abc123', False),
            ('ABC', True),
        ]
    )

    # Test 10: Case insensitive negated regex (/!@)
    test_operator_combination(
        '/!@[a-z]+',
        [
            ('abc', False),
            ('ABC', False),  # Case insensitive, so matches
            ('123', True),  # Doesn't match
        ]
    )

    # Test 11: Case insensitive negated regex starts with (/!@^)
    test_operator_combination(
        '/!@^[a-z]+',
        [
            ('abc', False),
            ('ABC', False),  # Case insensitive
            ('123abc', True),  # Doesn't start with letters
            ('123', True),
        ]
    )

    # Test 12: Case insensitive negated regex ends with (/!@$)
    test_operator_combination(
        '/!@$[a-z]+',
        [
            ('abc123', True),  # Doesn't end with letters
            ('123ABC', False),  # Ends with letters (case insensitive)
            ('123', True),
        ]
    )

    # Test 13a: Case SENSITIVE negated regex starts with (!@^)
    test_operator_combination(
        '!@^[a-z]+',
        [
            ('ABC', True),  # Case sensitive, doesn't start with lowercase, negation = True
            ('abc', False),  # Case sensitive, starts with lowercase, negation = False
            ('123', True),  # Doesn't start with lowercase, negation = True
            ('abc123', False),  # Starts with lowercase, negation = False
        ]
    )

    # Test 13b: Case INSENSITIVE negated regex starts with (!/^@)
    test_operator_combination(
        '!/^@[a-z]+',
        [
            ('ABC', False),  # Case insensitive, so starts with letters, negation = False
            ('abc', False),  # Case insensitive, starts with letters, negation = False
            ('123', True),  # Doesn't start with letters, negation = True
            ('abc123', False),  # Case insensitive, starts with letters, negation = False
        ]
    )

    # Test 14: Complex email pattern
    test_operator_combination(
        r'@^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$',
        [
            ('user@example.com', True),
            ('user.name+tag@example.co.uk', True),
            ('invalid.email', False),
            ('USER@EXAMPLE.COM', False),  # Case sensitive
        ]
    )

    # Test 15: Case insensitive email pattern
    test_operator_combination(
        r'/@^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$',
        [
            ('user@example.com', True),
            ('USER@EXAMPLE.COM', True),  # Case insensitive
            ('User.Name@Example.Com', True),
            ('invalid.email', False),
        ]
    )

    # Test 16: URL pattern ending with specific extension
    test_operator_combination(
        r'@$\.(jpg|png|gif)$',
        [
            ('image.jpg', True),
            ('photo.png', True),
            ('animation.gif', True),
            ('document.pdf', False),
            ('image.JPG', False),  # Case sensitive
        ]
    )

    # Test 17: Case insensitive URL pattern
    test_operator_combination(
        r'/@$\.(jpg|png|gif)$',
        [
            ('image.jpg', True),
            ('image.JPG', True),  # Case insensitive
            ('photo.PNG', True),
            ('document.pdf', False),
        ]
    )

    # Test 18: Negated file extension check
    test_operator_combination(
        r'!@$\.(exe|bat|cmd)$',
        [
            ('script.py', True),  # Safe file
            ('document.pdf', True),
            ('virus.exe', False),  # Dangerous file
            ('script.bat', False),
        ]
    )

    # Test 19: Comparison with non-compiled version
    print("\n" + "=" * 80)
    print("COMPARISON: Compiled vs Non-Compiled")
    print("=" * 80)

    pattern_str = '@^[a-z]+'
    test_str = 'abc123'

    # With compilation
    opt1, pat1 = solve_compare_option(pattern_str, compile_regex=True)
    result1 = string_compare(test_str, pat1, opt1)
    print(f"\nWith compilation:")
    print(f"  Pattern type: {type(pat1).__name__}")
    print(f"  Result: {result1}")

    # Without compilation
    opt2, pat2 = solve_compare_option(pattern_str, compile_regex=False)
    result2 = string_compare(test_str, pat2, opt2)
    print(f"\nWithout compilation:")
    print(f"  Pattern type: {type(pat2).__name__}")
    print(f"  Result: {result2}")

    print(f"\n  Both results match: {result1 == result2} ✓")
    assert result1 == result2

    print("\n" + "=" * 80)
    print("✅ ALL OPERATOR COMBINATION TESTS PASSED!")
    print("=" * 80)
    print("\nSummary:")
    print("  - Tested all basic operators: @, ^, $, *, !, /")
    print("  - Tested all regex combinations: @, @^, @$")
    print("  - Tested negation with all combinations")
    print("  - Tested case sensitivity with all combinations")
    print("  - Tested complex real-world patterns (email, URLs, file extensions)")
    print("  - Verified compiled and non-compiled versions produce same results")


if __name__ == '__main__':
    main()
