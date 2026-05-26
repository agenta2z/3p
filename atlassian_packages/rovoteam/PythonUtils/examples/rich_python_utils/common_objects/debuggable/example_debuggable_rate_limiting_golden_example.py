"""
Golden Example: Debuggable Rate Limiting with Console Utils Integration

This interactive example demonstrates the full integration of Debuggable's
rate limiting and console update features with hprint_message from console_utils.

Features:
- Choose console backend (Rich or Colorama)
- Choose mode: Rate Limit Only, Console Update Only, or Both Combined
- Specify custom rate limit
- See expected vs actual message counts
- Real in-place console updates when enabled

This is the recommended way to use Debuggable for training loops and progress tracking.
"""

import time

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.common_objects.debuggable import Debuggable
from python_utils.console_utils import hprint_message


def select_backend():
    """Let user choose console backend."""
    print("\n" + "=" * 70)
    print("Console Backend Selection")
    print("=" * 70)

    # Check what's available
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

    print("=" * 70)


def select_mode():
    """Let user choose the demo mode."""
    print("\n" + "=" * 70)
    print("Demo Mode Selection")
    print("=" * 70)
    print("\nAvailable modes:")
    print("  1. Rate Limit Only - Reduces message frequency, no in-place updates")
    print("  2. Console Update Only - All messages update in place, no rate limit")
    print("  3. Both Combined - Rate limited + in-place updates (recommended)")
    print("  4. No Features (baseline) - All messages printed normally")

    while True:
        choice = input("\nChoose mode (1/2/3/4) or press Enter for Combined: ").strip()
        if choice == "":
            choice = "3"
        if choice in ["1", "2", "3", "4"]:
            mode_names = {
                "1": "Rate Limit Only",
                "2": "Console Update Only",
                "3": "Both Combined",
                "4": "No Features (baseline)"
            }
            print(f"-> Selected: {mode_names[choice]}")
            return int(choice)
        print("Invalid choice. Please enter 1, 2, 3, or 4.")


def select_rate_limit():
    """Let user specify rate limit."""
    print("\n" + "=" * 70)
    print("Rate Limit Configuration")
    print("=" * 70)
    print("\nRate limit determines minimum seconds between displayed messages.")
    print("  - 0.0 = No rate limit (display all messages)")
    print("  - 0.5 = Display at most 2 messages per second")
    print("  - 1.0 = Display at most 1 message per second")

    while True:
        choice = input("\nEnter rate limit in seconds (0.0-5.0) or press Enter for 0.5: ").strip()
        if choice == "":
            rate_limit = 0.5
            break
        try:
            rate_limit = float(choice)
            if 0.0 <= rate_limit <= 5.0:
                break
            print("Please enter a value between 0.0 and 5.0")
        except ValueError:
            print("Please enter a valid number")

    print(f"-> Rate limit: {rate_limit}s")
    return rate_limit


def calculate_expected_messages(total_iterations, iteration_delay, rate_limit):
    """Calculate expected number of messages with rate limiting."""
    if rate_limit <= 0:
        return total_iterations

    total_time = total_iterations * iteration_delay
    # First message always displays, then one per rate_limit interval
    expected = 1 + int(total_time / rate_limit)
    return min(expected, total_iterations)


def check_cursor_control_support():
    """Check if terminal supports cursor control for in-place updates."""
    import os

    # PyCharm and some IDEs don't support cursor control
    if os.getenv('PYCHARM_HOSTED') or 'PYCHARM' in os.getenv('TERMINAL_EMULATOR', ''):
        return False, "PyCharm terminal detected"

    # Check if stdout is a tty
    if not sys.stdout.isatty():
        return False, "stdout is not a tty"

    # On Windows, try to enable ANSI escape codes
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True, "Windows ANSI enabled"
        except Exception:
            return False, "Windows ANSI not supported"

    return True, "Terminal supports cursor control"


