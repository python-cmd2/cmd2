# coding=utf-8
"""
Supports the definition of commands in separate classes to be composed into cmd2.Cmd
"""
from typing import Optional, Type

from .constants import COMMAND_FUNC_PREFIX
from .exceptions import CommandSetRegistrationError

# Allows IDEs to resolve types without impacting imports at runtime, breaking circular dependency issues
try:  # pragma: no cover
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        import cmd2

except ImportError:   # pragma: no cover
    pass


def with_default_category(category: str):
    """
    Decorator that applies a category to all ``do_*`` command methods in a class that do not already
    have a category specified.

    :param category: category to put all uncategorized commands in
    :return: decorator function
    """

    def decorate_class(cls: Type[CommandSet]):
        from .constants import CMD_ATTR_HELP_CATEGORY
        import inspect
        from .decorators import with_category
        methods = inspect.getmembers(
            cls,
            predicate=lambda meth: inspect.isfunction(meth) and meth.__name__.startswith(COMMAND_FUNC_PREFIX))
        category_decorator = with_category(category)
        for method in methods:
            if not hasattr(method[1], CMD_ATTR_HELP_CATEGORY):
                setattr(cls, method[0], category_decorator(method[1]))
        return cls
    return decorate_class


class CommandSet(object):
    """
    Base class for defining sets of commands to load in cmd2.

    ``with_default_category`` can be used to apply a default category to all commands in the CommandSet.

    ``do_``, ``help_``, and ``complete_`` functions differ only in that self is the CommandSet instead of the cmd2 app
    """

    def __init__(self):
        self._cmd = None  # type: Optional[cmd2.Cmd]

    def on_register(self, cmd):
        """
        Called by cmd2.Cmd when a CommandSet is registered. Subclasses can override this
        to perform an initialization requiring access to the Cmd object.

        :param cmd: The cmd2 main application
        :type cmd: cmd2.Cmd
        """
        if self._cmd is None:
            self._cmd = cmd
        else:
            raise CommandSetRegistrationError('This CommandSet has already been registered')

    def on_unregister(self):
        """
        Called by ``cmd2.Cmd`` when a CommandSet is unregistered and removed.

        :param cmd:
        :type cmd: cmd2.Cmd
        """
        self._cmd = None
