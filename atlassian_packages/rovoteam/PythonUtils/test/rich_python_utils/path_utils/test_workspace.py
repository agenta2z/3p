"""Property-based tests for MergedSpace.

Uses Hypothesis with ``tempfile`` to create real directory structures
and verify correctness properties from the design document.
"""

import shutil
import tempfile
from pathlib import Path
from typing import List

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.path_utils.workspace import MergedSpace


# ---------------------------------------------------------------------------
# Common settings for all property tests
# ---------------------------------------------------------------------------

_PBT_SETTINGS = settings(max_examples=50)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Safe relative path segments — letters only, min 2 chars
_SAFE_SEGMENTS = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_size=2,
    max_size=8,
)

# A relative path with 1-3 segments (e.g. "foo", "foo/bar", "foo/bar/baz")
_REL_PATHS = st.lists(_SAFE_SEGMENTS, min_size=1, max_size=3).map(
    lambda parts: str(Path(*parts))
)

# Number of distinct roots to create (1-4)
_NUM_ROOTS = st.integers(min_value=1, max_value=4)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workspace():
    """Create a fresh temporary directory for one Hypothesis example."""
    return Path(tempfile.mkdtemp())


def _cleanup(base: Path):
    """Remove the temporary directory tree."""
    shutil.rmtree(base, ignore_errors=True)


def _make_roots(base: Path, n: int) -> List[Path]:
    """Create *n* distinct root directories under *base*."""
    roots = []
    for i in range(n):
        r = base / f"root_{i}"
        r.mkdir(parents=True, exist_ok=True)
        roots.append(r)
    return roots


def _touch(root: Path, rel: str) -> Path:
    """Create an empty file at *root / rel*, ensuring parent dirs exist."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


# ---------------------------------------------------------------------------
# Property 1: Construction preserves root order after normalization and dedup
# ---------------------------------------------------------------------------


class TestProperty1ConstructionOrder:
    """**Validates: Requirements 1.1, 1.4, 1.5**"""

    @given(num_roots=_NUM_ROOTS, extra_dupes=st.integers(min_value=0, max_value=3))
    @_PBT_SETTINGS
    def test_root_order_preserved_after_dedup(self, num_roots, extra_dupes):
        """Construction preserves root order after normalization and deduplication."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)

            # Optionally add duplicates at random positions
            input_roots = list(roots)
            for i in range(extra_dupes):
                input_roots.append(roots[i % num_roots])

            ms = MergedSpace(input_roots)

            # Expected: resolve + dedup preserving first occurrence
            seen: List[Path] = []
            for r in input_roots:
                norm = Path(r).resolve()
                if norm not in seen:
                    seen.append(norm)

            assert ms.roots == seen
            assert ms.write_root == seen[0]
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 2: All stored roots are absolute paths
# ---------------------------------------------------------------------------


class TestProperty2AllRootsAbsolute:
    """**Validates: Requirements 1.4**"""

    @given(num_roots=_NUM_ROOTS)
    @_PBT_SETTINGS
    def test_all_roots_absolute(self, num_roots):
        """All stored roots are absolute paths."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            ms = MergedSpace(roots)

            for root in ms.roots:
                assert root.is_absolute(), f"Root {root} is not absolute"
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 3: Deduplication idempotence
# ---------------------------------------------------------------------------


class TestProperty3DeduplicationIdempotence:
    """**Validates: Requirements 1.5**"""

    @given(num_roots=_NUM_ROOTS, extra_dupes=st.integers(min_value=0, max_value=3))
    @_PBT_SETTINGS
    def test_dedup_idempotence(self, num_roots, extra_dupes):
        """MergedSpace(ms.roots).roots == ms.roots."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            input_roots = list(roots)
            for i in range(extra_dupes):
                input_roots.append(roots[i % num_roots])

            ms = MergedSpace(input_roots)
            ms2 = MergedSpace(ms.roots)
            assert ms2.roots == ms.roots
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 4: find result is absolute, exists, and equals root/rel
# ---------------------------------------------------------------------------