def run_demo(mode, rate_limit):
    """Run the demo with selected settings."""
    # Check cursor control support
    cursor_supported, cursor_reason = check_cursor_control_support()

    # Import after backend selection
    from python_utils.console_utils import hprint_message, get_current_backend
    from python_utils.common_objects.debuggable import Debuggable

    # Demo parameters
    total_iterations = 20
    iteration_delay = 0.1  # seconds per iteration
    total_time = total_iterations * iteration_delay

    # Configure based on mode
    enable_rate_limit = mode in [1, 3]
    enable_console_update = mode in [2, 3]
    actual_rate_limit = rate_limit if enable_rate_limit else 0.0

    # Calculate expectations
    if enable_rate_limit:
        expected_messages = calculate_expected_messages(total_iterations, iteration_delay, actual_rate_limit)
    else:
        expected_messages = total_iterations

    # Print configuration summary
    print("\n" + "=" * 70)
    print("Demo Configuration")
    print("=" * 70)
    print(f"\nBackend: {get_current_backend()}")
    print(f"Mode: {['', 'Rate Limit Only', 'Console Update Only', 'Both Combined', 'No Features'][mode]}")
    print(f"\nIterations: {total_iterations}")
    print(f"Delay per iteration: {iteration_delay}s")
    print(f"Total runtime: {total_time}s")
    print(f"\nRate limiting: {'ENABLED' if enable_rate_limit else 'DISABLED'}")
    if enable_rate_limit:
        print(f"  Rate limit: {actual_rate_limit}s")
    print(f"Console update: {'ENABLED' if enable_console_update else 'DISABLED'}")
    if enable_console_update:
        print(f"  Cursor control: {'SUPPORTED' if cursor_supported else 'NOT SUPPORTED'} ({cursor_reason})")
        if not cursor_supported:
            print("  WARNING: In-place updates will NOT work - messages will scroll")
    print("-" * 70)
    print(f"Without rate limiting: {total_iterations} messages would display")
    if enable_rate_limit:
        print(f"With {actual_rate_limit}s rate limit: expect ~{expected_messages} messages")
    if enable_console_update and cursor_supported:
        print("With console update: messages update in place (no scrolling)")
    elif enable_console_update and not cursor_supported:
        print("With console update: [UPD] shown but lines will scroll (terminal limitation)")
    print("=" * 70)

    input("\nPress Enter to start the demo...")

    # Create a wrapper logger that uses hprint_message
    displayed_count = [0]  # Use list for mutable closure

    def hprint_logger(log_data, message_id=None, update_previous=False, **kwargs):
        """Logger wrapper that uses hprint_message."""
        displayed_count[0] += 1
        item = log_data['item']

        # Format the content with [NEW]/[UPD] indicator
        mode_indicator = "[UPD]" if update_previous else "[NEW]"
        content = f"{mode_indicator} Epoch {item['epoch']:2d} | Loss: {item['loss']:.4f} | Accuracy: {item['accuracy']:.1f}%"

        hprint_message(
            title="Training Progress",
            content=content,
            message_id=message_id,
            update_previous=update_previous
        )

    # Define the training loop class
    class TrainingSimulator(Debuggable):
        def train(self, epochs):
            for epoch in range(epochs):
                # Simulate training metrics
                loss = 1.0 / (epoch + 1)
                accuracy = min(99.9, 50 + epoch * 2.5)

                self.log_info(
                    {
                        'epoch': epoch,
                        'loss': loss,
                        'accuracy': accuracy
                    },
                    log_type='Training'
                )
                time.sleep(iteration_delay)

    # Create and run the simulator
    print("\n" + "-" * 70)
    print("Training Output:")
    print("-" * 70 + "\n")

    simulator = TrainingSimulator(
        logger=hprint_logger,
        always_add_logging_based_logger=False,
        log_time=False,
        console_display_rate_limit=actual_rate_limit,
        enable_console_update=enable_console_update,
        console_loggers_or_logger_types=(hprint_logger,)  # Mark as console logger
    )

    start_time = time.time()
    simulator.train(total_iterations)
    elapsed_time = time.time() - start_time

    # Print results
    print("\n" + "-" * 70)
    print("Results:")
    print("-" * 70)
    print(f"\nTotal iterations: {total_iterations}")
    print(f"Elapsed time: {elapsed_time:.2f}s")
    print(f"Messages displayed: {displayed_count[0]}")
    if enable_rate_limit:
        print(f"Expected messages: ~{expected_messages}")
        if displayed_count[0] <= expected_messages + 1:
            print("-> Rate limiting working correctly!")
        else:
            print("-> Note: Slight variation is normal due to timing")

    if enable_console_update:
        print("\nConsole update was enabled - messages updated in place")
        print("(If you saw scrolling, your terminal may not support ANSI escape codes)")

    print("\n" + "=" * 70)


