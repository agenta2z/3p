"""
Test the refactored section separator functions
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

from python_utils.console_utils.rich_console_utils import (
    cprint_section_separator,
    hprint_section_separator,
    eprint_section_separator,
    wprint_section_separator,
    hprint_pairs,
    eprint_pairs,
    wprint_pairs,
    cprint_pairs
)

print("=" * 80)
print("Testing Refactored Section Separator Functions")
print("=" * 80)
print()

# Test 1: Base cprint_section_separator with default colors
print("1. cprint_section_separator with default (cyan) color:")
print("-" * 80)
cprint_section_separator()

# Test 2: Base cprint_section_separator with custom color
print("2. cprint_section_separator with custom green color:")
print("-" * 80)
cprint_section_separator(title_color="green", title_style="bold")

# Test 3: hprint_section_separator
print("3. hprint_section_separator (delegates to cprint_section_separator):")
print("-" * 80)
hprint_section_separator()

# Test 4: eprint_section_separator
print("4. eprint_section_separator (delegates to cprint_section_separator):")
print("-" * 80)
eprint_section_separator()

# Test 5: wprint_section_separator
print("5. wprint_section_separator (delegates to cprint_section_separator):")
print("-" * 80)
wprint_section_separator()

# Test 6: Verify separators are used in pairs functions
print("6. Verify separators are called from hprint_pairs:")
print("-" * 80)
hprint_pairs('metric1', 100, 'metric2', 200, title='Metrics')

print("7. Verify separators are called from eprint_pairs:")
print("-" * 80)
eprint_pairs('error', 'NotFound', 'code', 404, title='Error')

print("8. Verify separators are called from wprint_pairs:")
print("-" * 80)
wprint_pairs('memory', '85%', 'disk', '90%', title='Warnings')

print("9. Verify separators are called from cprint_pairs with custom color:")
print("-" * 80)
cprint_pairs('key1', 'val1', 'key2', 'val2', title='Custom', title_color='magenta')

print("=" * 80)
print("All section separator refactoring tests completed!")
print("=" * 80)
