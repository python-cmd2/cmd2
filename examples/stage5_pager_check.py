#!/usr/bin/env python
"""Manual check for the Stage 5 investigation of the built-in pager. Remove before merging to main.

    uv run python examples/stage5_pager_check.py [auto|reserved|legacy|off]

The argument is the bottom toolbar mode, ``auto`` by default. Then, at the prompt:

    info                      what was selected: toolbar rendering, terminal classes, pagers
    pager builtin|external    which pager ``rows`` uses (the built-in one needs a toolbar)
    hist 40                   print numbered lines, to have something above the pager
    rows 2000                 page 2000 lines; add ``color``, ``wide`` or ``long``, and ``chop``

After each ``rows`` the application prints how long Rich took to render the text, how long the
built-in pager took to draw its first page, and how long the pager was open.

What the investigation still needs from Windows, where none of this has been measured. Run it in
Windows Terminal, in conhost.exe and in mintty (Git Bash), once as ``auto`` and once as ``legacy``,
and record for each:

1. The output of ``info``.
2. ``hist 40`` then ``rows 2000 color``. Which pager came up: the built-in one ends in
   ``q: quit`` on the row above the toolbar, the external one shows ``-- More --``. Does the
   toolbar clock stay visible and keep ticking? Do Space, ``b``, ``G``, ``g``, ``/row 150`` Enter
   and ``n`` work, and are ``row N`` green and ``bold red`` red? After ``q``: the timing line, and
   whether ``hist 0`` to ``hist 39`` are intact and whether any paged rows, the pager's key
   summary or a second toolbar are left on the screen or in the scrollback.
3. ``rows 2000 long chop``: do the right and left arrows scroll sideways to ``tail0``?
4. ``rows 2000 wide``: do the wide characters wrap without breaking?
5. ``rows 100000``: the timing line.
6. Resize the window while the pager is open, then page on and quit. Ctrl-C while it is open.
7. ``pager external`` and steps 2 to 6 again. For ``more``: are colors shown or printed as escape
   sequences, can it go back or search, and does the toolbar return when it exits?
"""

import os
import platform
import subprocess
import sys
import time

import prompt_toolkit

import cmd2
from cmd2 import command_toolbar

KINDS = {
    "plain": lambda number: f"row {number} the quick brown fox jumps over the lazy dog",
    "color": lambda number: f"\x1b[32mrow {number}\x1b[0m plain \x1b[1;31mbold red\x1b[0m plain again",
    "wide": lambda number: f"row {number} " + "漢字" * 50 + " end",
    "long": lambda number: f"row {number} " + "abcdefghij" * 30 + f" tail{number}",
}


class PagerCheck(cmd2.Cmd):
    def __init__(self, mode: str) -> None:
        super().__init__(allow_cli_args=False, bottom_toolbar_mode=mode, refresh_interval=0.5)
        self.prompt = "check> "
        self.requested_mode = mode
        self.timings: dict[str, float] = {}

    def get_bottom_toolbar(self) -> str:
        return f"TOOLBAR {time.strftime('%H:%M:%S')}"

    def do_info(self, _: cmd2.Statement) -> None:
        """Show what this terminal selected."""
        reserved = self.reserved_toolbar
        rendering = "off" if self.main_session.bottom_toolbar is None else "legacy"
        if reserved is not None and reserved.is_active:
            rendering = "reserved"
        size = self.main_session.output.get_size()
        self.poutput(f"platform          {platform.platform()}")
        self.poutput(f"python            {sys.version.split()[0]}   prompt-toolkit {prompt_toolkit.__version__}")
        self.poutput(f"toolbar           requested {self.requested_mode}, rendering {rendering}")
        self.poutput(f"output / input    {type(self.main_session.output).__name__} / {type(self.main_session.input).__name__}")
        self.poutput(
            f"terminal          {size.columns}x{size.rows}  stdin tty {self.stdin.isatty()}  stdout tty {self.stdout.isatty()}"
        )
        self.poutput(f"environment       TERM={os.environ.get('TERM')}  MSYSTEM={os.environ.get('MSYSTEM')}")
        self.poutput(f"pager             {'built-in' if self.use_builtin_pager else 'external'}")
        self.poutput(f"external pagers   {self.pager!r} / chop {self.pager_chop!r}")

    def do_pager(self, arg: cmd2.Statement) -> None:
        """pager builtin|external: choose the pager which ``rows`` uses."""
        self.use_builtin_pager = str(arg).strip() != "external"
        self.poutput(f"using the {'built-in' if self.use_builtin_pager else 'external'} pager")

    def do_hist(self, arg: cmd2.Statement) -> None:
        """hist COUNT: print numbered lines."""
        for number in range(int(str(arg) or 40)):
            self.poutput(f"hist {number}")

    def do_rows(self, arg: cmd2.Statement) -> None:
        """rows COUNT [plain|color|wide|long] [chop]: page that many generated lines."""
        words = str(arg).split()
        count = int(words[0]) if words else 2000
        kind = next((word for word in words[1:] if word in KINDS), "plain")
        text = "\n".join(KINDS[kind](number) for number in range(count))
        self.timings = {"start": time.perf_counter()}
        self.ppaged(text, chop="chop" in words)
        timings, end = self.timings, time.perf_counter()
        handed = timings.get("handed")
        if handed is None:
            self.poutput(f"not paged ({end - timings['start']:.2f} s)")
            return
        report = (
            f"rendered by Rich in {handed - timings['start']:.2f} s; {timings['which']} pager open for {end - handed:.2f} s"
        )
        if "first frame" in timings:
            report += f"; its first page drawn after {timings['first frame'] - handed:.2f} s"
        self.poutput(report)


def instrument(app: PagerCheck) -> None:
    """Note when the text reaches a pager, and when the built-in one has drawn."""
    builtin_page = command_toolbar.CommandToolbar.page

    def page(display: command_toolbar.CommandToolbar, text: str, *, chop: bool) -> None:
        app.timings.update(handed=time.perf_counter(), which="built-in")

        def drawn(_: object) -> None:
            if display._paging:
                app.timings.setdefault("first frame", time.perf_counter())

        display.app.after_render += drawn
        try:
            builtin_page(display, text, chop=chop)
        finally:
            display.app.after_render -= drawn

    command_toolbar.CommandToolbar.page = page
    popen = subprocess.Popen

    class Popen(popen):
        def __init__(self, *args, **kwargs):
            if kwargs.get("stdin") == subprocess.PIPE and "handed" not in app.timings:
                app.timings.update(handed=time.perf_counter(), which="external")
            super().__init__(*args, **kwargs)

    subprocess.Popen = Popen


if __name__ == "__main__":
    check = PagerCheck(sys.argv[1] if len(sys.argv) > 1 else "auto")
    instrument(check)
    sys.exit(check.cmdloop())
