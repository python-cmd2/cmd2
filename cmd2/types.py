"""Defines common types used throughout cmd2."""

from collections.abc import (
    Callable,
    Mapping,
    Sequence,
)
from typing import (
    TYPE_CHECKING,
    TypeAlias,
    TypeVar,
    Union,
)

if TYPE_CHECKING:  # pragma: no cover
    from .cmd2 import Cmd
    from .command_definition import CommandSet
    from .completion import Choices, CompletionItem, Completions

# A Cmd or CommandSet
CmdOrSet = TypeVar("CmdOrSet", bound=Union["Cmd", "CommandSet"])

##################################################
# Types used in choices_providers and completers
##################################################

# Represents the parsed tokens from argparse during completion
ArgTokens: TypeAlias = Mapping[str, Sequence[str]]

# Represents a type that can be matched against when completing.
# Strings are matched directly while CompletionItems are matched
# against their 'text' member.
Matchable: TypeAlias = Union[str, "CompletionItem"]

##################################################
# choices_provider function types
##################################################

# Unbound choices_provider function types used by argparse-based completion.
# These expect a Cmd or CommandSet instance as the first argument.
ChoicesProviderUnbound: TypeAlias = (
    # Basic: (self) -> Choices
    Callable[[CmdOrSet], "Choices"]
    |
    # Context-aware: (self, arg_tokens) -> Choices
    Callable[[CmdOrSet, "ArgTokens"], "Choices"]
)

##################################################
# completer function types
##################################################

# Unbound completer function types used by argparse-based completion.
# These expect a Cmd or CommandSet instance as the first argument.
CompleterUnbound: TypeAlias = (
    # Basic: (self, text, line, begidx, endidx) -> Completions
    Callable[[CmdOrSet, str, str, int, int], "Completions"]
    |
    # Context-aware: (self, text, line, begidx, endidx, arg_tokens) -> Completions
    Callable[[CmdOrSet, str, str, int, int, ArgTokens], "Completions"]
)

# A bound completer used internally by cmd2 for basic completion logic.
# The 'self' argument is already tied to an instance and is omitted.
# Format: (text, line, begidx, endidx) -> Completions
CompleterBound: TypeAlias = Callable[[str, str, int, int], "Completions"]
