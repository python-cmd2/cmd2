#!/usr/bin/env python3
"""A simple example of setting a custom theme for a cmd2 application."""

from rich.style import Style

import cmd2
import cmd2.rich_utils as ru
from cmd2 import Cmd2Style, Color


class ThemedApp(cmd2.Cmd):
    """A simple cmd2 application with a custom theme."""

    def __init__(self, *args, **kwargs):
        """Initialize the application."""
        super().__init__(*args, **kwargs)
        self.intro = "This is a themed application. Try the 'theme_show' command."

        # Create a custom theme
        custom_theme = {
            Cmd2Style.SUCCESS: Style(color=Color.CYAN),
            Cmd2Style.WARNING: Style(color=Color.MAGENTA),
            Cmd2Style.ERROR: Style(color=Color.BRIGHT_RED),
            "argparse.args": Style(color=Color.AQUAMARINE3, underline=True),
            "inspect.attr": Style(color=Color.DARK_GOLDENROD, bold=True),
        }
        ru.set_theme(custom_theme)

    @cmd2.with_category("Theme Commands")
    def do_theme_show(self, _: cmd2.Statement):
        """Showcases the custom theme by printing messages with different styles."""
        self.poutput("This is a basic output message.")
        self.psuccess("This is a success message.")
        self.pwarning("This is a warning message.")
        self.perror("This is an error message.")


if __name__ == "__main__":
    import sys

    app = ThemedApp()
    sys.exit(app.cmdloop())
