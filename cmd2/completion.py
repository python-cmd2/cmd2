"""Provides classes and functions related to completion."""

import sys
from collections.abc import (
    Sequence,
)
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from rich.protocol import is_renderable

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


from dataclasses import (
    dataclass,
    field,
)

from . import rich_utils as ru


@dataclass(slots=True)
class Completions:
    """The result and display configuration for a completion operation.

    Note: Validation of data integrity is performed by Cmd.complete() before returning.
    """

    # The list of completions
    matches: list[str] = field(default_factory=list)

    # Optional strings for displaying the matches differently in the completion menu.
    # If populated, it must be the same length as matches.
    display_matches: list[str] = field(default_factory=list)

    # Optional meta information about each match which displays in the completion menu.
    # If populated, it must be the same length as matches.
    display_meta: list[str] = field(default_factory=list)

    # If True and a single match is returned to complete(), then a space will be appended
    # if the match appears at the end of the line
    allow_appended_space: bool = True

    # If True and a single match is returned to complete(), then a closing quote
    # will be added if there is an unmatched opening quote
    allow_closing_quote: bool = True

    # An optional hint which prints above completion suggestions
    completion_hint: str = ""

    # Normally cmd2 uses prompt-toolkit's formatter to columnize the list of completion suggestions.
    # If a custom format is preferred, write the formatted completions to this string. cmd2 will
    # then print it instead of the prompt-toolkit format. ANSI style sequences and newlines are supported
    # when using this value. Even when using formatted_completions, the full matches must still be returned
    # from your completer function. ArgparseCompleter writes its completion tables to this string.
    formatted_completions: str = ""

    # Used by functions like path_complete() and delimiter_complete() to properly
    # quote matches that are completed in a delimited fashion
    matches_delimited: bool = False

    # Set to True before returning matches to complete() in cases where matches have already been sorted.
    # If False, then complete() will sort the matches using self.default_sort_key before they are displayed.
    # This does not affect formatted_completions.
    matches_sorted: bool = False

    def __bool__(self) -> bool:
        """Return True if there are matches, False otherwise."""
        return bool(self.matches)

    def __len__(self) -> int:
        """Return the number of matches."""
        return len(self.matches)

    def validate(self) -> None:
        """Validate data integrity.

        :raises ValueError: if there is an issue with the data.
        """
        num_matches = len(self.matches)

        # Check display_matches
        if self.display_matches and len(self.display_matches) != num_matches:
            raise ValueError(
                f"Mismatched display_matches: expected {num_matches} items "
                f"(to match 'matches'), but got {len(self.display_matches)}."
            )

        # Check display_meta
        if self.display_meta and len(self.display_meta) != num_matches:
            raise ValueError(
                f"Mismatched display_meta: expected {num_matches} items "
                f"(to match 'matches'), but got {len(self.display_meta)}."
            )


class CompletionItem(str):  # noqa: SLOT000
    """Completion item with descriptive text attached.

    See header of this file for more information
    """

    def __new__(cls, value: object, *_args: Any, **_kwargs: Any) -> Self:
        """Responsible for creating and returning a new instance, called before __init__ when an object is instantiated."""
        return super().__new__(cls, value)

    def __init__(self, value: object, descriptive_data: Sequence[Any], *args: Any) -> None:
        """CompletionItem Initializer.

        :param value: the value being completed
        :param descriptive_data: a list of descriptive data to display in the columns that follow
                                 the completion value. The number of items in this list must equal
                                 the number of descriptive headers defined for the argument.
        :param args: args for str __init__
        """
        super().__init__(*args)

        # Make sure all objects are renderable by a Rich table.
        renderable_data = [obj if is_renderable(obj) else str(obj) for obj in descriptive_data]

        # Convert strings containing ANSI style sequences to Rich Text objects for correct display width.
        self.descriptive_data = ru.prepare_objects_for_rendering(*renderable_data)

        # Save the original value to support CompletionItems as argparse choices.
        # cmd2 has patched argparse so input is compared to this value instead of the CompletionItem instance.
        self._orig_value = value

    @property
    def orig_value(self) -> Any:
        """Read-only property for _orig_value."""
        return self._orig_value


@runtime_checkable
class ChoicesProviderFuncBase(Protocol):
    """Function that returns a list of choices in support of completion."""

    def __call__(self) -> list[str]:  # pragma: no cover
        """Enable instances to be called like functions."""


@runtime_checkable
class ChoicesProviderFuncWithTokens(Protocol):
    """Function that returns a list of choices in support of completion and accepts a dictionary of prior arguments."""

    def __call__(self, *, arg_tokens: dict[str, list[str]] = {}) -> list[str]:  # pragma: no cover  # noqa: B006
        """Enable instances to be called like functions."""


ChoicesProviderFunc = ChoicesProviderFuncBase | ChoicesProviderFuncWithTokens


@runtime_checkable
class CompleterFuncBase(Protocol):
    """Function to support completion with the provided state of the user prompt."""

    def __call__(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> Completions:  # pragma: no cover
        """Enable instances to be called like functions."""


@runtime_checkable
class CompleterFuncWithTokens(Protocol):
    """Function to support completion with the provided state of the user prompt, accepts a dictionary of prior args."""

    def __call__(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        *,
        arg_tokens: dict[str, list[str]] = {},  # noqa: B006
    ) -> Completions:  # pragma: no cover
        """Enable instances to be called like functions."""


CompleterFunc = CompleterFuncBase | CompleterFuncWithTokens
