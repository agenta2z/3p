"""
Test the panel printing functions in rich_console_utils.py
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

from python_utils.console_utils.rich_console_utils import (
    cprint_panel, hprint_panel, eprint_panel, wprint_panel
)

print("=" * 80)
print("Testing Panel Functions in rich_console_utils.py")
print("=" * 80)
print()

# Test 1: hprint_panel (cyan border)
print("1. hprint_panel (cyan border for info/highlight):")
print("-" * 80)
hprint_panel(
    "This is an information panel with cyan borders.\nYou can add multiple lines and formatting.",
    title="Information"
)
print()

# Test 2: eprint_panel (red border)
print("2. eprint_panel (red border for errors):")
print("-" * 80)
eprint_panel(
    "This is an error panel with red borders.\nUse for critical errors and failures!",
    title="Error"
)
print()

# Test 3: wprint_panel (magenta border)
print("3. wprint_panel (magenta border for warnings):")
print("-" * 80)
wprint_panel(
    "This is a warning panel with magenta borders.\nIdeal for warnings and deprecation notices.",
    title="Warning"
)
print()

# Test 4: cprint_panel (custom border)
print("4. cprint_panel (custom green border for success):")
print("-" * 80)
cprint_panel(
    "This is a custom panel with green borders.\nPerfect for success messages!",
    title="Success",
    border_style="green"
)
print()

print("=" * 80)
print("All panel tests completed!")
print("=" * 80)
