"""
Simulated Multi-Thread Executor Example

This demonstrates manual task processing with SimulatedMultiThreadExecutor:
- process_one(): Execute a single task on-demand
- process_all(): Process all available tasks at once
- Handling task results immediately after execution

Use Case:
    When you need fine-grained control over task execution, such as:
    - Browser automation with Selenium WebDriver (only one thread per driver)
    - Interactive processing where you control the timing
    - Testing and debugging task execution
    - Processing tasks in sync with external events

Prerequisites:
    No external dependencies (uses ThreadQueueService)

Usage:
    python example_simulated_executor.py
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

import time
from python_utils.mp_utils.task import Task, TaskStatus
from python_utils.mp_utils.queued_executor import SimulatedMultiThreadExecutor
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


# =============================================================================
# Simulated browser automation tasks (WebDriver-like scenario)
# =============================================================================

class WebPage:
    """Simulates a web page for demonstration."""

    def __init__(self, url):
        self.url = url
        self.title = f"Page: {url.split('/')[-1]}"
        self.loaded = False

    def load(self):
        """Simulate page loading."""
        time.sleep(0.1)  # Simulate network delay
        self.loaded = True
        return self

    def get_element(self, selector):
        """Simulate finding an element."""
        return f"<element selector='{selector}'>"

    def click(self, selector):
        """Simulate clicking an element."""
        return f"Clicked: {selector}"

    def fill_form(self, selector, value):
        """Simulate filling a form field."""
        return f"Filled {selector} with: {value}"


def navigate_to(url):
    """Navigate to a URL and return page info."""
    page = WebPage(url).load()
    return {
        'url': url,
        'title': page.title,
        'loaded': page.loaded
    }


def fill_login_form(username, password):
    """Fill a login form."""
    page = WebPage('https://example.com/login').load()
    results = [
        page.fill_form('#username', username),
        page.fill_form('#password', '***'),  # Don't log actual password
        page.click('#submit-btn')
    ]
    return {'actions': results, 'success': True}


def scrape_product_info(product_id):
    """Scrape product information."""
    page = WebPage(f'https://example.com/product/{product_id}').load()
    time.sleep(0.05)  # Simulate DOM parsing
    return {
        'product_id': product_id,
        'title': f'Product {product_id}',
        'price': 29.99 + product_id,
        'in_stock': product_id % 2 == 0
    }


def take_screenshot(page_name):
    """Simulate taking a screenshot."""
    time.sleep(0.02)
    return f"screenshot_{page_name}_{int(time.time())}.png"


def failing_network_request():
    """Simulate a network request that fails."""
    raise ConnectionError("Network timeout")


def main():
    print("""
==============================================================================
             SimulatedMultiThreadExecutor Usage Example
==============================================================================

