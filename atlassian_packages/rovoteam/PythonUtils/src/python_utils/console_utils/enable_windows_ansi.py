"""
Enable ANSI color codes in Windows console.

This module enables Virtual Terminal Processing on Windows,
allowing ANSI escape sequences (colors) to work in the console.
"""

import sys
import os


def enable_windows_ansi_support():
    """
    Enable ANSI escape sequence processing on Windows.

    This allows color codes to work in the Windows console.
    Returns True if successful, False otherwise.
    """
    if sys.platform != 'win32':
        # Not Windows, ANSI should work by default
        return True

    try:
        import ctypes
        from ctypes import wintypes

        # Get the Windows console handle
        kernel32 = ctypes.windll.kernel32

        # Constants for console modes
        STD_OUTPUT_HANDLE = -11
        STD_ERROR_HANDLE = -12
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

        # Get handles for stdout and stderr
        stdout_handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        stderr_handle = kernel32.GetStdHandle(STD_ERROR_HANDLE)

        # Get current console mode
        mode = wintypes.DWORD()

        # Enable for stdout
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            mode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(stdout_handle, mode.value)

        # Enable for stderr
        if kernel32.GetConsoleMode(stderr_handle, ctypes.byref(mode)):
            mode.value |= ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(stderr_handle, mode.value)

        return True

    except Exception as e:
        print(f"Warning: Could not enable ANSI support: {e}", file=sys.stderr)
        return False


# Auto-enable when module is imported
if __name__ != "__main__":
    enable_windows_ansi_support()
