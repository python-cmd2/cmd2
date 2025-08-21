#!/usr/bin/env python
"""A sample application for cmd2. Demonstrating colors available in the cmd2.colors.Color enum.

Execute the taste_the_rainbow command to see the colors available.
"""

from rich.style import Style

import cmd2
from cmd2.colors import Color


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application demonstrating colorized output."""

    def __init__(self) -> None:
        # Set include_ipy to True to enable the "ipy" command which runs an interactive IPython shell
        super().__init__(include_ipy=True)
        self.intro = 'Run the taste_the_rainbow command to see all of the colors available to you in cmd2.'

    rainbow_parser = cmd2.Cmd2ArgumentParser()
    rainbow_parser.add_argument('-b', '--background', action='store_true', help='Show background colors as well')

    @cmd2.with_argparser(rainbow_parser)
    def do_taste_the_rainbow(self, args) -> None:
        """Show all of the colors available within cmd2's Color StrEnum class."""

        for color_member in Color:
            style = Style(bgcolor=color_member.value) if args.background else Style(color=color_member.value)
            self.poutput(f"{color_member.name}", style=style, soft_wrap=False)


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
