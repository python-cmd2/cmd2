#!/usr/bin/env python3
# coding=utf-8
"""
Simple example demonstrating basic CommandSet usage.
"""

import cmd2
from cmd2 import (
    CommandSet,
    with_default_category,
)


@with_default_category('Default Category')
class MyBaseCommandSet(CommandSet):
    """Defines a default category for all sub-class CommandSets"""

    pass


class ChildInheritsParentCategories(MyBaseCommandSet):
    """
    This subclass doesn't declare any categories so all commands here are also categorized under 'Default Category'
    """

    def do_hello(self, _: cmd2.Statement):
        self._cmd.poutput('Hello')

    def do_world(self, _: cmd2.Statement):
        self._cmd.poutput('World')


@with_default_category('Non-Heritable Category', heritable=False)
class ChildOverridesParentCategoriesNonHeritable(MyBaseCommandSet):
    """
    This subclass overrides the 'Default Category' from the parent, but in a non-heritable fashion. Sub-classes of this
    CommandSet will not inherit this category and will, instead, inherit 'Default Category'
    """

    def do_goodbye(self, _: cmd2.Statement):
        self._cmd.poutput('Goodbye')


class GrandchildInheritsGrandparentCategory(ChildOverridesParentCategoriesNonHeritable):
    """
    This subclass's parent class declared its default category non-heritable. Instead, it inherits the category defined
    by the grandparent class.
    """

    def do_aloha(self, _: cmd2.Statement):
        self._cmd.poutput('Aloha')


@with_default_category('Heritable Category')
class ChildOverridesParentCategories(MyBaseCommandSet):
    """
    This subclass is decorated with a default category that is heritable. This overrides the parent class's default
    category declaration.
    """

    def do_bonjour(self, _: cmd2.Statement):
        self._cmd.poutput('Bonjour')


class GrandchildInheritsHeritable(ChildOverridesParentCategories):
    """
    This subclass's parent declares a default category that overrides its parent. As a result, commands in this
    CommandSet will be categorized under 'Heritable Category'
    """

    def do_monde(self, _: cmd2.Statement):
        self._cmd.poutput('Monde')


class ExampleApp(cmd2.Cmd):
    """
    Example to demonstrate heritable default categories
    """

    def __init__(self):
        super(ExampleApp, self).__init__()

    def do_something(self, arg):
        self.poutput('this is the something command')


if __name__ == '__main__':
    app = ExampleApp()
    app.cmdloop()