class TestProperty4FindResult:
    """**Validates: Requirements 2.1**"""

    @given(num_roots=_NUM_ROOTS, rel=_REL_PATHS, place_in=st.integers(min_value=0, max_value=100))
    @_PBT_SETTINGS
    def test_find_result_valid(self, num_roots, rel, place_in):
        """find result is absolute, exists, and equals root/rel for some root."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            target_idx = place_in % num_roots
            _touch(roots[target_idx], rel)

            ms = MergedSpace(roots)
            result = ms.find(rel)

            assert result is not None, f"Expected to find {rel}"
            assert result.is_absolute()
            assert result.exists()
            assert any(result == root / rel for root in ms._roots)
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 5: exists(rel) == (find(rel) is not None)
# ---------------------------------------------------------------------------


class TestProperty5ExistsDelegatesToFind:
    """**Validates: Requirements 2.4**"""

    @given(num_roots=_NUM_ROOTS, rel=_REL_PATHS, create_file=st.booleans())
    @_PBT_SETTINGS
    def test_exists_equals_find(self, num_roots, rel, create_file):
        """exists(rel) == (find(rel) is not None)."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            if create_file:
                _touch(roots[0], rel)

            ms = MergedSpace(roots)
            assert ms.exists(rel) == (ms.find(rel) is not None)
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 6: find_all[0] == find when find is not None
# ---------------------------------------------------------------------------


class TestProperty6FindAllSupersetOfFind:
    """**Validates: Requirements 2.1, 2.3**"""

    @given(
        num_roots=st.integers(min_value=2, max_value=4),
        rel=_REL_PATHS,
        place_count=st.integers(min_value=1, max_value=4),
    )
    @_PBT_SETTINGS
    def test_find_all_first_equals_find(self, num_roots, rel, place_count):
        """find_all[0] == find when find is not None."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            for i in range(min(place_count, num_roots)):
                _touch(roots[i], rel)

            ms = MergedSpace(roots)
            single = ms.find(rel)
            all_results = ms.find_all(rel)

            if single is not None:
                assert len(all_results) >= 1
                assert all_results[0] == single
            else:
                assert len(all_results) == 0
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 7: glob dedup produces unique relative paths;
#              allow_duplicates=True count >= default count
# ---------------------------------------------------------------------------


class TestProperty7GlobDedup:
    """**Validates: Requirements 4.1, 4.2, 4.3**"""

    @given(
        num_roots=st.integers(min_value=2, max_value=3),
        file_names=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @_PBT_SETTINGS
    def test_glob_dedup_unique_rels(self, num_roots, file_names):
        """Glob dedup produces unique relative paths; allow_duplicates count >= default."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)

            for fname in file_names:
                for root in roots:
                    _touch(root, f"{fname}.txt")

            ms = MergedSpace(roots)
            deduped = ms.glob("*.txt")
            all_results = ms.glob("*.txt", allow_duplicates=True)

            rel_paths = [rel for _, rel in deduped]
            assert len(rel_paths) == len(set(rel_paths))
            assert len(all_results) >= len(deduped)
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 8: write_path result == write_root / rel and is absolute
# ---------------------------------------------------------------------------


class TestProperty8WritePath:
    """**Validates: Requirements 5.1, 5.2**"""

    @given(num_roots=_NUM_ROOTS, rel=_REL_PATHS)
    @_PBT_SETTINGS
    def test_write_path_under_write_root(self, num_roots, rel):
        """write_path result == write_root / rel and is absolute."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            ms = MergedSpace(roots)

            wp = ms.write_path(rel)
            assert wp == ms.write_root / rel
            assert wp.is_absolute()
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 9: with_added_root twice produces same roots
# ---------------------------------------------------------------------------


class TestProperty9WithAddedRootIdempotence:
    """**Validates: Requirements 6.3**"""

    @given(num_roots=_NUM_ROOTS)
    @_PBT_SETTINGS
    def test_added_root_idempotent(self, num_roots):
        """Adding same root twice produces same roots."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            new_root = base / "extra_root"
            new_root.mkdir(parents=True, exist_ok=True)

            ms = MergedSpace(roots)
            ms2 = ms.with_added_root(new_root)
            ms3 = ms2.with_added_root(new_root)
            assert ms2.roots == ms3.roots
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 9b: with_added_root does not mutate original
# ---------------------------------------------------------------------------


class TestProperty9bWithAddedRootNoMutation:
    """**Validates: Requirements 6.5**"""

    @given(num_roots=_NUM_ROOTS)
    @_PBT_SETTINGS
    def test_added_root_no_mutation(self, num_roots):
        """with_added_root does not mutate original."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            new_root = base / "extra_root"
            new_root.mkdir(parents=True, exist_ok=True)

            ms = MergedSpace(roots)
            original_roots = ms.roots
            _ = ms.with_added_root(new_root)
            assert ms.roots == original_roots
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 10: subspace roots == [r / subdir for r in parent.roots]
# ---------------------------------------------------------------------------


class TestProperty10SubspaceRoots:
    """**Validates: Requirements 7.1, 7.2**"""

    @given(num_roots=_NUM_ROOTS, subdir=_SAFE_SEGMENTS)
    @_PBT_SETTINGS
    def test_subspace_joins_roots(self, num_roots, subdir):
        """subspace roots == [r / subdir for r in parent.roots]."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            ms = MergedSpace(roots)

            child = ms.subspace(subdir)
            expected = [r / subdir for r in ms._roots]
            assert child.roots == expected
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 11: relative_to round-trip
# ---------------------------------------------------------------------------


