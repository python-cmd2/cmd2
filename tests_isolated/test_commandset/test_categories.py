#!/usr/bin/env python3
# coding=utf-8
"""
Simple example demonstrating basic CommandSet usage.
"""
from typing import (
    Any,
)

import cmd2
from cmd2 import (
    CommandSet,
    with_default_category,
)


@with_default_category('Default Category')
class MyBaseCommandSet(CommandSet):
    """Defines a default category for all sub-class CommandSets"""

    def __init__(self, _: Any):
        super(MyBaseCommandSet, self).__init__()


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
        super(ExampleApp, self).__init__(auto_load_commands=False)

    def do_something(self, arg):
        self.poutput('this is the something command')


def test_heritable_categories():
    app = ExampleApp()

    base_cs = MyBaseCommandSet(0)
    assert getattr(base_cs, cmd2.constants.CLASS_ATTR_DEFAULT_HELP_CATEGORY, None) == 'Default Category'

    child1 = ChildInheritsParentCategories(1)
    assert getattr(child1, cmd2.constants.CLASS_ATTR_DEFAULT_HELP_CATEGORY, None) == 'Default Category'
    app.register_command_set(child1)
    assert getattr(app.cmd_func('hello').__func__, cmd2.constants.CMD_ATTR_HELP_CATEGORY, None) == 'Default Category'
    app.unregister_command_set(child1)

    child_nonheritable = ChildOverridesParentCategoriesNonHeritable(2)
    assert getattr(child_nonheritable, cmd2.constants.CLASS_ATTR_DEFAULT_HELP_CATEGORY, None) != 'Non-Heritable Category'
    app.register_command_set(child_nonheritable)
    assert getattr(app.cmd_func('goodbye').__func__, cmd2.constants.CMD_ATTR_HELP_CATEGORY, None) == 'Non-Heritable Category'
    app.unregister_command_set(child_nonheritable)

    grandchild1 = GrandchildInheritsGrandparentCategory(3)
    assert getattr(grandchild1, cmd2.constants.CLASS_ATTR_DEFAULT_HELP_CATEGORY, None) == 'Default Category'
    app.register_command_set(grandchild1)
    assert getattr(app.cmd_func('aloha').__func__, cmd2.constants.CMD_ATTR_HELP_CATEGORY, None) == 'Default Category'
    app.unregister_command_set(grandchild1)

    child_overrides = ChildOverridesParentCategories(4)
    assert getattr(child_overrides, cmd2.constants.CLASS_ATTR_DEFAULT_HELP_CATEGORY, None) == 'Heritable Category'
    app.register_command_set(child_overrides)
    assert getattr(app.cmd_func('bonjour').__func__, cmd2.constants.CMD_ATTR_HELP_CATEGORY, None) == 'Heritable Category'
    app.unregister_command_set(child_overrides)

    grandchild2 = GrandchildInheritsHeritable(5)
    assert getattr(grandchild2, cmd2.constants.CLASS_ATTR_DEFAULT_HELP_CATEGORY, None) == 'Heritable Category'
