"""
Test that bk_color parameter works correctly in rich_console_utils.py
to match the behavior of basics.py
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

print("=" * 80)
print("Testing bk_color parameter in rich_console_utils.py")
print("=" * 80)
print()

# Test 1: Import and test basics.py (colorama-based)
print("1. Testing basics.py (colorama-based):")
print("-" * 80)
from python_utils.console_utils.colorama_console_utils import hprint as colorama_hprint
from python_utils.console_utils.colorama_console_utils import eprint as colorama_eprint
from python_utils.console_utils.colorama_console_utils import wprint as colorama_wprint

colorama_hprint("This is `highlighted` text with white background", end='\n')
colorama_eprint("This is `error highlighted` text with bright yellow background", end='\n')
colorama_wprint("This is `warning highlighted` text with yellow background", end='\n')
print()

# Test 2: Import and test rich_console_utils.py (Rich-based)
print("2. Testing rich_console_utils.py (Rich-based):")
print("-" * 80)
from python_utils.console_utils.rich_console_utils import hprint as rich_hprint
from python_utils.console_utils.rich_console_utils import eprint as rich_eprint
from python_utils.console_utils.rich_console_utils import wprint as rich_wprint
from python_utils.console_utils.rich_console_utils import cprint

rich_hprint("This is `highlighted` text with white background", end='\n')
rich_eprint("This is `error highlighted` text with bright yellow background", end='\n')
rich_wprint("This is `warning highlighted` text with yellow background", end='\n')
print()

# Test 3: Test custom bk_color
print("3. Testing custom bk_color parameter:")
print("-" * 80)
cprint("This has `cyan` highlights on `white` background", color="cyan", bk_color="white")
cprint("This has `red` highlights on `bright_yellow` background", color="red", bk_color="bright_yellow")
cprint("This has `green` highlights on `blue` background", color="green", bk_color="blue")
print()

# Test 4: Verify color constants are used correctly
print("4. Verifying color constant usage:")
print("-" * 80)
from python_utils.console_utils.rich_console_utils import (
    HPRINT_HEADER_OR_HIGHLIGHT_COLOR, HPRINT_MESSAGE_BODY_COLOR,
    EPRINT_HEADER_OR_HIGHLIGHT_COLOR, EPRINT_MESSAGE_BODY_COLOR,
    WPRINT_HEADER_OR_HIGHLIGHT_COLOR, WPRINT_MESSAGE_BODY_COLOR,
)

print(f"HPRINT: highlight={HPRINT_HEADER_OR_HIGHLIGHT_COLOR}, background={HPRINT_MESSAGE_BODY_COLOR}")
print(f"EPRINT: highlight={EPRINT_HEADER_OR_HIGHLIGHT_COLOR}, background={EPRINT_MESSAGE_BODY_COLOR}")
print(f"WPRINT: highlight={WPRINT_HEADER_OR_HIGHLIGHT_COLOR}, background={WPRINT_MESSAGE_BODY_COLOR}")
print()

# Test 5: Test escaped backticks
print("5. Testing escaped backticks:")
print("-" * 80)
rich_hprint("Use ``double backticks`` to show `literal` backticks", end='\n')
rich_eprint("Error with ``escaped quotes`` and `highlighted` text", end='\n')
rich_wprint("Warning about ``code`` with `important` details", end='\n')
print()

print("=" * 80)
print("[OK] All tests completed!")
print("=" * 80)
