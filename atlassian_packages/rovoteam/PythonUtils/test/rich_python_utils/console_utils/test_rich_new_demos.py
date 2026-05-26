"""
Test the new demonstration functions
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

from python_utils.console_utils.rich_console_utils import (
    color_print_pair_str, hprint_message_pair_str,
    hprint_pairs, eprint_pairs, wprint_pairs,
    hprint_section_title, hprint_section_separator,
    eprint_section_separator, wprint_section_separator,
    console
)

print("=" * 80)
print("Testing New Demonstration Functions")
print("=" * 80)
print()

# Test pair string parsing
print("1. Testing color_print_pair_str:")
print("-" * 80)
color_print_pair_str("name:model.pt,size:100MB,accuracy:0.95")
print()

print("2. Testing color_print_pair_str with custom delimiters:")
print("-" * 80)
color_print_pair_str("host=localhost;port=8080;protocol=https", pair_delimiter=';', kv_delimiter='=')
print()

print("3. Testing hprint_message_pair_str:")
print("-" * 80)
hprint_message_pair_str("epoch:10,loss:0.05,accuracy:0.95,val_loss:0.08")
print()

print("4. Testing custom colored pair strings:")
print("-" * 80)
color_print_pair_str(
    "status:running,health:good,uptime:99.9%",
    key_color="green",
    value_color="yellow"
)
print()

# Test section separators
print("5. Testing hprint_section_separator:")
print("-" * 80)
hprint_section_title("Processing Phase 1")
hprint_pairs('files', 100, 'size', '1.5GB')
hprint_section_separator()

print("6. Testing eprint_section_separator:")
print("-" * 80)
eprint_pairs(
    'error_count', 5,
    'critical', 2,
    'warnings', 3,
    title='Error Summary'
)
console.print("[dim]eprint_section_separator() called:[/dim]")
eprint_section_separator()

print("7. Testing wprint_section_separator:")
print("-" * 80)
wprint_pairs(
    'memory', '85%',
    'disk', '90%',
    title='Resource Warnings'
)
console.print("[dim]wprint_section_separator() called:[/dim]")
wprint_section_separator()

print("=" * 80)
print("All new demonstration tests completed!")
print("=" * 80)