class TestProperty11RelativeToRoundTrip:
    """**Validates: Requirements 8.1**"""

    @given(num_roots=_NUM_ROOTS, rel=_REL_PATHS, place_in=st.integers(min_value=0, max_value=100))
    @_PBT_SETTINGS
    def test_relative_to_round_trip(self, num_roots, rel, place_in):
        """relative_to round-trip — some root / relative_to(abs) == abs."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            target_idx = place_in % num_roots
            abs_path = _touch(roots[target_idx], rel)

            ms = MergedSpace(roots)
            found = ms.find(rel)
            assume(found is not None)

            rel_result = ms.relative_to(found)
            assert any((r / rel_result) == found for r in ms._roots)
        finally:
            _cleanup(base)


# ---------------------------------------------------------------------------
# Property 12: Mutating returned roots list does not affect MergedSpace
# ---------------------------------------------------------------------------


class TestProperty12DefensiveCopy:
    """**Validates: Requirements 6.4**"""

    @given(num_roots=_NUM_ROOTS)
    @_PBT_SETTINGS
    def test_roots_defensive_copy(self, num_roots):
        """Mutating returned roots list does not affect MergedSpace."""
        base = _make_workspace()
        try:
            roots = _make_roots(base, num_roots)
            ms = MergedSpace(roots)

            original = ms.roots
            copy = ms.roots
            copy.append(Path("/mutated"))
            assert ms.roots == original
        finally:
            _cleanup(base)


# ===========================================================================
# Example-based edge-case and security tests (Tasks 3.1 – 3.5)
# ===========================================================================


# ---------------------------------------------------------------------------
# Task 3.1: Construction edge cases
# ---------------------------------------------------------------------------


class TestConstructionEdgeCases:
    """Edge-case tests for MergedSpace construction."""

    def test_empty_roots_raises_value_error(self):
        """Empty roots sequence raises ValueError."""
        with pytest.raises(ValueError, match="at least one root"):
            MergedSpace([])

    def test_single_string_accepted(self, tmp_path):
        """A single string (not wrapped in a list) is accepted as the sole root."""
        ms = MergedSpace(str(tmp_path))
        assert ms.roots == [tmp_path.resolve()]

    def test_single_path_accepted(self, tmp_path):
        """A single Path object (not wrapped in a list) is accepted as the sole root."""
        ms = MergedSpace(tmp_path)
        assert ms.roots == [tmp_path.resolve()]

    def test_write_root_index_out_of_bounds_raises_index_error(self, tmp_path):
        """write_root_index out of bounds raises IndexError."""
        with pytest.raises(IndexError, match="out of range"):
            MergedSpace([tmp_path], write_root_index=5)

    def test_write_root_index_negative_raises_index_error(self, tmp_path):
        """Negative write_root_index raises IndexError."""
        with pytest.raises(IndexError, match="out of range"):
            MergedSpace([tmp_path], write_root_index=-1)

    def test_duplicate_roots_collapsed(self, tmp_path):
        """Duplicate roots (after normalization) are collapsed, preserving first occurrence."""
        r = tmp_path / "root"
        r.mkdir()
        ms = MergedSpace([r, r, r])
        assert ms.roots == [r.resolve()]

    def test_duplicate_roots_via_different_representations(self, tmp_path):
        """Duplicates expressed as str vs Path are collapsed."""
        r = tmp_path / "root"
        r.mkdir()
        ms = MergedSpace([str(r), r, str(r)])
        assert ms.roots == [r.resolve()]


# ---------------------------------------------------------------------------
# Task 3.2: Security tests
# ---------------------------------------------------------------------------


class TestPathSecurity:
    """Security tests for path validation."""

    def test_find_absolute_path_raises_value_error(self, tmp_path):
        """find() with an absolute path raises ValueError."""
        ms = MergedSpace([tmp_path])
        abs_path = str(tmp_path / "some_file.txt")  # guaranteed absolute on any OS
        with pytest.raises(ValueError, match="absolute"):
            ms.find(abs_path)

    def test_write_path_absolute_raises_value_error(self, tmp_path):
        """write_path() with an absolute path raises ValueError."""
        ms = MergedSpace([tmp_path])
        abs_path = str(tmp_path / "some_file.txt")
        with pytest.raises(ValueError, match="absolute"):
            ms.write_path(abs_path)

    def test_glob_absolute_subdir_raises_value_error(self, tmp_path):
        """glob() with an absolute relative_subdir raises ValueError."""
        ms = MergedSpace([tmp_path])
        abs_path = str(tmp_path / "subdir")
        with pytest.raises(ValueError, match="absolute"):
            ms.glob("*.txt", relative_subdir=abs_path)

    def test_find_dotdot_traversal_raises_value_error(self, tmp_path):
        """find() with '..' traversal raises ValueError."""
        ms = MergedSpace([tmp_path])
        with pytest.raises(ValueError, match="traversal"):
            ms.find("../../etc/passwd")

    def test_write_path_dotdot_traversal_raises_value_error(self, tmp_path):
        """write_path() with '..' traversal raises ValueError."""
        ms = MergedSpace([tmp_path])
        with pytest.raises(ValueError, match="traversal"):
            ms.write_path("../escape")

    def test_exists_dotdot_traversal_raises_value_error(self, tmp_path):
        """exists() with '..' traversal raises ValueError."""
        ms = MergedSpace([tmp_path])
        with pytest.raises(ValueError, match="traversal"):
            ms.exists("foo/../../escape")

    def test_find_all_absolute_raises_value_error(self, tmp_path):
        """find_all() with an absolute path raises ValueError."""
        ms = MergedSpace([tmp_path])
        abs_path = str(tmp_path / "some_file.txt")
        with pytest.raises(ValueError, match="absolute"):
            ms.find_all(abs_path)

    def test_missing_root_skipped_on_read(self, tmp_path):
        """A non-existent root is silently skipped during find()."""
        existing = tmp_path / "exists"
        existing.mkdir()
        (existing / "file.txt").touch()

        missing = tmp_path / "does_not_exist"
        ms = MergedSpace([missing, existing])

        result = ms.find("file.txt")
        assert result is not None
        assert result == existing.resolve() / "file.txt"

    def test_missing_write_root_raises_on_ensure_write_dir(self, tmp_path):
        """ensure_write_dir() raises FileNotFoundError when write root doesn't exist."""
        missing = tmp_path / "nonexistent_write_root"
        ms = MergedSpace([missing])
        with pytest.raises(FileNotFoundError):
            ms.ensure_write_dir("subdir")


