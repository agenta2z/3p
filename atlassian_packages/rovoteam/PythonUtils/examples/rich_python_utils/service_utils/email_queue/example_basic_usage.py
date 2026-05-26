"""
Basic Email Queue Service Usage Example

Demonstrates basic put/get operations with email-based queues.

Setup:
1. Create a Google Cloud project
2. Enable Gmail API
3. Create OAuth2 credentials (Desktop app)
4. Download credentials.json to this directory
5. Run this script - it will open browser for authentication
6. Token will be saved for future use
"""

import os

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.service_utils.email_utils.gmail_client import GmailClient
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)
from python_utils.service_utils.queue_service.email_queue_service import (
    EmailQueueService
)


def main():
    """Basic email queue usage example."""
    
    # Configuration
    credentials_path = 'credentials.json'  # Path to your OAuth2 credentials
    token_path = 'token.pickle'  # Where to store the auth token
    email_address = 'your-email@gmail.com'  # Your Gmail address
    storage_path = '/tmp/email_queues'  # Local storage path
    
    # Check if credentials exist
    if not os.path.exists(credentials_path):
        print(f"Error: {credentials_path} not found!")
        print("Please download OAuth2 credentials from Google Cloud Console")
        return
    
    print("Creating email queue service...")
    
    # Create email client
    email_client = GmailClient(
        credentials_path=credentials_path,
        token_path=token_path
    )
    
    # Create storage service
    storage_service = StorageBasedQueueService(
        root_path=storage_path,
        archive_popped_items=True
    )
    
    # Create email queue service
    with EmailQueueService(
        email_client=email_client,
        storage_service=storage_service,
        email_address=email_address,
        sync_interval=300.0,  # Sync every 5 minutes
        sync_on_read=False
    ) as service:
        
        print("\n=== Email Queue Service Example ===\n")
        
        # Create a queue
        queue_id = 'example_queue'
        print(f"Creating queue: {queue_id}")
        service.create_queue(queue_id)
        
        # Put some items
        print("\nPutting items onto queue...")
        items = [
            {'task': 'process_data', 'priority': 1},
            {'task': 'send_email', 'priority': 2},
            {'task': 'generate_report', 'priority': 3}
        ]
        
        for item in items:
            service.put(queue_id, item)
            print(f"  Put: {item}")
        
        # Check queue size
        size = service.size(queue_id)
        print(f"\nQueue size: {size}")
        
        # Peek at first item
        first_item = service.peek(queue_id, index=0)
        print(f"First item (peek): {first_item}")
        
        # Get items
        print("\nGetting items from queue...")
        while service.size(queue_id) > 0:
            item = service.get(queue_id, blocking=False)
            print(f"  Got: {item}")
        
        # Check queue size again
        size = service.size(queue_id)
        print(f"\nQueue size after getting all items: {size}")
        
        # Get statistics
        print("\nQueue statistics:")
        stats = service.get_stats(queue_id)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # List all queues
        print("\nAll queues:")
        queues = service.list_queues()
        for q in queues:
            print(f"  - {q}")
        
        print("\n=== Example Complete ===")
        print("\nNote: Check your Gmail for the email thread with subject")
        print(f"'EmailQueue - {queue_id}' to see the operation log!")


if __name__ == '__main__':
    main()
