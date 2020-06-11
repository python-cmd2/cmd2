# coding=utf-8
"""
Supports the definition of commands in separate classes to be composed into cmd2.Cmd
"""
import functools
from typing import (
    Callable,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)
from .constants import COMMAND_FUNC_PREFIX, HELP_FUNC_PREFIX, COMPLETER_FUNC_PREFIX

# Allows IDEs to resolve types without impacting imports at runtime, breaking circular dependency issues
try:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from .cmd2 import Cmd, Statement
        import argparse
except ImportError:
    pass

_UNBOUND_COMMANDS = []  # type: List[Tuple[str, Callable, Optional[Callable], Optional[Callable]]]
"""
Registered command tuples. (command, do_ function, complete_ function, help_ function
"""


class _PartialPassthru(functools.partial):
    """
    Wrapper around partial function that passes through getattr, setattr, and dir to the wrapped function.
    This allows for CommandSet functions to be wrapped while maintaining the decorated properties
    """
    def __getattr__(self, item):
        return getattr(self.func, item)

    def __setattr__(self, key, value):
        return setattr(self.func, key, value)

    def __dir__(self) -> Iterable[str]:
        return dir(self.func)


def register_command(cmd_func: Callable[['Cmd', Union['Statement', 'argparse.Namespace']], None]):
    """
    Decorator that allows an arbitrary function to be automatically registered as a command.
    If there is a help_ or complete_ function that matches this command, that will also be registered.

    :param cmd_func: Function to register as a cmd2 command
    :return:
    """
    assert cmd_func.__name__.startswith(COMMAND_FUNC_PREFIX), 'Command functions must start with `do_`'

    import inspect

    cmd_name = cmd_func.__name__[len(COMMAND_FUNC_PREFIX):]
    cmd_completer = None
    cmd_help = None

    module = inspect.getmodule(cmd_func)

    module_funcs = [mf for mf in inspect.getmembers(module) if inspect.isfunction(mf[1])]
    for mf in module_funcs:
        if mf[0] == COMPLETER_FUNC_PREFIX + cmd_name:
            cmd_completer = mf[1]
        elif mf[0] == HELP_FUNC_PREFIX + cmd_name:
            cmd_help = mf[1]
        if cmd_completer is not None and cmd_help is not None:
            break

    _UNBOUND_COMMANDS.append((cmd_name, cmd_func, cmd_completer, cmd_help))


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

    ``do_``, ``help_``, and ``complete_`` functions differ only in that they're now required to accept
    a reference to ``cmd2.Cmd`` as the first argument after self.
    """

    def __init__(self):
        self._cmd = None  # type: Optional[Cmd]

    def on_register(self, cmd: 'Cmd'):
        """
        Called by cmd2.Cmd when a CommandSet is registered. Subclasses can override this
        to perform an initialization requiring access to the Cmd object.

        :param cmd: The cmd2 main application
        :return: None
        """
        self._cmd = cmd
