"""
Test that CSS color fixes in textual_console_utils.py are applied correctly
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

from python_utils.console_utils.textual_console_utils import (
    ProgressDashboard,
    LogViewer,
    LiveMetrics,
    HPRINT_TITLE_COLOR
)

print("=" * 80)
print("Testing CSS Color Fixes in textual_console_utils.py")
print("=" * 80)
print()

# Expected color value
expected_color = HPRINT_TITLE_COLOR
print(f"Expected color constant value: {expected_color}")
print()

# Test 1: ProgressDashboard CSS
print("1. Testing ProgressDashboard.CSS:")
print("-" * 80)
dashboard_css = ProgressDashboard.CSS
print(f"CSS contains '{expected_color}': {expected_color in dashboard_css}")
print(f"CSS contains hardcoded 'bright_cyan': {'bright_cyan' in dashboard_css}")
if expected_color in dashboard_css and 'bright_cyan' not in dashboard_css:
    print("[PASS] ProgressDashboard uses color constant correctly")
else:
    print("[FAIL] ProgressDashboard still has hardcoded colors or missing constant")
print()

# Test 2: LogViewer CSS
print("2. Testing LogViewer.CSS:")
print("-" * 80)
logviewer_css = LogViewer.CSS
print(f"CSS contains '{expected_color}': {expected_color in logviewer_css}")
print(f"CSS contains hardcoded 'bright_cyan': {'bright_cyan' in logviewer_css}")
if expected_color in logviewer_css and 'bright_cyan' not in logviewer_css:
    print("[PASS] LogViewer uses color constant correctly")
else:
    print("[FAIL] LogViewer still has hardcoded colors or missing constant")
print()

# Test 3: LiveMetrics CSS
print("3. Testing LiveMetrics.CSS:")
print("-" * 80)
livemetrics_css = LiveMetrics.CSS
print(f"CSS contains '{expected_color}': {expected_color in livemetrics_css}")
print(f"CSS contains hardcoded 'bright_cyan': {'bright_cyan' in livemetrics_css}")
if expected_color in livemetrics_css and 'bright_cyan' not in livemetrics_css:
    print("[PASS] LiveMetrics uses color constant correctly")
else:
    print("[FAIL] LiveMetrics still has hardcoded colors or missing constant")
print()

# Summary
print("=" * 80)
print("CSS Snippet Examples:")
print("=" * 80)
print()

print("ProgressDashboard CSS (first 200 chars):")
print(dashboard_css[:200])
print()

print("LogViewer CSS (first 200 chars):")
print(logviewer_css[:200])
print()

print("LiveMetrics CSS (first 200 chars):")
print(livemetrics_css[:200])
print()

print("=" * 80)
print("CSS color fix tests completed!")
print("=" * 80)
