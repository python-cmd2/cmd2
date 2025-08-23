#!/usr/bin/env python
"""A sample application for cmd2. Demonstrating colors available in the cmd2.colors.Color enum.

Execute the taste_the_rainbow command to see the colors available.
"""

import argparse

from rich.style import Style
from rich.text import Text

import cmd2
from cmd2 import Color


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application demonstrating colorized output."""

    def __init__(self) -> None:
        # Set include_ipy to True to enable the "ipy" command which runs an interactive IPython shell
        super().__init__(include_ipy=True)
        self.intro = 'Run the taste_the_rainbow command to see all of the colors available to you in cmd2.'

    rainbow_parser = cmd2.Cmd2ArgumentParser()
    rainbow_parser.add_argument('-b', '--background', action='store_true', help='show background colors as well')
    rainbow_parser.add_argument('-p', '--paged', action='store_true', help='display output using a pager')

    @cmd2.with_argparser(rainbow_parser)
    def do_taste_the_rainbow(self, args: argparse.Namespace) -> None:
        """Show all of the colors available within cmd2's Color StrEnum class."""

        def create_style(color: Color) -> Style:
            """Create a foreground or background color Style."""
            if args.background:
                return Style(bgcolor=color)
            return Style(color=color)

        styled_names = [Text(color.name, style=create_style(color)) for color in Color]
        output = Text("\n").join(styled_names)

        if args.paged:
            self.ppaged(output)
        else:
            self.poutput(output)


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
