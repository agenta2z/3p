"""
Real-world use case examples of OnStorageLists

This demonstrates practical applications:
- Persistent task queue
- Log aggregation system
- Configuration history tracking
- User data management
- Event sourcing pattern
- Data pipeline checkpointing

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_use_cases.py
"""

from pathlib import Path
import tempfile
import shutil
from datetime import datetime
import time

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.io_utils.on_storage_lists import OnStorageLists


def use_case_task_queue():
    """Use Case 1: Persistent Task Queue (Producer-Consumer Pattern)."""
    print("\n" + "="*80)
    print("USE CASE 1: Persistent Task Queue")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='tasks.pending'
        )
        
        print("\n1. Producer: Adding tasks to queue...")
        tasks = [
            {'id': 1, 'type': 'process_data', 'file': 'data1.csv', 'priority': 'high'},
            {'id': 2, 'type': 'send_email', 'to': 'user@example.com', 'priority': 'normal'},
            {'id': 3, 'type': 'generate_report', 'format': 'pdf', 'priority': 'low'},
            {'id': 4, 'type': 'backup_database', 'target': 's3', 'priority': 'high'},
        ]
        
        for task in tasks:
            storage.append(task, list_key='tasks.pending')
            print(f"   [+] Queued: {task['type']} (priority: {task['priority']})")
        
        print(f"\n   Total pending tasks: {storage._get_list_size(list_key='tasks.pending')}")
        
        print("\n2. Consumer: Processing tasks (FIFO)...")
        completed_storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='tasks.completed'
        )
        
        while storage._get_list_size(list_key='tasks.pending') > 0:
            # Pop first task (FIFO)
            task = storage.pop(index=0, list_key='tasks.pending')
            
            print(f"   [→] Processing: {task['type']}...")
            time.sleep(0.1)  # Simulate work
            
            # Mark as completed
            task['completed_at'] = datetime.now().isoformat()
            task['status'] = 'success'
            completed_storage.append(task, list_key='tasks.completed')
            
            print(f"   [✓] Completed: {task['type']}")
        
        print(f"\n   Pending: {storage._get_list_size(list_key='tasks.pending')}")
        print(f"   Completed: {completed_storage._get_list_size(list_key='tasks.completed')}")
        
        print("\n3. Viewing completed tasks...")
        completed = completed_storage.get(list_key='tasks.completed')
        for task in completed:
            print(f"   - {task['type']}: {task['status']} at {task['completed_at']}")
        
    finally:
        shutil.rmtree(tmpdir)


def use_case_log_aggregation():
    """Use Case 2: Log Aggregation System."""
    print("\n" + "="*80)
    print("USE CASE 2: Log Aggregation System")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        # Plain text storage for logs
        def write_text(obj, f):
            f.write(str(obj))
        
        def read_text(f):
            return f.read()
        
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='logs',
            read_method=read_text,
            write_method=write_text,
            file_extension='.log'
        )
        
        print("\n1. Collecting logs from multiple sources...")
        
        # Application logs
        app_logs = [
            '[2025-11-06 10:00:00] [INFO] Application started',
            '[2025-11-06 10:00:05] [INFO] Database connection established',
            '[2025-11-06 10:00:10] [WARNING] High memory usage detected',
            '[2025-11-06 10:00:15] [ERROR] Failed to connect to external API',
        ]
        
        for log in app_logs:
            storage.append(log, list_key='logs.application')
        
        print(f"   [OK] Collected {len(app_logs)} application logs")
        
        # Access logs
        access_logs = [
            '[2025-11-06 10:00:01] GET /api/users 200 45ms',
            '[2025-11-06 10:00:03] POST /api/login 200 120ms',
            '[2025-11-06 10:00:07] GET /api/data 404 12ms',
            '[2025-11-06 10:00:12] GET /api/users 200 38ms',
        ]
        
        for log in access_logs:
            storage.append(log, list_key='logs.access')
        
        print(f"   [OK] Collected {len(access_logs)} access logs")
        
        print("\n2. Analyzing logs...")
        
        # Count errors
        app_logs_data = storage.get(list_key='logs.application')
        error_count = sum(1 for log in app_logs_data if '[ERROR]' in log)
        warning_count = sum(1 for log in app_logs_data if '[WARNING]' in log)
        
        print(f"   Errors: {error_count}")
        print(f"   Warnings: {warning_count}")
        
        # Count 404s
        access_logs_data = storage.get(list_key='logs.access')
        not_found_count = sum(1 for log in access_logs_data if ' 404 ' in log)
        
        print(f"   404 Not Found: {not_found_count}")
        
        print("\n3. Filtering logs by severity...")
        errors = [log for log in app_logs_data if '[ERROR]' in log]
        print("   Error logs:")
        for error in errors:
            print(f"      {error}")
        
    finally:
        shutil.rmtree(tmpdir)


