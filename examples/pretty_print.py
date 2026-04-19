#!/usr/bin/env python3
"""A simple example demonstrating how to pretty print data."""

import cmd2

EXAMPLE_DATA = {
    "name": "John Doe",
    "age": 30,
    "address": {"street": "123 Main St", "city": "Anytown", "state": "CA"},
    "hobbies": ["reading", "hiking", "coding", "cooking", "running", "painting", "music", "photography", "cycling"],
    "member": True,
    "vip": False,
    "phone": None,
}


class Cmd2App(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()

    def do_pretty(self, _: cmd2.Statement) -> None:
        """Print an object using ppretty()."""
        self.ppretty(EXAMPLE_DATA)


if __name__ == "__main__":
    app = Cmd2App()
    app.cmdloop()
