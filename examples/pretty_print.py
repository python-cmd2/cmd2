#!/usr/bin/env python3
"""A simple example demonstrating use of cmd2.Cmd.ppretty()."""

import cmd2

data = {
    "name": "John Doe",
    "age": 30,
    "address": {"street": "123 Main St", "city": "Anytown", "state": "CA"},
    "hobbies": ["reading", "hiking", "coding"],
}


class Cmd2App(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()

    def do_normal(self, _) -> None:
        """Display the data using the normal poutput method."""
        self.poutput(data)

    def do_pretty(self, _) -> None:
        """Display the data using the ppretty method."""
        self.ppretty(data)


if __name__ == '__main__':
    app = Cmd2App()
    app.cmdloop()
