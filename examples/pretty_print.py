#!/usr/bin/env python3
"""A simple example demonstrating how to pretty print JSON data in a cmd2 app using rich."""

from rich.json import JSON

import cmd2

EXAMPLE_DATA = {
    "name": "John Doe",
    "age": 30,
    "address": {"street": "123 Main St", "city": "Anytown", "state": "CA"},
    "hobbies": ["reading", "hiking", "coding"],
}


class Cmd2App(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.data = EXAMPLE_DATA

    def do_normal(self, _) -> None:
        """Display the data using the normal poutput method."""
        self.poutput(self.data)

    def do_pretty(self, _) -> None:
        """Display the JSON data in a pretty way using rich."""

        json_renderable = JSON.from_data(
            self.data,
            indent=2,
            highlight=True,
            skip_keys=False,
            ensure_ascii=False,
            check_circular=True,
            allow_nan=True,
            default=None,
            sort_keys=False,
        )
        self.poutput(json_renderable)


if __name__ == '__main__':
    app = Cmd2App()
    app.cmdloop()
