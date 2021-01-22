# coding=utf-8
"""
Supports the definition of commands in separate classes to be composed into cmd2.Cmd
"""
from typing import (
    Optional,
    Type,
)

from .constants import (
    CLASS_ATTR_DEFAULT_HELP_CATEGORY,
    COMMAND_FUNC_PREFIX,
)
from .exceptions import (
    CommandSetRegistrationError,
)

# Allows IDEs to resolve types without impacting imports at runtime, breaking circular dependency issues
try:  # pragma: no cover
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        import cmd2

except ImportError:   # pragma: no cover
    pass


def with_default_category(category: str, *, heritable: bool = True):
    """
    Decorator that applies a category to all ``do_*`` command methods in a class that do not already
    have a category specified.

    CommandSets that are decorated by this with `heritable` set to True (default) will set a class attribute that is
    inherited by all subclasses unless overridden. All commands of this CommandSet and all subclasses of this CommandSet
    that do not declare an explicit category will be placed in this category. Subclasses may use this decorator to
    override the default category.

    If `heritable` is set to False, then only the commands declared locally to this CommandSet will be placed in the
    specified category. Dynamically created commands, and commands declared in sub-classes will not receive this
    category.

    :param category: category to put all uncategorized commands in
    :param heritable: Flag whether this default category should apply to sub-classes. Defaults to True
    :return: decorator function
    """

    def decorate_class(cls: Type[CommandSet]):
        if heritable:
            setattr(cls, CLASS_ATTR_DEFAULT_HELP_CATEGORY, category)

        from .constants import CMD_ATTR_HELP_CATEGORY
        import inspect
        from .decorators import with_category
        # get members of the class that meet the following criteria:
        # 1. Must be a function
        # 2. Must start with COMMAND_FUNC_PREFIX (do_)
        # 3. Must be a member of the class being decorated and not one inherited from a parent declaration
        methods = inspect.getmembers(
            cls,
            predicate=lambda meth: inspect.isfunction(meth) and meth.__name__.startswith(COMMAND_FUNC_PREFIX)
            and meth in inspect.getmro(cls)[0].__dict__.values())
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

    def on_register(self, cmd) -> None:
        """
        Called by cmd2.Cmd as the first step to registering a CommandSet. The commands defined in this class have
        not be added to the CLI object at this point. Subclasses can override this to perform any initialization
        requiring access to the Cmd object (e.g. configure commands and their parsers based on CLI state data).

        :param cmd: The cmd2 main application
        :type cmd: cmd2.Cmd
        """
        if self._cmd is None:
            self._cmd = cmd
        else:
            raise CommandSetRegistrationError('This CommandSet has already been registered')

    def on_registered(self) -> None:
        """
        Called by cmd2.Cmd after a CommandSet is registered and all its commands have been added to the CLI.
        Subclasses can override this to perform custom steps related to the newly added commands (e.g. setting
        them to a disabled state).
        """
        pass

    def on_unregister(self) -> None:
        """
        Called by ``cmd2.Cmd`` as the first step to unregistering a CommandSet. Subclasses can override this to
        perform any cleanup steps which require their commands being registered in the CLI.
        """
        pass

    def on_unregistered(self) -> None:
        """
        Called by ``cmd2.Cmd`` after a CommandSet has been unregistered and all its commands removed from the CLI.
        Subclasses can override this to perform remaining cleanup steps.
        """
        self._cmd = None
