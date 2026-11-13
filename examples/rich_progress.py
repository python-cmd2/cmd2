#!/usr/bin/env python3
"""An example of using Rich to show the progress and status of long-running commands in a cmd2 application.

Rich's spinners and progress bars repeatedly redraw the same lines of the terminal. To use them in a
cmd2 command, give them a console which writes to ``self.stdout``. They then honor output redirection,
the ``allow_style`` setting, and the cmd2 theme like the rest of your command's output.

The commands in this example are:

- ``status``    - a spinner with a status message, for work of an unknown length
- ``progress``  - a progress bar with messages printed above it while it is running
- ``downloads`` - several progress bars with custom columns updating at the same time
- ``track``     - the shortest way to add a progress bar to a loop

Pressing Ctrl-C while any of them is running stops the display and restores the cursor. Redirect
their output to a file (e.g. ``progress > out.txt``) to see that the animation is left out of it.
"""

import time

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    track,
)

import cmd2
from cmd2.rich_utils import Cmd2GeneralConsole

# Name, size in bytes, and bytes received per update for each simulated download
DOWNLOADS = [
    ("cmd2.tar.gz", 2_000_000, 50_000),
    ("rich.tar.gz", 6_000_000, 100_000),
    ("prompt_toolkit.tar.gz", 4_000_000, 40_000),
]


class ProgressApp(cmd2.Cmd):
    """Example cmd2 application which shows the progress and status of long-running commands."""

    def __init__(self) -> None:
        super().__init__()
        self.intro = "Run the status, progress, downloads, and track commands to see Rich progress displays."

    def _create_console(self) -> Cmd2GeneralConsole:
        """Create a Rich console which writes to the same place as poutput()."""
        return Cmd2GeneralConsole(file=self.stdout)

    def do_status(self, _: cmd2.Statement) -> None:
        """Show a spinner and a status message while doing work of an unknown length."""
        console = self._create_console()
        with console.status("Starting...") as status:
            for step in ("Connecting to the server", "Authenticating", "Fetching data"):
                status.update(f"{step}...")
                time.sleep(1.5)

        # The status line is erased when the with block exits
        self.poutput("Data fetched.")

    def do_progress(self, _: cmd2.Statement) -> None:
        """Show a progress bar and print messages above it while it is running."""
        files = [f"file_{i}.dat" for i in range(1, 11)]

        with Progress(console=self._create_console()) as progress:
            task_id = progress.add_task("Processing files", total=len(files))
            for file in files:
                time.sleep(0.4)

                # While the progress bar is active, print through its console so the message
                # appears above the bar. poutput() and the other print methods do not know about
                # the bar: their output lands on the end of its line and a stale copy of the bar
                # is left behind.
                progress.console.print(f"Processed {file}")
                progress.advance(task_id)

        # The finished bar is left on the screen. Once the with block exits, poutput() is safe again.
        self.poutput("All files processed.")

    def do_downloads(self, _: cmd2.Statement) -> None:
        """Show several progress bars with custom columns updating at the same time."""
        with Progress(
            # Task descriptions are parsed as Rich markup unless the column which shows them says otherwise.
            # File names can contain square brackets, so show them exactly as they are.
            TextColumn("{task.description}", style=cmd2.Color.CYAN, markup=False),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self._create_console(),
            # Erase the progress bars when the with block exits
            transient=True,
        ) as progress:
            for name, size, chunk_size in DOWNLOADS:
                # Extra keyword arguments are stored in the task's fields
                progress.add_task(name, total=size, chunk_size=chunk_size)

            while not progress.finished:
                time.sleep(0.05)
                for task in progress.tasks:
                    if not task.finished:
                        progress.advance(task.id, task.fields["chunk_size"])

        self.poutput(f"Downloaded {len(DOWNLOADS)} files.")

    def do_track(self, _: cmd2.Statement) -> None:
        """Add a progress bar to a loop with a single function call."""
        for _number in track(range(40), description="Crunching numbers", console=self._create_console()):
            time.sleep(0.05)


if __name__ == "__main__":
    app = ProgressApp()
    app.cmdloop()
