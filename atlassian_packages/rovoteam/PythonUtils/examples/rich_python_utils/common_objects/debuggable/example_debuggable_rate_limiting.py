"""
Example: Debuggable Rate Limiting and Console Update Features

This example demonstrates the new rate limiting and console update features
in the Debuggable class.

Features demonstrated:
1. Console display rate limiting
2. Backend logging rate limiting
3. Custom message_id generation
4. Console update integration
5. Multiple independent rate-limited trackers
"""

import time

from resolve_path import resolve_path

resolve_path()
from python_utils.common_objects.debuggable import Debuggable


def example_1_console_rate_limiting():
    """
    Example 1: Console Display Rate Limiting

    Demonstrates limiting how often messages are displayed to console.
    Useful for training loops where you don't want to flood the console.

    Without rate limiting: 20 messages (one per epoch)
    With rate limiting (0.5s limit, 0.1s per iteration):
        Total time: 20 * 0.1s = 2.0s
        Expected messages: ~4-5 (one every 0.5s)
    """
    print("\n" + "=" * 60)
    print("Example 1: Console Display Rate Limiting")
    print("=" * 60)
    print("Without rate limiting: 20 messages would display")
    print("With 0.5s rate limit over 2.0s total: expect ~4-5 messages")
    print("-" * 60)

    class TrainingLoop(Debuggable):
        def train(self, epochs=20):
            for epoch in range(epochs):
                # This will only print every 0.5 seconds
                self.log_info(
                    {'epoch': epoch, 'loss': 1.0 / (epoch + 1)},
                    log_type='Training'
                )
                time.sleep(0.1)  # Simulating fast training iterations

    trainer = TrainingLoop(
        logger=print,
        always_add_logging_based_logger=False,
        log_time=False,
        console_display_rate_limit=0.5  # Only display every 0.5 seconds
    )
    trainer.train()
    print("-" * 60)
    print("Verify: Count the messages above (should be ~4-5)")


def example_2_backend_logging_rate_limiting():
    """
    Example 2: Backend Logging Rate Limiting

    Demonstrates limiting how often messages are logged to backend loggers
    (like logging.Logger or file writers), independent of console display.

    Without rate limiting: 15 messages (one per item)
    With rate limiting (0.3s limit, 0.1s per iteration):
        Total time: 15 * 0.1s = 1.5s
        Expected messages: ~5-6 (one every 0.3s)
    """
    print("\n" + "=" * 60)
    print("Example 2: Backend Logging Rate Limiting")
    print("=" * 60)
    print("Without rate limiting: 15 messages would be logged")
    print("With 0.3s rate limit over 1.5s total: expect ~5-6 messages")
    print("-" * 60)

    logged_messages = []

    def file_logger(log_data):
        logged_messages.append(log_data)
        print(f"  [Logged to file] {log_data['type']}: {log_data['item']}")

    class DataProcessor(Debuggable):
        def process(self, items=15):
            for i in range(items):
                self.log_info(
                    {'item': i, 'status': 'processed'},
                    log_type='Progress'
                )
                time.sleep(0.1)

    processor = DataProcessor(
        logger=file_logger,
        always_add_logging_based_logger=False,
        log_time=False,
        logging_rate_limit=0.3  # Only log to backend every 0.3 seconds
    )
    processor.process()
    print("-" * 60)
    print(f"Total items processed: 15")
    print(f"Messages logged to backend: {len(logged_messages)} (expected ~5-6)")


def example_3_custom_message_id_generator():
    """
    Example 3: Custom Message ID Generator

    Demonstrates using a custom callable to generate message IDs.
    This allows you to control how messages are grouped for rate limiting.

    Without rate limiting: 10 messages (5 Initialization + 5 Processing)
    With rate limiting (0.3s limit, 0.15s per iteration):
        Phase 1 (Initialization): 5 * 0.15s = 0.75s -> expect ~3 messages
        Phase 2 (Processing): 5 * 0.15s = 0.75s -> expect ~3 messages
        Total expected: ~6 messages (3 per phase)
    """
    print("\n" + "=" * 60)
    print("Example 3: Custom Message ID Generator")
    print("=" * 60)
    print("Without rate limiting: 10 messages (5 Initialization + 5 Processing)")
    print("With 0.3s rate limit: expect ~3 per phase = ~6 total")
    print("-" * 60)

    def custom_id_gen(debuggable, log_item, log_type, log_level):
        """Generate message_id based on log_type only (ignore content)."""
        return f"{debuggable.id}_{log_type}"

    class MultiPhaseProcess(Debuggable):
        def run(self):
            for i in range(5):
                # These will all share the same message_id because log_type is the same
                self.log_info({'phase': 'init', 'step': i}, log_type='Initialization')
                time.sleep(0.15)

            for i in range(5):
                # These share a different message_id
                self.log_info({'phase': 'process', 'step': i}, log_type='Processing')
                time.sleep(0.15)

    process = MultiPhaseProcess(
        logger=print,
        always_add_logging_based_logger=False,
        log_time=False,
        console_display_rate_limit=0.3,
        default_message_id_gen=custom_id_gen
    )
    process.run()
    print("-" * 60)
    print("Verify: Should see ~3 Initialization + ~3 Processing messages")


