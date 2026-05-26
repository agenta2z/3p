"""Test script for message tracking and in-place update features in console_utils.

This test demonstrates the new message_id and update_previous parameters
that prevent console flooding by updating messages in place.
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

from python_utils.console_utils import hprint_message, clear_message


def test_basic_update():
    """Test 1: Basic message update in place"""
    print("\n=== Test 1: Basic Message Update ===")

    # Initial message
    hprint_message(title="Status", content="Initializing...", message_id="status")
    time.sleep(1)

    # Update the same message
    hprint_message(title="Status", content="Processing...", message_id="status", update_previous=True)
    time.sleep(1)

    # Update again
    hprint_message(title="Status", content="Complete!", message_id="status", update_previous=True)
    time.sleep(1)

    print("[+] Basic update test complete\n")


def test_without_update():
    """Test 2: Same message without update_previous (should print new lines)"""
    print("\n=== Test 2: Without Update (shows flooding) ===")

    for i in range(3):
        hprint_message(title="Attempt", content=f"{i+1}", message_id="attempt")
        time.sleep(0.5)

    print("[+] Non-update test complete (should see 3 separate lines)\n")


def test_with_update():
    """Test 3: Same message with update_previous (should update in place)"""
    print("\n=== Test 3: With Update (prevents flooding) ===")

    for i in range(3):
        hprint_message(title="Attempt", content=f"{i+1}", message_id="attempt_updated", update_previous=True)
        time.sleep(0.5)

    print("[+] Update test complete (should see only final line)\n")


def test_multiple_trackers():
    """Test 4: Multiple independent message trackers"""
    print("\n=== Test 4: Multiple Message Trackers ===")

    # Start first tracker
    hprint_message(title="Task A", content="Starting...", message_id="task_a")
    time.sleep(0.5)

    # Start second tracker
    hprint_message(title="Task B", content="Starting...", message_id="task_b")
    time.sleep(0.5)

    # Update first tracker
    hprint_message(title="Task A", content="50% complete", message_id="task_a", update_previous=True)
    time.sleep(0.5)

    # Update second tracker
    hprint_message(title="Task B", content="25% complete", message_id="task_b", update_previous=True)
    time.sleep(0.5)

    # Complete both
    hprint_message(title="Task A", content="Done!", message_id="task_a", update_previous=True)
    time.sleep(0.5)
    hprint_message(title="Task B", content="Done!", message_id="task_b", update_previous=True)

    print("[+] Multiple trackers test complete\n")


def test_clear_message():
    """Test 5: Clearing a tracked message"""
    print("\n=== Test 5: Clear Message ===")

    hprint_message(title="Temporary", content="This will be cleared", message_id="temp")
    time.sleep(1)

    clear_message("temp")
    print("[+] Message cleared (previous line should be gone)\n")


def test_polling_simulation():
    """Test 6: Simulating the original polling scenario"""
    print("\n=== Test 6: Polling Simulation (Real Use Case) ===")
    print("Simulating queue check that would normally flood console...\n")

    for i in range(5):
        # This simulates checking for queue repeatedly
        hprint_message(
            title="Queue Status",
            content=f"No queue storage found (attempt {i+1}/5)",
            message_id="queue_check",
            update_previous=True
        )
        time.sleep(0.8)

    # Finally found it
    hprint_message(
        title="Queue Status",
        content="Queue storage found!",
        message_id="queue_check",
        update_previous=True
    )

    print("\n[+] Polling simulation complete (should only see final status)\n")


if __name__ == "__main__":
    print("=" * 60)
    print("MESSAGE TRACKING AND UPDATE TESTS")
    print("=" * 60)

    test_basic_update()
    input("Press Enter to continue to next test...")

    test_without_update()
    input("Press Enter to continue to next test...")

    test_with_update()
    input("Press Enter to continue to next test...")

    test_multiple_trackers()
    input("Press Enter to continue to next test...")

    test_clear_message()
    input("Press Enter to continue to next test...")

    test_polling_simulation()

    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