def run_comparison_demo():
    """Run all four modes side by side for comparison."""
    # Check cursor control support
    cursor_supported, cursor_reason = check_cursor_control_support()

    # Import after backend selection
    from python_utils.console_utils import hprint_message, get_current_backend
    from python_utils.common_objects.debuggable import Debuggable

    rate_limit = 0.3
    total_iterations = 10
    iteration_delay = 0.1

    print("\n" + "=" * 70)
    print("Comparison Demo - All Four Modes")
    print("=" * 70)
    print(f"\nBackend: {get_current_backend()}")
    print(f"Cursor control: {'SUPPORTED' if cursor_supported else 'NOT SUPPORTED'} ({cursor_reason})")
    if not cursor_supported:
        print("WARNING: In-place updates will NOT work - all messages will scroll")
    print(f"\nIterations: {total_iterations}, Delay: {iteration_delay}s, Rate limit: {rate_limit}s")
    print("\nThis will run all 4 modes sequentially for comparison.")

    modes = [
        (4, "No Features (baseline)", 0.0, False),
        (1, "Rate Limit Only", rate_limit, False),
        (2, "Console Update Only", 0.0, True),
        (3, "Both Combined", rate_limit, True),
    ]

    results = []

    for mode_num, mode_name, rl, cu in modes:
        input(f"\nPress Enter to run: {mode_name}...")

        displayed_count = [0]

        def training_logger(log_data, message_id=None, update_previous=False, **kwargs):
            displayed_count[0] += 1
            item = log_data['item']
            mode_indicator = "[UPD]" if update_previous else "[NEW]"
            content = f"{mode_indicator} Epoch {item['epoch']:2d} | Loss: {item['loss']:.4f} | Accuracy: {item['accuracy']:.1f}%"
            # Use hprint_message for actual in-place updates
            hprint_message(
                title="Training Progress",
                content=content,
                message_id=message_id,
                update_previous=update_previous
            )

        class TrainingSimulator(Debuggable):
            def train(self):
                for epoch in range(total_iterations):
                    loss = 1.0 / (epoch + 1)
                    accuracy = min(99.9, 50 + epoch * 5.0)
                    self.log_info(
                        {'epoch': epoch, 'loss': loss, 'accuracy': accuracy},
                        log_type='Training'
                    )
                    time.sleep(iteration_delay)

        print(f"\n--- {mode_name} ---")

        simulator = TrainingSimulator(
            logger=training_logger,
            always_add_logging_based_logger=False,
            log_time=False,
            console_display_rate_limit=rl,
            enable_console_update=cu,
            console_loggers_or_logger_types=(training_logger,)
        )
        simulator.train()

        results.append((mode_name, displayed_count[0], cu))

    # Summary
    print("\n" + "=" * 70)
    print("Comparison Summary")
    print("=" * 70)
    print(f"\n{'Mode':<30} {'Messages':<12} {'Updates':<10}")
    print("-" * 52)
    for mode_name, count, cu in results:
        updates = "All" if cu else "None"
        print(f"{mode_name:<30} {count:<12} {updates:<10}")

    print("\n" + "=" * 70)


def main():
    print("\n" + "=" * 70)
    print(" DEBUGGABLE RATE LIMITING - GOLDEN EXAMPLE")
    print("=" * 70)
    print("\nThis example demonstrates the integration of Debuggable's rate limiting")
    print("and console update features with console_utils (hprint_message).")

    # Select backend first (only once at startup)
    select_backend()

    while True:
        print("\n" + "=" * 70)
        print("Demo Options")
        print("=" * 70)
        print("\nOptions:")
        print("  1. Interactive Demo - Choose mode and settings")
        print("  2. Comparison Demo - See all 4 modes side by side")

        choice = input("\nChoose option (1/2) or press Enter for Interactive: ").strip()

        if choice == "2":
            run_comparison_demo()
        else:
            mode = select_mode()
            if mode in [1, 3]:  # Modes that use rate limiting
                rate_limit = select_rate_limit()
            else:
                rate_limit = 0.0
            run_demo(mode, rate_limit)

        # Ask if user wants to continue
        print("\n" + "-" * 70)
        continue_choice = input("Would you like to try another setup? (y/n) or press Enter for yes: ").strip().lower()
        if continue_choice in ['n', 'no']:
            break

        # Ask if user wants to change backend
        change_backend = input("Would you like to change the backend? (y/n) or press Enter for no: ").strip().lower()
        if change_backend in ['y', 'yes']:
            select_backend()

    print("\n" + "=" * 70)
    print("Key Takeaways:")
    print("1. Use console_display_rate_limit to reduce console flooding")
    print("2. Use enable_console_update=True for in-place updates")
    print("3. Combine both for optimal training loop display")
    print("4. Mark your logger in console_loggers_or_logger_types for rate limiting")
    print("\nThank you for trying the golden example!")
    print("=" * 70)


if __name__ == "__main__":
    main()
