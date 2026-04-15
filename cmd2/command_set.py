"""Supports the definition of commands in separate classes to be composed into cmd2.Cmd."""

from collections.abc import Mapping
from typing import (
    ClassVar,
    Generic,
)

from .exceptions import CommandSetRegistrationError
from .types import CmdT
from .utils import Settable


class CommandSet(Generic[CmdT]):
    """Base class for defining sets of commands to load in cmd2.

    ``do_``, ``help_``, and ``complete_`` functions differ only in that self is the
    CommandSet instead of the cmd2 app.

    This class is generic over the `Cmd` type it is expected to be loaded into.
    By providing the specific `Cmd` subclass as a type argument
    (e.g., `class MyCommandSet(CommandSet[MyApp]):`), type checkers will know the exact
    type of `self._cmd`, allowing for autocompletion and type validation when accessing
    custom attributes and methods on the main application instance.
    """

    # Default category for commands defined in this CommandSet which have
    # not been explicitly categorized with the @with_category decorator.
    # This value is inherited by subclasses but they can set their own
    # DEFAULT_CATEGORY to place their commands into a custom category.
    DEFAULT_CATEGORY: ClassVar[str] = "CommandSet Commands"

    def __init__(self) -> None:
        """Private reference to the CLI instance in which this CommandSet running.

        This will be set when the CommandSet is registered and it should be
        accessed by child classes using the self._cmd property.
        """
        self._cmd_internal: CmdT | None = None

        self._settables: dict[str, Settable] = {}
        self._settable_prefix = self.__class__.__name__

    @property
    def _cmd(self) -> CmdT:
        """Property for child classes to access self._cmd_internal.

        Using this property ensures that the CommandSet has been registered
        and tells type checkers that self._cmd_internal is not None.

        Subclasses can specify their specific Cmd type during inheritance:

            class MyCommandSet(CommandSet[MyCustomApp]):
                ...

        :raises CommandSetRegistrationError: if CommandSet is not registered.
        """
        if (cmd := self._cmd_internal) is not None:
            return cmd
        raise CommandSetRegistrationError('This CommandSet is not registered')

    def on_register(self, cmd: CmdT) -> None:
        """First step to registering a CommandSet, called by cmd2.Cmd.

        The commands defined in this class have not been added to the CLI object at this point.
        Subclasses can override this to perform any initialization requiring access to the Cmd object
        (e.g. configure commands and their parsers based on CLI state data).

        :param cmd: The cmd2 main application
        :raises CommandSetRegistrationError: if CommandSet is already registered.
        """
        if self._cmd_internal is None:
            self._cmd_internal = cmd
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
        self._cmd_internal = None

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
        if (cmd := self._cmd_internal) is not None:
            if not cmd.always_prefix_settables:
                if settable.name in cmd.settables and settable.name not in self._settables:
                    raise KeyError(f'Duplicate settable: {settable.name}')
            else:
                prefixed_name = f'{self._settable_prefix}.{settable.name}'
                if prefixed_name in cmd.settables and settable.name not in self._settables:
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
