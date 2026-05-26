import os
import platform
import sys
from enum import StrEnum
from typing import Dict


class OperatingSystem(StrEnum):
    """String-based enum representing common operating systems."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


def get_current_platform(
        identify_mobile_operating_system: bool = True,
        system_str: str = None,
        platform_str: str = None
) -> OperatingSystem:
    """Detects the current operating system, optionally overriding system/platform strings.

    This function inspects either:
      1. The provided `system_str` and `platform_str`, if supplied, or
      2. The result of `platform.system()` and `platform.platform()` if they are not.

    It returns one of the enum values from OperatingSystem:
        - WINDOWS
        - LINUX
        - MACOS
        - ANDROID (if `identify_mobile_operating_system=True` and heuristics detect it)
        - IOS (if `identify_mobile_operating_system=True` and heuristics detect it)
        - UNKNOWN

    Args:
        identify_mobile_operating_system (bool, optional):
            If True (default), attempts additional heuristics to distinguish Android or iOS
            from generic 'Linux' or 'Darwin' outputs. If False, Android-based environments
            will be reported as LINUX, and iOS-based environments as MACOS.
        system_str (str, optional):
            A custom string to mimic the output of `platform.system().lower()`.
            If None, the function calls `platform.system()` internally.
        platform_str (str, optional):
            A custom string to mimic the output of `platform.platform().lower()`.
            If None, the function calls `platform.platform()` internally.

    Returns:
        OperatingSystem: An enum value representing the detected operating system.

    Examples:
        >>> ios_os = get_current_platform(
        ...     system_str='darwin',
        ...     platform_str='Darwin-iPhoneOS-16.0.0'
        ... )
        >>> print(ios_os)
        ios

        >>> macos = get_current_platform(
        ...     system_str='darwin',
        ...     platform_str='Darwin-iPhoneOS-16.0.0',
        ...     identify_mobile_operating_system=False
        ... )
        >>> print(macos)
        macos

        >>> android_os = get_current_platform(
        ...     system_str='linux',
        ...     platform_str='Linux-5.4.0-android'
        ... )
        >>> print(android_os)
        android

    Notes:
        - The detection for Android or iOS relies on heuristics:
          * 'platform.system()' often returns 'Linux' on Android, 'Darwin' on iOS.
          * 'platform.platform()' might include keywords like 'android', 'iphone', 'ios', etc.
          These checks are not guaranteed for all environments or Python distributions.
    """
    system_str = (system_str or platform.system()).lower()  # e.g., "windows", "linux", "darwin"
    platform_str = (platform_str or platform.platform()).lower()  # e.g., "linux-5.4.0-android...", "darwin-20.6.0..."

    if "darwin" in system_str:
        # Normally macOS, unless 'identify_mobile_operating_system' is True
        # and we see an iOS hint in the platform string
        if identify_mobile_operating_system:
            # Check for iOS-related keywords
            if any(x in platform_str for x in ["iphone", "ios", "iphonesimulator"]):
                return OperatingSystem.IOS
        return OperatingSystem.MACOS

    if "win" in system_str:
        return OperatingSystem.WINDOWS

    if "linux" in system_str:
        # Typically Linux, but attempt Android detection if enabled
        if identify_mobile_operating_system and "android" in platform_str:
            return OperatingSystem.ANDROID
        return OperatingSystem.LINUX

    # If none of the above conditions are met, return UNKNOWN
    return OperatingSystem.UNKNOWN


# ---------------------------------------------------------------------------
# ARG_MAX utilities
# ---------------------------------------------------------------------------

# Platform-specific ARG_MAX fallback defaults (argv + envp combined size limit).
# Only used when os.sysconf("SC_ARG_MAX") is unavailable (e.g., Windows).
# On Linux/macOS, sysconf returns the real value for the running kernel.
_PLATFORM_ARG_MAX_DEFAULTS: Dict[str, int] = {
    "linux": 2_097_152,  # 2 MB
    "darwin": 262_144,  # 256 KB (conservative; modern macOS may report 1 MB)
    "win32": 32_767,  # ~32 KB — Windows CreateProcess limit
}


def get_arg_max() -> int:
    """Return the OS ARG_MAX limit in bytes.

    Tries ``os.sysconf('SC_ARG_MAX')`` first (Linux / macOS), which returns
    the real value for the running kernel. Falls back to platform-specific
    defaults when ``sysconf`` is unavailable (Windows) or returns an invalid
    value.

    Returns:
        ARG_MAX in bytes.
    """
    try:
        val = os.sysconf("SC_ARG_MAX")
        if val > 0:
            return val
    except (AttributeError, ValueError, OSError):
        pass
    return _PLATFORM_ARG_MAX_DEFAULTS.get(sys.platform, 262_144)


def get_max_single_arg_size(safety_margin: int = 8192) -> int:
    """Estimate maximum safe size for a single ``execve()`` argument.

    On Linux the kernel enforces a **per-argument** limit called
    ``MAX_ARG_STRLEN`` = ``PAGE_SIZE * 32`` (typically 128 KB on x86_64).
    This is *separate* from the total ``ARG_MAX`` (argv + envp) limit
    and is the binding constraint when using
    ``asyncio.create_subprocess_shell`` (which passes the entire command
    as a single argument to ``/bin/sh -c``).

    Args:
        safety_margin: Extra bytes to reserve for the shell command
            overhead (flags, config name, variable assignments, etc.)
            that are added around the prompt.  Default 8192 (8 KB).

    Returns:
        Estimated maximum bytes for a single argument, or 0 if the
        calculated value would be negative.
    """
    try:
        page_size = os.sysconf("SC_PAGESIZE")
        max_arg_strlen = page_size * 32
    except (AttributeError, ValueError, OSError):
        # Fallback: 128 KB is the default on x86_64 Linux.
        max_arg_strlen = 131_072
    return max(max_arg_strlen - safety_margin, 0)


def get_available_arg_space(safety_margin: int = 8192) -> int:
    """Estimate usable ARG_MAX space after environment variables.

    The kernel ARG_MAX limit applies to ``argv + envp`` and their strings
    combined. This function measures the current environment size and
    subtracts it (plus a configurable safety margin) from ARG_MAX.

    Args:
        safety_margin: Extra bytes to reserve beyond the measured env size.
            Default 8192 (8 KB) covers the command path, flags, and other
            small arguments.

    Returns:
        Estimated available bytes for command-line arguments.
        Returns ``max(available, 0)`` — no artificial floor, so callers get
        an honest estimate for threshold calculations.
    """
    arg_max = get_arg_max()
    env_size = sum(
        len(k.encode("utf-8")) + len(v.encode("utf-8")) + 2  # +2 for '=' and NUL
        for k, v in os.environ.items()
    )
    return max(arg_max - env_size - safety_margin, 0)
