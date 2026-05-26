"""Test script for pairs message tracking and in-place update features.

This test demonstrates that the message_id and update_previous parameters
work correctly with xprint_pairs methods to prevent console flooding.
"""

import time
import sys
from pathlib import Path

# Enable ANSI escape codes on Windows for cursor control
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Fallback if enabling fails

# Find and add src directory to path (robust - works even if file is moved)
current = Path(__file__).resolve().parent
while current != current.parent:  # Stop at filesystem root
    src_candidate = current / 'src'
    if src_candidate.is_dir():
        sys.path.insert(0, str(src_candidate))
        break
    current = current.parent
else:
    raise FileNotFoundError("Could not find 'src' directory in parent hierarchy")

from python_utils.console_utils import hprint_pairs, eprint_pairs, wprint_pairs


def test_basic_pairs_update():
    """Test 1: Basic pairs update in place"""
    print("\n=== Test 1: Basic Pairs Update ===")

    # Initial pairs
    hprint_pairs(
        'status', 'Initializing',
        'progress', '0%',
        title='System',
        message_id='system'
    )
    time.sleep(1)

    # Update the same pairs
    hprint_pairs(
        'status', 'Processing',
        'progress', '50%',
        title='System',
        message_id='system',
        update_previous=True
    )
    time.sleep(1)

    # Update again
    hprint_pairs(
        'status', 'Complete',
        'progress', '100%',
        title='System',
        message_id='system',
        update_previous=True
    )
    time.sleep(1)

    print("[+] Basic pairs update test complete\n")


def test_without_update():
    """Test 2: Pairs without update_previous (should print new lines)"""
    print("\n=== Test 2: Without Update (shows flooding) ===")

    for i in range(3):
        hprint_pairs(
            'attempt', i+1,
            'status', 'checking',
            title='Check',
            message_id='check'
        )
        time.sleep(0.5)

    print("[+] Non-update test complete (should see 3 separate outputs)\n")


def test_with_update():
    """Test 3: Pairs with update_previous (should update in place)"""
    print("\n=== Test 3: With Update (prevents flooding) ===")

    for i in range(3):
        hprint_pairs(
            'attempt', i+1,
            'status', 'checking',
            title='Check',
            message_id='check_updated',
            update_previous=True
        )
        time.sleep(0.5)

    print("[+] Update test complete (should see only final output)\n")


def test_multiple_pairs():
    """Test 4: Multiple key-value pairs updating"""
    print("\n=== Test 4: Multiple Pairs Tracking ===")

    for i in range(5):
        hprint_pairs(
            'epoch', i+1,
            'loss', f'{1.0/(i+1):.3f}',
            'accuracy', f'{0.7 + i*0.05:.2f}',
            'learning_rate', f'{0.001 * (0.9**i):.6f}',
            title='Training',
            message_id='training',
            update_previous=True
        )
        time.sleep(0.7)

    print("[+] Multiple pairs test complete\n")


def test_multiple_trackers():
    """Test 5: Multiple independent pair trackers"""
    print("\n=== Test 5: Multiple Pair Trackers ===")

    for step in range(3):
        # Update first tracker
        hprint_pairs(
            'step', step,
            'value', step * 10,
            title='Tracker A',
            message_id='tracker_a',
            update_previous=True
        )
        time.sleep(0.4)

        # Update second tracker
        hprint_pairs(
            'step', step,
            'value', step * 20,
            title='Tracker B',
            message_id='tracker_b',
            update_previous=True
        )
        time.sleep(0.4)

    print("[+] Multiple trackers test complete\n")


def test_error_pairs():
    """Test 6: Error pairs with update"""
    print("\n=== Test 6: Error Pairs Update ===")

    for i in range(4):
        eprint_pairs(
            'errors', i,
            'warnings', i*2,
            'retries', i,
            title='Error Summary',
            message_id='errors',
            update_previous=True
        )
        time.sleep(0.6)

    print("[+] Error pairs test complete\n")


def test_warning_pairs():
    """Test 7: Warning pairs with update"""
    print("\n=== Test 7: Warning Pairs Update ===")

    for i in range(4):
        wprint_pairs(
            'checks', i+1,
            'issues', i,
            title='Validation',
            message_id='validation',
            update_previous=True
        )
        time.sleep(0.6)

    print("[+] Warning pairs test complete\n")


if __name__ == "__main__":
    print("=" * 60)
    print("PAIRS MESSAGE TRACKING AND UPDATE TESTS")
    print("=" * 60)

    test_basic_pairs_update()
    input("Press Enter to continue to next test...")

    test_without_update()
    input("Press Enter to continue to next test...")

    test_with_update()
    input("Press Enter to continue to next test...")

    test_multiple_pairs()
    input("Press Enter to continue to next test...")

    test_multiple_trackers()
    input("Press Enter to continue to next test...")

    test_error_pairs()
    input("Press Enter to continue to next test...")

    test_warning_pairs()

    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