def use_case_config_history():
    """Use Case 3: Configuration History Tracking."""
    print("\n" + "="*80)
    print("USE CASE 3: Configuration History Tracking")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='config.history'
        )
        
        print("\n1. Tracking configuration changes...")
        
        configs = [
            {
                'version': '1.0.0',
                'timestamp': '2025-11-01T10:00:00',
                'author': 'alice',
                'settings': {
                    'timeout': 30,
                    'retries': 3,
                    'debug': False
                }
            },
            {
                'version': '1.0.1',
                'timestamp': '2025-11-02T14:30:00',
                'author': 'bob',
                'settings': {
                    'timeout': 60,  # Changed
                    'retries': 3,
                    'debug': False
                }
            },
            {
                'version': '1.1.0',
                'timestamp': '2025-11-05T09:15:00',
                'author': 'alice',
                'settings': {
                    'timeout': 60,
                    'retries': 5,  # Changed
                    'debug': True  # Changed
                }
            },
        ]
        
        for config in configs:
            storage.append(config)
            print(f"   [+] Saved config v{config['version']} by {config['author']}")
        
        print("\n2. Viewing configuration history...")
        history = storage.get()
        print(f"   Total versions: {len(history)}")
        for i, config in enumerate(history):
            print(f"   [{i}] v{config['version']} - {config['timestamp']} by {config['author']}")
        
        print("\n3. Getting current configuration...")
        size = storage._get_list_size()
        current = storage.get(index=size-1)  # Last item
        print(f"   Current version: {current['version']}")
        print(f"   Settings: {current['settings']}")
        
        print("\n4. Rolling back to previous version...")
        previous = storage.get(index=size-2)  # Second to last
        print(f"   Rolling back to v{previous['version']}")
        print(f"   Settings: {previous['settings']}")
        
        # Apply rollback
        rollback_config = {
            'version': '1.1.1',
            'timestamp': datetime.now().isoformat(),
            'author': 'system',
            'settings': previous['settings'],
            'note': f'Rollback to v{previous["version"]}'
        }
        storage.append(rollback_config)
        print(f"   [OK] Rolled back to v{previous['version']} as v{rollback_config['version']}")
        
        print("\n5. Comparing versions...")
        v1 = history[0]['settings']
        v2 = history[-1]['settings']
        
        print("   Changes from v1.0.0 to current:")
        for key in v1:
            if v1[key] != v2.get(key):
                print(f"      {key}: {v1[key]} → {v2.get(key)}")
        
    finally:
        shutil.rmtree(tmpdir)


