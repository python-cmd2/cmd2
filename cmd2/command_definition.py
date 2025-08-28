"""Supports the definition of commands in separate classes to be composed into cmd2.Cmd."""

from collections.abc import Callable, Mapping
from typing import (
    TYPE_CHECKING,
    TypeVar,
)

from .constants import (
    CLASS_ATTR_DEFAULT_HELP_CATEGORY,
    COMMAND_FUNC_PREFIX,
)
from .exceptions import (
    CommandSetRegistrationError,
)
from .utils import (
    Settable,
)

if TYPE_CHECKING:  # pragma: no cover
    import cmd2

#: Callable signature for a basic command  function
#: Further refinements are needed to define the input parameters
CommandFunc = Callable[..., bool | None]

CommandSetType = TypeVar('CommandSetType', bound=type['CommandSet'])


def with_default_category(category: str, *, heritable: bool = True) -> Callable[[CommandSetType], CommandSetType]:
    """Apply a category to all ``do_*`` command methods in a class that do not already have a category specified (Decorator).

    CommandSets that are decorated by this with `heritable` set to True (default) will set a class attribute that is
    inherited by all subclasses unless overridden. All commands of this CommandSet and all subclasses of this CommandSet
    that do not declare an explicit category will be placed in this category. Subclasses may use this decorator to
    override the default category.

    If `heritable` is set to False, then only the commands declared locally to this CommandSet will be placed in the
    specified category. Dynamically created commands and commands declared in sub-classes will not receive this
    category.

    :param category: category to put all uncategorized commands in
    :param heritable: Flag whether this default category should apply to sub-classes. Defaults to True
    :return: decorator function
    """

    def decorate_class(cls: CommandSetType) -> CommandSetType:
        if heritable:
            setattr(cls, CLASS_ATTR_DEFAULT_HELP_CATEGORY, category)

        import inspect

        from .constants import (
            CMD_ATTR_HELP_CATEGORY,
        )
        from .decorators import (
            with_category,
        )

        # get members of the class that meet the following criteria:
        # 1. Must be a function
        # 2. Must start with COMMAND_FUNC_PREFIX (do_)
        # 3. Must be a member of the class being decorated and not one inherited from a parent declaration
        methods = inspect.getmembers(
            cls,
            predicate=lambda meth: inspect.isfunction(meth)
            and meth.__name__.startswith(COMMAND_FUNC_PREFIX)
            and meth in inspect.getmro(cls)[0].__dict__.values(),
        )
        category_decorator = with_category(category)
        for method in methods:
            if not hasattr(method[1], CMD_ATTR_HELP_CATEGORY):
                setattr(cls, method[0], category_decorator(method[1]))
        return cls

    return decorate_class


class CommandSet:
    """Base class for defining sets of commands to load in cmd2.

    ``with_default_category`` can be used to apply a default category to all commands in the CommandSet.

    ``do_``, ``help_``, and ``complete_`` functions differ only in that self is the CommandSet instead of the cmd2 app
    """

    def __init__(self) -> None:
        """Private reference to the CLI instance in which this CommandSet running.

        This will be set when the CommandSet is registered and it should be
        accessed by child classes using the self._cmd property.
        """
        self.__cmd_internal: cmd2.Cmd | None = None

        self._settables: dict[str, Settable] = {}
        self._settable_prefix = self.__class__.__name__

    @property
    def _cmd(self) -> 'cmd2.Cmd':
        """Property for child classes to access self.__cmd_internal.

        Using this property ensures that self.__cmd_internal has been set
        and it tells type checkers that it's no longer a None type.

        Override this property to specify a more specific return type for static
        type checking. The typing.cast function can be used to assert to the
        type checker that the parent cmd2.Cmd instance is of a more specific
        subclass, enabling better autocompletion and type safety in the child class.

        For example:

            @property
            def _cmd(self) -> CustomCmdApp:
                return cast(CustomCmdApp, super()._cmd)


        :raises CommandSetRegistrationError: if CommandSet is not registered.
        """
        if self.__cmd_internal is None:
            raise CommandSetRegistrationError('This CommandSet is not registered')
        return self.__cmd_internal

    def on_register(self, cmd: 'cmd2.Cmd') -> None:
        """First step to registering a CommandSet, called by cmd2.Cmd.

        The commands defined in this class have not been added to the CLI object at this point.
        Subclasses can override this to perform any initialization requiring access to the Cmd object
        (e.g. configure commands and their parsers based on CLI state data).

        :param cmd: The cmd2 main application
        :raises CommandSetRegistrationError: if CommandSet is already registered.
        """
        if self.__cmd_internal is None:
            self.__cmd_internal = cmd
        else:
            raise CommandSetRegistrationError('This CommandSet has already been registered')

    def on_registered(self) -> None:
        """2nd step to registering, called by cmd2.Cmd after a CommandSet is registered and all its commands have been added.

        Subclasses can override this to perform custom steps related to the newly added commands (e.g. setting
        them to a disabled state).
        """

    def on_unregister(self) -> None:
        """First step to unregistering a CommandSet, called by ``cmd2.Cmd``.

        Subclasses can override this to perform any cleanup steps which require their commands being registered in the CLI.
        """

    def on_unregistered(self) -> None:
        """2nd step to unregistering, called by ``cmd2.Cmd`` after a CommandSet is unregistered and all its commands removed.

        Subclasses can override this to perform remaining cleanup steps.
        """
        self.__cmd_internal = None

    @property
    def settable_prefix(self) -> str:
        """Read-only accessor for the underlying private settable_prefix field."""
        return self._settable_prefix

    @property
    def settables(self) -> Mapping[str, Settable]:
        """Read-only accessor for the underlying private settables field."""
        return self._settables

    def add_settable(self, settable: Settable) -> None:
        """Add a settable parameter to the CommandSet.

        :param settable: Settable object being added
        """
        if self.__cmd_internal is not None:
            if not self._cmd.always_prefix_settables:
                if settable.name in self._cmd.settables and settable.name not in self._settables:
                    raise KeyError(f'Duplicate settable: {settable.name}')
            else:
                prefixed_name = f'{self._settable_prefix}.{settable.name}'
                if prefixed_name in self._cmd.settables and settable.name not in self._settables:
                    raise KeyError(f'Duplicate settable: {settable.name}')
        self._settables[settable.name] = settable

    def remove_settable(self, name: str) -> None:
        """Remove a settable parameter from the CommandSet.

        :param name: name of the settable being removed
        :raises KeyError: if the Settable matches this name
        """
        try:
            del self._settables[name]
        except KeyError as exc:
            raise KeyError(name + " is not a settable parameter") from exc

    def sigint_handler(self) -> bool:
        """Handle a SIGINT that occurred for a command in this CommandSet.

        :return: True if this completes the interrupt handling and no KeyboardInterrupt will be raised.
                 False to raise a KeyboardInterrupt.
        """
        return False
