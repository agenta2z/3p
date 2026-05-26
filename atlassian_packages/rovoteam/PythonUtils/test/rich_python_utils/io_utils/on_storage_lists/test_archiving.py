"""
Test OnStorageLists archiving mechanism

Tests the archiving functionality for OnStorageLists which allows popped items
to be moved to an archive directory instead of being deleted.
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
import re

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.io_utils.on_storage_lists import OnStorageLists


def test_archiving_enabled():
    """Test that items are archived when archiving is enabled."""
    print("\n" + "="*80)
    print("TEST 1: Archiving Enabled")
    print("="*80)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list',
            archive_enabled=True,
            archive_dir_name='_archive'
        )

        # Add items to the list
        print("\n1. Adding items to list...")
        items = [
            {'id': 1, 'data': 'first'},
            {'id': 2, 'data': 'second'},
            {'id': 3, 'data': 'third'}
        ]
        for item in items:
            storage.append(item)
        print(f"   [OK] Added {len(items)} items")

        # Pop an item
        print("\n2. Popping item (should be archived)...")
        popped = storage.pop(0)
        print(f"   [OK] Popped: {popped}")
        assert popped == items[0], f"Expected {items[0]}, got {popped}"

        # Check that archive directory exists
        print("\n3. Checking archive directory...")
        list_dir = Path(tmpdir) / 'test_list'
        archive_dir = list_dir / '_archive'
        assert archive_dir.exists(), "Archive directory not created"
        print(f"   [OK] Archive directory exists: {archive_dir}")

        # Check archived files
        print("\n4. Verifying archived file...")
        archived_files = list(archive_dir.glob('*.json'))
        assert len(archived_files) == 1, f"Expected 1 archived file, found {len(archived_files)}"

        # Verify filename format: {timestamp}_{original_name}_{random_suffix}.json
        archived_file = archived_files[0]
        filename_pattern = r'^\d{8}_\d{6}_0_[A-Za-z0-9]{8}\.json$'
        assert re.match(filename_pattern, archived_file.name), \
            f"Filename doesn't match expected pattern: {archived_file.name}"
        print(f"   [OK] Archived file: {archived_file.name}")

        # Verify archived content
        with open(archived_file, 'r') as f:
            archived_content = json.load(f)
        assert archived_content == items[0], \
            f"Archived content doesn't match: {archived_content}"
        print(f"   [OK] Archived content matches original item")

        # Verify remaining items
        print("\n5. Verifying remaining items in list...")
        remaining = storage.get()
        assert len(remaining) == 2, f"Expected 2 items, got {len(remaining)}"
        assert remaining[0] == items[1], "Second item should now be first"
        assert remaining[1] == items[2], "Third item should now be second"
        print(f"   [OK] Remaining items: {remaining}")

        print("\n[SUCCESS] All archiving tests passed!")


def test_archiving_disabled():
    """Test that items are deleted when archiving is disabled (default)."""
    print("\n" + "="*80)
    print("TEST 2: Archiving Disabled (Default Behavior)")
    print("="*80)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create storage with archiving disabled (default)
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )

        # Add items
        print("\n1. Adding items to list...")
        items = [{'id': 1}, {'id': 2}]
        for item in items:
            storage.append(item)
        print(f"   [OK] Added {len(items)} items")

        # Pop item
        print("\n2. Popping item (should be deleted)...")
        popped = storage.pop(0)
        print(f"   [OK] Popped: {popped}")

        # Verify archive directory does NOT exist
        print("\n3. Verifying no archive directory created...")
        list_dir = Path(tmpdir) / 'test_list'
        archive_dir = list_dir / '_archive'

        if archive_dir.exists():
            archived_files = list(archive_dir.glob('*.json'))
            assert len(archived_files) == 0, \
                f"Archive directory should be empty, found {len(archived_files)} files"
            print(f"   [OK] Archive directory empty (acceptable)")
        else:
            print(f"   [OK] No archive directory created")

        print("\n[SUCCESS] Archiving disabled test passed!")


def test_custom_archive_directory_name():
    """Test archiving with custom archive directory name."""
    print("\n" + "="*80)
    print("TEST 3: Custom Archive Directory Name")
    print("="*80)

    with tempfile.TemporaryDirectory() as tmpdir:
        custom_dir_name = '_history'
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list',
            archive_enabled=True,
            archive_dir_name=custom_dir_name
        )

        # Add and pop item
        print("\n1. Adding and popping item...")
        storage.append({'test': 'data'})
        popped = storage.pop()
        print(f"   [OK] Popped: {popped}")

        # Verify custom archive directory
        print(f"\n2. Verifying custom archive directory '{custom_dir_name}'...")
        list_dir = Path(tmpdir) / 'test_list'
        archive_dir = list_dir / custom_dir_name

        assert archive_dir.exists(), f"Custom archive directory not created: {custom_dir_name}"
        archived_files = list(archive_dir.glob('*.json'))
        assert len(archived_files) == 1, f"Expected 1 archived file, found {len(archived_files)}"
        print(f"   [OK] Custom archive directory created with {len(archived_files)} file(s)")

        print("\n[SUCCESS] Custom archive directory test passed!")


def test_multiple_pops_unique_filenames():
    """Test that multiple pops create unique archived filenames."""
    print("\n" + "="*80)
    print("TEST 4: Multiple Pops - Unique Filenames")
    print("="*80)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list',
            archive_enabled=True
        )

        # Add multiple items with same content
        print("\n1. Adding 5 identical items...")
        for i in range(5):
            storage.append({'value': 'same'})
        print(f"   [OK] Added 5 items")

        # Pop all items
        print("\n2. Popping all items...")
        for i in range(5):
            storage.pop(0)
        print(f"   [OK] Popped 5 items")

        # Verify all archived with unique filenames
        print("\n3. Verifying unique archived filenames...")
        list_dir = Path(tmpdir) / 'test_list'
        archive_dir = list_dir / '_archive'
        archived_files = list(archive_dir.glob('*.json'))

        assert len(archived_files) == 5, f"Expected 5 archived files, found {len(archived_files)}"

        # Check all filenames are unique
        filenames = [f.name for f in archived_files]
        assert len(filenames) == len(set(filenames)), "Archived filenames are not unique!"

        print(f"   [OK] All {len(archived_files)} files have unique names:")
        for fname in sorted(filenames):
            print(f"        - {fname}")

        print("\n[SUCCESS] Unique filenames test passed!")


def test_archive_error_on_missing_file():
    """Test that archiving raises error when file doesn't exist."""
    print("\n" + "="*80)
    print("TEST 5: Error Handling - Missing File")
    print("="*80)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list',
            archive_enabled=True
        )

        # Create path to non-existent file
        print("\n1. Testing archive of non-existent file...")
        non_existent_path = Path(tmpdir) / 'test_list' / 'non_existent.json'

        # Should raise FileNotFoundError
        try:
            storage._archive_item(non_existent_path)
            assert False, "Expected FileNotFoundError but none was raised"
        except FileNotFoundError as e:
            print(f"   [OK] FileNotFoundError raised: {e}")

        print("\n2. Testing with archiving disabled...")
        storage2 = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list2',
            archive_enabled=False
        )

        # Should NOT raise error when archiving is disabled
        try:
            storage2._archive_item(non_existent_path)
            print(f"   [OK] No error raised (archiving disabled)")
        except FileNotFoundError:
            assert False, "Should not raise error when archiving is disabled"

        print("\n[SUCCESS] Error handling test passed!")


