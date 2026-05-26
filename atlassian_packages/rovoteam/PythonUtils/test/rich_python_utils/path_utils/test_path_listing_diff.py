"""Tests for multi-root file diffing and conflict detection in path_listing.py."""

import os

import pytest

from python_utils.path_utils.path_listing import (
    FileCandidate,
    MultiRootDiff,
    canonicalize_text,
    hash_file_canonical,
    find_conflicting_and_agreed_files,
    safe_copy_agreed,
    safe_copy_per_file,
    group_conflicts_by_parent,
)


# ---------------------------------------------------------------------------
# canonicalize_text
# ---------------------------------------------------------------------------

class TestCanonicalizeText:
    def test_strips_trailing_whitespace(self):
        assert canonicalize_text(b"hello   \nworld  \n") == b"hello\nworld\n"

    def test_normalizes_crlf(self):
        assert canonicalize_text(b"hello\r\nworld\r\n") == b"hello\nworld\n"

    def test_normalizes_cr(self):
        assert canonicalize_text(b"hello\rworld\r") == b"hello\nworld\n"

    def test_ensures_trailing_newline(self):
        assert canonicalize_text(b"hello\nworld") == b"hello\nworld\n"

    def test_binary_passthrough(self):
        binary = bytes(range(256))
        assert canonicalize_text(binary) == binary

    def test_empty_content(self):
        assert canonicalize_text(b"") == b"\n"

    def test_unicode_nfc_normalization(self):
        # e + combining accent vs precomposed
        decomposed = "e\u0301".encode("utf-8")
        composed = "\u00e9".encode("utf-8")
        assert canonicalize_text(decomposed) == canonicalize_text(composed)


# ---------------------------------------------------------------------------
# hash_file_canonical
# ---------------------------------------------------------------------------

