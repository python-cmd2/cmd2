#!/usr/bin/env python
"""
Create a CLI with a nested command structure as follows. The commands 'second' and 'third' navigate the CLI to the scope
of the submenu. Nesting of the submenus is done with the cmd2.AddSubmenu() decorator.

      (Top Level)----second----->(2nd Level)----third----->(3rd Level)
        |                            |                          |
        ---> say                     ---> say                   ---> say



"""

from __future__ import print_function
import cmd2


class ThirdLevel(cmd2.Cmd):
    """To be used as a third level command class. """

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = '3rdLevel '
        self.top_level_attr = None
        self.second_level_attr = None

    def do_say(self, line):
        print("You called a command in ThirdLevel with '%s'. " 
              "It has access to top_level_attr: %s " 
              "and second_level_attr: %s" % (line, self.top_level_attr, self.second_level_attr))

    def help_say(self):
        print("This is a third level submenu (submenu_ab). Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]


@cmd2.AddSubmenu(ThirdLevel(),
                 command='third',
                 aliases=('third_alias',),
                 shared_attributes=dict(second_level_attr='second_level_attr', top_level_attr='top_level_attr'))
class SecondLevel(cmd2.Cmd):
    """To be used as a second level command class. """
    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = '2ndLevel '
        self.top_level_attr = None
        self.second_level_attr = 987654321

    def do_say(self, line):
        print("You called a command in SecondLevel with '%s'. "
              "It has access to top_level_attr: %s" % (line, self.top_level_attr))

    def help_say(self):
        print("This is a SecondLevel menu. Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]



@cmd2.AddSubmenu(SecondLevel(),
                 command='second',
                 aliases=('second_alias',),
                 shared_attributes=dict(top_level_attr='top_level_attr'))
class TopLevel(cmd2.Cmd):
    """To be used as the main / top level command class that will contain other submenus."""

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = 'TopLevel '
        self.top_level_attr = 123456789

    def do_say(self, line):
        print("You called a command in TopLevel with '%s'. "
              "TopLevel has attribute top_level_attr=%s" % (line, self.top_level_attr))

    def help_say(self):
        print("This is a top level submenu. Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]



if __name__ == '__main__':

    root = TopLevel()
    root.cmdloop()

