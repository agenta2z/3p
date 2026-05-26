"""
Simple color test for rich_console_utils.py

This script tests if colors are displaying correctly in your terminal.
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

from python_utils.console_utils.rich_console_utils import (
    console, hprint, eprint, wprint, hprint_message, cprint_message
)

print("=== COLOR TEST ===\n")

# Test 1: Direct console print with colors
print("Test 1: Direct Rich console print")
console.print("[cyan]This should be CYAN[/cyan]")
console.print("[red]This should be RED[/red]")
console.print("[yellow]This should be YELLOW[/yellow]")
console.print("[green]This should be GREEN[/green]")
console.print("[magenta]This should be MAGENTA[/magenta]")
console.print("[bright_cyan]This should be BRIGHT CYAN[/bright_cyan]")
console.print()

# Test 2: Backtick highlighting
print("Test 2: Backtick highlighting")
hprint("This has `cyan highlights` in the text")
eprint("This has `red highlights` in the text")
wprint("This has `yellow highlights` in the text")
print()

# Test 3: Message printing
print("Test 3: Message printing")
hprint_message(title="Info", content="This should have cyan title")
cprint_message("Success", "This should be green", title_color="green", content_color="white")
print()

# Test 4: Check console capabilities
print("Test 4: Console capabilities")
print(f"Console color system: {console.color_system}")
print(f"Is terminal: {console.is_terminal}")
print(f"Legacy windows: {console.legacy_windows}")
print(f"Force terminal: {console._force_terminal}")
print()

print("=== END OF TEST ===")
print("\nIf you see color names above but no actual colors,")
print("your terminal doesn't support ANSI color codes.")
print("\nRECOMMENDED SOLUTIONS:")
print("1. Use Windows Terminal (recommended)")
print("2. Enable Virtual Terminal Processing in Windows Console")
print("3. Use VSCode integrated terminal")
print("4. Use Git Bash or similar Unix-like terminal")