This example demonstrates manual task processing, useful for scenarios where
you need precise control over when each task executes (e.g., WebDriver).
""")

    # =========================================================================
    # 1. Setup: Create queue service and executor
    # =========================================================================
    print("1. Setting up the simulated executor...")

    queue_service = ThreadQueueService()

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='browser_tasks',
        output_queue_id='browser_results',
        name='BrowserAutomation',
        verbose=False
    )

    print(f"   [OK] Executor created: {executor.name}")
    print(f"   [OK] Processed count: {executor.processed_count}")

    # =========================================================================
    # 2. Example: Process tasks one at a time (process_one)
    # =========================================================================
    print("\n2. Processing tasks one at a time with process_one()...")
    print("   (This simulates a WebDriver session where tasks run sequentially)")

    # Submit a sequence of browser tasks
    browser_tasks = [
        Task(callable=navigate_to, args=('https://example.com/home',), name='Navigate-Home'),
        Task(callable=fill_login_form, args=('alice', 'secret123'), name='Login'),
        Task(callable=take_screenshot, args=('after_login',), name='Screenshot'),
    ]

    for task in browser_tasks:
        executor.submit(task)
        print(f"   [OK] Queued: {task.name}")

    print(f"\n   Processing {len(browser_tasks)} tasks one by one...")

    # Process each task and handle the result immediately
    for i in range(len(browser_tasks)):
        print(f"\n   --- Processing task {i+1} ---")

        # Process exactly one task
        result = executor.process_one()

        if result:
            if result.is_success():
                print(f"   Task ID: {result.task_id[:8]}...")
                print(f"   Status: SUCCESS")
                print(f"   Time: {result.execution_time:.4f}s")
                print(f"   Result: {result.result}")
            else:
                print(f"   Status: FAILED")
                print(f"   Error: {result.exception}")

    print(f"\n   Processed count: {executor.processed_count}")

    # =========================================================================
    # 3. Example: Batch processing with process_all()
    # =========================================================================
    print("\n3. Batch processing with process_all()...")
    print("   (Useful when you have multiple independent tasks)")

    # Submit multiple product scraping tasks
    product_ids = [101, 102, 103, 104, 105]
    for pid in product_ids:
        task = Task(callable=scrape_product_info, args=(pid,), name=f'Scrape-{pid}')
        executor.submit(task)

    print(f"   [OK] Submitted {len(product_ids)} scraping tasks")
    print(f"   Queue size: {queue_service.size('browser_tasks')}")

    # Process all tasks at once
    results = executor.process_all()

    print(f"\n   Processed {len(results)} tasks:")
    for result in results:
        if result.is_success():
            product = result.result
            stock_status = "In Stock" if product['in_stock'] else "Out of Stock"
            print(f"   - {product['title']}: ${product['price']:.2f} ({stock_status})")

    print(f"\n   Total processed: {executor.processed_count}")

    # =========================================================================
    # 4. Example: Handling failed tasks
    # =========================================================================
    print("\n4. Handling failed tasks...")

    executor.submit(Task(callable=failing_network_request, name='FailingRequest'))
    executor.submit(Task(callable=navigate_to, args=('https://example.com/success',), name='SuccessRequest'))

    results = executor.process_all()

    for result in results:
        if result.is_success():
            print(f"   [SUCCESS] Task completed: {result.result}")
        else:
            print(f"   [FAILED] Task error: {type(result.exception).__name__}: {result.exception}")

    # =========================================================================
    # 5. Example: Using with blocking wait
    # =========================================================================
    print("\n5. Using blocking wait for tasks...")

    # Submit a task
    task = Task(callable=take_screenshot, args=('final_state',), name='FinalScreenshot')
    executor.submit(task)
    print("   [OK] Task submitted, waiting for it to appear...")

    # Process with blocking (will wait if queue is empty)
    # In real usage, another thread might be adding tasks
    result = executor.process_one(blocking=False)  # Use blocking=True with timeout in production

    if result:
        print(f"   [OK] Screenshot saved: {result.result}")

    # =========================================================================
    # 6. Comparison: Manual control vs Background execution
    # =========================================================================
    print("\n6. Running in background thread (alternative mode)...")

    # Clear any remaining tasks and results from previous sections
    queue_service.clear('browser_tasks')
    queue_service.clear('browser_results')

    # Submit some tasks
    for i in range(3):
        task = Task(callable=scrape_product_info, args=(200 + i,), name=f'BgTask-{i}')
        executor.submit(task)

    # Start processing in background
    thread = executor.run_in_thread()
    print(f"   [OK] Background thread started: {thread.name}")

    # Wait for results
    time.sleep(0.5)

    # Collect results
    count = 0
    while queue_service.size('browser_results') > 0:
        result = executor.get_result(blocking=False)
        if result:
            count += 1
            print(f"   [OK] Got result: Product {result.result['product_id']}")

    # Stop the background thread
    executor.stop()
    print(f"   [OK] Background thread stopped")
    print(f"   [OK] Results collected: {count}")

    # =========================================================================
    # 7. Summary
    # =========================================================================
    print("\n7. Summary...")
    print(f"   Total tasks processed: {executor.processed_count}")

    # =========================================================================
    # 8. Cleanup
    # =========================================================================
    print("\n8. Cleaning up...")

    queue_service.delete('browser_tasks')
    queue_service.delete('browser_results')
    queue_service.close()

    print("   [OK] Cleanup complete")

    print("\n" + "=" * 80)
    print("[OK] Example completed successfully!")
    print("=" * 80)
    print("""
Key Takeaways:
- process_one(): Execute exactly one task with full control
- process_all(): Batch process all queued tasks
- run_in_thread(): Switch to background processing when needed
- Results include timing, status, and error information
""")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
