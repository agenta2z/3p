"""Example: Using message tracking with xprint_pairs methods.

This example demonstrates how to use the message_id and update_previous
parameters with hprint_pairs, eprint_pairs, and wprint_pairs to update
key-value pair messages in place instead of flooding the console.

Use Cases:
- Training loops and metrics tracking
- Multi-metric progress reporting
- Custom section separators
- Vertical/spaced layouts with newline separators
- Status changes with mixed print types

Examples (10 total):
1. Training loop metrics
2. System resource monitoring
3. Multiple independent metric sets
4. Error and warning tracking
5. Many key-value pairs
6. Custom section separators
7. Newline separators (vertical layout)
8. No title (inline updates)
9. Mixed print types (status changes)
10. Double newline separators (spaced layout)
"""

import time
import sys
import os
from pathlib import Path

# Find and add src directory to path (find 'examples' folder and replace with 'src')
current = Path(__file__).resolve()
while current != current.parent:  # Stop at filesystem root
    if current.name == 'examples':
        src_path = current.parent / 'src'
        if src_path.is_dir():
            sys.path.insert(0, str(src_path))
            break
    current = current.parent
else:
    raise FileNotFoundError("Could not find 'examples' directory in path hierarchy")

# Let user choose backend BEFORE importing console_utils
print("\n" + "=" * 70)
print("Console Backend Selection")
print("=" * 70)

# Check what's available (try importing rich)
try:
    import rich
    has_rich = True
    print("\n[+] Rich library is installed")
except ImportError:
    has_rich = False
    print("\n[-] Rich library is NOT installed")

print("[+] Colorama library is available (required dependency)")

print("\nAvailable backends:")
if has_rich:
    print("  1. Rich (enhanced formatting, recommended)")
print("  2. Colorama (basic colors, always available)")

if has_rich:
    choice = input("\nChoose backend (1/2) or press Enter for Rich: ").strip()
    if choice == "2":
        os.environ['CONSOLE_UTILS_BACKEND'] = 'colorama'
        print("-> Using Colorama backend")
    else:
        print("-> Using Rich backend")
else:
    print("\n-> Only Colorama available (Rich not installed)")

print("=" * 70 + "\n")

# NOW import console_utils (will use the selected backend)
from python_utils.console_utils import hprint_pairs, eprint_pairs, wprint_pairs, get_current_backend

# Enable ANSI escape codes on Windows for cursor control
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Fallback if enabling fails


def example_1_training_metrics():
    """Example 1: Training loop metrics update"""
    print("\n" + "=" * 50)
    print("Example 1: Training Loop Metrics")
    print("=" * 50 + "\n")

    epochs = 5
    for epoch in range(1, epochs + 1):
        # Simulate training metrics
        loss = 1.0 / epoch
        accuracy = min(0.95, epoch * 0.15 + 0.2)
        learning_rate = 0.001 * (0.9 ** epoch)

        hprint_pairs(
            'epoch', epoch,
            'loss', f'{loss:.4f}',
            'accuracy', f'{accuracy:.2%}',
            'lr', f'{learning_rate:.6f}',
            title='Training Progress',
            message_id='training',
            update_previous=True
        )
        time.sleep(0.8)

    print("\n[+] Training complete!\n")


def example_2_system_metrics():
    """Example 2: System resource monitoring"""
    print("\n" + "=" * 50)
    print("Example 2: System Resource Monitoring")
    print("=" * 50 + "\n")

    for i in range(10):
        cpu_usage = 20 + (i * 5)
        memory_usage = 40 + (i * 3)
        disk_io = 100 + (i * 10)

        hprint_pairs(
            'CPU', f'{cpu_usage}%',
            'Memory', f'{memory_usage}%',
            'Disk I/O', f'{disk_io} MB/s',
            title='System Resources',
            message_id='system',
            update_previous=True
        )
        time.sleep(0.5)

    print("\n[+] Monitoring complete!\n")


