"""
Simple usage example of OnStorageLists

This demonstrates the most common operations:
- Creating persistent lists
- Appending, inserting, and removing items
- Getting and setting items
- Using nested list keys
- Custom serialization methods

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_simple_usage.py
"""

from pathlib import Path
import tempfile
import shutil

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.io_utils.on_storage_lists import OnStorageLists


def main():
    print("""
==============================================================================
                OnStorageLists Simple Usage Example
==============================================================================
""")

    # Create a temporary directory for this demo
    tmpdir = tempfile.mkdtemp()
    print(f"Using temporary storage: {tmpdir}")

    try:
        # 1. Basic Setup - Create OnStorageLists instance
        print("\n1. Creating OnStorageLists instance...")
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='demo_list'
        )
        print(f"   [OK] Storage initialized with root: {tmpdir}")

        # 2. Append items to the list
        print("\n2. Appending items to the list...")
        items_to_add = [
            "First item",
            42,
            3.14159,
            {'name': 'Alice', 'age': 30},
            ['nested', 'list', 'data'],
        ]

        for i, item in enumerate(items_to_add, 1):
            storage.append(item)
            print(f"   [{i}] Appended: {item}")

        # 3. Get the entire list
        print("\n3. Getting the entire list...")
        all_items = storage.get()
        print(f"   [OK] List has {len(all_items)} items")
        for i, item in enumerate(all_items):
            print(f"   [{i}] {item}")

        # 4. Get individual items by index
        print("\n4. Getting individual items by index...")
        item_0 = storage.get(index=0)
        item_3 = storage.get(index=3)
        print(f"   [OK] Item at index 0: {item_0}")
        print(f"   [OK] Item at index 3: {item_3}")

        # 5. Insert item at specific position
        print("\n5. Inserting item at index 2...")
        storage.insert(2, "Inserted item")
        all_items = storage.get()
        print(f"   [OK] List after insert: {all_items}")

        # 6. Pop items from the list
        print("\n6. Popping items from the list...")
        last_item = storage.pop()  # Pop last item
        print(f"   [OK] Popped last item: {last_item}")

        second_item = storage.pop(1)  # Pop item at index 1
        print(f"   [OK] Popped item at index 1: {second_item}")

        all_items = storage.get()
        print(f"   [OK] List after pops: {all_items}")

        # 7. Count and search operations
        print("\n7. Count and search operations...")
        storage.extend([10, 20, 10, 30, 10])
        count_10 = storage.count(10)
        index_20 = storage.index(20)
        print(f"   [OK] Count of '10': {count_10}")
        print(f"   [OK] Index of '20': {index_20}")

        # 8. Sort the list
        print("\n8. Sorting the list...")
        storage.clear()
        storage.extend([5, 2, 8, 1, 9, 3])
        print(f"   [OK] Before sort: {storage.get()}")
        storage.sort()
        print(f"   [OK] After sort: {storage.get()}")

        # 9. Reverse the list
        print("\n9. Reversing the list...")
        storage.reverse()
        print(f"   [OK] After reverse: {storage.get()}")

        # 10. Using nested list keys
        print("\n10. Using nested list keys (hierarchical organization)...")
        storage.append("User data item 1", list_key="users.alice.messages")
        storage.append("User data item 2", list_key="users.alice.messages")
        storage.append("Config item 1", list_key="config.settings")

        alice_messages = storage.get(list_key="users.alice.messages")
        config_settings = storage.get(list_key="config.settings")

        print(f"   [OK] Alice's messages: {alice_messages}")
        print(f"   [OK] Config settings: {config_settings}")

        # Show directory structure
        print(f"\n   Directory structure created:")
        for root, dirs, files in Path(tmpdir).walk():
            level = len(root.relative_to(tmpdir).parts)
            indent = "   " * (level + 1)
            print(f"{indent}{root.name}/")
            subindent = "   " * (level + 2)
            for file in files:
                print(f"{subindent}{file}")

        # 11. Set entire list at once
        print("\n11. Setting entire list at once...")
        storage.set(['a', 'b', 'c', 'd', 'e'], list_key='alphabet', overwrite=True)
        alphabet = storage.get(list_key='alphabet')
        print(f"   [OK] Alphabet list: {alphabet}")

        # 12. Update specific item
        print("\n12. Updating specific item...")
        storage.set('Z', list_key='alphabet', index=2, overwrite=True)
        alphabet = storage.get(list_key='alphabet')
        print(f"   [OK] After update: {alphabet}")

        # 13. Custom serialization - Plain text example
        print("\n13. Using custom serialization (plain text)...")

        def write_text(obj, f):
            f.write(str(obj))

        def read_text(f):
            return f.read()

        text_storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='text_data',
            read_method=read_text,
            write_method=write_text,
            file_extension='.txt'
        )

        text_storage.append("Line 1")
        text_storage.append("Line 2")
        text_storage.append("Line 3")

        text_items = text_storage.get()
        print(f"   [OK] Text items: {text_items}")

        # 14. Clear a list
        print("\n14. Clearing a list...")
        print(f"   Before clear: {len(storage.get())} items in default list")
        storage.clear()
        print(f"   [OK] After clear: {len(storage.get())} items in default list")

        print("\n" + "="*80)
        print("[OK] Example completed successfully!")
        print("="*80 + "\n")

    finally:
        # Clean up temporary directory
        print(f"\nCleaning up temporary directory: {tmpdir}")
        shutil.rmtree(tmpdir)
        print("[OK] Cleanup complete")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
