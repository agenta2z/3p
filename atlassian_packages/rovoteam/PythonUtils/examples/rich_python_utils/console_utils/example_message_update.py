"""Example: Using message tracking to prevent console flooding.

This example demonstrates how to use the message_id and update_previous
parameters in hprint_message to update messages in place instead of
printing repeated lines.

Use Case: Polling loops, progress updates, status checks
"""

import time
import sys
import os

from resolve_path import resolve_path
resolve_path()

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
from python_utils.console_utils import hprint_message, clear_message, get_current_backend

# Enable ANSI escape codes on Windows for cursor control
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Fallback if enabling fails


def example_1_simple_progress():
    """Example 1: Simple progress indicator"""
    print("\n" + "=" * 50)
    print("Example 1: Simple Progress Update")
    print("=" * 50 + "\n")

    for progress in range(0, 101, 10):
        hprint_message(
            title="Progress",
            content=f"{progress}%",
            message_id="progress",
            update_previous=True
        )
        time.sleep(0.3)

    print("\n[+] Progress complete!\n")


def example_2_status_polling():
    """Example 2: Status polling (like queue checking)"""
    print("\n" + "=" * 50)
    print("Example 2: Service Status Polling")
    print("=" * 50 + "\n")

    # Simulate checking for a service
    for attempt in range(1, 6):
        hprint_message(
            title="Service Check",
            content=f"Waiting for service... (attempt {attempt})",
            message_id="service_status",
            update_previous=True
        )
        time.sleep(0.5)

    # Service found
    hprint_message(
        title="Service Check",
        content="Service is ready!",
        message_id="service_status",
        update_previous=True
    )

    print("\n[+] Service connected!\n")


def example_3_multiple_tasks():
    """Example 3: Tracking multiple independent tasks"""
    print("\n" + "=" * 50)
    print("Example 3: Multiple Task Tracking")
    print("=" * 50 + "\n")

    # Initialize tasks
    tasks = {
        "download": ["Preparing...", "Downloading...", "Extracting...", "Complete!"],
        "processing": ["Loading...", "Processing...", "Finalizing...", "Done!"],
        "upload": ["Connecting...", "Uploading...", "Verifying...", "Success!"]
    }

    # Simulate tasks progressing at different rates
    max_steps = max(len(steps) for steps in tasks.values())

    for step in range(max_steps):
        for task_name, steps in tasks.items():
            if step < len(steps):
                hprint_message(
                    title=task_name.capitalize(),
                    content=steps[step],
                    message_id=f"task_{task_name}",
                    update_previous=(step > 0)  # Update after first message
                )
        time.sleep(0.5)

    print("\n[+] All tasks complete!\n")


def example_4_temporary_message():
    """Example 4: Temporary message that gets cleared"""
    print("\n" + "=" * 50)
    print("Example 4: Temporary Message")
    print("=" * 50 + "\n")

    # Show a temporary warning
    hprint_message(
        title="Notice",
        content="Processing large file, this may take a while...",
        message_id="temp_notice"
    )
    time.sleep(2)

    # Clear the warning and show completion
    clear_message("temp_notice")
    hprint_message(title="Complete", content="File processed successfully!")

    print("\n[+] Temporary message demonstration complete!\n")


def example_5_real_world_polling():
    """Example 5: Real-world polling scenario (like agent_debugger)"""
    print("\n" + "=" * 50)
    print("Example 5: Real-World Queue Polling")
    print("=" * 50 + "\n")

    print("Starting queue monitor...\n")

    # Simulate the agent_debugger scenario
    queue_found = False
    attempt = 0
    max_attempts = 10

    while not queue_found and attempt < max_attempts:
        attempt += 1

        # This would normally flood the console with repeated messages
        hprint_message(
            title="Queue Check",
            content=f"No queue storage found. Waiting... (attempt {attempt}/{max_attempts})",
            message_id="queue_monitor",
            update_previous=(attempt > 1)  # Update after first message
        )

        time.sleep(0.5)

        # Simulate finding the queue after a few attempts
        if attempt >= 5:
            queue_found = True

    if queue_found:
        hprint_message(
            title="Queue Check",
            content="Queue storage found! Connecting...",
            message_id="queue_monitor",
            update_previous=True
        )
        time.sleep(0.5)

        hprint_message(
            title="Queue Check",
            content="Connected successfully!",
            message_id="queue_monitor",
            update_previous=True
        )

    print("\n[+] Queue monitoring demonstration complete!\n")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print(" MESSAGE UPDATE FEATURE - EXAMPLES")
    print("=" * 60)
    print(f"\nActive backend: {get_current_backend()}")
    print("\nThese examples show how to prevent console flooding")
    print("using message_id and update_previous parameters.\n")

    example_1_simple_progress()
    input("Press Enter for next example...")

    example_2_status_polling()
    input("Press Enter for next example...")

    example_3_multiple_tasks()
    input("Press Enter for next example...")

    example_4_temporary_message()
    input("Press Enter for next example...")

    example_5_real_world_polling()

    print("=" * 60)
    print(" ALL EXAMPLES COMPLETE")
    print("=" * 60)
    print(f"\nBackend used: {get_current_backend()}")
    print("\nKey Takeaways:")
    print("1. Use message_id to track messages")
    print("2. Set update_previous=True to update in place")
    print("3. Use clear_message() to remove tracked messages")
    print("4. Perfect for polling loops and progress indicators")
    print("\n[i] Run this script again and choose the other backend to compare!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
