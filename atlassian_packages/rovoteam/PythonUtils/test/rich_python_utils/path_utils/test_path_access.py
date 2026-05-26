"""Tests for PathAccess and AllowedPath."""

import pytest

from python_utils.path_utils import AllowedPath, PathAccess
from python_utils.path_utils.path_access import (
    AllowedPath as _AllowedPathDirect,
    PathAccess as _PathAccessDirect,
)


class TestPathAccessBitValues:
    """Pin the bit values so changes can't silently break consumers."""

    def test_bit_values(self):
        assert int(PathAccess.READ) == 1
        assert int(PathAccess.WRITE) == 2
        assert int(PathAccess.EXEC) == 4

    def test_all_is_union(self):
        assert PathAccess.ALL == (PathAccess.READ | PathAccess.WRITE | PathAccess.EXEC)
        assert int(PathAccess.ALL) == 7


class TestPathAccessComposition:
    """IntFlag bitmask semantics."""

    def test_or_composition(self):
        p = PathAccess.READ | PathAccess.WRITE
        assert int(p) == 3
        assert PathAccess.READ in p
        assert PathAccess.WRITE in p
        assert PathAccess.EXEC not in p

    def test_and_decomposition(self):
        p = PathAccess.READ | PathAccess.EXEC
        assert (p & PathAccess.READ) == PathAccess.READ
        assert (p & PathAccess.WRITE) == PathAccess(0)
        assert (p & PathAccess.EXEC) == PathAccess.EXEC

    def test_xor_toggles(self):
        p = PathAccess.READ | PathAccess.WRITE
        toggled = p ^ PathAccess.WRITE
        assert toggled == PathAccess.READ
        assert PathAccess.WRITE not in toggled

    def test_invert_excludes(self):
        # ~ within ALL = the complement, restricted to the flag set
        not_write = PathAccess.ALL & ~PathAccess.WRITE
        assert PathAccess.READ in not_write
        assert PathAccess.EXEC in not_write
        assert PathAccess.WRITE not in not_write

    def test_membership_with_all(self):
        assert PathAccess.READ in PathAccess.ALL
        assert PathAccess.WRITE in PathAccess.ALL
        assert PathAccess.EXEC in PathAccess.ALL

    def test_empty_flag_membership(self):
        empty = PathAccess(0)
        assert PathAccess.READ not in empty
        assert PathAccess.WRITE not in empty
        assert PathAccess.EXEC not in empty


class TestPathAccessFromInt:
    """Constructing from raw ints (e.g., deserialization)."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (0, PathAccess(0)),
            (1, PathAccess.READ),
            (2, PathAccess.WRITE),
            (3, PathAccess.READ | PathAccess.WRITE),
            (4, PathAccess.EXEC),
            (5, PathAccess.READ | PathAccess.EXEC),
            (6, PathAccess.WRITE | PathAccess.EXEC),
            (7, PathAccess.ALL),
        ],
    )
    def test_from_int_roundtrip(self, raw, expected):
        flag = PathAccess(raw)
        assert flag == expected
        assert int(flag) == raw


class TestAllowedPathDefaults:
    def test_default_access_is_all(self):
        ap = AllowedPath("/tmp/foo")
        assert ap.access == PathAccess.ALL

    def test_explicit_access(self):
        ap = AllowedPath("/etc/hosts", access=PathAccess.READ)
        assert ap.path == "/etc/hosts"
        assert ap.access == PathAccess.READ
        assert PathAccess.WRITE not in ap.access


class TestAllowedPathFrozen:
    """The dataclass is frozen — must be hashable and immutable."""

    def test_frozen_assignment_raises(self):
        ap = AllowedPath("/tmp/x")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            ap.path = "/tmp/y"  # type: ignore[misc]

    def test_hashable_and_dedupes_in_set(self):
        # Same path + same access must dedupe in a set.
        s = {
            AllowedPath("/a"),
            AllowedPath("/a"),
            AllowedPath("/a", access=PathAccess.READ),
        }
        # ("/a", ALL) and ("/a", READ) are distinct; the two ALL duplicates collapse.
        assert len(s) == 2

    def test_equality_value_based(self):
        assert AllowedPath("/a") == AllowedPath("/a")
        assert AllowedPath("/a", PathAccess.READ) != AllowedPath("/a", PathAccess.WRITE)
        assert AllowedPath("/a") != AllowedPath("/b")

    def test_usable_as_dict_key(self):
        d = {AllowedPath("/a"): "first", AllowedPath("/a"): "second"}
        # Same key — second write replaces first.
        assert len(d) == 1
        assert d[AllowedPath("/a")] == "second"


class TestPackageExposure:
    """The classes are reachable via the path_utils package as well as direct import."""

    def test_same_object_via_both_import_paths(self):
        assert PathAccess is _PathAccessDirect
        assert AllowedPath is _AllowedPathDirect

    def test_in_package_all(self):
        from python_utils import path_utils

        assert "PathAccess" in path_utils.__all__
        assert "AllowedPath" in path_utils.__all__
