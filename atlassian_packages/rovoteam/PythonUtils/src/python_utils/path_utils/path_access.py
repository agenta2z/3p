"""PathAccess + AllowedPath — minimal types for declaring "what a process is
allowed to do with a path."

These are *policy intent* types — they describe what a piece of code (an
inferencer, a sandboxed subprocess, a plugin) *should be permitted* to do with
a path. They are deliberately distinct from POSIX file mode bits
(``stat.S_IRUSR`` etc.) which describe **inode state**, and from
``os.R_OK``/``W_OK``/``X_OK`` which are constants for the ``access(2)``
syscall query. Use those when you want to ask the kernel; use ``PathAccess``
when you want to model "this code is allowed to read/write/execute these
paths."

Python's stdlib has no built-in type for this domain — POSIX mode bits and
``os.access`` constants are at the wrong semantic layer, ``mmap.PROT_*`` is
about memory pages, and the old ``rexec``/``Bastion`` sandbox modules were
removed in Python 3.0. ``enum.IntFlag`` is the right primitive to build on
(same primitive ``re.RegexFlag``, ``socket.AddressFamily`` etc. use).

Examples:
    >>> from python_utils.path_utils.path_access import (
    ...     PathAccess, AllowedPath,
    ... )

    >>> # Bitmask composition / decomposition
    >>> p = PathAccess.READ | PathAccess.WRITE
    >>> PathAccess.READ in p
    True
    >>> PathAccess.EXEC in p
    False
    >>> int(p)
    3

    >>> # Default is ALL (read + write + exec)
    >>> ap = AllowedPath("/tmp/foo")
    >>> ap.access == PathAccess.ALL
    True

    >>> # Restrict to read-only
    >>> ro = AllowedPath("/etc/hosts", access=PathAccess.READ)
    >>> PathAccess.WRITE in ro.access
    False

    >>> # Frozen — safe to use as dict key / set member
    >>> {AllowedPath("/a"), AllowedPath("/a")} == {AllowedPath("/a")}
    True

Optional alias variant (off by default — see ``_alternative_os_alias`` in the
source for the trade-offs):

    >>> import os
    >>> # If you'd rather have READ/WRITE/EXEC bit values match os.R_OK/W_OK/X_OK
    >>> # so the flag is directly passable to os.access(path, mode), see the
    >>> # note in the module docstring. We default to ascending bit order
    >>> # (READ=1, WRITE=2, EXEC=4) for reader-friendliness; os.access uses
    >>> # POSIX convention (R=4, W=2, X=1) which inverts the natural ordering.
"""

from dataclasses import dataclass
from enum import IntFlag


__all__ = [
    "PathAccess",
    "AllowedPath",
]


class PathAccess(IntFlag):
    """Bitmask of access rights granted to a path.

    Bit values use ascending order for reader friendliness, NOT POSIX
    ``os.R_OK``/``W_OK``/``X_OK`` convention (which is ``R=4, W=2, X=1`` —
    inverted). If you need values compatible with ``os.access(path, mode)``,
    see the alternative aliased variant in this module's docstring.

    The enum is a true bitmask: members compose with ``|``, decompose with
    ``in``, and ``ALL`` is the union of the three primitive rights. Adding
    more rights later (e.g. ``DELETE``, ``LIST``) is a non-breaking change as
    long as existing bit values are preserved.
    """

    READ = 1
    WRITE = 2
    EXEC = 4
    ALL = READ | WRITE | EXEC


@dataclass(frozen=True)
class AllowedPath:
    """A path plus the access rights granted on it.

    Frozen so instances are hashable and usable as dict keys / set members.
    No path validation is performed here — callers decide whether to pass
    absolute or relative paths, expand ``~``, etc. (this keeps the type
    pure policy modeling, free of side effects).

    Attributes:
        path: The filesystem path the rights apply to. May be a directory or
            file path; interpretation is up to the consumer (e.g., a
            "directory" path typically grants the rights to all descendants).
        access: The bitmask of rights granted. Defaults to ``PathAccess.ALL``.
    """

    path: str
    access: PathAccess = PathAccess.ALL


# ---------------------------------------------------------------------------
# Alternative variant (NOT exported) — kept here as documentation only.
#
# If you want PathAccess bit values to be passable directly to
# os.access(path, mode), aliasing to the os module's constants works:
#
#     import os
#     class PathAccess(IntFlag):
#         READ = os.R_OK   # 4
#         WRITE = os.W_OK  # 2
#         EXEC = os.X_OK   # 1
#         ALL = READ | WRITE | EXEC  # 7
#
# Trade-offs vs the default:
#   PRO: Direct interop with os.access() — pass `int(allowed.access)` straight in.
#   CON: Bit values are POSIX-conventional (R=4, W=2, X=1), which inverts the
#        "smallest first" reading order most developers expect.
#   CON: Couples the type's bit assignments to an OS-syscall convention that
#        is irrelevant if you never call os.access() with these values.
#   CON: If we ever add new rights (DELETE, LIST, ...), we'd need to start
#        from bit 8+ to avoid clashing with os.F_OK and any future os.*_OK
#        constants — minor but real complexity.
#
# Default chosen here (READ=1, WRITE=2, EXEC=4) optimises for clarity at the
# call site and gives free room above bit 4 for future rights.
# ---------------------------------------------------------------------------