# ---------------------------------------------------------------------------
# Task 3.3: find behavior tests
# ---------------------------------------------------------------------------


class TestFindBehavior:
    """Tests for find() priority and fallthrough behavior."""

    def test_first_match_wins(self, tmp_path):
        """find() returns the match from the highest-priority root."""
        high = tmp_path / "high"
        low = tmp_path / "low"
        high.mkdir()
        low.mkdir()
        (high / "shared.txt").write_text("high")
        (low / "shared.txt").write_text("low")

        ms = MergedSpace([high, low])
        result = ms.find("shared.txt")
        assert result == high.resolve() / "shared.txt"

    def test_falls_through_to_lower_priority(self, tmp_path):
        """find() falls through to a lower-priority root when the file is absent in higher ones."""
        high = tmp_path / "high"
        low = tmp_path / "low"
        high.mkdir()
        low.mkdir()
        # Only in low
        (low / "only_low.txt").touch()

        ms = MergedSpace([high, low])
        result = ms.find("only_low.txt")
        assert result == low.resolve() / "only_low.txt"

    def test_returns_none_when_nothing_matches(self, tmp_path):
        """find() returns None when the file exists in no root."""
        r = tmp_path / "root"
        r.mkdir()
        ms = MergedSpace([r])
        assert ms.find("nonexistent.txt") is None


# ---------------------------------------------------------------------------
# Task 3.4: glob behavior tests
# ---------------------------------------------------------------------------


