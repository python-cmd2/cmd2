#!/usr/bin/env python3
"""Terminal inventory and reserved-row probe for the bottom-toolbar work.

    uv run python scripts/toolbar_inventory.py

Run this INSIDE each terminal under test -- Windows Terminal, mintty/git-bash,
conhost, iTerm2, Terminal.app, gnome-terminal, xterm. It records what the plan
requires before manual qualification: the backend classes actually selected,
viewport vs backing-buffer geometry, console-mode restoration, and two visual
probes a human confirms.

It changes no cmd2 code and makes no permanent terminal changes: every escape
sequence it emits is reset before exit.

Two properties are deliberately *not* left to chance, because getting either
wrong makes the output unreadable and the tester's answers meaningless:

* Every probe line erases to end of line. Without that, a probe line overwrites
  only the first columns of whatever was already on the row and the old tail
  survives beside it, which looks exactly like scrollback corruption but is not.
* Every margin change is wrapped in DECSC/DECRC. DECSTBM homes the cursor on set
  *and* on reset, so an unwrapped reset drops the cursor at row 1 and everything
  printed afterwards lands on top of the probe output.

Both are how ``cmd2.scroll_region`` already behaves; this script uses that module
directly rather than re-transcribing its sequences, so a passing probe is
evidence about shipped code.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import prompt_toolkit
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.output.defaults import create_output

from cmd2.scroll_region import (
    MIN_USABLE_ROWS,
    bounded_erase_screen_sequence,
    cursor_restore_sequence,
    cursor_save_sequence,
    reset_scroll_region_sequence,
    scroll_region_sequence,
)

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.output import Output

#: The token the tester searches scrollback for. It must never appear there.
MARKER = "TOOLBARMARKER"

#: Seconds between probe lines. The scroll is the thing under observation, so it has to
#: happen slowly enough for a human to watch the reserved row while it moves. Each line is
#: also flushed individually: buffering the whole probe and flushing once at the end paints
#: it as a single atomic repaint, which does not exercise scrolling at all.
DEFAULT_LINE_DELAY = 0.08


def section(title: str) -> None:
    """Print a section heading.

    :param title: heading text
    """
    print(f"\n=== {title} ===")


def multiplexer() -> str | None:
    """Identify a terminal multiplexer wrapping this session, if any.

    A multiplexer owns its own scrollback and its own scroll-region
    implementation, so a result collected inside one qualifies the multiplexer
    rather than the host terminal.

    :return: the multiplexer's name, or ``None`` if this is a bare terminal
    """
    if os.environ.get("TMUX"):
        return "tmux"
    if os.environ.get("STY"):
        return "screen"
    term = os.environ.get("TERM", "")
    if term.startswith(("screen", "tmux")):
        return f"screen/tmux (TERM={term})"
    return None


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
        "TERM_PROGRAM_VERSION": os.environ.get("TERM_PROGRAM_VERSION"),
        "COLORTERM": os.environ.get("COLORTERM"),
        "multiplexer": multiplexer(),
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


def _paint_bar(out: Output, rows: int, columns: int, note: str) -> None:
    """Paint the reserved row as a full-width reverse-video bar.

    A bare marker word is easy to mistake for ordinary output. Painting the whole
    row makes it unmistakable whether the reserved row is holding its position.

    :param out: the output to emit through
    :param rows: height of the terminal in rows
    :param columns: width of the terminal in columns
    :param note: text shown after the marker token
    """
    text = f" {MARKER}  {note}"[: columns - 1].ljust(columns - 1)
    out.write_raw(f"{cursor_save_sequence()}\x1b[{rows};1H\x1b[7m{text}\x1b[0m{cursor_restore_sequence()}")
    out.flush()


def _wait() -> None:
    """Pause for the tester, without printing anything over the screen under test."""
    with contextlib.suppress(EOFError, KeyboardInterrupt):
        input()


def probe_reserved_row(out: Output, rows: int, columns: int, delay: float = DEFAULT_LINE_DELAY) -> dict[str, Any]:
    """Reserve the bottom row, scroll past it, then clear the region beneath it.

    Stage one proves ordinary output scrolls without disturbing the reserved row
    and without losing history. Stage two proves the margin-bounded erase --
    ``DL`` standing in for ``ED``, the substitution the design depends on --
    clears the usable region only.

    :param out: the output to emit through
    :param rows: height of the terminal in rows
    :param columns: width of the terminal in columns
    :param delay: seconds to pause after each line, so the scroll can be watched
    :return: what was emitted, and the console mode afterwards
    """
    usable = rows - 1
    results: dict[str, Any] = {
        "region_emitted": scroll_region_sequence(rows, 1).replace("\x1b", "\\x1b"),
        "usable_rows": usable,
        "line_delay_seconds": delay,
    }
    try:
        # Start from a known-clean screen. Without this, probe text overwrites the
        # prefix of whatever was already on each row and the surviving tails read
        # as corruption.
        out.write_raw("\x1b[H\x1b[J")
        out.write_raw(f"{cursor_save_sequence()}{scroll_region_sequence(rows, 1)}{cursor_restore_sequence()}")
        _paint_bar(out, rows, columns, "must stay on this row -- press Enter after watching the scroll")
        out.write_raw("\x1b[1;1H")

        lines = rows * 3
        for i in range(1, lines + 1):
            out.write_raw(f"probe line {i:04d}\x1b[K\r\n")
            # Flush every line. One flush at the end would paint the whole probe as a
            # single repaint, which tests nothing about scrolling.
            out.flush()
            if delay:
                time.sleep(delay)
        results["lines_written"] = lines
        _wait()

        # Stage two: the bounded erase must not reach the reserved row.
        _paint_bar(out, rows, columns, "bounded erase next -- this row must survive; press Enter")
        out.flush()
        _wait()
        out.write_raw(bounded_erase_screen_sequence(usable))
        for i in range(1, 4):
            out.write_raw(f"after bounded erase {i:02d}\x1b[K\r\n")
            out.flush()
            if delay:
                time.sleep(delay)
        results["bounded_erase_emitted"] = bounded_erase_screen_sequence(usable).replace("\x1b", "\\x1b")
        _paint_bar(out, rows, columns, "still here? press Enter to finish")
        out.flush()
        _wait()
    finally:
        # Reset margins with the cursor preserved, then erase the reserved row
        # before anything else scrolls -- otherwise the marker itself is pushed
        # into scrollback and check 3 fails for a reason the design did not cause.
        out.write_raw(
            f"{cursor_save_sequence()}{reset_scroll_region_sequence()}{cursor_restore_sequence()}"
            f"{cursor_save_sequence()}\x1b[{rows};1H\x1b[2K{cursor_restore_sequence()}"
            "\x1b[0m\x1b[H\x1b[J"
        )
        out.flush()
    results["console_mode_after"] = _console_mode()
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the inventory and the visual probes.

    :param argv: command-line arguments, or ``None`` to read them from ``sys.argv``
    :return: process exit status
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_LINE_DELAY,
        metavar="SECONDS",
        help=(
            f"pause between probe lines so the scroll can be watched (default: {DEFAULT_LINE_DELAY}). "
            "Raise it if the scroll is still too quick to follow; 0 runs at full speed."
        ),
    )
    args = parser.parse_args(argv)
    if args.delay < 0:
        parser.error("--delay must not be negative")
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
    columns = data["viewport_columns"]
    if rows - 1 < MIN_USABLE_ROWS:
        print(f"\n  viewport of {rows} rows is too small for the probe; resize and rerun")
        return 2

    if data["multiplexer"]:
        section("WARNING")
        print(f"  Running inside {data['multiplexer']}.")
        print("  A multiplexer owns its own scrollback and scroll regions, so this run")
        print("  qualifies the multiplexer, NOT the host terminal. For a bare-terminal")
        print("  result, exit it and rerun directly in the terminal under test.")

    section("Reserved-row probe (visual confirmation required)")
    lines = rows * 3
    print("  The screen will be cleared, the bottom row reserved and painted as a bar,")
    print("  then ordinary output will scroll past it. You will be prompted twice more.")
    if args.delay:
        print(f"\n  {lines} lines at {args.delay:g}s each -- about {lines * args.delay:.0f}s of scrolling.")
        print("  Rerun with --delay to slow it down further, or --delay 0 for full speed.")
    else:
        print(f"\n  {lines} lines at full speed; rerun without --delay 0 to watch it scroll.")
    print("\n  WATCH THE BOTTOM ROW. Press Enter when ready.")
    with contextlib.suppress(EOFError, KeyboardInterrupt):
        input()
    data["reserved_row_probe"] = probe_reserved_row(out, rows, columns, args.delay)

    section("Report")
    print("  console mode before :", data["console_mode_before"])
    print("  console mode after  :", data["reserved_row_probe"]["console_mode_after"])
    print("  modes match         :", data["console_mode_before"] == data["reserved_row_probe"]["console_mode_after"])
    print("\n  Answer these -- every question is phrased so that yes is good:")
    print(f"    1. Did the {MARKER} bar stay on the bottom row for the whole scroll?")
    print("    2. Did it survive the bounded erase, with the region above it cleared?")
    print("    3. Is the scrollback unbroken and in order, from 'probe line 0001' upward?")
    print("       It stops partway on purpose -- stage two's erase deletes the last")
    print("       screenful rather than scrolling it away. Check that what is there is")
    print("       complete and in order, not that it reaches the highest number written.")
    print(f"    4. Is the scrollback free of {MARKER}? (it must not appear -- a no here is a hard failure)")
    print("    5. After this program exits, does the shell prompt behave normally?")
    print("    6. Is the cursor visible and correctly placed after exit?")

    # Write beside this script rather than into whatever directory the tester
    # happened to be in, so the artifact is easy to find and collect.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"toolbar_inventory_{platform.node()}.json")
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"\n  machine-readable record written to: {path}")
    print("  Attach that file to the result template.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