def use_case_user_data_management():
    """Use Case 4: User Data Management System."""
    print("\n" + "="*80)
    print("USE CASE 4: User Data Management System")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='default'
        )
        
        print("\n1. Storing user activity data...")
        
        users = ['alice', 'bob', 'charlie']
        
        for user in users:
            # User messages
            messages = [
                {'from': 'system', 'text': f'Welcome {user}!', 'timestamp': '2025-11-06T10:00:00'},
                {'from': 'admin', 'text': 'Please update your profile', 'timestamp': '2025-11-06T10:05:00'},
            ]
            for msg in messages:
                storage.append(msg, list_key=f'users.{user}.messages')
            
            # User preferences
            prefs = {
                'theme': 'dark' if user == 'alice' else 'light',
                'notifications': True,
                'language': 'en'
            }
            storage.append(prefs, list_key=f'users.{user}.preferences')
            
            # User activity log
            activities = [
                {'action': 'login', 'timestamp': '2025-11-06T09:00:00'},
                {'action': 'view_dashboard', 'timestamp': '2025-11-06T09:05:00'},
                {'action': 'edit_profile', 'timestamp': '2025-11-06T09:10:00'},
            ]
            for activity in activities:
                storage.append(activity, list_key=f'users.{user}.activity')
            
            print(f"   [OK] Stored data for user: {user}")
        
        print("\n2. Retrieving user data...")
        user = 'alice'
        messages = storage.get(list_key=f'users.{user}.messages')
        preferences = storage.get(list_key=f'users.{user}.preferences')
        activity = storage.get(list_key=f'users.{user}.activity')
        
        print(f"\n   User: {user}")
        print(f"   Messages: {len(messages)}")
        print(f"   Preferences: {preferences[0]}")
        print(f"   Activity log: {len(activity)} actions")
        
        print("\n3. Analyzing user activity...")
        for user in users:
            activity = storage.get(list_key=f'users.{user}.activity')
            print(f"   {user}: {len(activity)} actions")
            for act in activity:
                print(f"      - {act['action']} at {act['timestamp']}")
        
        print("\n4. Updating user preferences...")
        user = 'bob'
        prefs = storage.get(list_key=f'users.{user}.preferences', index=0)
        prefs['theme'] = 'dark'
        prefs['updated_at'] = datetime.now().isoformat()
        storage.set(prefs, list_key=f'users.{user}.preferences', index=0, overwrite=True)
        print(f"   [OK] Updated {user}'s theme to dark")
        
    finally:
        shutil.rmtree(tmpdir)


def use_case_event_sourcing():
    """Use Case 5: Event Sourcing Pattern."""
    print("\n" + "="*80)
    print("USE CASE 5: Event Sourcing Pattern")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='events'
        )
        
        print("\n1. Recording events...")
        
        events = [
            {'type': 'AccountCreated', 'account_id': 'ACC-001', 'name': 'Alice', 'timestamp': '2025-11-01T10:00:00'},
            {'type': 'DepositMade', 'account_id': 'ACC-001', 'amount': 1000, 'timestamp': '2025-11-01T10:05:00'},
            {'type': 'WithdrawalMade', 'account_id': 'ACC-001', 'amount': 200, 'timestamp': '2025-11-02T14:30:00'},
            {'type': 'DepositMade', 'account_id': 'ACC-001', 'amount': 500, 'timestamp': '2025-11-03T09:15:00'},
            {'type': 'WithdrawalMade', 'account_id': 'ACC-001', 'amount': 300, 'timestamp': '2025-11-04T16:45:00'},
        ]
        
        for event in events:
            storage.append(event, list_key='events.account.ACC-001')
            print(f"   [+] Event: {event['type']} - ${event.get('amount', 'N/A')}")
        
        print("\n2. Reconstructing state from events...")
        account_events = storage.get(list_key='events.account.ACC-001')
        
        # Replay events to build current state
        state = {
            'account_id': None,
            'name': None,
            'balance': 0,
            'created_at': None
        }
        
        for event in account_events:
            if event['type'] == 'AccountCreated':
                state['account_id'] = event['account_id']
                state['name'] = event['name']
                state['created_at'] = event['timestamp']
            elif event['type'] == 'DepositMade':
                state['balance'] += event['amount']
            elif event['type'] == 'WithdrawalMade':
                state['balance'] -= event['amount']
        
        print(f"\n   Current Account State:")
        print(f"   Account ID: {state['account_id']}")
        print(f"   Name: {state['name']}")
        print(f"   Balance: ${state['balance']}")
        print(f"   Created: {state['created_at']}")
        
        print("\n3. Querying event history...")
        deposits = [e for e in account_events if e['type'] == 'DepositMade']
        withdrawals = [e for e in account_events if e['type'] == 'WithdrawalMade']
        
        total_deposits = sum(e['amount'] for e in deposits)
        total_withdrawals = sum(e['amount'] for e in withdrawals)
        
        print(f"   Total deposits: ${total_deposits}")
        print(f"   Total withdrawals: ${total_withdrawals}")
        print(f"   Number of transactions: {len(deposits) + len(withdrawals)}")
        
        print("\n4. Point-in-time reconstruction...")
        # Reconstruct state as of 2025-11-02
        cutoff = '2025-11-03T00:00:00'
        past_events = [e for e in account_events if e['timestamp'] < cutoff]
        
        past_state = {'balance': 0}
        for event in past_events:
            if event['type'] == 'DepositMade':
                past_state['balance'] += event['amount']
            elif event['type'] == 'WithdrawalMade':
                past_state['balance'] -= event['amount']
        
        print(f"   Balance as of {cutoff}: ${past_state['balance']}")
        
    finally:
        shutil.rmtree(tmpdir)