def example_3_multiple_pair_sets():
    """Example 3: Multiple independent metric sets"""
    print("\n" + "=" * 50)
    print("Example 3: Multiple Metric Sets")
    print("=" * 50 + "\n")

    for step in range(5):
        # Model A metrics
        hprint_pairs(
            'step', step,
            'loss', f'{1.0/(step+1):.3f}',
            'acc', f'{0.7 + step*0.05:.2f}',
            title='Model A',
            message_id='model_a',
            update_previous=True
        )

        time.sleep(0.3)

        # Model B metrics
        hprint_pairs(
            'step', step,
            'loss', f'{1.2/(step+1):.3f}',
            'acc', f'{0.65 + step*0.06:.2f}',
            title='Model B',
            message_id='model_b',
            update_previous=True
        )

        time.sleep(0.5)

    print("\n[+] All models complete!\n")


def example_4_error_warnings():
    """Example 4: Error and warning pairs"""
    print("\n" + "=" * 50)
    print("Example 4: Error and Warning Tracking")
    print("=" * 50 + "\n")

    print("Simulating error tracking...\n")

    for i in range(5):
        errors = i
        warnings = i * 2

        eprint_pairs(
            'errors', errors,
            'warnings', warnings,
            'retries', i,
            title='Error Summary',
            message_id='errors',
            update_previous=True
        )
        time.sleep(0.6)

    print("\n[+] Error tracking complete!\n")


def example_5_many_pairs():
    """Example 5: Many key-value pairs updating"""
    print("\n" + "=" * 50)
    print("Example 5: Many Metrics Update")
    print("=" * 50 + "\n")

    for iteration in range(1, 6):
        hprint_pairs(
            'iteration', iteration,
            'train_loss', f'{1.0/iteration:.3f}',
            'val_loss', f'{1.2/iteration:.3f}',
            'train_acc', f'{0.5 + iteration*0.08:.2%}',
            'val_acc', f'{0.48 + iteration*0.07:.2%}',
            'precision', f'{0.6 + iteration*0.05:.2%}',
            'recall', f'{0.55 + iteration*0.06:.2%}',
            'f1_score', f'{0.57 + iteration*0.055:.2%}',
            title='Comprehensive Metrics',
            message_id='comprehensive',
            update_previous=True
        )
        time.sleep(0.7)

    print("\n[+] Comprehensive metrics complete!\n")


def example_6_custom_separators():
    """Example 6: Custom section separators"""
    print("\n" + "=" * 50)
    print("Example 6: Custom Section Separators")
    print("=" * 50 + "\n")

    print("Demonstrating different separator styles...\n")

    for i in range(1, 6):
        # Different separator for each iteration
        separators = ['----', '='*40, '***', '-='*20, '']
        sep_names = ['Default', 'Equals', 'Asterisks', 'Pattern', 'None']

        hprint_pairs(
            'iteration', i,
            'separator', sep_names[i-1],
            'progress', f'{i*20}%',
            title='Custom Separator Demo',
            message_id='custom_sep',
            update_previous=True,
            section_separator=separators[i-1]
        )
        time.sleep(0.8)

    print("\n[+] Custom separator demo complete!\n")


def example_7_newline_separators():
    """Example 7: Newline separators between pairs"""
    print("\n" + "=" * 50)
    print("Example 7: Newline Separators (Vertical Layout)")
    print("=" * 50 + "\n")

    print("Each key-value pair on its own line...\n")

    for i in range(1, 6):
        hprint_pairs(
            'batch', i,
            'samples_processed', i * 32,
            'current_loss', f'{1.0/(i+1):.4f}',
            'throughput', f'{i * 128} samples/sec',
            title='Batch Processing',
            sep='\n',  # Newline separator - each pair on own line
            message_id='vertical',
            update_previous=True
        )
        time.sleep(0.7)

    print("\n[+] Vertical layout demo complete!\n")


def example_8_no_title_pairs():
    """Example 8: Pairs without title (inline updates)"""
    print("\n" + "=" * 50)
    print("Example 8: No Title (Inline Updates)")
    print("=" * 50 + "\n")

    print("Simple inline status updates...\n")

    for i in range(1, 11):
        hprint_pairs(
            'Status', 'Processing',
            'File', f'data_{i:03d}.csv',
            'Progress', f'{i*10}%',
            message_id='inline',
            update_previous=True
        )
        time.sleep(0.4)

    # Final update
    hprint_pairs(
        'Status', 'Complete',
        'File', 'All files',
        'Progress', '100%',
        message_id='inline',
        update_previous=True
    )

    print("\n[+] Inline updates complete!\n")