def test_archive_with_remove_method():
    """Test that remove() method also archives items."""
    print("\n" + "="*80)
    print("TEST 6: Archiving with remove() Method")
    print("="*80)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list',
            archive_enabled=True
        )

        # Add items
        print("\n1. Adding items...")
        items = [{'id': i} for i in range(3)]
        for item in items:
            storage.append(item)
        print(f"   [OK] Added {len(items)} items")

        # Remove middle item using remove() method
        print("\n2. Removing item at index 1...")
        storage.remove(1)
        print(f"   [OK] Item removed")

        # Verify item was archived
        print("\n3. Verifying item was archived...")
        list_dir = Path(tmpdir) / 'test_list'
        archive_dir = list_dir / '_archive'
        archived_files = list(archive_dir.glob('*.json'))

        assert len(archived_files) == 1, f"Expected 1 archived file, found {len(archived_files)}"

        # Verify it was the correct item (originally at index 1, which was file 1.json)
        archived_file = archived_files[0]
        # Filename should contain "_1_" (the original index)
        assert '_1_' in archived_file.name, \
            f"Archived filename should contain '_1_': {archived_file.name}"

        with open(archived_file, 'r') as f:
            archived_content = json.load(f)
        assert archived_content == items[1], f"Wrong item archived: {archived_content}"
        print(f"   [OK] Correct item archived: {archived_file.name}")

        print("\n[SUCCESS] remove() archiving test passed!")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("TESTING OnStorageLists ARCHIVING MECHANISM")
    print("="*80)

    try:
        test_archiving_enabled()
        test_archiving_disabled()
        test_custom_archive_directory_name()
        test_multiple_pops_unique_filenames()
        test_archive_error_on_missing_file()
        test_archive_with_remove_method()

        print("\n" + "="*80)
        print("ALL ARCHIVING TESTS PASSED!")
        print("="*80 + "\n")

    except AssertionError as e:
        print(f"\n[FAILED] Assertion error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
