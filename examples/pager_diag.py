#!/usr/bin/env python
"""Diagnostic for the built-in pager on Windows.

Background: ``ppaged()`` uses cmd2's built-in pager only while the bottom toolbar is
running during a command. Otherwise it falls through to the external pager, which on
Windows is ``more``. This script reports which of those guards is failing.

Run it from a real terminal (git bash, Windows Terminal, cmd.exe) and answer these:

1. ``slow``    - does the bottom toolbar stay visible for the 5 seconds it runs?
2. ``longout`` - does the pager show a help line ending in ``q: quit`` (built-in),
                 or ``-- More --`` (Windows' external ``more``)?
3. ``diag``    - prints the state below to stderr. Copy the whole report.
4. ``quit``

The three lines that decide which pager runs are ``use_builtin_pager``,
``_command_toolbar``, and ``toolbar.is_active``.
"""

import sys
import time

import cmd2


class PagerDiag(cmd2.Cmd):
    """Minimal app with the bottom toolbar enabled, so the built-in pager is eligible."""

    def __init__(self) -> None:
        super().__init__(enable_bottom_toolbar=True)

    def get_bottom_toolbar(self):
        """Show something unmistakable, so its presence or absence is obvious."""
        return "TOOLBAR IS HERE"

    def do_slow(self, _) -> None:
        """Sleep 5 seconds. The bottom toolbar should stay visible the whole time."""
        time.sleep(5)
        self.poutput("done")

    def do_longout(self, _) -> None:
        """Page 500 wide lines. This should open the built-in pager, not `more`."""
        self.ppaged("\n".join(f"row {i:03d} " + "col " * 30 for i in range(500)))

    def do_diag(self, _) -> None:
        """Report why ppaged() chooses the built-in pager or the external one."""
        toolbar = self._command_toolbar
        report = [
            f"platform            = {sys.platform}",
            f"stdin.isatty()      = {self.stdin.isatty()}",
            f"stdout.isatty()     = {self.stdout.isatty()}",
            f"_redirecting        = {self._redirecting}",
            f"in_pyscript/script  = {self.in_pyscript()} / {self.in_script()}",
            f"use_builtin_pager   = {self.use_builtin_pager}",
            f"_command_toolbar    = {toolbar!r}",
            f"_toolbar_disabled   = {self._command_toolbar_disabled}",
            f"main_session.input  = {type(self.main_session.input).__name__}",
            f"main_session.output = {type(self.main_session.output).__name__}",
            f"bottom_toolbar set  = {self.main_session.bottom_toolbar is not None}",
        ]
        if toolbar is not None:
            report += [
                f"toolbar.is_active   = {toolbar.is_active}",
                f"toolbar._proxy      = {toolbar._proxy!r}",
                f"toolbar.app.is_running = {toolbar.app.is_running}",
                f"toolbar._thread alive  = {toolbar._thread is not None and toolbar._thread.is_alive()}",
                f"toolbar._error      = {toolbar._error!r}",
            ]
        # Write straight to the real terminal so the report survives whatever the
        # toolbar or a pager does to the screen afterwards.
        sys.__stderr__.write("\n".join(report) + "\n")
        sys.__stderr__.flush()


if __name__ == "__main__":
    sys.exit(PagerDiag().cmdloop())