def example_9_mixed_print_types():
    """Example 9: Switching between print types"""
    print("\n" + "=" * 50)
    print("Example 9: Mixed Print Types (Status Changes)")
    print("=" * 50 + "\n")

    # Start with info
    hprint_pairs(
        'status', 'Starting',
        'phase', 'Initialization',
        title='Process Status',
        message_id='status',
        update_previous=False
    )
    time.sleep(1)

    # Update to running
    hprint_pairs(
        'status', 'Running',
        'phase', 'Processing',
        title='Process Status',
        message_id='status',
        update_previous=True
    )
    time.sleep(1)

    # Warning state
    wprint_pairs(
        'status', 'Warning',
        'phase', 'Retry needed',
        title='Process Status',
        message_id='status',
        update_previous=True
    )
    time.sleep(1)

    # Error state
    eprint_pairs(
        'status', 'Error',
        'phase', 'Failed',
        title='Process Status',
        message_id='status',
        update_previous=True
    )
    time.sleep(1)

    # Recovery
    hprint_pairs(
        'status', 'Recovered',
        'phase', 'Resuming',
        title='Process Status',
        message_id='status',
        update_previous=True
    )
    time.sleep(1)

    # Success
    hprint_pairs(
        'status', 'Complete',
        'phase', 'Finished',
        title='Process Status',
        message_id='status',
        update_previous=True
    )

    print("\n[+] Status change demo complete!\n")


def example_10_double_newline_separator():
    """Example 10: Double newline separators (spaced layout)"""
    print("\n" + "=" * 50)
    print("Example 10: Double Newline Separators (Spaced)")
    print("=" * 50 + "\n")

    print("Extra spacing between pairs...\n")

    for i in range(1, 5):
        hprint_pairs(
            'checkpoint', i,
            'model_saved', f'model_v{i}.pt',
            'accuracy', f'{0.8 + i*0.03:.2%}',
            'size', f'{150 + i*25} MB',
            title='Model Checkpoints',
            sep='\n\n',  # Double newline - blank line between pairs
            message_id='spaced',
            update_previous=True
        )
        time.sleep(0.9)

    print("\n[+] Spaced layout demo complete!\n")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print(" PAIRS MESSAGE UPDATE FEATURE - EXAMPLES")
    print("=" * 60)
    print(f"\nActive backend: {get_current_backend()}")
    print("\nThese examples show how to use message_id and update_previous")
    print("with xprint_pairs methods to prevent console flooding.\n")

    example_1_training_metrics()
    input("Press Enter for next example...")

    example_2_system_metrics()
    input("Press Enter for next example...")

    example_3_multiple_pair_sets()
    input("Press Enter for next example...")

    example_4_error_warnings()
    input("Press Enter for next example...")

    example_5_many_pairs()
    input("Press Enter for next example...")

    example_6_custom_separators()
    input("Press Enter for next example...")

    example_7_newline_separators()
    input("Press Enter for next example...")

    example_8_no_title_pairs()
    input("Press Enter for next example...")

    example_9_mixed_print_types()
    input("Press Enter for next example...")

    example_10_double_newline_separator()

    print("=" * 60)
    print(" ALL EXAMPLES COMPLETE")
    print("=" * 60)
    print(f"\nBackend used: {get_current_backend()}")
    print("\nKey Takeaways:")
    print("1. Use message_id to track pair messages")
    print("2. Set update_previous=True to update in place")
    print("3. Perfect for training loops and metrics tracking")
    print("4. Works with multiple pairs - all update together")
    print("5. Customize section separators with section_separator parameter")
    print("6. Use sep='\\n' for vertical layout (each pair on own line)")
    print("7. Use sep='\\n\\n' for extra spacing between pairs")
    print("8. Mix hprint/eprint/wprint for status changes")
    print("\n[i] Run this script again and choose the other backend to compare!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
