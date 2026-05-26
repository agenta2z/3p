"""
Test the refactored message functions in rich_console_utils.py
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

from python_utils.console_utils.rich_console_utils import (
    cprint_message, hprint_message, eprint_message, wprint_message
)

print("=" * 80)
print("Testing Refactored Message Functions")
print("=" * 80)
print()

# Test 1: hprint_message with single message
print("1. hprint_message with single message:")
print("-" * 80)
hprint_message(title="Status", content="Processing data")
print()

# Test 2: hprint_message with pairs
print("2. hprint_message with key-value pairs:")
print("-" * 80)
hprint_message('file', 'data.csv', 'rows', 1000, title='Data Loading')
print()

# Test 3: eprint_message with single message
print("3. eprint_message with single message:")
print("-" * 80)
eprint_message(title="Error", content="File not found")
print()

# Test 4: eprint_message with pairs
print("4. eprint_message with key-value pairs:")
print("-" * 80)
eprint_message('error_code', 404, 'error_type', 'NotFoundError', title='Error Details')
print()

# Test 5: wprint_message with single message
print("5. wprint_message with single message:")
print("-" * 80)
wprint_message(title="Warning", content="Low memory")
print()

# Test 6: wprint_message with pairs
print("6. wprint_message with key-value pairs:")
print("-" * 80)
wprint_message('memory', '85%', 'disk', '90%', title='Resource Warnings')
print()

# Test 7: cprint_message with custom colors (single message)
print("7. cprint_message with custom colors:")
print("-" * 80)
cprint_message(title="Success", content="Operation completed", title_color="green", content_color="white")
print()

# Test 8: cprint_message with custom colors (pairs)
print("8. cprint_message with custom colors and pairs:")
print("-" * 80)
cprint_message('metric1', 100, 'metric2', 200, title='Custom Metrics', title_color="magenta", content_color="yellow")
print()

print("=" * 80)
print("All message function tests completed!")
print("=" * 80)
