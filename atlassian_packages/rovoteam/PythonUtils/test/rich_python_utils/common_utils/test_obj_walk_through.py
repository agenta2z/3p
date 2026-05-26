"""Tests for obj_walk_through in map_helper."""

from typing import Optional

import pytest
from attr import attrs, attrib

from python_utils.common_utils.map_helper import obj_walk_through


class TestDictWalk:
    """Walk through dict instances."""

    def test_flat_dict(self):
        result = list(obj_walk_through({'a': 1, 'b': 2}))
        paths = [p for p, _ in result]
        assert ['a'] in paths
        assert ['b'] in paths

    def test_nested_dict(self):
        result = list(obj_walk_through({'a': {'b': 1}}))
        assert (['a'], {'b': 1}) in result
        assert (['a', 'b'], 1) in result

    def test_empty_dict(self):
        assert list(obj_walk_through({})) == []


class TestListWalk:
    """Walk through list/tuple instances."""

    def test_flat_list(self):
        result = list(obj_walk_through([10, 20]))
        assert (['0'], 10) in result
        assert (['1'], 20) in result

    def test_nested_list(self):
        result = list(obj_walk_through([10, [20, 30]]))
        assert (['0'], 10) in result
        assert (['1'], [20, 30]) in result
        assert (['1', '0'], 20) in result
        assert (['1', '1'], 30) in result

    def test_dict_in_list(self):
        result = list(obj_walk_through([{'x': 1}]))
        assert (['0'], {'x': 1}) in result
        assert (['0', 'x'], 1) in result


class TestTypeWalk:
    """Walk through type annotations."""

    def test_simple_class(self):
        @attrs(slots=True)
        class Simple:
            name: str = attrib(default='')
            count: int = attrib(default=0)

        result = list(obj_walk_through(Simple))
        paths = [p for p, _ in result]
        assert ['name'] in paths
        assert ['count'] in paths

    def test_nested_type(self):
        @attrs(slots=True)
        class Inner:
            data: str = attrib(default='')

        @attrs(slots=True)
        class Outer:
            inner: Inner = attrib(factory=Inner)

        result = list(obj_walk_through(Outer))
        assert (['inner'], Inner) in result
        assert (['inner', 'data'], str) in result

    def test_optional_unwrapped(self):
        @attrs(slots=True)
        class Inner:
            value: int = attrib(default=0)

        @attrs(slots=True)
        class Outer:
            maybe: Optional[Inner] = attrib(default=None)

        result = list(obj_walk_through(Outer))
        assert (['maybe'], Inner) in result
        assert (['maybe', 'value'], int) in result

    def test_dag_same_type_at_sibling_paths(self):
        """Same type at two sibling paths yields both paths."""
        @attrs(slots=True)
        class Shared:
            x: int = attrib(default=0)

        @attrs(slots=True)
        class Root:
            a: Shared = attrib(factory=Shared)
            b: Shared = attrib(factory=Shared)

        result = list(obj_walk_through(Root))
        paths = [p for p, _ in result]
        assert ['a'] in paths
        assert ['a', 'x'] in paths
        assert ['b'] in paths
        assert ['b', 'x'] in paths

    def test_cycle_does_not_infinite_loop(self):
        """Circular type annotations terminate."""
        @attrs(slots=True)
        class B:
            pass

        @attrs(slots=True)
        class A:
            b: B = attrib(factory=B)

        # Inject circular annotation
        B.__annotations__['a'] = A

        result = list(obj_walk_through(A))
        assert (['b'], B) in result
        assert (['b', 'a'], A) in result
        # A is ancestor of b.a, so recursion stops — no ['b', 'a', 'b']
        deep = [p for p, _ in result if len(p) > 2]
        assert deep == []


class TestAttrsInstanceWalk:
    """Walk through attrs object instances."""

    def test_attrs_instance(self):
        @attrs(slots=True)
        class Point:
            x: int = attrib(default=0)
            y: int = attrib(default=0)

        obj = Point(x=10, y=20)
        result = list(obj_walk_through(obj))
        assert (['x'], 10) in result
        assert (['y'], 20) in result

    def test_nested_attrs_instance(self):
        @attrs(slots=True)
        class Inner:
            val: str = attrib(default='')

        @attrs(slots=True)
        class Outer:
            inner: Inner = attrib(factory=Inner)

        obj = Outer(inner=Inner(val='hello'))
        result = list(obj_walk_through(obj))
        assert (['inner', 'val'], 'hello') in result


class TestBasicTypesNotRecursed:
    """Strings, ints, etc. are not recursed into."""

    def test_string_not_iterated(self):
        result = list(obj_walk_through({'s': 'hello'}))
        # Only the top-level entry, no char-level iteration
        assert result == [(['s'], 'hello')]

    def test_none_not_recursed(self):
        result = list(obj_walk_through({'n': None}))
        assert result == [(['n'], None)]


class TestShouldRecurse:
    """Tests for the should_recurse callback."""

    def test_false_stops_recursion(self):
        """should_recurse returning False yields node but skips its subtree."""
        result = list(obj_walk_through(
            {'a': {'b': 1}},
            should_recurse=lambda _path, _child: False,
        ))
        assert result == [(['a'], {'b': 1})]

    def test_selective_pruning(self):
        """should_recurse can selectively prune specific branches."""
        data = {'keep': {'x': 1}, 'skip': {'y': 2}}
        result = list(obj_walk_through(
            data,
            should_recurse=lambda path, _child: path != ['skip'],
        ))
        paths = [p for p, _ in result]
        assert ['keep'] in paths
        assert ['keep', 'x'] in paths
        assert ['skip'] in paths      # yielded
        assert ['skip', 'y'] not in paths  # not explored

    def test_none_means_recurse_all(self):
        """should_recurse=None (default) recurses into everything."""
        result = list(obj_walk_through({'a': {'b': 1}}))
        assert (['a', 'b'], 1) in result

    def test_type_walk_pruning(self):
        """should_recurse works with type walks too."""
        @attrs(slots=True)
        class Inner:
            data: str = attrib(default='')

        @attrs(slots=True)
        class Outer:
            inner: Inner = attrib(factory=Inner)
            name: str = attrib(default='')

        result = list(obj_walk_through(
            Outer,
            should_recurse=lambda path, _child: path != ['inner'],
        ))
        paths = [p for p, _ in result]
        assert ['inner'] in paths
        assert ['inner', 'data'] not in paths
        assert ['name'] in paths
