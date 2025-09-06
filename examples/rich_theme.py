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

        # Set text which prints right before all of the help tables are listed.
        self.doc_leader = "Welcome to this glorious help ..."

        # Create a custom theme
        # Colors can come from the cmd2.color.Color StrEnum class, be RGB hex values, or
        # be any of the rich standard colors: https://rich.readthedocs.io/en/stable/appendix/colors.html
        custom_theme = {
            Cmd2Style.SUCCESS: Style(color=Color.GREEN1, bgcolor=Color.GRAY30),  # Use color from cmd2 Color class
            Cmd2Style.WARNING: Style(color=Color.ORANGE1),
            Cmd2Style.ERROR: Style(color=Color.PINK1),
            Cmd2Style.HELP_HEADER: Style(color=Color.CYAN, bgcolor="#44475a"),
            Cmd2Style.HELP_LEADER: Style(color="#f8f8f2", bgcolor="#282a36"),  # use RGB hex colors
            Cmd2Style.TABLE_BORDER: Style(color="turquoise2"),  # use a rich standard color
            "traceback.exc_type": Style(color=Color.RED, bgcolor=Color.LIGHT_YELLOW3, bold=True),
            "argparse.args": Style(color=Color.AQUAMARINE3, underline=True),
        }
        ru.set_theme(custom_theme)

    @cmd2.with_category("Theme Commands")
    def do_theme_show(self, _: cmd2.Statement):
        """Showcases the custom theme by printing messages with different styles."""
        self.poutput("This is a basic output message.")
        self.psuccess("This is a success message.")
        self.pwarning("This is a warning message.")
        self.perror("This is an error message.")
        self.pexcept(ValueError("This is a dummy ValueError exception."))


if __name__ == "__main__":
    import sys

    app = ThemedApp()
    sys.exit(app.cmdloop())
