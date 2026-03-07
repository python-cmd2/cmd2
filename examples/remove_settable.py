#!/usr/bin/env python
"""A sample application for cmd2 demonstrating how to remove one of the built-in runtime settable parameters.

It also demonstrates how to use the cmd2.Cmd.select method.
"""

import cmd2


class MyApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.remove_settable('debug')

    def do_eat(self, arg):
        sauce = self.select('sweet salty', 'Sauce? ')
        result = '{food} with {sauce} sauce, yum!'
        result = result.format(food=arg, sauce=sauce)
        self.stdout.write(result + '\n')


if __name__ == '__main__':
    import sys

    c = MyApp()
    sys.exit(c.cmdloop())
