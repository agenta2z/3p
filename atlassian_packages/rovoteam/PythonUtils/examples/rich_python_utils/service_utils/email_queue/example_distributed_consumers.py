"""
Distributed Consumers Example

Demonstrates how multiple processes can consume from the same email queue.
This shows the distributed nature of email-based queues.

Run this script in multiple terminals to see distributed consumption.
"""

import os
import time
import random

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.service_utils.email_utils.gmail_client import GmailClient
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)
from python_utils.service_utils.queue_service.email_queue_service import (
    EmailQueueService
)


def producer(service, queue_id, num_items=10):
    """Producer: Add items to the queue."""
    print(f"\n[PRODUCER] Adding {num_items} items to queue...")
    
    for i in range(num_items):
        item = {
            'task_id': i,
            'task': f'process_item_{i}',
            'timestamp': time.time()
        }
        service.put(queue_id, item)
        print(f"[PRODUCER] Put: {item['task']}")
        time.sleep(0.5)  # Simulate work
    
    print("[PRODUCER] Done adding items")


def consumer(service, queue_id, consumer_id, duration=30):
    """Consumer: Get items from the queue."""
    print(f"\n[CONSUMER {consumer_id}] Starting consumption for {duration}s...")
    
    start_time = time.time()
    items_processed = 0
    
    while time.time() - start_time < duration:
        # Sync with email periodically
        if items_processed % 5 == 0:
            print(f"[CONSUMER {consumer_id}] Syncing with email...")
            service.sync(queue_id)
        
        # Try to get an item
        item = service.get(queue_id, blocking=False)
        
        if item:
            items_processed += 1
            print(f"[CONSUMER {consumer_id}] Got: {item['task']}")
            
            # Simulate processing time
            time.sleep(random.uniform(0.5, 2.0))
        else:
            # No items available, wait a bit
            time.sleep(1.0)
    
    print(f"[CONSUMER {consumer_id}] Processed {items_processed} items")


def main():
    """Distributed consumers example."""
    
    # Configuration
    credentials_path = 'credentials.json'
    token_path = 'token.pickle'
    email_address = 'your-email@gmail.com'
    storage_path = f'/tmp/email_queues_consumer_{os.getpid()}'  # Unique per process
    
    if not os.path.exists(credentials_path):
        print(f"Error: {credentials_path} not found!")
        return
    
    # Create email client
    email_client = GmailClient(
        credentials_path=credentials_path,
        token_path=token_path
    )
    
    # Create storage service (unique per process)
    storage_service = StorageBasedQueueService(
        root_path=storage_path,
        archive_popped_items=True
    )
    
    # Create email queue service
    with EmailQueueService(
        email_client=email_client,
        storage_service=storage_service,
        email_address=email_address,
        sync_interval=10.0,  # Sync every 10 seconds
        sync_on_read=True  # Sync before each get
    ) as service:
        
        print("\n=== Distributed Email Queue Example ===")
        print(f"Process ID: {os.getpid()}")
        
        queue_id = 'distributed_queue'
        
        # Create queue if it doesn't exist
        if not service.exists(queue_id):
            print(f"\nCreating queue: {queue_id}")
            service.create_queue(queue_id)
        
        # Ask user what role to play
        print("\nWhat would you like to do?")
        print("1. Producer (add items to queue)")
        print("2. Consumer (process items from queue)")
        print("3. Both (producer then consumer)")
        
        choice = input("Enter choice (1/2/3): ").strip()
        
        if choice == '1':
            producer(service, queue_id, num_items=20)
        elif choice == '2':
            consumer_id = random.randint(1000, 9999)
            consumer(service, queue_id, consumer_id, duration=60)
        elif choice == '3':
            producer(service, queue_id, num_items=10)
            time.sleep(2)
            consumer_id = random.randint(1000, 9999)
            consumer(service, queue_id, consumer_id, duration=30)
        else:
            print("Invalid choice")
        
        # Show final stats
        print("\n=== Final Statistics ===")
        stats = service.get_stats(queue_id)
        print(f"Queue size: {stats['local_size']}")
        print(f"Last sync: {stats.get('last_sync_time', 'Never')}")
        
        print("\n=== Example Complete ===")


if __name__ == '__main__':
    main()
