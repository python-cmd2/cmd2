#!/usr/bin/env python3
"""Windows terminal inventory for the reserved-row bottom-toolbar work.

    uv run python scripts/windows_toolbar_inventory.py

Run this INSIDE each terminal under test (Windows Terminal, mintty/git-bash,
conhost). It records what the plan requires before manual qualification: backend
classes actually selected, viewport vs backing-buffer geometry, console-mode
restoration, and the checks that can be made without a human looking at the screen.

It changes no cmd2 code and makes no permanent terminal changes: every escape
sequence it emits is reset before exit.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import prompt_toolkit
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.output.defaults import create_output

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.output import Output


def section(title: str) -> None:
    """Print a section heading.

    :param title: heading text
    """
    print(f"\n=== {title} ===")


def inventory() -> tuple[dict[str, Any], Output]:
    """Collect backend, geometry and console-mode facts for the current terminal.

    :return: the collected facts, and the output object they were collected from
    """
    out = create_output(stdout=sys.stdout)
    try:
        inp = create_input()
        in_cls = f"{type(inp).__module__}.{type(inp).__name__}"
    except (OSError, ValueError, ImportError) as exc:  # pragma: no cover - diagnostic
        in_cls = f"<unavailable: {exc!r}>"

    size = out.get_size()
    data: dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "os_release": platform.release(),
        "python": sys.version,
        "python_executable": sys.executable,
        "prompt_toolkit": prompt_toolkit.__version__,
        "TERM": os.environ.get("TERM"),
        "WT_SESSION": os.environ.get("WT_SESSION"),
        "MSYSTEM": os.environ.get("MSYSTEM"),
        "TERM_PROGRAM": os.environ.get("TERM_PROGRAM"),
        "output_class": f"{type(out).__module__}.{type(out).__name__}",
        "input_class": in_cls,
        "stdout_isatty": sys.stdout.isatty(),
        "stdin_isatty": sys.stdin.isatty(),
        "viewport_rows": size.rows,
        "viewport_columns": size.columns,
    }

    # Windows: the backing buffer is usually taller than the viewport, and the
    # delegation whitelist means geometry comes from the native side while
    # rendering goes through VT.
    try:
        info = out.get_win32_screen_buffer_info()  # type: ignore[attr-defined]
        data["win32_buffer_size"] = {"X": info.dwSize.X, "Y": info.dwSize.Y}
        data["win32_window"] = {
            "Left": info.srWindow.Left,
            "Top": info.srWindow.Top,
            "Right": info.srWindow.Right,
            "Bottom": info.srWindow.Bottom,
        }
        data["win32_cursor"] = {"X": info.dwCursorPosition.X, "Y": info.dwCursorPosition.Y}
        data["viewport_differs_from_buffer"] = (info.srWindow.Bottom - info.srWindow.Top + 1) != info.dwSize.Y
    except (AttributeError, OSError, NotImplementedError) as exc:
        data["win32_screen_buffer_info"] = f"<not available: {exc!r}>"

    try:
        data["rows_below_cursor_position"] = out.get_rows_below_cursor_position()
    except (AttributeError, OSError, NotImplementedError) as exc:
        data["rows_below_cursor_position"] = f"<not available: {exc!r}>"

    # Which object actually serves erase_down / get_size on this backend?
    for name in ("erase_down", "erase_screen", "get_size", "get_rows_below_cursor_position", "flush"):
        try:
            bound = getattr(out, name)
            owner = getattr(bound, "__self__", None)
            data[f"delegate::{name}"] = (
                f"{type(owner).__module__}.{type(owner).__name__}" if owner is not None else "<unbound>"
            )
        except (AttributeError, OSError, NotImplementedError) as exc:
            data[f"delegate::{name}"] = f"<error: {exc!r}>"

    data["console_mode_before"] = _console_mode()
    return data, out


def _console_mode() -> str:
    """Read the Win32 console output mode, if this is a Windows console.

    :return: a human-readable description of the mode, or why it is unavailable
    """
    try:
        from ctypes import byref, windll  # type: ignore[attr-defined]
        from ctypes.wintypes import DWORD, HANDLE  # type: ignore[attr-defined]

        handle = HANDLE(windll.kernel32.GetStdHandle(-11))
        mode = DWORD()
        if not windll.kernel32.GetConsoleMode(handle, byref(mode)):
            return "<GetConsoleMode failed>"
        value = mode.value
        return (
            f"0x{value:04X} "
            f"(VIRTUAL_TERMINAL_PROCESSING={'on' if value & 0x0004 else 'off'}, "
            f"WRAP_AT_EOL={'on' if value & 0x0002 else 'off'})"
        )
    except (ImportError, AttributeError, OSError) as exc:
        return f"<not a Windows console: {exc!r}>"


def probe_decstbm(out: Output, rows: int) -> dict[str, Any]:
    """Set and reset a reserved-row region; report whether modes survive it.

    Deliberately conservative: it prints a marker, establishes the region, writes
    enough lines to scroll, then resets. The human confirms what they saw.

    :param out: the output to emit through
    :param rows: the terminal's physical height
    :return: what was emitted, and the console mode afterwards
    """
    results: dict[str, Any] = {}
    mark = "TOOLBARMARKER"
    try:
        out.write_raw(f"\x1b[{rows};1H{mark}")
        out.write_raw(f"\x1b[1;{rows - 1}r")
        out.write_raw("\x1b[1;1H")
        for i in range(1, rows * 3):
            out.write_raw(f"probe line {i:04d}\r\n")
        out.flush()
        results["region_emitted"] = f"\\x1b[1;{rows - 1}r"
        results["lines_written"] = rows * 3 - 1
    finally:
        out.write_raw("\x1b[r")  # always restore full-screen margins
        out.write_raw("\x1b[0m")
        out.flush()
    results["console_mode_after"] = _console_mode()
    return results


def main() -> int:
    """Run the inventory and the visual probe.

    :return: process exit status
    """
    # Piping or redirecting selects PlainTextOutput, which would record the wrong
    # backend and silently invalidate the whole inventory.
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        print("REFUSING TO RUN: stdout/stdin is not a terminal.")
        print("Run this directly in the terminal under test -- do not pipe or redirect it,")
        print("or the recorded backend classes will be wrong.")
        return 2

    data, out = inventory()
    section("Environment inventory")
    for k, v in data.items():
        print(f"  {k:38s} {v}")

    rows = data["viewport_rows"]
    if rows < 4:
        print("\n  viewport too small for the probe; resize and rerun")
        return 2

    section("DECSTBM probe (visual confirmation required)")
    print("  About to reserve the bottom row, scroll past it, then reset.")
    print("  WATCH THE BOTTOM ROW. Press Enter when ready.")
    with contextlib.suppress(EOFError):
        input()
    data["decstbm_probe"] = probe_decstbm(out, rows)

    section("Report")
    print("  console mode before :", data["console_mode_before"])
    print("  console mode after  :", data["decstbm_probe"]["console_mode_after"])
    print("  modes match         :", data["console_mode_before"] == data["decstbm_probe"]["console_mode_after"])
    print("\n  Answer in the result template:")
    print("    1. Did TOOLBARMARKER stay on the bottom row for the whole scroll?")
    print("    2. Is the scrollback complete (probe line 0001 upward) and in order?")
    print("    3. Does TOOLBARMARKER appear anywhere in the scrollback? (it must not)")
    print("    4. After this program exits, does the shell prompt behave normally?")

    # Write beside this script rather than into whatever directory the tester
    # happened to be in, so the artifact is easy to find and collect.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"windows_toolbar_inventory_{platform.node()}.json")
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"\n  machine-readable record written to: {path}")
    print("  Attach that file to the result template.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
