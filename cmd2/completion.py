"""Provides classes and functions related to completion."""

import re
import sys
from collections.abc import (
    Callable,
    Collection,
    Iterator,
    Sequence,
)
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    TYPE_CHECKING,
    Any,
    TypeAlias,
    cast,
    overload,
)

if TYPE_CHECKING:
    from .cmd2 import Cmd
    from .command_definition import CommandSet

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from rich.protocol import is_renderable

from . import rich_utils as ru
from . import utils

# Regular expression to identify strings which we should sort numerically
NUMERIC_RE = re.compile(
    r"""
    ^              # Start of string
    [-+]?          # Optional sign
    (?:            # Start of non-capturing group
        \d+\.?\d*  # Matches 123 or 123. or 123.45
        |          # OR
        \.\d+      # Matches .45
    )              # End of group
    $              # End of string
""",
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionItem:
    """A single completion result."""

    # The underlying object this completion represents (e.g., str, int, Path).
    # This is used to support argparse choices validation.
    value: Any = field(kw_only=False)

    # The actual string that will be inserted into the command line.
    # If not provided, it defaults to str(value).
    text: str = ""

    # Optional string for displaying the completion differently in the completion menu.
    display: str = ""

    # Optional meta information about completion which displays in the completion menu.
    display_meta: str = ""

    # Optional row data for completion tables. Length must match the associated argparse
    # argument's table_header. This is stored internally as a tuple.
    table_row: Sequence[Any] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Finalize the object after initialization."""
        # Derive text from value if it wasn't explicitly provided
        if not self.text:
            object.__setattr__(self, "text", str(self.value))

        # Ensure display is never blank.
        if not self.display:
            object.__setattr__(self, "display", self.text)

        # Make sure all table row objects are renderable by a Rich table.
        renderable_data = [obj if is_renderable(obj) else str(obj) for obj in self.table_row]

        # Convert strings containing ANSI style sequences to Rich Text objects for correct display width.
        object.__setattr__(
            self,
            'table_row',
            ru.prepare_objects_for_rendering(*renderable_data),
        )

    def __str__(self) -> str:
        """Return the completion text."""
        return self.text

    def __eq__(self, other: object) -> bool:
        """Compare this CompletionItem for equality.

        Identity is determined by value, text, display, and display_meta.
        table_row is excluded from equality checks to ensure that items
        with the same functional value are treated as duplicates.

        Also supports comparison against non-CompletionItems to facilitate argparse
        choices validation.
        """
        if isinstance(other, CompletionItem):
            return (
                self.value == other.value
                and self.text == other.text
                and self.display == other.display
                and self.display_meta == other.display_meta
            )

        # This supports argparse validation when a CompletionItem is used as a choice
        return bool(self.value == other)

    def __hash__(self) -> int:
        """Return a hash of the item's identity fields."""
        return hash((self.value, self.text, self.display, self.display_meta))


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionResultsBase:
    """Base class for results containing a collection of CompletionItems."""

    # The collection of CompletionItems. This is stored internally as a tuple.
    items: Sequence[CompletionItem] = field(default_factory=tuple, kw_only=False)

    # If True, indicates the items are already provided in the desired display order.
    # If False, items will be sorted by their display value during initialization.
    is_sorted: bool = False

    def __post_init__(self) -> None:
        """Finalize the object after initialization."""
        unique_items = utils.remove_duplicates(self.items)
        if not self.is_sorted:
            if all_display_numeric(unique_items):
                # Sort numerically
                unique_items.sort(key=lambda item: float(item.display))
            else:
                # Standard string sort
                unique_items.sort(key=lambda item: utils.DEFAULT_STR_SORT_KEY(item.display))

            object.__setattr__(self, "is_sorted", True)

        object.__setattr__(self, "items", tuple(unique_items))

    @classmethod
    def from_values(cls, values: Iterator[Any], *, is_sorted: bool = False) -> Self:
        """Create a CompletionItem instance from arbitrary objects.

        :param values: the raw objects (e.g. strs, ints, Paths) to be converted into CompletionItems.
        :param is_sorted: whether the values are already in the desired order.
        """
        items = [v if isinstance(v, CompletionItem) else CompletionItem(value=v) for v in values]
        return cls(items=items, is_sorted=is_sorted)

    def to_strings(self) -> tuple[str, ...]:
        """Return a tuple of the completion strings (the 'text' field of each item)."""
        return tuple(item.text for item in self.items)

    # --- Sequence Protocol Functions ---

    def __bool__(self) -> bool:
        """Return True if there are items, False otherwise."""
        return bool(self.items)

    def __len__(self) -> int:
        """Return the number of items."""
        return len(self.items)

    def __contains__(self, item: object) -> bool:
        """Return True if the item is present in the collection."""
        return item in self.items

    def __iter__(self) -> Iterator[CompletionItem]:
        """Allow the collection to be used in loops or comprehensions."""
        return iter(self.items)

    def __reversed__(self) -> Iterator[CompletionItem]:
        """Allow the collection to be iterated in reverse order using reversed()."""
        return reversed(self.items)

    @overload
    def __getitem__(self, index: int) -> CompletionItem: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[CompletionItem, ...]: ...

    def __getitem__(self, index: int | slice) -> CompletionItem | tuple[CompletionItem, ...]:
        """Retrieve an item by its integer index or a range of items using a slice."""
        items_tuple = cast(tuple[CompletionItem, ...], self.items)
        return items_tuple[index]


@dataclass(frozen=True, slots=True, kw_only=True)
class Choices(CompletionResultsBase):
    """A collection of potential values available for completion, typically provided by a choice provider."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Completions(CompletionResultsBase):
    """The results of a completion operation."""

    # An optional hint which prints above completion suggestions
    completion_hint: str = ""

    # Optional message to display if an error occurs during completion
    completion_error: str = ""

    # An optional table string populated by the argparse completer
    completion_table: str = ""

    # If True, the completion engine is allowed to finalize a completion
    # when a single match is found by appending a trailing space and
    # closing any open quotation marks.
    #
    # Set this to False for intermediate or hierarchical matches (such as
    # directories) where the user needs to continue typing the next segment.
    # This flag is ignored if there are multiple matches.
    allow_finalization: bool = True

    # If True, indicates that matches represent portions of a hierarchical
    # string (e.g., paths or "a::b::c"). This signals the shell to use
    # specialized quoting logic.
    is_delimited: bool = False

    #####################################################################
    # The following fields are used internally by cmd2 to handle
    # automatic quoting and are not intended for user modification.
    #####################################################################

    # Whether to add an opening quote to the matches.
    _add_opening_quote: bool = False

    # The starting index of the user-provided search text within a full match.
    # This accounts for leading shortcuts (e.g., in '?cmd', the offset is 1).
    # Used to ensure opening quotes are inserted after the shortcut rather than before it.
    _search_text_offset: int = 0

    # The quote character to use if adding an opening or closing quote to the matches.
    _quote_char: str = ""


def all_display_numeric(items: Collection[CompletionItem]) -> bool:
    """Return True if items is non-empty and every item.display is a numeric string."""
    return bool(items) and all(NUMERIC_RE.match(item.display) for item in items)


#############################################
# choices_provider function types
#############################################

# Represents the parsed tokens from argparse during completion
ArgTokens: TypeAlias = dict[str, list[str]]

# Unbound choices_provider function types used by argparse-based completion.
# These expect a Cmd or CommandSet instance as the first argument.
ChoicesProviderUnbound: TypeAlias = (
    # Basic: (self) -> Choices
    Callable[["Cmd"], Choices]
    | Callable[["CommandSet"], Choices]
    |
    # Context-aware: (self, arg_tokens) -> Choices
    Callable[["Cmd", ArgTokens], Choices]
    | Callable[["CommandSet", ArgTokens], Choices]
)

#############################################
# completer function types
#############################################

# Unbound completer function types used by argparse-based completion.
# These expect a Cmd or CommandSet instance as the first argument.
CompleterUnbound: TypeAlias = (
    # Basic: (self, text, line, begidx, endidx) -> Completions
    Callable[["Cmd", str, str, int, int], Completions]
    | Callable[["CommandSet", str, str, int, int], Completions]
    |
    # Context-aware: (self, text, line, begidx, endidx, arg_tokens) -> Completions
    Callable[["Cmd", str, str, int, int, ArgTokens], Completions]
    | Callable[["CommandSet", str, str, int, int, ArgTokens], Completions]
)

# A bound completer used internally by cmd2 for basic completion logic.
# The 'self' argument is already tied to an instance and is omitted.
# Format: (text, line, begidx, endidx) -> Completions
CompleterBound: TypeAlias = Callable[[str, str, int, int], Completions]

# Represents a type that can be matched against when completing.
# Strings are matched directly while CompletionItems are matched
# against their 'text' member.
Matchable: TypeAlias = str | CompletionItem