def example_4_separate_console_and_backend_rates():
    """
    Example 4: Separate Console and Backend Rate Limits

    Demonstrates having different rate limits for console vs backend logging.
    Console can update slowly while backend logs everything.

    Without rate limiting: 20 messages to console, 20 to backend
    With rate limiting:
        Console (0.3s limit, 0.05s per iteration):
            Total time: 20 * 0.05s = 1.0s -> expect ~4 messages
        Backend (no limit): 20 messages (all logged)
    """
    print("\n" + "=" * 60)
    print("Example 4: Separate Console and Backend Rates")
    print("=" * 60)
    print("Without rate limiting: 20 console + 20 backend messages")
    print("With 0.3s console limit, no backend limit:")
    print("  Console: expect ~4 messages")
    print("  Backend: expect 20 messages (all logged)")
    print("-" * 60)

    backend_log = []

    def backend_logger(log_data):
        backend_log.append(log_data)

    class Monitor(Debuggable):
        def monitor(self, samples=20):
            for i in range(samples):
                self.log_info(
                    {'sample': i, 'value': i * 10},
                    log_type='Metric'
                )
                time.sleep(0.05)

    monitor = Monitor(
        logger=(print, backend_logger),
        always_add_logging_based_logger=False,
        log_time=False,
        console_display_rate_limit=0.3,  # Console: every 0.3 seconds
        logging_rate_limit=0.0  # Backend: no limit (log everything)
    )
    monitor.monitor()
    print("-" * 60)
    print(f"Console messages: ~4 displayed (count above)")
    print(f"Backend messages logged: {len(backend_log)} (expected 20)")


def example_5_explicit_message_id():
    """
    Example 5: Explicit Message ID

    Demonstrates using explicit message_id for fine-grained control
    over which messages share the same rate limit bucket.

    Without rate limiting: 20 messages (10 loss + 10 accuracy)
    With rate limiting (0.25s limit, 0.1s per iteration):
        Total time: 10 * 0.1s = 1.0s
        Loss messages (independent bucket): expect ~4 messages
        Accuracy messages (independent bucket): expect ~4 messages
        Total expected: ~8 messages
    """
    print("\n" + "=" * 60)
    print("Example 5: Explicit Message ID")
    print("=" * 60)
    print("Without rate limiting: 20 messages (10 loss + 10 accuracy)")
    print("With 0.25s rate limit, independent buckets:")
    print("  Loss: expect ~4 messages")
    print("  Accuracy: expect ~4 messages")
    print("  Total: expect ~8 messages")
    print("-" * 60)

    class MultiTracker(Debuggable):
        def track(self):
            for i in range(10):
                # Track loss with its own rate limit bucket
                self.log_info(
                    {'loss': 1.0 / (i + 1)},
                    log_type='Training',
                    message_id='loss_tracker'
                )
                # Track accuracy with its own rate limit bucket
                self.log_info(
                    {'accuracy': (i + 1) * 10},
                    log_type='Training',
                    message_id='accuracy_tracker'
                )
                time.sleep(0.1)

    tracker = MultiTracker(
        logger=print,
        always_add_logging_based_logger=False,
        log_time=False,
        console_display_rate_limit=0.25
    )
    tracker.track()
    print("-" * 60)
    print("Verify: Should see ~4 loss + ~4 accuracy = ~8 total messages")


def example_6_console_update():
    """
    Example 6: Console Update (In-Place Message Updates)

    Demonstrates using enable_console_update to update messages in place
    instead of printing new lines. The logger must support message_id and
    update_previous parameters.

    This example uses a custom logger that simulates console_utils behavior.
    In real use, you would use hprint_pairs, hprint_message, etc.
    """
    print("\n" + "=" * 60)
    print("Example 6: Console Update (In-Place Updates)")
    print("=" * 60)
    print("With enable_console_update=True, loggers that support")
    print("message_id and update_previous will receive these params.")
    print("-" * 60)

    received_params = []

    def update_aware_logger(log_data, message_id=None, update_previous=False, **kwargs):
        """A logger that supports message_id and update_previous."""
        received_params.append({
            'message_id': message_id,
            'update_previous': update_previous
        })
        update_str = " [UPDATE]" if update_previous else " [NEW]"
        print(f"  {update_str} id={message_id}: {log_data['item']}")

    class ProgressTracker(Debuggable):
        def run(self):
            for i in range(5):
                self.log_info({'step': i, 'progress': f'{i*25}%'}, log_type='Progress')
                time.sleep(0.1)

    tracker = ProgressTracker(
        logger=update_aware_logger,
        always_add_logging_based_logger=False,
        log_time=False,
        enable_console_update=True  # Enable console update feature
    )
    tracker.run()
    print("-" * 60)
    print(f"Messages sent: {len(received_params)}")
    print(f"First message update_previous: {received_params[0]['update_previous']}")
    print(f"Subsequent messages update_previous: {received_params[1]['update_previous'] if len(received_params) > 1 else 'N/A'}")
    print("Note: All messages have update_previous=True when enable_console_update=True")