def use_case_data_pipeline_checkpointing():
    """Use Case 6: Data Pipeline Checkpointing."""
    print("\n" + "="*80)
    print("USE CASE 6: Data Pipeline Checkpointing")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='pipeline.checkpoints'
        )
        
        print("\n1. Running data pipeline with checkpoints...")
        
        # Simulate data processing pipeline
        data_batches = [
            {'batch_id': 1, 'records': 100},
            {'batch_id': 2, 'records': 150},
            {'batch_id': 3, 'records': 200},
            {'batch_id': 4, 'records': 120},
            {'batch_id': 5, 'records': 180},
        ]
        
        processed_records = 0
        
        for batch in data_batches:
            print(f"   [→] Processing batch {batch['batch_id']}...")
            time.sleep(0.1)  # Simulate processing
            
            processed_records += batch['records']
            
            # Save checkpoint
            checkpoint = {
                'batch_id': batch['batch_id'],
                'records_processed': processed_records,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            storage.append(checkpoint)
            
            print(f"   [✓] Batch {batch['batch_id']} completed ({batch['records']} records)")
            print(f"       Checkpoint saved: {processed_records} total records")
        
        print(f"\n   Pipeline completed: {processed_records} total records processed")
        
        print("\n2. Viewing checkpoint history...")
        checkpoints = storage.get()
        print(f"   Total checkpoints: {len(checkpoints)}")
        for cp in checkpoints:
            print(f"   - Batch {cp['batch_id']}: {cp['records_processed']} records at {cp['timestamp']}")
        
        print("\n3. Simulating pipeline recovery...")
        # Get last checkpoint
        size = storage._get_list_size()
        last_checkpoint = storage.get(index=size-1)
        print(f"   Last checkpoint: Batch {last_checkpoint['batch_id']}")
        print(f"   Records processed: {last_checkpoint['records_processed']}")
        print(f"   [OK] Pipeline can resume from batch {last_checkpoint['batch_id'] + 1}")
        
        print("\n4. Pipeline statistics...")
        total_batches = len(checkpoints)
        total_records = checkpoints[len(checkpoints)-1]['records_processed']
        avg_records_per_batch = total_records / total_batches
        
        print(f"   Total batches: {total_batches}")
        print(f"   Total records: {total_records}")
        print(f"   Average records per batch: {avg_records_per_batch:.1f}")
        
    finally:
        shutil.rmtree(tmpdir)


def main():
    print("""
==============================================================================
                OnStorageLists Real-World Use Cases
==============================================================================
""")
    
    use_cases = [
        use_case_task_queue,
        use_case_log_aggregation,
        use_case_config_history,
        use_case_user_data_management,
        use_case_event_sourcing,
        use_case_data_pipeline_checkpointing,
    ]
    
    for use_case_func in use_cases:
        try:
            use_case_func()
        except Exception as e:
            print(f"\n[X] Use case failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("[OK] All use case examples completed!")
    print("="*80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