class TestHashFileCanonical:
    def test_identical_files_same_hash(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello\n")
        (tmp_path / "b.txt").write_text("hello\n")
        assert hash_file_canonical(str(tmp_path / "a.txt")) == hash_file_canonical(str(tmp_path / "b.txt"))

    def test_trailing_whitespace_same_hash(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello\n")
        (tmp_path / "b.txt").write_text("hello   \n")
        assert hash_file_canonical(str(tmp_path / "a.txt")) == hash_file_canonical(str(tmp_path / "b.txt"))

    def test_crlf_vs_lf_same_hash(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"hello\n")
        (tmp_path / "b.txt").write_bytes(b"hello\r\n")
        assert hash_file_canonical(str(tmp_path / "a.txt")) == hash_file_canonical(str(tmp_path / "b.txt"))

    def test_different_content_different_hash(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello\n")
        (tmp_path / "b.txt").write_text("world\n")
        assert hash_file_canonical(str(tmp_path / "a.txt")) != hash_file_canonical(str(tmp_path / "b.txt"))

    def test_large_file_threshold(self, tmp_path):
        f = tmp_path / "large.txt"
        f.write_bytes(b"x" * 100)
        # With threshold=50, file is "large" → raw hash (no normalization)
        h1 = hash_file_canonical(str(f), large_file_threshold=50)
        # With default threshold, file is "small" → canonical hash
        h2 = hash_file_canonical(str(f))
        # Both should produce valid hashes (64 hex chars)
        assert len(h1) == 64
        assert len(h2) == 64


# ---------------------------------------------------------------------------
# find_conflicting_and_agreed_files
# ---------------------------------------------------------------------------

@pytest.fixture
def three_roots(tmp_path):
    """Three roots with overlapping files."""
    r0 = tmp_path / "root_0"
    r1 = tmp_path / "root_1"
    r2 = tmp_path / "root_2"

    # Agreed file: same content in all 3
    for r in [r0, r1, r2]:
        d = r / "shared"
        d.mkdir(parents=True)
        (d / "common.txt").write_text("same content\n")

    # Conflicting file: different content
    (r0 / "shared" / "conflict.txt").write_text("version A short\n")
    (r1 / "shared" / "conflict.txt").write_text("version B much longer with more detail and content\n")
    (r2 / "shared" / "conflict.txt").write_text("version C medium length\n")

    # Unique file: only in root_1
    (r1 / "unique.txt").write_text("only here\n")

    return [str(r0), str(r1), str(r2)], ["root_0", "root_1", "root_2"]


class TestFindConflictingAndAgreedFiles:
    def test_agreed_files(self, three_roots):
        roots, names = three_roots
        agreed, conflicts = find_conflicting_and_agreed_files(roots, names)
        agreed_paths = {a["path"] for a in agreed}
        assert "shared/common.txt" in agreed_paths

    def test_conflicting_files(self, three_roots):
        roots, names = three_roots
        agreed, conflicts = find_conflicting_and_agreed_files(roots, names)
        assert "shared/conflict.txt" in conflicts
        assert len(conflicts["shared/conflict.txt"]) == 3

    def test_unique_file_is_agreed(self, three_roots):
        roots, names = three_roots
        agreed, _ = find_conflicting_and_agreed_files(roots, names)
        agreed_paths = {a["path"] for a in agreed}
        assert "unique.txt" in agreed_paths

    def test_agreed_has_abs_path(self, three_roots):
        roots, names = three_roots
        agreed, _ = find_conflicting_and_agreed_files(roots, names)
        for a in agreed:
            assert "abs_path" in a
            assert os.path.isabs(a["abs_path"])

    def test_empty_roots(self, tmp_path):
        r = tmp_path / "empty"
        r.mkdir()
        agreed, conflicts = find_conflicting_and_agreed_files([str(r)], ["empty"])
        assert agreed == []
        assert conflicts == {}

    def test_default_root_names(self, tmp_path):
        r = tmp_path / "myroot"
        r.mkdir()
        (r / "file.txt").write_text("content\n")
        agreed, _ = find_conflicting_and_agreed_files([str(r)])
        assert agreed[0]["source_roots"] == ["myroot"]


# ---------------------------------------------------------------------------
# safe_copy_agreed + safe_copy_per_file
# ---------------------------------------------------------------------------

class TestSafeCopyAgreed:
    def test_copies_files(self, three_roots, tmp_path):
        roots, names = three_roots
        agreed, _ = find_conflicting_and_agreed_files(roots, names)
        dst = str(tmp_path / "dest")
        os.makedirs(dst)
        copied = safe_copy_agreed(agreed, dst)
        assert len(copied) > 0
        assert os.path.exists(os.path.join(dst, "shared", "common.txt"))

    def test_skip_existing(self, three_roots, tmp_path):
        roots, names = three_roots
        agreed, _ = find_conflicting_and_agreed_files(roots, names)
        dst = str(tmp_path / "dest")
        os.makedirs(os.path.join(dst, "shared"), exist_ok=True)
        # Pre-write a file
        with open(os.path.join(dst, "shared", "common.txt"), "w") as f:
            f.write("pre-existing\n")
        copied = safe_copy_agreed(agreed, dst, skip_existing=True)
        assert "shared/common.txt" not in copied
        # Pre-existing content preserved
        with open(os.path.join(dst, "shared", "common.txt")) as f:
            assert f.read() == "pre-existing\n"


class TestSafeCopyPerFile:
    def test_copies_agreed_and_fallback_conflicts(self, three_roots, tmp_path):
        roots, names = three_roots
        diff = find_conflicting_and_agreed_files(roots, names)
        dst = str(tmp_path / "dest")
        os.makedirs(dst)
        copied = safe_copy_per_file(diff, dst, conflict_fallback="largest")
        assert "shared/common.txt" in copied
        assert "shared/conflict.txt" in copied
        # Conflict fallback picks largest
        with open(os.path.join(dst, "shared", "conflict.txt")) as f:
            content = f.read()
        assert "much longer" in content  # root_1 is the largest

    def test_skip_existing_protects_pre_written(self, three_roots, tmp_path):
        roots, names = three_roots
        diff = find_conflicting_and_agreed_files(roots, names)
        dst = str(tmp_path / "dest")
        os.makedirs(os.path.join(dst, "shared"), exist_ok=True)
        # Simulate aggregator having written a merged version
        with open(os.path.join(dst, "shared", "conflict.txt"), "w") as f:
            f.write("aggregator merged version\n")
        copied = safe_copy_per_file(diff, dst, skip_existing=True, conflict_fallback="largest")
        assert "shared/conflict.txt" not in copied
        with open(os.path.join(dst, "shared", "conflict.txt")) as f:
            assert f.read() == "aggregator merged version\n"

    def test_skip_fallback(self, three_roots, tmp_path):
        roots, names = three_roots
        diff = find_conflicting_and_agreed_files(roots, names)
        dst = str(tmp_path / "dest")
        os.makedirs(dst)
        copied = safe_copy_per_file(diff, dst, conflict_fallback="skip")
        assert "shared/conflict.txt" not in copied


# ---------------------------------------------------------------------------
# group_conflicts_by_parent
# ---------------------------------------------------------------------------

class TestGroupConflictsByParent:
    def test_depth_1(self):
        conflicts = {
            "skills/alpha/SKILL.md": [{"root_name": "w0"}],
            "skills/beta/SKILL.md": [{"root_name": "w0"}],
            "tools/gamma/tool.json": [{"root_name": "w0"}],
        }
        groups = group_conflicts_by_parent(conflicts, depth=1)
        assert "skills" in groups
        assert "tools" in groups
        assert len(groups["skills"]) == 2
        assert len(groups["tools"]) == 1

    def test_depth_2(self):
        conflicts = {
            "skills/alpha/SKILL.md": [{"root_name": "w0"}],
            "skills/alpha/refs/ref.md": [{"root_name": "w0"}],
            "skills/beta/SKILL.md": [{"root_name": "w0"}],
        }
        groups = group_conflicts_by_parent(conflicts, depth=2)
        assert "skills/alpha" in groups
        assert "skills/beta" in groups
        assert len(groups["skills/alpha"]) == 2

    def test_single_segment_path(self):
        conflicts = {"file.txt": [{"root_name": "w0"}]}
        groups = group_conflicts_by_parent(conflicts, depth=1)
        assert "." in groups
