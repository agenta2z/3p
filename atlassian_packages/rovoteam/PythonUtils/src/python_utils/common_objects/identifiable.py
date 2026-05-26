"""
Identifiable base class for objects that need a unique identifier.
"""
import uuid
from abc import ABC
from typing import Optional, Union, Any, Callable

from attr import attrs, attrib


@attrs(slots=False)
class Identifiable(ABC):
    """
    A base class to provide unique identification for objects.

    Attributes:
        id (Union[int, str], optional):
            Unique identifier for this object instance. Auto-generated if None.
            Format: `{ClassName}_{uuid}` (e.g., "Agent_a3f2b1c4").
        _auto_id_suffix (Union[bool, Callable], optional):
            Controls whether to automatically append a suffix to the ID:
            - None or False: No automatic suffix (use ID as-is)
            - True: Append UUID suffix (e.g., "MyID-a3f2b1c4")
            - Callable: Call the function to generate suffix (e.g., lambda: "v2")

    Examples:
        Basic usage with auto-generated ID:
        >>> class MyObject(Identifiable):
        ...     pass
        >>> obj = MyObject()
        >>> obj.id  # doctest: +ELLIPSIS
        'MyObject_...'

        Custom ID without suffix:
        >>> obj2 = MyObject(id="CustomID", _auto_id_suffix=False)
        >>> obj2.id
        'CustomID'

        Custom ID with automatic UUID suffix:
        >>> obj3 = MyObject(id="CustomID", _auto_id_suffix=True)
        >>> obj3.id  # doctest: +ELLIPSIS
        'CustomID-...'

        Custom ID with callable suffix:
        >>> obj4 = MyObject(id="CustomID", _auto_id_suffix=lambda: "v2")
        >>> obj4.id
        'CustomID-v2'
    """
    id: Optional[Union[int, str]] = attrib(default=None, kw_only=True)
    _auto_id_suffix: Union[bool, Callable] = attrib(default=None, kw_only=True, alias='auto_id_suffix')
    _enable_suffix_for_initial_id : bool = attrib(default=False, kw_only=True, alias='enable_suffix_for_initial_id')
    _raw_id: Any = attrib(default=None, kw_only=True)

    def new_id(self):
        """
        Generate a new ID for this object.

        Behavior:
        - If _raw_id exists and _auto_id_suffix is enabled, appends suffix
        - If _raw_id exists but _auto_id_suffix is False, uses _raw_id as-is
        - If no _raw_id, generates {ClassName}_{uuid}
        """
        import uuid

        if self._raw_id:
            # We have a custom ID
            if self._auto_id_suffix is False:
                # Explicitly disabled suffix - use raw ID as-is
                self.id = f"{self._raw_id}"
            elif self._auto_id_suffix is True:
                # Explicitly enabled suffix - append UUID
                self.id = f"{self._raw_id}-{uuid.uuid4().hex[:8]}"
            elif callable(self._auto_id_suffix):
                # Custom suffix generator
                suffix = self._auto_id_suffix()
                self.id = f"{self._raw_id}-{suffix}"
            else:
                # _auto_id_suffix is None - default to appending UUID
                self.id = f"{self._raw_id}-{uuid.uuid4().hex[:8]}"
        else:
            # No custom ID - generate default with UUID
            self.id = f"{self.__class__.__name__}-{uuid.uuid4().hex[:8]}"


    def __attrs_post_init__(self):
        """
        Initialize the ID after object creation.

        Logic:
        - If id is None, generate a new auto ID
        - If id is provided:
          - Store it in _raw_id
          - Apply _auto_id_suffix logic via new_id()
        """
        # Auto-generate id if not provided
        if self.id is None:
            self._raw_id = None
            self.new_id()
        else:
            # Store the raw ID
            self._raw_id = self.id

            if isinstance(self._raw_id, str):
                self._raw_id = self._raw_id.replace("$class", self.__class__.__name__)
                self.id = self._raw_id
            elif isinstance(self._raw_id, int):
                self.id = self._raw_id
            else:
                self.id = f"{self._raw_id}"

            # DO NOT apply suffix logic initially if `_enable_suffix_for_initial_id` is set False
            if self._enable_suffix_for_initial_id:
                self.new_id()



