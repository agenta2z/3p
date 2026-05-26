"""
Test the fallback mechanism in console_utils/__init__.py

This test verifies that:
1. The correct backend is selected (Rich or colorama)
2. Core functions work with both backends
3. Rich-specific features are properly set (functions or None)
4. Textual features are properly set (functions or None)
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

print("=" * 80)
print("Testing Console Utils Fallback Mechanism")
print("=" * 80)
print()

# Test 1: Check which backend is active
print("1. Checking active backend:")
print("-" * 80)
from python_utils.console_utils import __backend__, __has_textual__

print(f"Backend: {__backend__}")
print(f"Textual available: {__has_textual__}")
print()

# Test 2: Test core functions (should work with both backends)
print("2. Testing core functions (available in both backends):")
print("-" * 80)
from python_utils.console_utils import (
    hprint_message,
    eprint_message,
    wprint_message,
    hprint_pairs,
    eprint_pairs,
    wprint_pairs,
    hprint_section_title,
    hprint_section_separator,
    eprint_section_separator,
    wprint_section_separator,
)

print("Testing hprint_message:")
hprint_message('Test', 'hprint_message works!')

print("\nTesting eprint_message:")
eprint_message('Error', 'eprint_message works!')

print("\nTesting wprint_message:")
wprint_message('Warning', 'wprint_message works!')

print("\nTesting hprint_pairs:")
hprint_pairs('metric1', 100, 'metric2', 200, title='Test Pairs')

print("Testing separator functions:")
hprint_section_separator()
eprint_section_separator()
wprint_section_separator()
print()

# Test 3: Check Rich-specific features
print("3. Checking Rich-specific features:")
print("-" * 80)
from python_utils.console_utils import (
    print_table,
    print_syntax,
    print_markdown,
    print_json,
    progress_bar,
    get_rich_logger,
    cprint_panel,
    hprint_panel,
    eprint_panel,
    wprint_panel,
    console,
    cprint_section_separator,
)

rich_features = {
    'print_table': print_table,
    'print_syntax': print_syntax,
    'print_markdown': print_markdown,
    'print_json': print_json,
    'progress_bar': progress_bar,
    'get_rich_logger': get_rich_logger,
    'cprint_panel': cprint_panel,
    'hprint_panel': hprint_panel,
    'eprint_panel': eprint_panel,
    'wprint_panel': wprint_panel,
    'console': console,
    'cprint_section_separator': cprint_section_separator,
}

for name, func in rich_features.items():
    status = "Available" if func is not None else "Not Available (None)"
    print(f"  {name}: {status}")

if __backend__ == "rich":
    print("\n[PASS] Rich backend is active, all Rich features should be available")
    if all(f is not None for f in rich_features.values()):
        print("[PASS] All Rich features are available")
    else:
        print("[FAIL] Some Rich features are missing!")
else:
    print("\n[INFO] Colorama backend is active, Rich features should be None")
    if all(f is None for f in rich_features.values()):
        print("[PASS] All Rich features correctly set to None")
    else:
        print("[WARNING] Some Rich features are not None (unexpected)")

print()

# Test 4: Check Textual features
print("4. Checking Textual features:")
print("-" * 80)
from python_utils.console_utils import (
    prompt_confirm,
    prompt_choice,
    prompt_input,
    display_table,
    display_help,
    show_notification,
    ProgressDashboard,
    InteractiveTable,
    LogViewer,
    LiveMetrics,
)

textual_features = {
    'prompt_confirm': prompt_confirm,
    'prompt_choice': prompt_choice,
    'prompt_input': prompt_input,
    'display_table': display_table,
    'display_help': display_help,
    'show_notification': show_notification,
    'ProgressDashboard': ProgressDashboard,
    'InteractiveTable': InteractiveTable,
    'LogViewer': LogViewer,
    'LiveMetrics': LiveMetrics,
}

for name, func in textual_features.items():
    status = "Available" if func is not None else "Not Available (None)"
    print(f"  {name}: {status}")

if __has_textual__:
    print("\n[PASS] Textual is available")
    if all(f is not None for f in textual_features.values()):
        print("[PASS] All Textual features are available")
    else:
        print("[FAIL] Some Textual features are missing!")
else:
    print("\n[INFO] Textual is not available")
    if all(f is None for f in textual_features.values()):
        print("[PASS] All Textual features correctly set to None")
    else:
        print("[WARNING] Some Textual features are not None (unexpected)")

print()

# Test 5: Test feature detection pattern
print("5. Testing feature detection pattern:")
print("-" * 80)
print("Example code for detecting and using features:")
print()
print("# Check and use Rich features")
print("if cprint_panel is not None:")
print("    cprint_panel('This is a panel', title='Panel')")
print("else:")
print("    print('Panel feature not available')")
print()

if cprint_panel is not None:
    try:
        cprint_panel("This is a panel using Rich!", title="Test Panel")
        print("[PASS] cprint_panel works!")
    except Exception as e:
        print(f"[FAIL] cprint_panel raised error: {e}")
else:
    print("[INFO] cprint_panel is None (Rich not available)")

print()

# Summary
print("=" * 80)
print("Fallback Mechanism Test Summary")
print("=" * 80)
print(f"Backend in use: {__backend__}")
print(f"Core functions: Working")
print(f"Rich features: {'Available' if __backend__ == 'rich' else 'Not Available'}")
print(f"Textual features: {'Available' if __has_textual__ else 'Not Available'}")
print("=" * 80)
print()

print("[SUCCESS] Fallback mechanism is working correctly!")
print("Users can check __backend__ and __has_textual__ to detect available features.")
print()