def example_7_console_update_with_rate_limit():
    """
    Example 7: Console Update Combined with Rate Limiting

    Demonstrates using both enable_console_update AND rate limiting together.
    This is ideal for training loops where you want:
    - Rate-limited updates (not too frequent)
    - In-place updates (no scrolling)

    Without rate limiting: 20 messages
    With rate limiting (0.3s limit, 0.05s per iteration):
        Total time: 20 * 0.05s = 1.0s -> expect ~4 messages
        All messages will have update_previous=True
    """
    print("\n" + "=" * 60)
    print("Example 7: Console Update + Rate Limiting Combined")
    print("=" * 60)
    print("Without rate limiting: 20 messages")
    print("With 0.3s rate limit over 1.0s: expect ~4 messages")
    print("All messages have update_previous=True for in-place update")
    print("-" * 60)

    message_count = 0

    def training_display(log_data, message_id=None, update_previous=False, **kwargs):
        """Simulates a console display that supports updates."""
        nonlocal message_count
        message_count += 1
        mode = "UPDATE" if update_previous else "NEW"
        item = log_data['item']
        print(f"  [{mode}] Epoch {item['epoch']}: loss={item['loss']:.4f}")

    class TrainingLoop(Debuggable):
        def train(self, epochs=20):
            for epoch in range(epochs):
                self.log_info(
                    {'epoch': epoch, 'loss': 1.0 / (epoch + 1)},
                    log_type='Training'
                )
                time.sleep(0.05)

    trainer = TrainingLoop(
        logger=training_display,
        always_add_logging_based_logger=False,
        log_time=False,
        console_display_rate_limit=0.3,  # Rate limit: every 0.3 seconds
        enable_console_update=True,       # Enable in-place updates
        console_loggers_or_logger_types=(training_display,)  # Mark as console logger
    )
    trainer.train()
    print("-" * 60)
    print(f"Messages displayed: {message_count} (expected ~4)")
    print("All displayed messages used UPDATE mode (in-place)")


def example_8_rate_limit_vs_console_update_comparison():
    """
    Example 8: Comparison - Rate Limiting vs Console Update vs Both

    Shows the difference between:
    1. No features: 10 messages, each on new line
    2. Rate limiting only: ~3-4 messages, each on new line
    3. Console update only: 10 messages, in-place (simulated)
    4. Both combined: ~3-4 messages, in-place

    For clarity, this example counts messages rather than simulating
    in-place updates (which require actual terminal control).
    """
    print("\n" + "=" * 60)
    print("Example 8: Comparison - Rate Limit vs Console Update vs Both")
    print("=" * 60)

    def run_test(name, rate_limit, console_update):
        messages = []

        def test_logger(log_data, message_id=None, update_previous=False, **kwargs):
            messages.append({
                'data': log_data,
                'message_id': message_id,
                'update_previous': update_previous
            })

        class TestLoop(Debuggable):
            def run(self):
                for i in range(10):
                    self.log_info({'step': i}, log_type='Test')
                    time.sleep(0.1)

        loop = TestLoop(
            logger=test_logger,
            always_add_logging_based_logger=False,
            log_time=False,
            console_display_rate_limit=rate_limit,
            enable_console_update=console_update,
            console_loggers_or_logger_types=(test_logger,)
        )
        loop.run()

        update_count = sum(1 for m in messages if m['update_previous'])
        return len(messages), update_count

    print("-" * 60)
    print("Running 4 configurations (10 iterations each, 0.1s/iter)...")
    print()

    # Test 1: No features
    count1, updates1 = run_test("No features", 0.0, False)
    print(f"1. No features:           {count1} messages, {updates1} with update_previous=True")

    # Test 2: Rate limiting only
    count2, updates2 = run_test("Rate limit only", 0.25, False)
    print(f"2. Rate limit (0.25s):    {count2} messages, {updates2} with update_previous=True")

    # Test 3: Console update only
    count3, updates3 = run_test("Console update only", 0.0, True)
    print(f"3. Console update only:   {count3} messages, {updates3} with update_previous=True")

    # Test 4: Both combined
    count4, updates4 = run_test("Both combined", 0.25, True)
    print(f"4. Both combined:         {count4} messages, {updates4} with update_previous=True")

    print("-" * 60)
    print("Expected results:")
    print("  1. 10 messages, 0 updates (all new lines)")
    print("  2. ~4 messages, 0 updates (rate limited, new lines)")
    print("  3. 10 messages, 10 updates (all in-place)")
    print("  4. ~4 messages, ~4 updates (rate limited + in-place)")


if __name__ == '__main__':
    example_1_console_rate_limiting()
    example_2_backend_logging_rate_limiting()
    example_3_custom_message_id_generator()
    example_4_separate_console_and_backend_rates()
    example_5_explicit_message_id()
    example_6_console_update()
    example_7_console_update_with_rate_limit()
    example_8_rate_limit_vs_console_update_comparison()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
