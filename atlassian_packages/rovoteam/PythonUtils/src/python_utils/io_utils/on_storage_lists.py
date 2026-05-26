"""OnStorageLists - A class for managing lists stored on disk.

This module provides a persistent list implementation where each list item is stored
as a separate file on disk. Lists are organized in directories based on list keys,
and items are stored with numeric filenames (0.json, 1.json, etc.).
"""

import os
import shutil
from pathlib import Path
from typing import Any, Callable, List, Optional, Union
from attr import attrs, attrib
import json as json_module
from python_utils.datetime_utils.common import current_date_time_string
from python_utils.string_utils.common import random_string


@attrs(slots=False)
class OnStorageLists:
    """A class for managing lists stored on disk with file-based persistence.
    
    Each list is stored in a directory, with individual items saved as separate files.
    The list key is split by a separator and converted to a directory path structure.
    This allows for hierarchical organization of lists.
    
    Attributes:
        root_path (str): The root directory where all lists are stored.
        default_list_key (str): The default list key to use when none is specified.
        list_key_components_sep (str): Separator for splitting list keys into path components.
            Defaults to '.'.
        read_method (Callable): Function to deserialize items from files. Defaults to json.load.
        write_method (Callable): Function to serialize items to files. Defaults to json.dump.
        file_extension (str): File extension for stored items. Defaults to '.json'.
        archive_enabled (bool): Whether to archive items to a subdirectory instead of deleting
            them when removed. Defaults to False.
        archive_dir_name (str): Name of the subdirectory for archived items. Defaults to '_archive'.
    
    Examples:
        Basic usage with default JSON serialization:
        
        >>> import tempfile, os
        >>> tmpdir = tempfile.mkdtemp()
        >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='my_list')
        >>> storage.append({'name': 'Alice', 'age': 30})
        >>> storage.append({'name': 'Bob', 'age': 25})
        >>> items = storage.get()
        >>> len(items)
        2
        >>> items[0]['name']
        'Alice'
        >>> import shutil
        >>> shutil.rmtree(tmpdir)
        
        Using nested list keys:
        
        >>> tmpdir = tempfile.mkdtemp()
        >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='default')
        >>> storage.append('item1', list_key='user.data.items')
        >>> storage.append('item2', list_key='user.data.items')
        >>> items = storage.get(list_key='user.data.items')
        >>> items
        ['item1', 'item2']
        >>> shutil.rmtree(tmpdir)
        
        Custom serialization (plain text):
        
        >>> tmpdir = tempfile.mkdtemp()
        >>> def write_text(obj, f): f.write(str(obj))
        >>> def read_text(f): return f.read()
        >>> storage = OnStorageLists(
        ...     root_path=tmpdir,
        ...     default_list_key='text_list',
        ...     read_method=read_text,
        ...     write_method=write_text,
        ...     file_extension='.txt'
        ... )
        >>> storage.append('Hello')
        >>> storage.append('World')
        >>> storage.get()
        ['Hello', 'World']
        >>> shutil.rmtree(tmpdir)
    """
    
    root_path: str = attrib()
    default_list_key: str = attrib()
    list_key_components_sep: str = attrib(default='.')
    read_method: Callable = attrib(default=json_module.load)
    write_method: Callable = attrib(default=json_module.dump)
    file_extension: str = attrib(default='.json')
    archive_enabled: bool = attrib(default=False)
    archive_dir_name: str = attrib(default='_archive')
    
    def _get_list_dir(self, list_key: Optional[str] = None) -> Path:
        """Get the directory path for a given list key."""
        key = list_key if list_key is not None else self.default_list_key
        components = key.split(self.list_key_components_sep)
        return Path(self.root_path).joinpath(*components)
    
    def _get_item_path(self, index: int, list_key: Optional[str] = None) -> Path:
        """Get the file path for a specific item at the given index."""
        list_dir = self._get_list_dir(list_key)
        return list_dir / f"{index}{self.file_extension}"
    
    def _ensure_list_dir(self, list_key: Optional[str] = None):
        """Ensure the list directory exists."""
        list_dir = self._get_list_dir(list_key)
        list_dir.mkdir(parents=True, exist_ok=True)

    def _archive_item(self, item_path: Path) -> None:
        """Archive an item before deletion (only if archive_enabled=True).

        Moves the item file to an archive subdirectory with a timestamp and random suffix
        to avoid filename conflicts. The archived filename format is:
        {timestamp}_{original_name}_{random_suffix}{extension}

        Args:
            item_path (Path): Path to the item file to archive.

        Raises:
            FileNotFoundError: If archive_enabled is True but the item file doesn't exist.

        Examples:
            Original file: 0.json
            Archived as: 20231121_143022_0_aB3dE7Gh.json
        """
        if not self.archive_enabled:
            return  # Skip archiving if disabled

        if not item_path.exists():
            raise FileNotFoundError(f"Cannot archive item: {item_path} does not exist")

        # Create archive directory
        archive_dir = item_path.parent / self.archive_dir_name
        archive_dir.mkdir(exist_ok=True)

        # Generate unique archived filename using existing utility functions
        timestamp_str = current_date_time_string('%Y%m%d_%H%M%S')
        original_name = item_path.stem  # Filename without extension
        random_suffix = random_string(8)

        archived_name = f"{timestamp_str}_{original_name}_{random_suffix}{item_path.suffix}"
        archive_path = archive_dir / archived_name

        # Move file to archive (removes original)
        shutil.move(str(item_path), str(archive_path))

    def _get_list_size(self, list_key: Optional[str] = None) -> int:
        """Get the current size of the list by counting files."""
        list_dir = self._get_list_dir(list_key)
        if not list_dir.exists():
            return 0
        count = 0
        while self._get_item_path(count, list_key).exists():
            count += 1
        return count
    
    def get(self, list_key: Optional[str] = None, index: Optional[int] = None, default: Any = None) -> Union[Any, List[Any]]:
        """Get an item or the whole list from storage.
        
        If index is specified, returns the single item at that index.
        If index is None, returns the entire list as a Python list.
        
        Args:
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
            index (Optional[int]): The index of the item to retrieve. If None, retrieves
                the entire list.
            default (Any): Default value to return if the item doesn't exist. Defaults to None.
        
        Returns:
            Union[Any, List[Any]]: If index is specified, returns the object at that index
                or the default value. If index is None, returns the entire list.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.append('first')
            >>> storage.append('second')
            >>> storage.append('third')
            >>> 
            >>> # Get single item
            >>> storage.get(index=0)
            'first'
            >>> storage.get(index=1)
            'second'
            >>> 
            >>> # Get whole list
            >>> storage.get()
            ['first', 'second', 'third']
            >>> 
            >>> # Get with default for non-existent item
            >>> storage.get(index=10, default='not_found')
            'not_found'
            >>> shutil.rmtree(tmpdir)
        """
        if index is not None:
            item_path = self._get_item_path(index, list_key)
            if not item_path.exists():
                return default
            try:
                with open(item_path, 'r') as f:
                    return self.read_method(f)
            except Exception as e:
                print(f"Error reading item at index {index}: {e}")
                return default
        else:
            size = self._get_list_size(list_key)
            result = []
            for i in range(size):
                item = self.get(list_key, i, default=None)
                if item is not None:
                    result.append(item)
            return result
    
    def set(self, obj_or_list: Union[Any, List[Any]], list_key: Optional[str] = None, 
            index: Optional[int] = None, overwrite: bool = False):
        """Set an item or replace the entire list.
        
        If index is specified, sets the item at that index.
        If index is None, replaces the entire list with the provided list/tuple.
        
        Args:
            obj_or_list (Union[Any, List[Any]]): The object to set (if index is specified)
                or the list/tuple to replace the entire list with (if index is None).
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
            index (Optional[int]): The index to set. If None, sets the entire list.
            overwrite (bool): If True, overwrites existing items. If False, raises
                FileExistsError if item already exists. Defaults to False.
        
        Raises:
            FileExistsError: If item at index exists and overwrite is False.
            TypeError: If index is None and obj_or_list is not a list or tuple.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> 
            >>> # Set entire list
            >>> storage.set([1, 2, 3])
            >>> storage.get()
            [1, 2, 3]
            >>> 
            >>> # Set single item
            >>> storage.set(99, index=1, overwrite=True)
            >>> storage.get()
            [1, 99, 3]
            >>> 
            >>> # Replace entire list
            >>> storage.set(['a', 'b', 'c'], overwrite=True)
            >>> storage.get()
            ['a', 'b', 'c']
            >>> shutil.rmtree(tmpdir)
        """
        self._ensure_list_dir(list_key)
        if index is not None:
            item_path = self._get_item_path(index, list_key)
            if item_path.exists() and not overwrite:
                raise FileExistsError(f"Item at index {index} already exists. Use overwrite=True to replace.")
            with open(item_path, 'w') as f:
                self.write_method(obj_or_list, f)
        else:
            if not isinstance(obj_or_list, (list, tuple)):
                raise TypeError("When index is None, obj_or_list must be a list or tuple")
            if overwrite:
                self.clear(list_key)
            for i, item in enumerate(obj_or_list):
                self.set(item, list_key, index=i, overwrite=overwrite)
    
    def append(self, obj: Any, list_key: Optional[str] = None):
        """Append an object to the end of the list.
        
        Args:
            obj (Any): The object to append to the list.
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.append('first')
            >>> storage.append('second')
            >>> storage.append({'key': 'value'})
            >>> storage.get()
            ['first', 'second', {'key': 'value'}]
            >>> shutil.rmtree(tmpdir)
        """
        size = self._get_list_size(list_key)
        self.set(obj, list_key, index=size, overwrite=False)
    
    def pop(self, index: int = -1, list_key: Optional[str] = None, default: Any = None) -> Any:
        """Remove and return an item at the specified index.
        
        Removes the item at the given index and shifts all subsequent items down by one.
        Supports negative indices (e.g., -1 for last item).
        
        Args:
            index (int): The index of the item to pop. Defaults to -1 (last item).
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
            default (Any): Default value to return if the list is empty or index is out
                of range. Defaults to None.
        
        Returns:
            Any: The object at the specified index, or default if not found.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend(['a', 'b', 'c', 'd'])
            >>> 
            >>> # Pop last item
            >>> storage.pop()
            'd'
            >>> storage.get()
            ['a', 'b', 'c']
            >>> 
            >>> # Pop specific index
            >>> storage.pop(1)
            'b'
            >>> storage.get()
            ['a', 'c']
            >>> 
            >>> # Pop from empty list with default
            >>> storage.clear()
            >>> storage.pop(default='empty')
            'empty'
            >>> shutil.rmtree(tmpdir)
        """
        size = self._get_list_size(list_key)
        if size == 0:
            return default
        if index < 0:
            index = size + index
        if index < 0 or index >= size:
            return default
        item = self.get(list_key, index, default=default)
        self.remove(index, list_key)
        return item
    
    def remove(self, index: int, list_key: Optional[str] = None):
        """Remove an item at the specified index and shift subsequent items.
        
        Removes the item at the given index and shifts all subsequent items down by one.
        Unlike pop(), this method doesn't return the removed item.
        
        Args:
            index (int): The index of the item to remove.
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Raises:
            IndexError: If index is out of range for the list.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend([10, 20, 30, 40, 50])
            >>> 
            >>> # Remove item at index 2
            >>> storage.remove(2)
            >>> storage.get()
            [10, 20, 40, 50]
            >>> 
            >>> # Remove first item
            >>> storage.remove(0)
            >>> storage.get()
            [20, 40, 50]
            >>> shutil.rmtree(tmpdir)
        """
        size = self._get_list_size(list_key)
        if index < 0 or index >= size:
            raise IndexError(f"Index {index} out of range for list of size {size}")
        item_path = self._get_item_path(index, list_key)
        if item_path.exists():
            # Archive the item if archiving is enabled
            self._archive_item(item_path)

            # Only unlink if the file still exists (i.e., archiving was disabled or failed)
            if item_path.exists():
                item_path.unlink()
        for i in range(index + 1, size):
            old_path = self._get_item_path(i, list_key)
            new_path = self._get_item_path(i - 1, list_key)
            if old_path.exists():
                old_path.rename(new_path)
    
    def insert(self, index: int, obj: Any, list_key: Optional[str] = None):
        """Insert an item at the specified index, shifting subsequent items up.
        
        Inserts the object at the given index and shifts all items at that index
        and beyond up by one position.
        
        Args:
            index (int): The index at which to insert the item. Negative indices are supported.
            obj (Any): The object to insert.
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend(['a', 'b', 'c'])
            >>> 
            >>> # Insert at beginning
            >>> storage.insert(0, 'start')
            >>> storage.get()
            ['start', 'a', 'b', 'c']
            >>> 
            >>> # Insert in middle
            >>> storage.insert(2, 'middle')
            >>> storage.get()
            ['start', 'a', 'middle', 'b', 'c']
            >>> 
            >>> # Insert at end
            >>> storage.insert(5, 'end')
            >>> storage.get()
            ['start', 'a', 'middle', 'b', 'c', 'end']
            >>> shutil.rmtree(tmpdir)
        """
        size = self._get_list_size(list_key)
        if index < 0:
            index = max(0, size + index + 1)
        if index > size:
            index = size
        self._ensure_list_dir(list_key)
        for i in range(size - 1, index - 1, -1):
            old_path = self._get_item_path(i, list_key)
            new_path = self._get_item_path(i + 1, list_key)
            if old_path.exists():
                old_path.rename(new_path)
        self.set(obj, list_key, index=index, overwrite=True)
    
    def clear(self, list_key: Optional[str] = None):
        """Remove all items from the list.
        
        Deletes all item files from the list directory, effectively clearing the list.
        The list directory itself is not removed.
        
        Args:
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend([1, 2, 3, 4, 5])
            >>> len(storage.get())
            5
            >>> storage.clear()
            >>> storage.get()
            []
            >>> shutil.rmtree(tmpdir)
        """
        list_dir = self._get_list_dir(list_key)
        if not list_dir.exists():
            return
        for item_file in list_dir.glob(f"*{self.file_extension}"):
            try:
                if item_file.stem.isdigit():
                    item_file.unlink()
            except Exception as e:
                print(f"Error removing file {item_file}: {e}")
    
    def index(self, item: Any, list_key: Optional[str] = None, start: int = 0, stop: Optional[int] = None) -> int:
        """Find the first index of an item in the list.
        
        Searches for the item in the list and returns its index. Optionally searches
        within a specified range.
        
        Args:
            item (Any): The item to search for.
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
            start (int): Start index for the search. Defaults to 0.
            stop (Optional[int]): Stop index for the search (exclusive). If None, searches
                to the end of the list.
        
        Returns:
            int: The index of the first occurrence of the item.
        
        Raises:
            ValueError: If the item is not found in the list.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend(['a', 'b', 'c', 'b', 'd'])
            >>> 
            >>> # Find first occurrence
            >>> storage.index('b')
            1
            >>> 
            >>> # Find within range
            >>> storage.index('b', start=2)
            3
            >>> 
            >>> # Item not found raises ValueError
            >>> try:
            ...     storage.index('z')
            ... except ValueError as e:
            ...     print("Not found")
            Not found
            >>> shutil.rmtree(tmpdir)
        """
        size = self._get_list_size(list_key)
        stop = size if stop is None else min(stop, size)
        for i in range(start, stop):
            if self.get(list_key, i) == item:
                return i
        raise ValueError(f"{item} is not in list")
    
    def count(self, item: Any, list_key: Optional[str] = None) -> int:
        """Count the number of occurrences of an item in the list.
        
        Args:
            item (Any): The item to count.
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Returns:
            int: The number of times the item appears in the list.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend([1, 2, 3, 2, 4, 2, 5])
            >>> 
            >>> # Count occurrences
            >>> storage.count(2)
            3
            >>> storage.count(1)
            1
            >>> storage.count(99)
            0
            >>> shutil.rmtree(tmpdir)
        """
        count = 0
        size = self._get_list_size(list_key)
        for i in range(size):
            if self.get(list_key, i) == item:
                count += 1
        return count
    
    def extend(self, items: List[Any], list_key: Optional[str] = None):
        """Extend the list by appending all items from an iterable.
        
        Args:
            items (List[Any]): An iterable of items to append to the list.
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.append('first')
            >>> storage.extend(['second', 'third', 'fourth'])
            >>> storage.get()
            ['first', 'second', 'third', 'fourth']
            >>> shutil.rmtree(tmpdir)
        """
        for item in items:
            self.append(item, list_key)
    
    def reverse(self, list_key: Optional[str] = None):
        """Reverse the order of items in the list in place.
        
        Args:
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> storage.extend([1, 2, 3, 4, 5])
            >>> storage.reverse()
            >>> storage.get()
            [5, 4, 3, 2, 1]
            >>> shutil.rmtree(tmpdir)
        """
        items = self.get(list_key)
        items.reverse()
        self.set(items, list_key, overwrite=True)
    
    def sort(self, list_key: Optional[str] = None, key: Optional[Callable] = None, reverse: bool = False):
        """Sort the list in place.
        
        Args:
            list_key (Optional[str]): The list identifier. If None, uses default_list_key.
            key (Optional[Callable]): Optional function to extract a comparison key from
                each element. Defaults to None (compare elements directly).
            reverse (bool): If True, sort in descending order. Defaults to False.
        
        Examples:
            >>> import tempfile, shutil
            >>> tmpdir = tempfile.mkdtemp()
            >>> storage = OnStorageLists(root_path=tmpdir, default_list_key='test')
            >>> 
            >>> # Sort numbers
            >>> storage.extend([3, 1, 4, 1, 5, 9, 2, 6])
            >>> storage.sort()
            >>> storage.get()
            [1, 1, 2, 3, 4, 5, 6, 9]
            >>> 
            >>> # Sort in reverse
            >>> storage.sort(reverse=True)
            >>> storage.get()
            [9, 6, 5, 4, 3, 2, 1, 1]
            >>> 
            >>> # Sort with key function
            >>> storage.clear()
            >>> storage.extend(['apple', 'pie', 'a', 'longer'])
            >>> storage.sort(key=len)
            >>> storage.get()
            ['a', 'pie', 'apple', 'longer']
            >>> shutil.rmtree(tmpdir)
        """
        items = self.get(list_key)
        items.sort(key=key, reverse=reverse)
        self.set(items, list_key, overwrite=True)
