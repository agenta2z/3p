"""
Test OnStorageLists class

Tests all list operations for the OnStorageLists class which stores
list items as individual files on disk.
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.io_utils.on_storage_lists import OnStorageLists


def test_basic_operations():
    """Test basic get/set/append operations."""
    print("\n" + "="*80)
    print("TEST 1: Basic Operations")
    print("="*80)
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )
        
        # Test append
        print("\n1. Testing append...")
        storage.append({'id': 1, 'name': 'Alice'})
        storage.append({'id': 2, 'name': 'Bob'})
        storage.append({'id': 3, 'name': 'Charlie'})
        print(f"   [OK] Appended 3 items")
        
        # Test get whole list
        print("\n2. Testing get whole list...")
        items = storage.get()
        print(f"   [OK] Retrieved {len(items)} items: {items}")
        assert len(items) == 3, f"Expected 3 items, got {len(items)}"
        assert items[0]['name'] == 'Alice'
        assert items[1]['name'] == 'Bob'
        assert items[2]['name'] == 'Charlie'
        
        # Test get single item
        print("\n3. Testing get single item...")
        item = storage.get(index=1)
        print(f"   [OK] Retrieved item at index 1: {item}")
        assert item['name'] == 'Bob'
        
        # Test set single item
        print("\n4. Testing set single item...")
        storage.set({'id': 2, 'name': 'Robert'}, index=1, overwrite=True)
        item = storage.get(index=1)
        print(f"   [OK] Updated item at index 1: {item}")
        assert item['name'] == 'Robert'
        
        print("\n[OK] Basic operations test passed")
        return True


def test_list_key_separation():
    """Test list key separation with different keys."""
    print("\n" + "="*80)
    print("TEST 2: List Key Separation")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='default',
            list_key_components_sep='.'
        )
        
        # Create multiple lists
        print("\n1. Creating multiple lists...")
        storage.append('item1', list_key='list_a')
        storage.append('item2', list_key='list_a')
        storage.append('data1', list_key='list_b')
        storage.append('data2', list_key='list_b')
        storage.append('data3', list_key='list_b')
        print(f"   [OK] Created list_a with 2 items and list_b with 3 items")
        
        # Verify separation
        print("\n2. Verifying list separation...")
        list_a = storage.get(list_key='list_a')
        list_b = storage.get(list_key='list_b')
        print(f"   [OK] list_a: {list_a}")
        print(f"   [OK] list_b: {list_b}")
        assert len(list_a) == 2
        assert len(list_b) == 3
        assert list_a[0] == 'item1'
        assert list_b[0] == 'data1'
        
        # Test nested key
        print("\n3. Testing nested list key...")
        storage.append('nested_item', list_key='user.data.items')
        nested_items = storage.get(list_key='user.data.items')
        print(f"   [OK] Nested list: {nested_items}")
        assert len(nested_items) == 1
        
        # Verify directory structure
        print("\n4. Verifying directory structure...")
        user_dir = Path(tmpdir) / 'user' / 'data' / 'items'
        assert user_dir.exists(), "Nested directory should exist"
        print(f"   [OK] Directory structure created: {user_dir}")
        
        print("\n[OK] List key separation test passed")
        return True


def test_pop_and_remove():
    """Test pop and remove operations."""
    print("\n" + "="*80)
    print("TEST 3: Pop and Remove Operations")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )
        
        # Setup
        print("\n1. Setting up list...")
        for i in range(5):
            storage.append(f'item_{i}')
        items = storage.get()
        print(f"   [OK] Created list: {items}")
        
        # Test pop last item
        print("\n2. Testing pop (last item)...")
        popped = storage.pop()
        print(f"   [OK] Popped: {popped}")
        assert popped == 'item_4'
        assert len(storage.get()) == 4
        
        # Test pop specific index
        print("\n3. Testing pop (index 1)...")
        popped = storage.pop(1)
        print(f"   [OK] Popped: {popped}")
        assert popped == 'item_1'
        remaining = storage.get()
        print(f"   [OK] Remaining: {remaining}")
        assert remaining == ['item_0', 'item_2', 'item_3']
        
        # Test remove
        print("\n4. Testing remove...")
        storage.remove(1)
        remaining = storage.get()
        print(f"   [OK] After remove(1): {remaining}")
        assert remaining == ['item_0', 'item_3']
        
        # Test pop with default
        print("\n5. Testing pop with default on empty index...")
        storage.clear()
        popped = storage.pop(default='default_value')
        print(f"   [OK] Popped from empty list: {popped}")
        assert popped == 'default_value'
        
        print("\n[OK] Pop and remove test passed")
        return True


def test_insert_and_clear():
    """Test insert and clear operations."""
    print("\n" + "="*80)
    print("TEST 4: Insert and Clear Operations")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )
        
        # Setup
        print("\n1. Setting up list...")
        storage.append('a')
        storage.append('b')
        storage.append('c')
        print(f"   [OK] Initial list: {storage.get()}")
        
        # Test insert at beginning
        print("\n2. Testing insert at beginning...")
        storage.insert(0, 'start')
        items = storage.get()
        print(f"   [OK] After insert(0, 'start'): {items}")
        assert items == ['start', 'a', 'b', 'c']
        
        # Test insert in middle
        print("\n3. Testing insert in middle...")
        storage.insert(2, 'middle')
        items = storage.get()
        print(f"   [OK] After insert(2, 'middle'): {items}")
        assert items == ['start', 'a', 'middle', 'b', 'c']
        
        # Test insert at end
        print("\n4. Testing insert at end...")
        storage.insert(5, 'end')
        items = storage.get()
        print(f"   [OK] After insert(5, 'end'): {items}")
        assert items == ['start', 'a', 'middle', 'b', 'c', 'end']
        
        # Test clear
        print("\n5. Testing clear...")
        storage.clear()
        items = storage.get()
        print(f"   [OK] After clear: {items}")
        assert items == []
        
        print("\n[OK] Insert and clear test passed")
        return True


def test_list_methods():
    """Test additional list methods."""
    print("\n" + "="*80)
    print("TEST 5: Additional List Methods")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )
        
        # Setup
        print("\n1. Setting up list...")
        storage.extend([1, 2, 3, 2, 4, 2])
        print(f"   [OK] Initial list: {storage.get()}")
        
        # Test count
        print("\n2. Testing count...")
        count = storage.count(2)
        print(f"   [OK] Count of 2: {count}")
        assert count == 3
        
        # Test index
        print("\n3. Testing index...")
        idx = storage.index(3)
        print(f"   [OK] Index of 3: {idx}")
        assert idx == 2
        
        # Test reverse
        print("\n4. Testing reverse...")
        storage.reverse()
        items = storage.get()
        print(f"   [OK] After reverse: {items}")
        assert items == [2, 4, 2, 3, 2, 1]
        
        # Test sort
        print("\n5. Testing sort...")
        storage.sort()
        items = storage.get()
        print(f"   [OK] After sort: {items}")
        assert items == [1, 2, 2, 2, 3, 4]
        
        # Test sort reverse
        print("\n6. Testing sort (reverse)...")
        storage.sort(reverse=True)
        items = storage.get()
        print(f"   [OK] After sort(reverse=True): {items}")
        assert items == [4, 3, 2, 2, 2, 1]
        
        print("\n[OK] Additional list methods test passed")
        return True


def test_set_whole_list():
    """Test setting the whole list at once."""
    print("\n" + "="*80)
    print("TEST 6: Set Whole List")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )
        
        # Test set whole list
        print("\n1. Testing set whole list...")
        new_list = [{'id': 1}, {'id': 2}, {'id': 3}]
        storage.set(new_list)
        items = storage.get()
        print(f"   [OK] Set list: {items}")
        assert items == new_list
        
        # Test overwrite
        print("\n2. Testing overwrite...")
        newer_list = [{'id': 10}, {'id': 20}]
        storage.set(newer_list, overwrite=True)
        items = storage.get()
        print(f"   [OK] Overwritten list: {items}")
        assert items == newer_list
        
        print("\n[OK] Set whole list test passed")
        return True


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "="*80)
    print("TEST 7: Edge Cases")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='test_list'
        )
        
        # Test get from empty list
        print("\n1. Testing get from empty list...")
        items = storage.get()
        print(f"   [OK] Empty list: {items}")
        assert items == []
        
        # Test get with default
        print("\n2. Testing get with default...")
        item = storage.get(index=0, default='not_found')
        print(f"   [OK] Get non-existent item: {item}")
        assert item == 'not_found'
        
        # Test remove from empty list
        print("\n3. Testing remove from empty list...")
        try:
            storage.remove(0)
            print(f"   [X] Should have raised IndexError")
            return False
        except IndexError as e:
            print(f"   [OK] Raised IndexError: {e}")
        
        # Test index not found
        print("\n4. Testing index not found...")
        storage.append('item')
        try:
            storage.index('not_exists')
            print(f"   [X] Should have raised ValueError")
            return False
        except ValueError as e:
            print(f"   [OK] Raised ValueError: {e}")
        
        # Test negative indices
        print("\n5. Testing negative indices...")
        storage.clear()
        storage.extend(['a', 'b', 'c'])
        item = storage.pop(-1)
        print(f"   [OK] Pop(-1): {item}")
        assert item == 'c'
        assert storage.get() == ['a', 'b']
        
        print("\n[OK] Edge cases test passed")
        return True


def test_custom_serialization():
    """Test with custom read/write methods."""
    print("\n" + "="*80)
    print("TEST 8: Custom Serialization")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Custom serialization for plain text
        def write_text(obj, f):
            f.write(str(obj))
        
        def read_text(f):
            return f.read()
        
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='text_list',
            read_method=read_text,
            write_method=write_text,
            file_extension='.txt'
        )
        
        print("\n1. Testing custom serialization...")
        storage.append('Hello')
        storage.append('World')
        items = storage.get()
        print(f"   [OK] Items: {items}")
        assert items == ['Hello', 'World']
        
        # Verify file extension
        print("\n2. Verifying file extension...")
        list_dir = Path(tmpdir) / 'text_list'
        txt_files = list(list_dir.glob('*.txt'))
        print(f"   [OK] Found {len(txt_files)} .txt files")
        assert len(txt_files) == 2
        
        print("\n[OK] Custom serialization test passed")
        return True


def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
                    OnStorageLists Test Suite                    
==============================================================================
""")
    
    tests = [
        ("Basic Operations", test_basic_operations),
        ("List Key Separation", test_list_key_separation),
        ("Pop and Remove", test_pop_and_remove),
        ("Insert and Clear", test_insert_and_clear),
        ("Additional List Methods", test_list_methods),
        ("Set Whole List", test_set_whole_list),
        ("Edge Cases", test_edge_cases),
        ("Custom Serialization", test_custom_serialization),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[X] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for name, success in results:
        status = "[OK] PASS" if success else "[X] FAIL"
        print(f"  {status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return True
    else:
        print(f"\n[FAILED] {total - passed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
