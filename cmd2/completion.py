"""Provides classes and functions related to command-line completion."""

import copy
import re
import sys
from collections.abc import (
    Iterable,
    Iterator,
    Sequence,
)
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    cast,
    overload,
)

from rich.table import Table

from . import string_utils as su

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from rich.protocol import is_renderable

from . import rich_utils as ru


class _UnsetStr(str):
    """Internal sentinel to distinguish between an unset and an explicit empty string."""

    __slots__ = ()


_UNSET_STR = _UnsetStr("")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionItem:
    """A single completion result."""

    # Regular expression to identify whitespace characters that are rendered as
    # control sequences (like ^J or ^I) in the completion menu.
    _CONTROL_WHITESPACE_RE = re.compile(r"\r\n|[\n\r\t\f\v]")

    # The underlying object this completion represents (e.g., str, int, Path).
    # This serves as the default source for 'text' and is used to support
    # object-based validation when this item is used as an argparse choice.
    value: Any = field(kw_only=False)

    # The actual completion string. Defaults to str(value). This should only be
    # set manually if this item is used as an argparse choice and you want the
    # choice string to differ from str(value).
    text: str = _UNSET_STR

    # Optional string for displaying the completion differently in the completion menu.
    # This can contain ANSI style sequences. A plain version is stored in display_plain.
    # If not provided, defaults to the (possibly computed) value of 'text'.
    display: str = _UNSET_STR

    # Optional meta information about completion which displays in the completion menu.
    # This can contain ANSI style sequences. A plain version is stored in display_meta_plain.
    display_meta: str = ""

    # Optional data for completion tables. Length must match the associated argparse
    # argument's table_columns. This is stored internally as a tuple.
    table_data: Sequence[Any] = field(default_factory=tuple)

    # Plain text versions of display fields (stripped of ANSI) for sorting/filtering.
    display_plain: str = field(default="", init=False)
    display_meta_plain: str = field(default="", init=False)

    @classmethod
    def _clean_display(cls, val: str) -> str:
        """Clean a string for display in the completion menu.

        This replaces whitespace characters that are rendered as
        control sequences (like ^J or ^I) with spaces.

        :param val: string to be cleaned
        :return: the cleaned string
        """
        return cls._CONTROL_WHITESPACE_RE.sub(" ", val)

    def __post_init__(self) -> None:
        """Finalize the object after initialization.

        By using the sentinel pattern to distinguish between a field that was never
        set and one explicitly blanked out, this handles the two-stage lifecycle:

        1. Initial creation (usually by a developer-provided choices_provider or completer).
        2. Post-processing by cmd2 via dataclasses.replace(), which may modify fields or
           explicitly set them to empty strings.
        """
        # If the completion string was not provided, derive it from value.
        if isinstance(self.text, _UnsetStr):
            object.__setattr__(self, "text", str(self.value))

        # If the display string was not provided, use text.
        if isinstance(self.display, _UnsetStr):
            object.__setattr__(self, "display", self.text)

        # Clean display and display_meta
        object.__setattr__(self, "display", self._clean_display(self.display))
        object.__setattr__(self, "display_meta", self._clean_display(self.display_meta))

        # Create plain text versions by stripping ANSI sequences.
        # These are stored as attributes for fast access during sorting/filtering.
        object.__setattr__(self, "display_plain", su.strip_style(self.display))
        object.__setattr__(self, "display_meta_plain", su.strip_style(self.display_meta))

        # Make sure all table data objects are renderable by a Rich table.
        renderable_data = [obj if is_renderable(obj) else str(obj) for obj in self.table_data]

        # Convert strings containing ANSI style sequences to Rich Text objects for correct display width.
        object.__setattr__(
            self,
            "table_data",
            ru.prepare_objects_for_rendering(*renderable_data),
        )

    def __deepcopy__(self, memo: dict[int, Any]) -> "CompletionItem":
        """Return a shallow copy of this CompletionItem during a deepcopy operation.

        This is necessary because cmd2 deepcopies argument parsers to keep them unique
        across command instances. This override prevents the deepcopying of
        CompletionItems stored within a parser's 'choices' list.

        Since the 'value' and 'table_data' fields may contain complex objects which
        should not be deep copied, a shallow copy ensures the original object
        references are preserved.
        """
        return copy.copy(self)

    def __str__(self) -> str:
        """Return the completion text."""
        return self.text

    def __eq__(self, other: object) -> bool:
        """Compare this CompletionItem for equality.

        Identity is determined by value, text, display, and display_meta.
        table_data is excluded from equality checks to ensure that items
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

    # Regular expression to identify strings that we should sort numerically
    _NUMERIC_RE = re.compile(
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

    # The collection of CompletionItems. This is stored internally as a tuple.
    items: Sequence[CompletionItem] = field(default_factory=tuple, kw_only=False)

    # If True, indicates the items are already provided in the desired display order.
    # If False, items will be sorted by their display value during initialization.
    is_sorted: bool = False

    # True if every item in this collection has a numeric display string.
    # Used for sorting and alignment.
    numeric_display: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Finalize the object after initialization."""
        from . import utils

        unique_items = utils.remove_duplicates(self.items)

        # Determine if all items have numeric display strings
        numeric_display = bool(unique_items) and all(self._NUMERIC_RE.match(i.display_plain) for i in unique_items)
        object.__setattr__(self, "numeric_display", numeric_display)

        if not self.is_sorted:
            if self.numeric_display:
                # Sort numerically
                unique_items.sort(key=lambda item: float(item.display_plain))
            else:
                # Standard string sort
                unique_items.sort(key=lambda item: utils.DEFAULT_STR_SORT_KEY(item.display_plain))

            object.__setattr__(self, "is_sorted", True)

        object.__setattr__(self, "items", tuple(unique_items))

    @classmethod
    def from_values(cls, values: Iterable[Any], *, is_sorted: bool = False) -> Self:
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

    # Optional hint which prints above completion suggestions
    hint: str = ""

    # Optional message to display if an error occurs during completion
    error: str = ""

    # Optional Rich table which provides more context for the data being completed
    table: Table | None = None

    # If True, the completion engine is allowed to finalize a completion
    # when a single match is found by appending a trailing space and
    # closing any open quotation marks.
    #
    # Set this to False for intermediate or hierarchical matches (such as
    # directories) where the user needs to continue typing the next segment.
    # This flag is ignored if there are multiple matches.
    allow_finalization: bool = True

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
