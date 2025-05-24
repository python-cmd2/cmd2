#!/usr/bin/env python
"""A simple example demonstrating support for unicode command names."""

import math

import cmd2


class UnicodeApp(cmd2.Cmd):
    """Example cmd2 application with unicode command names."""

    def __init__(self) -> None:
        super().__init__()
        self.intro = 'Welcome the Unicode example app. Note the full Unicode support:  😇 💩'

    def do_𝛑print(self, _) -> None:  # noqa: PLC2401
        """This command prints 𝛑 to 5 decimal places."""
        self.poutput(f"𝛑 = {math.pi:.6}")

    def do_你好(self, arg) -> None:  # noqa: N802, PLC2401
        """This command says hello in Chinese (Mandarin)."""
        self.poutput("你好 " + arg)


if __name__ == '__main__':
    app = UnicodeApp()
    app.cmdloop()
