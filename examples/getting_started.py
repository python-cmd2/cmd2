#!/usr/bin/env python3
"""A simple example cmd2 application demonstrating many common features.

Features demonstrated include all of the following:
 1) Colorizing/stylizing output
 2) Using multiline commands
 3) Persistent history
 4) How to run an initialization script at startup
 5) How to group and categorize commands when displaying them in help
 6) Opting-in to using the ipy command to run an IPython shell
 7) Allowing access to your application in py and ipy
 8) Displaying an intro banner upon starting your application
 9) Using a custom prompt
10) How to make custom attributes settable at runtime.
11) Shortcuts for commands
"""

import pathlib

from rich.style import Style

import cmd2
from cmd2 import (
    Color,
    stylize,
)


class BasicApp(cmd2.Cmd):
    """Cmd2 application to demonstrate many common features."""

    CUSTOM_CATEGORY = 'My Custom Commands'

    def __init__(self) -> None:
        """Initialize the cmd2 application."""
        # Startup script that defines a couple aliases for running shell commands
        alias_script = pathlib.Path(__file__).absolute().parent / '.cmd2rc'

        # Create a shortcut for one of our commands
        shortcuts = cmd2.DEFAULT_SHORTCUTS
        shortcuts.update({'&': 'intro'})
        super().__init__(
            include_ipy=True,
            multiline_commands=['echo'],
            persistent_history_file='cmd2_history.dat',
            shortcuts=shortcuts,
            startup_script=str(alias_script),
        )

        # Prints an intro banner once upon application startup
        self.intro = (
            stylize(
                'Welcome to cmd2!',
                style=Style(color=Color.GREEN1, bgcolor=Color.GRAY0, bold=True),
            )
            + ' Note the full Unicode support:  😇 💩'
        )

        # Show this as the prompt when asking for input
        self.prompt = 'myapp> '

        # Used as prompt for multiline commands after the first line
        self.continuation_prompt = '... '

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = 'cmd2 Built-in Commands'

        # Color to output text in with echo command
        self.foreground_color = Color.CYAN.value

        # Make echo_fg settable at runtime
        fg_colors = [c.value for c in Color]
        self.add_settable(
            cmd2.Settable(
                'foreground_color',
                str,
                'Foreground color to use with echo command',
                self,
                choices=fg_colors,
            )
        )

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_intro(self, _: cmd2.Statement) -> None:
        """Display the intro banner."""
        self.poutput(self.intro)

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_echo(self, arg: cmd2.Statement) -> None:
        """Multiline command."""
        self.poutput(
            stylize(
                arg,
                style=Style(color=self.foreground_color),
            )
        )


if __name__ == '__main__':
    import sys

    app = BasicApp()
    sys.exit(app.cmdloop())
