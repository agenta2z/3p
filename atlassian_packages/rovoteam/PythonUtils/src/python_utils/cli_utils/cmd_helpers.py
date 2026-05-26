"""Shared command-line construction helpers for subprocess-spawning code paths.

Utilities for safe argv construction:

- :func:`substitute_placeholders` — ``${KEY}`` substitution into a list of
  argv strings.
- :func:`scrub_shell_metachars` — reject argv strings that contain shell
  metacharacters that could compose into a command-injection vector after
  substitution.

Both raise :class:`CmdHelperError` (a regular ``ValueError`` subclass) so
callers can let the exception bubble or wrap it in a domain-specific error.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


SHELL_METACHARS: tuple[str, ...] = (";", "|", "&&", "||", ">", "<", "`", "$(")


class CmdHelperError(ValueError):
    """Raised when placeholder substitution or scrub validation fails."""


def substitute_placeholders(
    args: Iterable[str],
    substitutions: Mapping[str, str],
    *,
    allow_unresolved: bool = False,
) -> list[str]:
    """Return ``args`` with every ``${KEY}`` token replaced by its value.

    Args:
        args: Argv-shaped iterable of strings (typically a list).
        substitutions: ``{KEY: value}``. Each ``KEY`` is matched as the
            literal token ``${KEY}``; values are substituted as-is (the
            caller is responsible for any prior validation / escaping).
        allow_unresolved: If ``False`` (default), raise when any
            ``${...}`` token survives substitution.

    Returns:
        A new list with substitutions applied; original input is not mutated.

    Raises:
        CmdHelperError: when an unresolved ``${...}`` placeholder remains
            and ``allow_unresolved=False``.
    """
    out: list[str] = []
    for raw in args:
        substituted = raw
        for key, value in substitutions.items():
            substituted = substituted.replace("${" + key + "}", value)
        if not allow_unresolved and "${" in substituted and "}" in substituted:
            _raise_unresolved_if_real(raw, substituted, substitutions)
        out.append(substituted)
    return out


def _raise_unresolved_if_real(
    raw: str, substituted: str, substitutions: Mapping[str, str]
) -> None:
    """Raise CmdHelperError iff ``substituted`` carries an unresolved placeholder."""
    idx = substituted.find("${")
    while idx != -1:
        end = substituted.find("}", idx + 2)
        if end == -1:
            return
        key = substituted[idx + 2 : end]
        if key and key not in substitutions:
            raise CmdHelperError(
                f"unresolved placeholder ${{{key}}} in argv element "
                f"{raw!r} (substituted to {substituted!r}); add the "
                f"key to the substitutions mapping or pass "
                f"allow_unresolved=True"
            )
        idx = substituted.find("${", end + 1)


def scrub_shell_metachars(
    args: Iterable[str], *, metachars: tuple[str, ...] = SHELL_METACHARS
) -> list[str]:
    """Return ``args`` unchanged after asserting no element contains a
    shell metacharacter from ``metachars``.

    Args:
        args: Argv-shaped iterable of strings.
        metachars: Tokens to reject. Defaults to :data:`SHELL_METACHARS`.

    Returns:
        ``list(args)`` (materialized) — same elements, same order.

    Raises:
        CmdHelperError: when any element contains any of ``metachars``.
    """
    materialized: list[str] = list(args)
    for arg in materialized:
        for meta in metachars:
            if meta in arg:
                raise CmdHelperError(
                    f"argv element {arg!r} contains shell metachar "
                    f"{meta!r}; use cwd / separate argv elements "
                    "instead of embedded cd / pipe / redirect / "
                    "command-substitution"
                )
    return materialized


def render_argv(
    template: Iterable[str],
    substitutions: Mapping[str, str],
    *,
    allow_unresolved: bool = False,
    metachars: tuple[str, ...] = SHELL_METACHARS,
) -> list[str]:
    """Convenience: substitute then scrub in one call."""
    return scrub_shell_metachars(
        substitute_placeholders(
            template, substitutions, allow_unresolved=allow_unresolved
        ),
        metachars=metachars,
    )
