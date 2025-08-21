#!/usr/bin/env python
"""A sample application for cmd2. Demonstrating colors available in the cmd2.colors.Color enum.

Execute the taste_the_rainbow command to see the colors available.
"""

import argparse

from rich.style import Style

import cmd2
from cmd2 import (
    Color,
    stylize,
)


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

        color_names = []
        for color_member in Color:
            style = Style(bgcolor=color_member) if args.background else Style(color=color_member)
            styled_name = stylize(color_member.name, style=style)
            if args.paged:
                color_names.append(styled_name)
            else:
                self.poutput(styled_name)

        if args.paged:
            self.ppaged('\n'.join(color_names))


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
