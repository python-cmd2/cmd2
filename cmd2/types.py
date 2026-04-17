"""Defines common types used throughout cmd2."""

from collections.abc import (
    Callable,
    Mapping,
    Sequence,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    ParamSpec,
    TypeAlias,
    TypeVar,
    Union,
)

if TYPE_CHECKING:  # pragma: no cover
    from .cmd2 import Cmd
    from .command_set import CommandSet
    from .completion import Choices, Completions

P = ParamSpec("P")


##################################################################################################
# Cmd and CommandSet Aliases (For basic inputs)
#
# Use these for arguments where the function can handle either a Cmd or a CommandSet.
# Note: The function logic must be able to handle both types.
#
# If the function returns the object it was passed, using these aliases will cause
# the IDE to "lose track" of the specific subclass. Use the Generics below instead.
##################################################################################################

# A Cmd or CommandSet instance
CmdOrSet: TypeAlias = Union["Cmd", "CommandSet[Any]"]

# A Cmd or CommandSet class
CmdOrSetClass: TypeAlias = type["Cmd"] | type["CommandSet[Any]"]


##################################################################################################
# Cmd and CommandSet Generics (Subclass Tracking)
#
# Use these when you need to track a specific subclass through a function.
# This ensures that if you pass in 'CustomCmd', the type checker knows it's
# still a 'CustomCmd' (not just a generic 'Cmd') when it comes out.
##################################################################################################

# Tracks a specific subclass instance of Cmd
CmdT = TypeVar("CmdT", bound="Cmd")

# Tracks a specific subclass instance of CommandSet
CommandSetT = TypeVar("CommandSetT", bound="CommandSet[Any]")

# Tracks the specific subclass instance (either a Cmd or CommandSet)
CmdOrSetT = TypeVar("CmdOrSetT", bound=CmdOrSet)

# Tracks the specific class itself (either a Cmd or CommandSet class)
CmdOrSetClassT = TypeVar("CmdOrSetClassT", bound=CmdOrSetClass)


##################################################################################################
# Command Function Types
##################################################################################################

# A bound cmd2 command function (e.g. do_command).
# The 'self' argument is already tied to an instance and is omitted.
BoundCommandFunc: TypeAlias = Callable[..., bool | None]

# An unbound cmd2 command function (e.g. the class method do_command).
# The 'self' argument can be either a Cmd or CommandSet instance.
UnboundCommandFunc: TypeAlias = Callable[Concatenate[CmdOrSetT, P], bool | None]


##################################################################################################
# Types used in choices_providers and completers
##################################################################################################

# Represents the parsed tokens from argparse during completion
ArgTokens: TypeAlias = Mapping[str, Sequence[str]]

##################################################
# choices_provider function types
##################################################

# Unbound choices_provider function types used by argparse-based completion.
# These expect a Cmd or CommandSet instance as the first argument.
UnboundChoicesProvider: TypeAlias = (
    # Basic: (self) -> Choices
    Callable[[CmdOrSetT], "Choices"]
    # Context-aware: (self, arg_tokens) -> Choices
    | Callable[[CmdOrSetT, ArgTokens], "Choices"]
)

##################################################
# completer function types
##################################################

# Unbound completer function types used by argparse-based completion.
# These expect a Cmd or CommandSet instance as the first argument.
UnboundCompleter: TypeAlias = (
    # Basic: (self, text, line, begidx, endidx) -> Completions
    Callable[[CmdOrSetT, str, str, int, int], "Completions"]
    # Context-aware: (self, text, line, begidx, endidx, arg_tokens) -> Completions
    | Callable[[CmdOrSetT, str, str, int, int, ArgTokens], "Completions"]
)

# A bound completer used internally by cmd2 for basic completion logic.
# The 'self' argument is already tied to an instance and is omitted.
# Format: (text, line, begidx, endidx) -> Completions
BoundCompleter: TypeAlias = Callable[[str, str, int, int], "Completions"]