class TestGlobBehavior:
    """Tests for glob() dedup, allow_duplicates, relative_subdir, and empty results."""

    def test_dedup_shadows_lower_priority(self, tmp_path):
        """Default glob dedup keeps the highest-priority match for each relative path."""
        high = tmp_path / "high"
        low = tmp_path / "low"
        high.mkdir()
        low.mkdir()
        (high / "a.txt").write_text("high-a")
        (low / "a.txt").write_text("low-a")
        (low / "b.txt").write_text("low-b")

        ms = MergedSpace([high, low])
        results = ms.glob("*.txt")

        rel_names = {str(rel) for _, rel in results}
        assert "a.txt" in rel_names
        assert "b.txt" in rel_names

        # a.txt should come from high
        a_abs = next(abs_p for abs_p, rel in results if str(rel) == "a.txt")
        assert a_abs == high.resolve() / "a.txt"

    def test_allow_duplicates_yields_all(self, tmp_path):
        """allow_duplicates=True returns matches from all roots."""
        high = tmp_path / "high"
        low = tmp_path / "low"
        high.mkdir()
        low.mkdir()
        (high / "a.txt").touch()
        (low / "a.txt").touch()

        ms = MergedSpace([high, low])
        deduped = ms.glob("*.txt")
        all_results = ms.glob("*.txt", allow_duplicates=True)

        assert len(deduped) == 1  # only one "a.txt"
        assert len(all_results) == 2  # both copies

    def test_scoped_to_relative_subdir(self, tmp_path):
        """glob with relative_subdir scopes the search correctly."""
        root = tmp_path / "root"
        sub = root / "sub"
        sub.mkdir(parents=True)
        (sub / "in_sub.txt").touch()
        (root / "at_root.txt").touch()

        ms = MergedSpace([root])
        results = ms.glob("*.txt", relative_subdir="sub")

        rel_names = [str(rel) for _, rel in results]
        assert "in_sub.txt" in rel_names
        assert "at_root.txt" not in rel_names

    def test_empty_pattern_returns_empty_list(self, tmp_path):
        """A pattern that matches nothing returns an empty list."""
        root = tmp_path / "root"
        root.mkdir()
        (root / "file.txt").touch()

        ms = MergedSpace([root])
        results = ms.glob("*.xyz")
        assert results == []


# ---------------------------------------------------------------------------
# Task 3.5: with_added_root, subspace, relative_to tests
# ---------------------------------------------------------------------------


class TestWithAddedRoot:
    """Tests for with_added_root priority and immutability."""

    def test_lowest_appends(self, tmp_path):
        """priority='lowest' (default) appends the new root at the end."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        r1.mkdir()
        r2.mkdir()

        ms = MergedSpace([r1])
        ms2 = ms.with_added_root(r2, priority="lowest")
        assert ms2.roots == [r1.resolve(), r2.resolve()]

    def test_highest_prepends(self, tmp_path):
        """priority='highest' prepends the new root at the beginning."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        r1.mkdir()
        r2.mkdir()

        ms = MergedSpace([r1])
        ms2 = ms.with_added_root(r2, priority="highest")
        assert ms2.roots == [r2.resolve(), r1.resolve()]

    def test_original_unchanged(self, tmp_path):
        """with_added_root does not mutate the original MergedSpace."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        r1.mkdir()
        r2.mkdir()

        ms = MergedSpace([r1])
        original_roots = ms.roots
        _ = ms.with_added_root(r2)
        assert ms.roots == original_roots


class TestSubspace:
    """Tests for subspace behavior."""

    def test_nonexistent_subdirectory_returns_valid_merged_space(self, tmp_path):
        """subspace with a non-existent subdirectory returns a valid MergedSpace."""
        r = tmp_path / "root"
        r.mkdir()

        ms = MergedSpace([r])
        child = ms.subspace("does_not_exist")

        # Should be a valid MergedSpace with roots pointing to non-existent dirs
        assert len(child.roots) == 1
        assert child.roots[0] == r.resolve() / "does_not_exist"
        # find should return None (dir doesn't exist), not raise
        assert child.find("anything.txt") is None


class TestRelativeTo:
    """Tests for relative_to behavior."""

    def test_unrecognized_path_raises_value_error(self, tmp_path):
        """relative_to with a path not under any root raises ValueError."""
        r = tmp_path / "root"
        r.mkdir()
        ms = MergedSpace([r])

        # Use a path guaranteed to be absolute and outside the root on any OS
        unrelated = tmp_path / "completely_unrelated_dir"
        unrelated.mkdir()
        with pytest.raises(ValueError, match="not under any root"):
            ms.relative_to(str(unrelated / "file.txt"))

    def test_path_under_multiple_roots_uses_highest_priority(self, tmp_path):
        """relative_to uses the highest-priority root when the path is under multiple roots."""
        # Create nested roots: outer contains inner
        outer = tmp_path / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True)
        (inner / "file.txt").touch()

        # outer is higher priority than inner
        ms = MergedSpace([outer, inner])

        abs_path = inner.resolve() / "file.txt"
        rel = ms.relative_to(abs_path)

        # Should be relative to outer (highest priority), not inner
        expected = Path("inner") / "file.txt"
        assert rel == expected
