"""Build argparse parsers from type-annotated function signatures.

.. warning:: Experimental

   This module is experimental and its behavior may change in future releases.

The :func:`with_annotated` decorator inspects a command function's type hints and
default values to build a ``Cmd2ArgumentParser``.  :class:`Argument` and
:class:`Option` metadata classes give finer per-parameter control via
``typing.Annotated``.

Parameters without defaults become positional arguments; parameters with defaults
become ``--option`` flags; keyword-only parameters (after ``*``) are always options.
A ``bool`` option is a flag, not a value: when absent it means ``False`` (or ``None``
for ``bool | None``), so it defaults to that and is never ``required``.  A ``*args``
parameter becomes a variadic positional accepting zero or more values (``nargs='*'``),
collected into a tuple.  Underscores in a parameter name become dashes in the generated
flag (``dry_run`` -> ``--dry-run``); pass an explicit ``Option("--my_flag")`` to opt out.
Positional-only parameters (before ``/``) and ``**kwargs`` raise ``TypeError``.  The parameter
names ``dest`` and ``subcommand`` are reserved; ``cmd2_statement`` receives the parsed
``Statement`` and (with ``base_command=True``) ``cmd2_handler`` receives the subcommand handler::

    class MyApp(cmd2.Cmd):
        @cmd2.with_annotated
        def do_greet(self, name: str, count: int = 1, loud: bool = False):
            for _ in range(count):
                msg = f"Hello {name}"
                self.poutput(msg.upper() if loud else msg)

Use ``Annotated`` with :class:`Argument` or :class:`Option` for finer
control over individual parameters::

    from typing import Annotated

    class MyApp(cmd2.Cmd):
        def color_choices(self) -> cmd2.Choices:
            return cmd2.Choices.from_values(["red", "green", "blue"])

        @cmd2.with_annotated
        def do_paint(
            self,
            item: str,
            color: Annotated[str, Option("--color", "-c",
                                         choices_provider=color_choices,
                                         help_text="Color to use")] = "blue",
        ):
            self.poutput(f"Painting {item} {color}")

How annotations map to argparse settings:

- ``str`` -- default string argument
- ``int``, ``float`` -- sets ``type=``
- ``bool`` option -- ``--flag / --no-flag`` via ``BooleanOptionalAction``; defaults to
  ``False`` (or ``None`` for ``bool | None``) when omitted, so it is never ``required``
- positional ``bool`` -- parsed from ``true/false``, ``yes/no``, ``on/off``, ``1/0``
- ``pathlib.Path`` -- sets ``type=Path``
- ``enum.Enum`` subclass -- ``type=converter``, ``choices`` from member values
- ``decimal.Decimal`` -- sets ``type=Decimal``
- ``Literal[...]`` -- ``type=converter`` and ``choices`` from the literal values
- ``list[T]`` / ``set[T]`` / ``tuple[T, ...]`` -- ``nargs='+'`` (or ``'*'`` with a default or ``| None``)
- ``tuple[T, T]`` (fixed arity, same type) -- ``nargs=N`` with ``type=T``
- ``*args: T`` -- variadic positional (``nargs='*'``); ``T`` is each value's type, not the
  collected tuple.  ``Annotated[T, Argument(...)]`` metadata is honored
- ``T | None`` (no default) -- positional with ``nargs='?'`` (0-or-1 tokens)
- ``T | None = None`` -- ``--flag`` option with ``default=None``

A value option with no default is made ``required`` (omitting it would pass ``None``,
violating a non-Optional hint); annotate it ``T | None`` or give it a default to make it
omittable.

Explicit ``Option(action=...)`` is type-checked so the parsed result matches the
declared type:

- ``store_true`` / ``store_false`` -- require a ``bool`` parameter (``type=`` is dropped;
  argparse supplies the ``False``/``True`` default)
- ``count`` -- requires an ``int`` parameter; defaults to ``0`` (``None`` for ``int | None``)
- ``append`` / ``extend`` -- require a ``list[T]`` parameter and default to ``[]``
  (``append`` takes one value per flag; ``extend`` takes ``nargs`` values per flag)
- ``store_const`` / ``append_const`` -- store the ``Option(const=...)`` value (``type=`` is dropped).
  The action is inferred from the type when ``action=`` is omitted: a scalar ``Option(const=X)`` becomes
  ``store_const`` (present -> ``const``, absent -> the default, which must exist or be ``T | None``); a
  ``list[T]`` ``Option(const=X)`` becomes ``append_const`` (each flag appends ``const``; defaults to ``[]``).
  A scalar ``Option(const=X)`` given an explicit ``nargs`` (e.g. ``nargs='?'``) instead keeps the ``store``
  action for argparse's optional-value idiom (absent -> default, bare flag -> ``const``, ``flag VALUE`` ->
  converted ``VALUE``); the ``const`` is stored verbatim and must match the declared type.
  ``const`` is validated against the declared type and is rejected on a positional ``Argument`` (argparse
  ignores it there)
- a custom :class:`argparse.Action` subclass -- passed straight through to ``add_argument``.
  The user's class owns storage, so the collection-casting wrapper is dropped and the action-specific
  type/const/collection-shape constraints are skipped.  The type-inferred converter, default, and
  ``required`` are still applied; the action receives them like any hand-built ``add_argument`` call.
  ``action='help'`` and ``action='version'`` are not supported.

The zero-argument actions above (``store_true`` / ``store_false`` / ``count`` / ``store_const`` /
``append_const``) take no value from the command line, so the value-oriented metadata inferred from
the type is dropped before ``add_argument`` is called: the ``type=`` converter, the static
``choices``, and any inferred tab-completer (e.g. the path completer for ``Path``).  There is nothing
to complete or convert on a value-less action.  A completer that was only *inferred* from the type is
dropped silently, but a ``completer`` / ``choices_provider`` you supply *explicitly* on such an action
is a contradiction and raises ``TypeError`` (matching argparse, which rejects it outright).  Actions
that *do* consume values (``append`` / ``extend`` on a ``list[T]``, or a plain value option) keep the
inferred converter and completer unchanged.

The metadata classes refuse a handful of ``add_argument`` kwargs that the decorator derives from the
signature itself, so passing them through ``Argument(...)`` / ``Option(...)`` raises ``TypeError``:
``type`` (from the annotation), ``dest`` (from the parameter name), ``help`` (use the ``help_text``
parameter, which maps to it -- a raw ``help`` would silently shadow it), and -- on ``Argument`` only
-- ``action`` / ``required`` (which have no meaning on a positional).  Every other ``add_argument``
parameter, including those registered via
:func:`~cmd2.argparse_utils.register_argparse_argument_parameter`, passes through unchanged.

A ``default`` may be supplied either as the function-signature default (``param: T = v``) or as
``Argument(default=v)`` / ``Option(default=v)`` -- the two forms are equivalent.  Specifying both at
once raises ``TypeError`` (the value would have two sources of truth), and ``argparse.SUPPRESS`` is
rejected as a default from either source because it would remove the keyword argument the function
expects.

Parser-level customization is forwarded to :class:`~cmd2.Cmd2ArgumentParser`'s constructor via PEP
692 ``**parser_kwargs: Unpack[Cmd2ParserKwargs]``.  Anything the parser ctor accepts -- ``description``,
``epilog``, ``prog``, ``usage``, ``parents``, ``argument_default``, ``prefix_chars``,
``fromfile_prefix_chars``, ``conflict_handler``, ``add_help``, ``allow_abbrev``, ``exit_on_error``,
``formatter_class``, ``ap_completer_type``, and on Python >= 3.14 ``suggest_on_error`` / ``color`` --
flows straight through; the :class:`Cmd2ParserKwargs` ``TypedDict`` is the single source of truth
and gives type-checkers/IDEs autocomplete on the decorator's call site.  ``parser_class`` stays as
its own explicit kwarg because it selects the class itself, not a value passed to it.  Two
behaviors layer on top of the raw passthrough: if ``description`` is omitted, the first paragraph
of ``func.__doc__`` (up to the first blank line) is used so docstrings double as help text without
leaking ``:param:`` directives; and ``prog`` is rejected with ``subcommand_to`` because cmd2
rewrites it from the parent command's hierarchy.  Mutually exclusive groups accept
``Group(required=True)`` to require exactly one member; the same flag on a plain ``groups=`` entry
raises ``ValueError`` (argparse's ``add_argument_group`` has no ``required``).

Unsupported patterns (raise ``TypeError``):

- a non-Optional type with a ``None`` default (e.g. ``name: str = None``); annotate it
  ``T | None`` or use a non-None default.  ``Any``/``object``/unannotated are exempt
- a scalar type with no converter (e.g. ``datetime.datetime``, ``uuid.UUID``, ``bytes``,
  or any custom class), which would silently arrive as a plain string.  Supported scalars
  are ``str``, ``int``, ``float``, ``bool``, ``decimal.Decimal``, ``pathlib.Path``,
  ``enum.Enum`` subclasses, and ``Literal[...]`` (``str``/``Any``/``object`` pass through raw)
- ``str | int`` -- a union of multiple non-None types is ambiguous
- ``tuple[int, str, float]`` -- mixed element types (argparse applies one ``type=`` per argument)
- ``*args: tuple[T, ...]`` (or any collection element) -- the annotation is each value's type,
  so a collection element means a tuple-of-collections; annotate the element, e.g. ``*args: str``
- ``*args: Annotated[T, Option(...)]`` -- ``*args`` is always positional; use ``Argument()``
- ``*args: Annotated[T, Argument(nargs=N)]`` -- ``*args`` arity is fixed to ``nargs='*'``
- a keyword-only parameter annotated with ``Argument()`` -- it marks a positional; use ``Option()``
- a required option (no default, not ``T | None``) in a ``mutually_exclusive_groups`` group --
  only one member is supplied, so the others arrive as ``None``; give it a default or ``T | None``
- ``Annotated[T, Argument(nargs=N)]`` producing a list (``'*'``, ``'+'``, integer ``>= 1``)
  on a non-collection ``T``; use ``list[T]`` or ``tuple[T, ...]`` to match the runtime shape
- ``Annotated[tuple[T, T], Argument(nargs=N)]`` where ``N`` differs from the tuple's arity
- ``Option(action=...)`` whose result type mismatches the declared type, an unsupported action,
  or a non-list action on a collection (use ``append``/``extend``/``append_const`` with ``list[T]``)
- a variable-arity positional (``T | None``, ``list[T]``, ``tuple[T, ...]``) followed by another
  positional -- it must come last (``def f(self, a: str, *rest: str)`` is fine)

When combining ``Annotated`` with ``Optional``, the union should go *inside*:
``Annotated[T | None, meta]``.  ``Annotated[T, meta] | None`` is ambiguous and raises -- unless the
inner type already carries the ``None`` (``Annotated[T | None, meta] | None``), in which case the
redundant outer ``| None`` is accepted as equivalent to ``Annotated[T | None, meta]``.

``Path`` and ``Enum`` annotations also get automatic tab completion.  A user-supplied
``choices_provider`` or ``completer`` drives completion in place of the inferred static
``choices``, while the inferred ``type`` converter is kept so values still coerce to the
declared type (an ``Enum`` to its member, ``Literal[1, 2]`` to ``int``) and out-of-type
values are rejected at parse time.  An ``Enum`` accepts both member values and member names on the
command line (completion and ``--help`` show the values).

An explicit ``choices=`` is reconciled with the inferred type rather than fighting it: its values are
run through the inferred ``type`` converter so they match argparse's post-conversion comparison
(``Annotated[int, Option('--n', choices=['1', '2'])]`` becomes ``choices=[1, 2]``, so ``--n 1``
matches; a value the converter rejects is a build-time ``TypeError``), and an explicit ``choices=``
takes precedence over a *type-inferred* completer (the ``Path`` completer is dropped so the choices
drive both validation and completion).  A ``choices_provider`` / ``completer`` you supply yourself
still wins over ``choices=``.
"""

import argparse
import decimal
import enum
import functools
import inspect
import types
from collections.abc import Callable, Container, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    TypedDict,
    TypeVar,
    Union,
    Unpack,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from rich.table import Column

from . import constants
from .argparse_utils import DEFAULT_ARGUMENT_PARSER, Cmd2ArgumentParser, SubcommandSpec
from .completion import CompletionItem
from .decorators import _parse_positionals
from .exceptions import Cmd2ArgparseError
from .rich_utils import Cmd2HelpFormatter, HelpContent
from .types import CmdOrSetT, UnboundChoicesProvider, UnboundCompleter

if TYPE_CHECKING:
    from .argparse_completer import ArgparseCompleter

#: ``nargs`` values accepted by cmd2's patched ``add_argument`` (incl. ranged tuples).
_NargsValue = int | str | tuple[int] | tuple[int, int] | tuple[int, float]


class Cmd2ParserKwargs(TypedDict, total=False):
    """Forwarded ctor kwargs for :class:`~cmd2.Cmd2ArgumentParser`.

    Single source of truth for the parser-construction kwargs accepted by
    :func:`with_annotated` and :func:`build_parser_from_function` via PEP 692
    ``Unpack[Cmd2ParserKwargs]``. Adding a new ctor kwarg to
    :class:`~cmd2.Cmd2ArgumentParser` only needs a matching field here -- the
    decorator picks it up automatically and IDEs/type-checkers surface it on
    the call site.

    All fields are optional (``total=False``); omit a key to use argparse's
    default. ``suggest_on_error`` and ``color`` only take effect on
    Python >= 3.14, where :class:`~cmd2.Cmd2ArgumentParser` forwards them to
    the stdlib parent.
    """

    prog: str | None
    usage: str | None
    description: HelpContent | None
    epilog: HelpContent | None
    parents: Sequence[argparse.ArgumentParser]
    formatter_class: type[Cmd2HelpFormatter]
    prefix_chars: str
    fromfile_prefix_chars: str | None
    argument_default: Any
    conflict_handler: str
    add_help: bool
    allow_abbrev: bool
    exit_on_error: bool
    suggest_on_error: bool
    color: bool
    ap_completer_type: "type[ArgparseCompleter] | None"


# ---------------------------------------------------------------------------
# Metadata classes
# ---------------------------------------------------------------------------

#: Sentinel marking "no value assigned" (a builder slot, or an unset ``const``).
#: Defined here so the metadata classes can use it as a default before the builder section.
_UNSET: Any = object()


class _BaseArgMetadata:
    """Shared fields for ``Argument`` and ``Option`` metadata."""

    _KWARGS_MAP: ClassVar[dict[str, str]] = {
        "help_text": "help",
        "metavar": "metavar",
        "choices": "choices",
        "choices_provider": "choices_provider",
        "completer": "completer",
        "table_columns": "table_columns",
        "suppress_tab_hint": "suppress_tab_hint",
        "nargs": "nargs",
    }

    #: ``add_argument`` kwargs that ``@with_annotated`` derives from the function signature
    #: itself (or exposes under a different name), so the metadata classes refuse to accept them
    #: as ``extra_kwargs``: setting them there would silently disagree with (or be overridden by)
    #: the inferred value.  ``type`` comes from the annotation, ``dest`` from the parameter name,
    #: and ``action``/``required`` are the named ``Option`` arguments and have no meaning on a
    #: positional ``Argument``.  ``help`` is exposed as the ``help_text`` parameter; accepting a
    #: raw ``help`` too would silently shadow it (``to_kwargs`` lets ``extra_kwargs`` win).
    #: ``default`` is accepted as a named parameter (see :meth:`__init__`) and reconciled with
    #: the signature default; it must not appear in ``extra_kwargs`` as well.
    _RESERVED_EXTRA_KWARGS: ClassVar[frozenset[str]] = frozenset(
        {
            "type",
            "dest",
            "action",
            "required",
            "help",
        }
    )

    def __init__(
        self,
        *,
        help_text: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
        nargs: _NargsValue | None = None,
        choices: Iterable[Any] | None = None,
        choices_provider: UnboundChoicesProvider[CmdOrSetT] | None = None,
        completer: UnboundCompleter[CmdOrSetT] | None = None,
        table_columns: Sequence[str | Column] | None = None,
        suppress_tab_hint: bool | None = None,
        const: Any = _UNSET,
        default: Any = _UNSET,
        **extra_kwargs: Any,
    ) -> None:
        """Initialise shared metadata fields.

        ``const`` is the value stored when a flag is present without an argument; on an
        :class:`Option` it selects ``store_const`` (scalar type) or ``append_const``
        (``list[T]``).  It is meaningless for a positional :class:`Argument` (argparse
        ignores it there) and is rejected when the parser is built.  Left as :data:`_UNSET`
        when not given, so an explicit ``const=None`` is distinct from "no const".

        ``default`` is the value the parser stores when the argument is absent; it is
        equivalent to writing the same default in the function signature
        (``Annotated[T, Option('--x', default=v)]`` is the same as
        ``Annotated[T, Option('--x')] = v``).  Specifying both the signature default and
        the metadata default is a conflict and rejected; :data:`argparse.SUPPRESS` is also
        rejected because it removes the kwarg the function expects.

        ``extra_kwargs`` forwards any ``add_argument`` parameter not named above -- in
        particular custom parameters registered via
        :func:`~cmd2.argparse_utils.register_argparse_argument_parameter`.  They pass
        straight through to ``add_argument`` (which validates them: an unknown keyword
        raises ``TypeError`` when the parser is built), giving parity with a hand-built parser.
        """
        reserved = self._RESERVED_EXTRA_KWARGS & extra_kwargs.keys()
        if reserved:
            name = sorted(reserved)[0]
            # Per-key remediation hint for the reserved kwarg.
            hint = {
                "type": "The converter is derived from the parameter annotation; change the annotation instead.",
                "dest": "The dest is the parameter name; rename the parameter instead.",
                "action": "Use Option(action=...) (only Option supports an action; Argument is always positional).",
                "required": (
                    "Use Option(required=True); a positional Argument is always required unless it has "
                    "a default or is annotated as `T | None`."
                ),
                "help": "Use the help_text= parameter instead; it maps to argparse's help= and would otherwise be shadowed.",
            }[name]
            raise TypeError(f"{type(self).__name__}({name}=...) is not accepted by @with_annotated. {hint}")
        self.help_text = help_text
        self.metavar = metavar
        self.nargs = nargs
        self.choices = choices
        self.choices_provider = choices_provider
        self.completer = completer
        self.table_columns = table_columns
        self.suppress_tab_hint = suppress_tab_hint
        self.const = const
        self.default = default
        self.extra_kwargs = extra_kwargs

    def to_kwargs(self) -> dict[str, Any]:
        """Return non-None mapped fields, an explicit ``const``, and any passthrough ``extra_kwargs``."""
        kwargs = {kwarg: val for attr, kwarg in self._KWARGS_MAP.items() if (val := getattr(self, attr)) is not None}
        if self.const is not _UNSET:
            kwargs["const"] = self.const
        kwargs.update(self.extra_kwargs)
        return kwargs


class Argument(_BaseArgMetadata):
    """Metadata for a positional argument in an ``Annotated`` type hint.

    Example::

        def do_greet(self, name: Annotated[str, Argument(help_text="Person to greet")]):
            ...
    """


class Option(_BaseArgMetadata):
    """Metadata for an optional/flag argument in an ``Annotated`` type hint.

    Positional ``*names`` are the flag strings (e.g. ``"--color"``, ``"-c"``).
    When omitted, the decorator auto-generates ``--param-name`` (underscores
    in the parameter name are converted to dashes).

    Pass ``const=`` to store a fixed value when the flag is present: on a scalar parameter this
    selects ``store_const`` (present -> ``const``, absent -> the default), on a ``list[T]`` it
    selects ``append_const`` (each flag appends ``const``). A scalar ``const=`` paired with an
    explicit ``nargs`` (e.g. ``nargs='?'``) instead keeps the ``store`` action for argparse's
    optional-value idiom (bare flag -> ``const``, ``flag VALUE`` -> the value). ``action=`` may
    still be given explicitly; otherwise it is inferred from the type.

    Example::

        def do_paint(
            self,
            color: Annotated[str, Option("--color", "-c", help_text="Color")] = "blue",
            verbose: Annotated[int, Option("-v", const=2)] = 0,
        ):
            ...
    """

    def __init__(
        self,
        *names: str,
        action: str | type[argparse.Action] | None = None,
        required: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialise Option metadata.

        ``action`` may be a string (one of the supported actions: ``store_true``, ``store_false``,
        ``count``, ``append``, ``extend``, ``store_const``, ``append_const``) or a custom
        :class:`argparse.Action` subclass.  A custom class is passed straight through to
        ``add_argument`` and the user's class owns the storage behaviour; the type-inferred
        action, container factory, and the action-specific constraint checks are skipped.
        """
        super().__init__(**kwargs)
        self.names = names
        self.action = action
        self.required = required

    def to_kwargs(self) -> dict[str, Any]:
        """Return non-None fields as an argparse kwargs dict."""
        kwargs = super().to_kwargs()
        if self.action is not None:
            kwargs["action"] = self.action
        if self.required:
            kwargs["required"] = True
        return kwargs


class Group:
    """Argument-group definition for ``with_annotated(groups=...)``.

    Wrap parameter names with an optional ``title`` and ``description`` so the
    group renders its own section in ``--help`` output. Every ``groups`` and
    ``mutually_exclusive_groups`` entry must be a ``Group`` instance.

    Example::

        @with_annotated(
            groups=(Group("host", "port", title="connection", description="where to connect"),),
        )
        def do_connect(self, host: str, port: int = 22): ...
    """

    def __init__(
        self,
        *members: str,
        title: str | None = None,
        description: str | None = None,
        required: bool = False,
    ) -> None:
        """Initialise an argument group definition.

        :param members: parameter names to place in the group (at least one)
        :param title: optional group title shown as a section header in help
        :param description: optional group description shown under the title
        :param required: only meaningful for ``mutually_exclusive_groups``; when
                         ``True`` argparse requires exactly one member to be supplied.
                         Setting this on a group passed to ``groups=`` raises ``ValueError``
                         (argparse's ``add_argument_group`` has no ``required`` flag).
        """
        if not members:
            raise ValueError("Group requires at least one member parameter name")
        self.members = members
        self.title = title
        self.description = description
        self.required = required

    def _validate_members(self, *, all_param_names: set[str], group_type: str) -> None:
        """Validate that every referenced member parameter exists."""
        for name in self.members:
            if name not in all_param_names:
                raise ValueError(f"{group_type} references nonexistent parameter {name!r}")


#: Metadata extracted from ``Annotated[T, meta]``, or ``None`` for plain types.
ArgMetadata = Argument | Option | None

_NormalizedAnnotation = tuple[Any, ArgMetadata, bool]
_ArgumentTarget = argparse.ArgumentParser | argparse._MutuallyExclusiveGroup | argparse._ArgumentGroup


@dataclass
class _TypeResult:
    """How a declared type maps onto argparse settings.

    Produced by ``_TYPE_TABLE`` entries and consumed by :meth:`_ArgparseArgument._apply_type`.
    ``converter``/``choices``/``action``/``completer`` flow to argparse;
    ``is_collection``/``fixed_arity`` are scratch the nargs table reads.
    """

    converter: Callable[[str], Any] | None = None
    choices: Iterable[Any] | None = None
    action: str | type[argparse.Action] | None = None
    completer: Any = None
    is_collection: bool = False
    container_factory: Callable[[list[Any]], Any] | None = None
    fixed_arity: int | None = None


# ---------------------------------------------------------------------------
# Type resolvers
# ---------------------------------------------------------------------------
#
# Each resolver has the signature ``(tp, args, *, is_positional) -> _TypeResult`` and is
# registered in ``_TYPE_TABLE``.  ``_resolve_base_type`` looks one up by type; ``_apply_type``
# copies the resulting ``_TypeResult`` onto the builder's slots and context scratch.
# ---------------------------------------------------------------------------

_BOOL_TRUE_VALUES = ["1", "true", "t", "yes", "y", "on"]
_BOOL_FALSE_VALUES = ["0", "false", "f", "no", "n", "off"]
_BOOL_CHOICES = [CompletionItem(True, text=text) for text in _BOOL_TRUE_VALUES] + [
    CompletionItem(False, text=text) for text in _BOOL_FALSE_VALUES
]


def _parse_bool(value: str) -> bool:
    """Parse a string into a boolean value for argparse type conversion."""
    lowered = value.strip().lower()
    if lowered in _BOOL_TRUE_VALUES:
        return True
    if lowered in _BOOL_FALSE_VALUES:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value!r} (choose from: 1, 0, true, false, yes, no, on, off)")


def _make_literal_type(literal_values: list[Any]) -> Callable[[str], Any]:
    """Create an argparse converter for a Literal's exact values."""
    value_map: dict[str, Any] = {}
    for value in literal_values:
        key = str(value)
        if key in value_map and value_map[key] is not value:
            raise TypeError(
                f"Literal values {value_map[key]!r} and {value!r} have the same string "
                f"representation {key!r} and cannot be distinguished on the command line."
            )
        value_map[key] = value

    def _convert(value: str) -> Any:
        if value in value_map:
            return value_map[value]
        if value.lower() in _BOOL_TRUE_VALUES:
            bool_value = True
        elif value.lower() in _BOOL_FALSE_VALUES:
            bool_value = False
        else:
            bool_value = None

        if bool_value is not None:
            for v in literal_values:
                if type(v) is bool and v == bool_value:
                    return bool_value

        valid = ", ".join(str(v) for v in literal_values)
        raise argparse.ArgumentTypeError(f"invalid choice: {value!r} (choose from {valid})")

    _convert.__name__ = "literal"
    return _convert


def _make_enum_type(enum_class: type[enum.Enum]) -> Callable[[str], enum.Enum]:
    """Create an argparse *type* converter for an Enum class.

    Accepts both member *values* and member *names*.
    """
    _value_map = {str(m.value): m for m in enum_class}

    def _convert(value: str) -> enum.Enum:
        member = _value_map.get(value)
        if member is not None:
            return member
        try:
            return enum_class[value]
        except KeyError as err:
            valid = ", ".join(_value_map)
            raise argparse.ArgumentTypeError(f"invalid choice: {value!r} (choose from {valid})") from err

    _convert.__name__ = enum_class.__name__
    _convert._cmd2_enum_class = enum_class  # type: ignore[attr-defined]
    return _convert


class _CollectionCastingAction(argparse._StoreAction):
    """Store action that can coerce parsed collection values to a container type."""

    def __init__(self, *args: Any, container_factory: Callable[[list[Any]], Any] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._container_factory = container_factory

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        _option_string: str | None = None,
    ) -> None:
        result = values
        if self._container_factory is not None and isinstance(values, list):
            result = self._container_factory(values)
        setattr(namespace, self.dest, result)


# -- Individual resolvers -----------------------------------------------------


def _make_simple_resolver(converter: Callable[..., Any] | type) -> Callable[..., _TypeResult]:
    """Create a resolver for types that just need ``type=converter``."""

    def _resolve(_tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> _TypeResult:
        return _TypeResult(converter=converter)

    return _resolve


def _resolve_path(_tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> _TypeResult:
    """Resolve Path and add completer."""
    from .cmd2 import Cmd

    return _TypeResult(converter=Path, completer=Cmd.path_complete)


def _resolve_bool(_tp: Any, _args: tuple[Any, ...], *, is_positional: bool = False, **_ctx: Any) -> _TypeResult:
    """Resolve bool: a positional gets a converter, an option a flag action.

    A user ``Option(action=...)`` overrides this later; here we set only the default option action.
    """
    if not is_positional:
        return _TypeResult(action=argparse.BooleanOptionalAction)
    return _TypeResult(converter=_parse_bool, choices=list(_BOOL_CHOICES))


def _resolve_element(tp: Any) -> _TypeResult:
    """Resolve a collection element type and reject nested collections."""
    inner = _resolve_base_type(tp, is_positional=True)
    if inner.is_collection:
        raise TypeError("Nested collections are not supported")
    return inner


def _make_collection_resolver(collection_type: type) -> Callable[..., _TypeResult]:
    """Create a resolver for single-arg collections (list[T], set[T])."""

    def _resolve(_tp: Any, args: tuple[Any, ...], **_ctx: Any) -> _TypeResult:
        if len(args) == 0:
            # Bare list/set without type args -- treat as list[str]/set[str].
            return _TypeResult(is_collection=True, container_factory=collection_type)
        if len(args) != 1:
            raise TypeError(
                f"{collection_type.__name__}[...] with {len(args)} type arguments is not supported; "
                f"use {collection_type.__name__}[T] with a single element type."
            )
        element = _resolve_element(args[0])
        return _TypeResult(
            converter=element.converter,
            choices=element.choices,
            completer=element.completer,
            is_collection=True,
            container_factory=collection_type,
        )

    return _resolve


def _resolve_tuple(_tp: Any, args: tuple[Any, ...], **_ctx: Any) -> _TypeResult:
    """Resolve tuple[T, ...] (variable) and tuple[T, T] (fixed arity)."""
    if not args:
        # Bare tuple without type args -- treat as tuple[str, ...].
        return _TypeResult(is_collection=True, container_factory=tuple)

    if len(args) == 2 and args[1] is Ellipsis:
        element = _resolve_element(args[0])
        return _TypeResult(
            converter=element.converter,
            choices=element.choices,
            completer=element.completer,
            is_collection=True,
            container_factory=tuple,
        )

    if Ellipsis not in args:
        first = args[0]
        if not all(a == first for a in args[1:]):
            raise TypeError(
                f"tuple[{', '.join(_type_name(a) for a in args)}] "
                f"has mixed element types which is not currently supported because argparse "
                f"can only apply a single type= converter per argument. "
                f"Use tuple[T, T] (same type) or tuple[T, ...] instead."
            )
        element = _resolve_element(first)
        return _TypeResult(
            converter=element.converter,
            choices=element.choices,
            completer=element.completer,
            is_collection=True,
            container_factory=tuple,
            fixed_arity=len(args),
        )

    raise TypeError(
        "tuple with Ellipsis in an unexpected position is not supported; "
        "use tuple[T, ...] for variable-length or tuple[T, T] for fixed-arity."
    )


def _resolve_literal(_tp: Any, args: tuple[Any, ...], **_ctx: Any) -> _TypeResult:
    """Resolve Literal["a", "b", ...] into converter + choices."""
    literal_values = list(args)
    return _TypeResult(converter=_make_literal_type(literal_values), choices=literal_values)


def _resolve_enum(tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> _TypeResult:
    """Resolve Enum subclasses into converter + choices."""
    return _TypeResult(
        converter=_make_enum_type(tp),
        choices=[CompletionItem(m, text=str(m.value), display_meta=m.name) for m in tp],
    )


# -- Registry -----------------------------------------------------------------

_TYPE_TABLE: dict[Any, Callable[..., _TypeResult]] = {
    # Subclass-matchable entries first -- iteration order matters for the
    # issubclass fallback. enum.Enum must precede int (IntEnum <: int).
    enum.Enum: _resolve_enum,
    Path: _resolve_path,
    # Exact-match entries (order among these doesn't affect subclass lookup).
    bool: _resolve_bool,
    decimal.Decimal: _make_simple_resolver(decimal.Decimal),
    float: _make_simple_resolver(float),
    int: _make_simple_resolver(int),
    Literal: _resolve_literal,
    list: _make_collection_resolver(list),
    set: _make_collection_resolver(set),
    tuple: _resolve_tuple,
}


# -- Helpers ------------------------------------------------------------------


def _type_name(tp: Any) -> str:
    """Best-effort type name for diagnostic messages."""
    return tp.__name__ if hasattr(tp, "__name__") else str(tp)


#: Scalar annotations that argparse stores as the raw string (no converter needed).
_PASSTHROUGH_TYPES = frozenset({str, object, Any, inspect.Parameter.empty})


def _resolve_base_type(tp: Any, *, is_positional: bool = False) -> _TypeResult:
    """Resolve a declared type into a :class:`_TypeResult` via the registry.

    Lookup order: ``get_origin(tp)`` -> ``tp`` -> ``issubclass`` fallback -> passthrough.
    Raises ``TypeError`` for a scalar with no converter.
    """
    args = get_args(tp)
    resolver = _TYPE_TABLE.get(get_origin(tp)) or _TYPE_TABLE.get(tp)

    # Subclass fallback (e.g. MyEnum -> enum.Enum, MyPath -> pathlib.Path).
    if resolver is None and isinstance(tp, type):
        for parent, candidate in _TYPE_TABLE.items():
            if isinstance(parent, type) and issubclass(tp, parent):
                resolver = candidate
                break

    if resolver is not None:
        return resolver(tp, args, is_positional=is_positional)
    if tp in _PASSTHROUGH_TYPES or get_origin(tp) is not None:
        return _TypeResult()
    raise TypeError(
        f"Unsupported parameter type {_type_name(tp)!r} for @with_annotated: there is no converter "
        f"for it, so command-line values would silently arrive as plain strings. Supported scalar types "
        f"are str, int, float, bool, decimal.Decimal, pathlib.Path, enum.Enum subclasses, and Literal[...]; "
        f"use one of these (optionally in list/set/tuple) or a subclass of one."
    )


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """If *tp* is ``T | None``, return ``(T, True)``.  Otherwise ``(tp, False)``.

    Raises ``TypeError`` for ambiguous unions like ``str | int`` or ``str | int | None``.
    """
    origin = get_origin(tp)
    if origin is Union or origin is types.UnionType:  # type: ignore[comparison-overlap]
        all_args = get_args(tp)
        non_none = [a for a in all_args if a is not type(None)]
        has_none = len(non_none) < len(all_args)
        if len(non_none) == 1:
            if has_none:
                return non_none[0], True
            raise TypeError(
                f"Unexpected single-element Union without None: Union[{non_none[0]}]. "
                f"Use the type directly instead of wrapping in Union."
            )
        type_names = " | ".join(_type_name(a) for a in non_none)
        raise TypeError(f"Union type {type_names} is ambiguous for auto-resolution.")
    return tp, False


def _normalize_annotation(annotation: Any) -> _NormalizedAnnotation:
    """Normalize an annotation into its inner type, metadata, and optionality."""
    tp = annotation
    metadata: ArgMetadata = None
    is_optional = False

    tp, unwrapped = _unwrap_optional(tp)
    if unwrapped:
        is_optional = True
        if get_origin(tp) is Annotated:  # type: ignore[comparison-overlap]
            inner_tp = get_args(tp)[0]
            inner_origin = get_origin(inner_tp)
            inner_is_union = inner_origin is Union or inner_origin is types.UnionType  # type: ignore[comparison-overlap]
            if not (inner_is_union and type(None) in get_args(inner_tp)):
                raise TypeError("Annotated[T, meta] | None is ambiguous. Use Annotated[T | None, meta] instead.")

    if get_origin(tp) is Annotated:  # type: ignore[comparison-overlap]
        args = get_args(tp)
        tp = args[0]
        for meta in args[1:]:
            if isinstance(meta, (Argument, Option)):
                metadata = meta
                break

    tp, inner_unwrapped = _unwrap_optional(tp)
    if inner_unwrapped:
        is_optional = True

    return tp, metadata, is_optional


# ---------------------------------------------------------------------------
# Annotation resolution -- builder anchored to argparse's add_argument schema
# ---------------------------------------------------------------------------


class _NargsMode(enum.Enum):
    """How an explicit action sets ``nargs`` in the final override pass."""

    ARITY = "arity"  # keep the nargs resolved by the arity table
    CLEAR = "clear"  # take one value per flag, so emit no nargs


@dataclass(frozen=True)
class _ActionPolicy:
    """Declarative data for an explicit ``Option(action=...)``.

    Applied verbatim by :meth:`_ArgparseArgument._apply_action`; the type
    compatibility check (``requires``) is enforced by the constraint table.
    """

    requires: Callable[["_ArgparseArgument"], bool] | None = None  # declared type the result needs
    requires_label: str = ""  # human name of the required type (for the error message)
    drop_converter: bool = False  # action does not accept type=
    nargs_mode: _NargsMode = _NargsMode.ARITY  # whether to keep or clear the arity-table nargs
    default_factory: Callable[[], Any] | None = None  # default when omitted (also -> None for T | None)


#: Actions that accumulate values into a list via argparse's native action (replace the casting action).
_LIST_ACTIONS = frozenset({"append", "extend", "append_const"})
#: Actions that store a fixed ``const`` value: ``store_const`` (scalar) and ``append_const`` (list[T]).
_CONST_ACTIONS = frozenset({"store_const", "append_const"})

#: Metadata kwargs the builder reasons about itself (the override facts read on demand via the
#: ``_meta_*`` properties); every other ``to_kwargs()`` entry passes straight through to
#: ``extras`` for argparse (help / metavar / choices_provider / completer / ...).
_METADATA_SPECIAL_KEYS = frozenset({"choices", "action", "required", "nargs", "const"})

#: A rule table maps a subject ``_S`` (a single :class:`_ArgparseArgument`) to a result ``_R``.
_S = TypeVar("_S")
_R = TypeVar("_R")

#: One rule-table row: ``(predicate, producer)``.  A table is scanned top-to-bottom and the first
#: row whose ``predicate(subject)`` holds yields ``producer(subject)`` (see :func:`_first_match`).
#: Derivation tables produce an output slot's value; constraint tables produce an error or ``None``.
#: (Keyed dispatch -- ``_TYPE_TABLE`` / ``_ACTION_TABLE`` -- is separate: a payload looked up by key.)
_Rule = tuple[Callable[[_S], bool], Callable[[_S], _R]]


def _always(_subject: object) -> bool:
    """Predicate for a catch-all row -- always matches (every table ends with one)."""
    return True


def _const(value: _R) -> Callable[[object], _R]:
    """Return a producer that ignores its subject and always yields *value*."""
    return lambda _subject: value


def _first_match(rules: list[_Rule[_S, _R]], subject: _S) -> _R:
    """Return ``producer(subject)`` for the first rule whose predicate matches *subject*.

    Every table ends with an ``_always`` catch-all, so a match is guaranteed and only the
    matching producer runs (a producer may assume its predicate held).
    """
    return next(produce(subject) for predicate, produce in rules if predicate(subject))


class _ArgparseArgument:
    """Builder whose output fields mirror ``parser.add_argument(...)``'s schema.

    Constructed by :func:`_resolve_parameters` from the signature-derived inputs and populated by
    :meth:`_apply`, which fills each output slot from its decision table (role / nargs / default /
    required) or imperative phase (targets / type / metadata / action).  Inputs and scratch live
    alongside the output slots, but only the named slots are emitted (see :meth:`_emit`).

    Building does *not* validate: validation is deferred to a final pass in :func:`_resolve_parameters`,
    which links cross-argument facts (e.g. :attr:`has_following_positional`) onto each argument and then
    runs the single :data:`_CONSTRAINTS` table.  New behavior is added as a table row, not an ``if`` in
    the phases.  :meth:`add_to` emits the ``add_argument`` call.
    """

    def __init__(
        self,
        *,
        name: str,
        func_qualname: str,
        has_default: bool,
        param_default: Any,
        is_kw_only: bool,
        is_variadic: bool,
        inner_type: Any,
        metadata: ArgMetadata,
        is_optional: bool,
        kind: inspect._ParameterKind,
        is_base_command: bool,
    ) -> None:
        # signature-derived inputs (never emitted):
        self.name = name
        self.func_qualname = func_qualname
        self.has_default = has_default
        self.param_default = param_default  # the function's own default, not the argparse `default` slot
        self.is_kw_only = is_kw_only
        self.is_variadic = is_variadic
        self.inner_type = inner_type  # peeled type (after Annotated + Optional)
        self.metadata = metadata
        self.is_optional = is_optional
        self.kind = kind  # unsupported kinds (positional-only, **kwargs) are rejected by _CONSTRAINTS
        self.is_base_command = is_base_command
        # scratch filled by the type table (_apply_type):
        self.is_collection = False
        self.fixed_arity: int | None = None
        # output slots (1:1 with add_argument):
        self.is_positional = False
        self.flags: list[str] = []
        self.action: str | type[argparse.Action] | None = None
        self.nargs: _NargsValue | None = None
        self.type: Callable[[str], Any] | None = None
        self.choices: Iterable[Any] | None = None
        self.default: Any = _UNSET  # _UNSET until a default rule/action sets one
        self.required: bool = False
        self.container_factory: Callable[[list[Any]], Any] | None = None
        self.extras: dict[str, Any] = {}
        # first type-resolution error, captured so _CONSTRAINTS (not build order) picks the message:
        self.build_error: Exception | None = None
        # cross-argument facts, linked by _resolve_parameters once the whole list is built:
        self.has_following_positional = False
        # 1-based indices of the groups=/mutually_exclusive_groups= this parameter belongs to:
        self.argument_group_indices: list[int] = []
        self.mutex_group_indices: list[int] = []
        # Derive every output slot now; validation stays deferred to _check_constraints.
        self._apply()

    @property
    def omittable(self) -> bool:
        """Whether the argument may be absent (drives ``nargs`` and required).

        A metadata default (``Option(default=...)``) counts the same as a signature default here.
        """
        return self._effective_has_default or self.is_kw_only or self.is_optional or self.is_variadic

    @property
    def _is_list(self) -> bool:
        """Whether the declared type is ``list``/``list[T]`` -- the shape the list actions need.

        Distinct from :attr:`is_collection` (also true for ``set``/``tuple``): ``append``/``extend``/
        ``append_const`` accumulate specifically into a ``list``.
        """
        return get_origin(self.inner_type) is list or self.inner_type is list

    # -- ``*args`` element facts, derived from the ``tuple[element, ...]`` wrapper that
    #    _resolve_parameters builds for a variadic parameter (only meaningful when ``is_variadic``) --

    @property
    def _var_positional_element(self) -> Any:
        """The ``*args`` element type ``T`` (``inner_type`` is the variadic ``tuple[T, ...]``)."""
        return get_args(self.inner_type)[0]

    @property
    def _var_positional_element_display(self) -> str:
        """Display name of the ``*args`` element type (for the collection-element constraint message)."""
        element = self._var_positional_element
        return str(element) if get_origin(element) is not None else _type_name(element)

    @property
    def _var_positional_element_is_collection(self) -> bool:
        """Whether the ``*args`` element is itself a collection (``list``/``set``/``tuple``).

        Mirrors the collection entries in :data:`_TYPE_TABLE`; a collection element means ``*args``
        would collect a tuple of collections, which the constraint table rejects.
        """
        element = self._var_positional_element
        origin = get_origin(element)
        return (origin if origin is not None else element) in (list, set, tuple)

    # -- the user's metadata overrides, derived read-only from ``metadata`` (consulted by the
    #    choices/action/nargs/required tables, the action phase, and the constraints) --

    @property
    def _meta_nargs(self) -> _NargsValue | None:
        """An explicit ``Argument/Option(nargs=)``, else ``None``."""
        return self.metadata.nargs if self.metadata is not None else None

    @property
    def _meta_choices(self) -> Iterable[Any] | None:
        """Explicit ``Argument/Option(choices=)``, else ``None``."""
        return self.metadata.choices if self.metadata is not None else None

    @property
    def _has_user_completion(self) -> bool:
        """Whether the user supplied a ``choices_provider`` / ``completer`` on the metadata.

        A user-supplied completion source drives completion in place of any static ``choices``.
        Distinct from a completer the *type* inferred (e.g. ``Path``'s ``path_complete``), which
        yields to an explicit ``choices=`` instead of overriding it.
        """
        if self.metadata is None:
            return False
        return self.metadata.choices_provider is not None or self.metadata.completer is not None

    @property
    def _meta_action(self) -> str | type[argparse.Action] | None:
        """An explicit ``Option(action=)`` value, else ``None`` (only ``Option`` carries one).

        May be a string (one of the supported actions) or a custom :class:`argparse.Action`
        subclass; the constraint and policy rules below key on the string form, so a class
        action skips them and is passed straight through to ``add_argument``.
        """
        return self.metadata.action if isinstance(self.metadata, Option) else None

    @property
    def _meta_action_is_class(self) -> bool:
        """Whether ``Option(action=)`` is a custom :class:`argparse.Action` subclass."""
        return isinstance(self._meta_action, type)

    @property
    def _meta_required(self) -> bool:
        """Whether the user set ``Option(required=True)``."""
        return self.metadata.required if isinstance(self.metadata, Option) else False

    @property
    def _const_value(self) -> Any:
        """The explicit ``Argument/Option(const=)`` value, or :data:`_UNSET` when none was given."""
        return self.metadata.const if self.metadata is not None else _UNSET

    @property
    def _has_const(self) -> bool:
        """Whether a ``const`` value was supplied (drives const-action inference and validation)."""
        return self._const_value is not _UNSET

    @property
    def _meta_default(self) -> Any:
        """The explicit ``Argument/Option(default=)`` value, or :data:`_UNSET` when none was given."""
        return self.metadata.default if self.metadata is not None else _UNSET

    @property
    def _has_meta_default(self) -> bool:
        """Whether a metadata default was supplied (treated like a signature default)."""
        return self._meta_default is not _UNSET

    @property
    def _effective_has_default(self) -> bool:
        """Whether any default applies (signature or metadata).

        A metadata default is the equivalent of a signature default:
        ``Annotated[T, Option('--x', default=v)]`` behaves the same as
        ``Annotated[T, Option('--x')] = v``.  Specifying both is a conflict (see ``_CONSTRAINTS``).
        """
        return self.has_default or self._has_meta_default

    @property
    def _effective_param_default(self) -> Any:
        """The default to emit -- signature default if present, else the metadata default, else ``None``."""
        if self.has_default:
            return self.param_default
        if self._has_meta_default:
            return self._meta_default
        return None

    @property
    def _effective_action(self) -> str | None:
        """The resolved action as a string -- explicit ``Option(action=)`` or const-inferred.

        ``None`` for the type-inferred class actions (``BooleanOptionalAction`` /
        ``_CollectionCastingAction``), which carry no :data:`_ACTION_TABLE` policy.  Reads the
        resolved ``action`` slot, so it is only meaningful after :data:`_ACTION_RULES` run.
        """
        return self.action if isinstance(self.action, str) else None

    @property
    def _policy(self) -> _ActionPolicy | None:
        """The action policy for the effective action (``None`` for no/an unknown/a class action).

        Keyed on :attr:`_effective_action` so a const-inferred ``store_const``/``append_const``
        gets the same policy treatment as an explicit one.
        """
        return _ACTION_TABLE.get(self._effective_action) if self._effective_action else None

    @property
    def _is_inferred_bool_flag(self) -> bool:
        """Whether this is a bool option using the inferred ``BooleanOptionalAction`` (no explicit action).

        Like the explicit flag actions, it supplies its own value when absent (``False``, or ``None`` for
        ``bool | None``), so it is neither ``required`` nor needs a user default.  Reads the resolved
        ``action`` slot, so it is only meaningful after :meth:`_apply_type` / :data:`_ACTION_RULES` run.
        """
        return self.action is argparse.BooleanOptionalAction

    def _apply(self) -> None:
        """Build this argument by deriving each output slot (no validation here).

        :meth:`_apply_type` seeds the type-inferred baselines and :meth:`_apply_metadata_extras` merges
        the user's display kwargs into ``extras``; then every output slot is filled from its value table
        (role / action / choices / nargs / default / required).  The action *policy* is applied last, as
        an override, because ``action=`` is cross-cutting and only makes sense once the rest is known.
        Validity is checked later by :func:`_resolve_parameters` (via :meth:`_check_constraints`).
        """
        self.is_positional = _first_match(_ROLE_RULES, self)
        self._apply_targets()
        self._apply_type()
        if self.build_error is not None:
            # Type unresolved: the remaining phases assume a resolved type, so stop here and let
            # _CONSTRAINTS raise the captured error.
            return
        self._apply_metadata_extras()
        self.action = _first_match(_ACTION_RULES, self)
        self.choices = _first_match(_CHOICES_RULES, self)
        if self._meta_choices is not None and self.choices is not None:
            # The choices the user wrote in source are compared by argparse *after* the type
            # converter runs, so run them through that converter to land in the same value-space
            # (Annotated[int, Option(choices=['1','2'])] -> [1, 2], so `--x 1` matches), and drop a
            # type-inferred completer (e.g. Path's) so completion is driven by these choices.
            if self.type is not None:
                self.choices = self._convert_choices(self.choices, self.type)
            if not self._has_user_completion:
                self.extras.pop("completer", None)
                self.extras.pop("choices_provider", None)
        self.nargs = _first_match(_NARGS_RULES, self)
        self.default = _first_match(_DEFAULT_RULES, self)
        self.required = _first_match(_REQUIRED_RULES, self)
        self._apply_action()

    def _convert_choices(self, choices: Iterable[Any], converter: Callable[[str], Any]) -> list[Any]:
        """Run string ``choices`` through the inferred ``type`` *converter* so they match post-conversion.

        Non-string choices are assumed already in the target type and left untouched (the simple
        converters are idempotent on them).  A choice the converter rejects is a build-time error.
        """
        converted: list[Any] = []
        for choice in choices:
            if not isinstance(choice, str):
                converted.append(choice)
                continue
            try:
                converted.append(converter(choice))
            except (ValueError, TypeError, ArithmeticError, argparse.ArgumentTypeError) as exc:
                raise TypeError(f"choice {choice!r} on '{self.name}' is not a valid '{_type_name(self.inner_type)}'.") from exc
        return converted

    # -- construction (fill output slots from the tables; no business rules here) --

    def _apply_targets(self) -> None:
        """Set ``flags`` for options (positionals keep the empty default)."""
        if self.is_positional:
            return
        self.flags = (
            list(self.metadata.names)
            if isinstance(self.metadata, Option) and self.metadata.names
            else [f"--{self.name.replace('_', '-')}"]
        )

    def _apply_type(self) -> None:
        """Copy the type table's result onto the output slots + type scratch.

        Type resolution is the only build step that can fail (unsupported type, nested collection, ...).
        Rather than raise here -- which would let build order decide the message -- the error is captured
        so :data:`_CONSTRAINTS` can rank it against more specific rules and raise the winner.
        """
        try:
            result = _resolve_base_type(self.inner_type, is_positional=self.is_positional)
        except TypeError as exc:
            self.build_error = exc
            return
        self.type = result.converter
        self.choices = result.choices
        # A collection coerces its parsed list into the declared container type; option bool
        # gets ``--flag/--no-flag``.  Either may be overridden by an explicit ``Option(action=)``.
        self.action = _CollectionCastingAction if result.is_collection else result.action
        self.container_factory = result.container_factory
        if result.completer is not None:
            self.extras["completer"] = result.completer
        self.is_collection = result.is_collection
        self.fixed_arity = result.fixed_arity

    def _apply_metadata_extras(self) -> None:
        """Pass the user's display/completion metadata straight through to ``extras``.

        The override facts (choices/action/required/nargs) are read on demand from ``metadata`` via
        properties; only these passthrough kwargs need merging into ``extras``.
        """
        if self.metadata is None:
            return
        kwargs = self.metadata.to_kwargs()
        self.extras.update({key: value for key, value in kwargs.items() if key not in _METADATA_SPECIAL_KEYS})

    def _apply_action(self) -> None:
        """Apply an explicit ``Option(action=...)`` as the final override pass.

        Runs after type/nargs/default/required are resolved and only sets slots; the action's validity
        (type match, unknown action, ...) is enforced by the constraints.

        A custom :class:`argparse.Action` subclass has no :data:`_ACTION_TABLE` policy: it owns its
        own storage so the collection casting wrapper is dropped, but the type-inferred converter,
        default, and required-ness are kept (the user can override them via :data:`extra_kwargs`).
        """
        if self._meta_action_is_class:
            # The user's class owns storage; drop the casting wrapper's container_factory kwarg.
            self.container_factory = None
            return
        policy = self._policy
        if policy is None:
            return
        if policy.drop_converter:
            # The action stores a fixed value and takes no command-line argument, so the parsed
            # string is never converted, validated against choices, or tab-completed -- drop the
            # converter, choices, and any value-completion metadata (e.g. the completer inferred
            # for a Path type), which argparse rejects on a zero-argument action.
            self.type = None
            self.choices = None
            self.extras.pop("completer", None)
            self.extras.pop("choices_provider", None)
        if self._effective_action in _LIST_ACTIONS:
            # append/extend/append_const use argparse's native list action, not the casting action.
            self.container_factory = None
        if policy.nargs_mode is _NargsMode.CLEAR:
            self.nargs = None  # append collects one value per flag, so it takes no nargs
        if self.default is _UNSET and policy.default_factory is not None:
            # The action carries its own default (count -> 0, append/extend -> []),
            # except T | None, where None is the natural absence value.
            self.default = None if self.is_optional else policy.default_factory()
        if not self._meta_required:
            # A supported action supplies a value when absent, so it is never required by default.
            self.required = False

    def _check_constraints(self) -> None:
        """Raise for the first violated constraint (declarative validation)."""
        error = _first_match(_CONSTRAINTS, self)
        if error is not None:
            raise error

    # -- emission ------------------------------------------------------------

    def _emit(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Return ``(args, kwargs)`` for ``target.add_argument(*args, **kwargs)``."""
        kwargs: dict[str, Any] = dict(self.extras)
        if self.type is not None:
            kwargs["type"] = self.type
        if self.choices is not None:
            # Materialize so argparse can re-iterate it (a one-shot generator would be exhausted).
            kwargs["choices"] = list(self.choices)
        if self.action is not None:
            kwargs["action"] = self.action
        if self._has_const:
            kwargs["const"] = self._const_value
        if self.nargs is not None:
            kwargs["nargs"] = self.nargs
        if self.container_factory is not None:
            kwargs["container_factory"] = self.container_factory
        if self.default is not _UNSET:
            kwargs["default"] = self.default
        if self.required:
            kwargs["required"] = True
        if self.is_positional:
            return (self.name,), kwargs
        kwargs["dest"] = self.name
        return tuple(self.flags), kwargs

    def add_to(self, target: _ArgumentTarget) -> None:
        """Add this argument to *target* (a parser, group, or mutex group)."""
        args, kwargs = self._emit()
        target.add_argument(*args, **kwargs)


#: Explicit ``Option(action=...)`` policies.  Defined after :class:`_ArgparseArgument` so the
#: ``requires`` predicates can read its ``inner_type`` slot (like the other rule tables below).
_ACTION_TABLE: dict[str, _ActionPolicy] = {
    "store_true": _ActionPolicy(
        requires=lambda a: a.inner_type is bool,
        requires_label="bool",
        drop_converter=True,
        default_factory=lambda: False,
    ),
    "store_false": _ActionPolicy(
        requires=lambda a: a.inner_type is bool,
        requires_label="bool",
        drop_converter=True,
        default_factory=lambda: True,
    ),
    "count": _ActionPolicy(
        requires=lambda a: a.inner_type is int, requires_label="int", drop_converter=True, default_factory=lambda: 0
    ),
    "append": _ActionPolicy(
        requires=lambda a: a._is_list,
        requires_label="list[T]",
        nargs_mode=_NargsMode.CLEAR,
        default_factory=list,
    ),
    "extend": _ActionPolicy(
        requires=lambda a: a._is_list,
        requires_label="list[T]",
        default_factory=list,
    ),
    # const actions: shape (scalar vs list[T]) and the const value itself are validated by dedicated
    # _CONSTRAINTS rows, so requires=None here.  Both store a fixed value, so the converter/choices are
    # dropped (drop_converter) and they take no command-line value (nargs CLEAR).
    "store_const": _ActionPolicy(drop_converter=True, nargs_mode=_NargsMode.CLEAR),
    "append_const": _ActionPolicy(drop_converter=True, nargs_mode=_NargsMode.CLEAR, default_factory=list),
}


#: Role table: the first matching predicate decides positional (``True``) vs option (``False``).
_ROLE_RULES: list[_Rule[_ArgparseArgument, bool]] = [
    (lambda a: a.is_variadic, _const(True)),  # *args is always positional
    (lambda a: isinstance(a.metadata, Argument), _const(True)),  # Argument() forces positional
    (lambda a: isinstance(a.metadata, Option), _const(False)),  # Option() forces option
    (lambda a: a.is_kw_only, _const(False)),  # keyword-only -> option
    (lambda a: a.has_default, _const(False)),  # a signature default -> option (metadata-only
    # default never reaches this row: Argument/Option metadata already pinned the role above)
    (_always, _const(True)),  # otherwise positional
]

#: Action table: an explicit ``Option(action=)`` overrides the type-inferred action
#: (collection-casting / ``BooleanOptionalAction`` / none).  The action *policy* is applied later.
_ACTION_RULES: list[_Rule[_ArgparseArgument, str | type[argparse.Action] | None]] = [
    (lambda a: a._meta_action is not None, lambda a: a._meta_action),  # explicit Option(action=)
    # A const with no explicit action selects the const action by type shape:
    # list[T] -> append_const (accumulate), any scalar -> store_const (single value).
    # Exception: a scalar that *also* sets an explicit nargs (e.g. nargs='?') wants argparse's native
    # optional-value-with-const semantics (absent -> default, bare flag -> const, flag VALUE -> converted
    # VALUE), so it keeps the type-inferred ``store`` action instead of the value-less store_const -- the
    # explicit nargs and the type converter would otherwise be silently dropped.  list[T] still infers
    # append_const regardless of nargs (append_const takes no value, so nargs is meaningless there).
    (
        lambda a: a._has_const and (a.is_collection or a._meta_nargs is None),
        lambda a: "append_const" if a.is_collection else "store_const",
    ),
    (_always, lambda a: a.action),  # the type-inferred action baseline
]

#: Choices table, in precedence order: a *user* choices_provider/completer drives completion (drop
#: static choices); otherwise an explicit metadata ``choices=`` wins (even over a type-inferred
#: completer such as ``Path``'s -- see ``_apply``, which then drops that completer); otherwise a
#: type-inferred completer drives completion (drop choices); otherwise the type-inferred choices.
_CHOICES_RULES: list[_Rule[_ArgparseArgument, Iterable[Any] | None]] = [
    (lambda a: a._has_user_completion, _const(None)),  # user completer/provider overrides choices
    (lambda a: a._meta_choices is not None, lambda a: a._meta_choices),  # explicit Argument/Option choices
    (lambda a: bool(a.extras.get("choices_provider") or a.extras.get("completer")), _const(None)),  # inferred completer
    (_always, lambda a: a.choices),  # the type-inferred choices baseline
]

#: ``nargs`` table -- the sole source of arity.  An explicit ``Argument(nargs=)`` wins; otherwise the
#: value shape decides (fixed tuple -> its arity, collection -> ``'+'``/``'*'``, optional scalar
#: positional -> ``'?'``).  Action effects (append clears nargs) are applied later by the action phase.
_NARGS_RULES: list[_Rule[_ArgparseArgument, _NargsValue | None]] = [
    (lambda a: a._meta_nargs is not None, lambda a: a._meta_nargs),  # an explicit Argument(nargs=) wins
    (lambda a: a.fixed_arity is not None, lambda a: a.fixed_arity),  # tuple[T, T] pins nargs to its arity
    (lambda a: a.is_collection and a.omittable, _const("*")),  # list/set/tuple[T, ...] that may be empty
    (lambda a: a.is_collection, _const("+")),  # collection requiring >= 1 value
    (lambda a: a.is_positional and a.omittable, _const("?")),  # an optional scalar positional
    (_always, _const(None)),  # required scalar / any option scalar
]

#: Default-value table.  Either source (signature or metadata) feeds the parser default;
#: explicit-action defaults (count -> 0, append/extend -> []) are added later by the action phase.
_DEFAULT_RULES: list[_Rule[_ArgparseArgument, Any]] = [
    (lambda a: a._effective_has_default, lambda a: a._effective_param_default),
    # A bool option is a flag: when absent it means ``False`` (not a missing value), so -- like
    # store_true -- it carries its own default.  ``bool | None`` keeps the catch-all ``_UNSET``
    # (argparse's ``None``), the natural absence value for the Optional case.
    (lambda a: a._is_inferred_bool_flag and not a.is_optional, _const(False)),
    (_always, _const(_UNSET)),  # nothing to set (the action may still add one)
]

#: Required table.  Positionals never carry ``required=``; the action phase may relax it.
_REQUIRED_RULES: list[_Rule[_ArgparseArgument, bool]] = [
    (lambda a: a.is_positional, _const(False)),
    (lambda a: a._meta_required, _const(True)),  # explicit Option(required=True)
    (lambda a: a._effective_has_default or a.is_optional, _const(False)),  # omittable
    # A bool option is a flag that supplies its own value (False/None) when absent, so it is never
    # required without an explicit Option(required=True) -- same reasoning as the flag actions below.
    (lambda a: a._is_inferred_bool_flag, _const(False)),
    (_always, _const(True)),  # an option with no default and no ``| None`` must be supplied
]


#: ``nargs`` values that let a positional consume a variable number of tokens.
_VARIABLE_NARGS = frozenset({"?", "*", "+", argparse.REMAINDER})


# Parameter names that conflict with argparse internals and cannot be used as annotated
# parameter names (checked by _CONSTRAINTS).
_RESERVED_PARAM_NAMES = frozenset({"dest", "subcommand"})


def _const_element_type(a: _ArgparseArgument) -> Any:
    """Return the type a const must match: the element ``T`` for ``list[T]``, else the scalar itself."""
    if a.is_collection:
        args = get_args(a.inner_type)
        element = args[0] if args else str
    else:
        element = a.inner_type
    element, _ = _unwrap_optional(element)
    return element


def _const_mismatches_type(a: _ArgparseArgument) -> bool:
    """Whether a supplied ``const`` is incompatible with the declared (element) type.

    Best-effort, mirroring the decorator's "parsed value matches the annotation" guarantee:
    ``Literal``/``Enum`` are checked for membership and the concrete scalars by ``isinstance``;
    open types (``str``/``Any``/``object``/the bool flag) and unresolved types are not validated.
    A class :class:`argparse.Action` owns its storage semantics, so any ``const`` paired with one
    is the user's responsibility and is not type-checked here.
    """
    if not a._has_const or a._meta_action_is_class:
        return False
    try:
        result = _resolve_base_type(_const_element_type(a))
    except TypeError:
        return False  # an unresolved element type is reported by the build_error row instead
    const = a._const_value
    if result.choices is not None:
        accepted = [c.value if isinstance(c, CompletionItem) else c for c in result.choices]
        return const not in accepted
    converter = result.converter
    if converter is int:  # bool is an int subclass but not a valid int const
        return type(const) is not int
    if converter is float:
        return not (isinstance(const, (int, float)) and not isinstance(const, bool))
    if converter is decimal.Decimal:
        return not isinstance(const, decimal.Decimal)
    if converter is Path:
        return not isinstance(const, Path)
    if _const_element_type(a) is str:  # a str parameter stores the const verbatim, so it must be a str
        return not isinstance(const, str)
    return False  # Any / object / unannotated / bool flag: genuinely untyped, nothing to validate


# The single validity table, evaluated by :func:`_resolve_parameters` once every argument is built
# and its cross-argument facts are linked.
_CONSTRAINTS: list[_Rule[_ArgparseArgument, Exception | None]] = [
    (
        # Signature shape: positional-only parameters cannot be passed by keyword, which is how
        # the decorator forwards parsed values.
        lambda a: a.kind == inspect.Parameter.POSITIONAL_ONLY,
        lambda a: TypeError(
            f"Parameter {a.name!r} in {a.func_qualname} is positional-only, "
            "which is not supported by @with_annotated because parameters are passed as keyword arguments."
        ),
    ),
    (
        # Signature shape: **kwargs has no fixed names to map command-line arguments onto.
        lambda a: a.kind == inspect.Parameter.VAR_KEYWORD,
        lambda a: TypeError(
            f"Parameter '**{a.name}' in {a.func_qualname} is variadic keyword (**kwargs), "
            "which is not supported by @with_annotated because there is no native way to map "
            "command-line arguments onto arbitrary keyword names."
        ),
    ),
    (
        # A name argparse reserves on the namespace; raised as ValueError (a bad name value).
        lambda a: a.name in _RESERVED_PARAM_NAMES,
        lambda a: ValueError(
            f"Parameter name {a.name!r} in {a.func_qualname} is reserved by argparse "
            f"and cannot be used as an annotated parameter name."
        ),
    ),
    (
        # *args (is_variadic) is always a plain positional, so Option() metadata is contradictory.
        lambda a: a.is_variadic and isinstance(a.metadata, Option),
        lambda a: TypeError(
            f"Parameter '*{a.name}' in {a.func_qualname} uses Option() metadata, but *args is "
            f"always a positional argument. Use Argument() metadata instead."
        ),
    ),
    (
        # *args is fixed at nargs='*'; Argument(nargs=...) cannot override it.
        lambda a: a.is_variadic and a._meta_nargs is not None,
        lambda a: TypeError(
            f"Parameter '*{a.name}' in {a.func_qualname} sets nargs={a._meta_nargs!r} via Argument(), "
            f"but *args always accepts zero or more values (nargs='*') and its arity cannot be overridden."
        ),
    ),
    (
        # For *args the annotation is the element type; a collection element would mean a tuple of
        # collections
        lambda a: a.is_variadic and a._var_positional_element_is_collection,
        lambda a: TypeError(
            f"Parameter '*{a.name}' in {a.func_qualname} is annotated with the collection type "
            f"'{a._var_positional_element_display}'. For *args the annotation is the type of each "
            f"value, not the collected tuple, so '*{a.name}: {a._var_positional_element_display}' "
            f"would mean a tuple of '{a._var_positional_element_display}'. Annotate the element type "
            f"instead (e.g. '*{a.name}: str'); values are always collected into a tuple."
        ),
    ),
    (
        lambda a: a.is_kw_only and isinstance(a.metadata, Argument),
        lambda a: TypeError(
            f"Parameter '{a.name}' in {a.func_qualname} is keyword-only but uses Argument() metadata, "
            f"which marks it as a positional argument. Keyword-only parameters always become options; "
            f"use Option() metadata (or omit the metadata) instead."
        ),
    ),
    (
        # const is meaningless on a positional: argparse rejects store_const/append_const there and
        # ignores const with nargs='?'. A positional only ever gets its command-line value or its default.
        lambda a: a._has_const and a.is_positional,
        lambda a: TypeError(
            f"Parameter '{a.name}' in {a.func_qualname} sets const=, but const is not supported on a "
            f"positional argument (argparse ignores it). Use a default value or '{_type_name(a.inner_type)} | None' "
            f"for the absent value, or use Option() to make it a flag."
        ),
    ),
    (
        # const only makes sense with the const actions; pairing it with another explicit action is contradictory.
        # Restricted to *known* actions so an unsupported action (e.g. 'store') falls through to the
        # "not supported" row below -- that is the more fundamental problem to report first.
        # A class action is exempt -- the user's action owns const semantics.
        lambda a: (
            isinstance(a._meta_action, str)
            and a._has_const
            and a._meta_action in _ACTION_TABLE
            and a._meta_action not in _CONST_ACTIONS
        ),
        lambda a: TypeError(
            f"Option(const=...) on '{a.name}' cannot be combined with action={a._meta_action!r}. "
            f"const is only valid with store_const or append_const (or omit action= to infer it from the type)."
        ),
    ),
    (
        # An explicit const action with no const value: argparse would store None on presence.
        lambda a: a._meta_action in _CONST_ACTIONS and not a._has_const,
        lambda a: TypeError(f"Option(action={a._meta_action!r}) on '{a.name}' needs a const value. Pass Option(const=...)."),
    ),
    (
        # append_const accumulates into list[T]; reject it (explicit or inferred) on a non-list type.
        lambda a: a._effective_action == "append_const" and not a._is_list,
        lambda a: TypeError(
            f"const on '{a.name}' accumulates into list[T] (append_const), but '{_type_name(a.inner_type)}' "
            f"is not a list. Use list[T] to accumulate, or a scalar type to store a single value (store_const)."
        ),
    ),
    (
        # store_const stores a single value, so a list/collection annotation is the wrong shape.
        lambda a: a._effective_action == "store_const" and a.is_collection,
        lambda a: TypeError(
            f"const on '{a.name}' stores a single value (store_const), but '{_type_name(a.inner_type)}' is a "
            f"collection. Use a scalar type, or list[T] to accumulate the const on each flag (append_const)."
        ),
    ),
    (
        # A store_const flag falls back to its default when absent; without a default (and not Optional)
        # that absent value is None, violating the declared type.
        lambda a: a._effective_action == "store_const" and not (a._effective_has_default or a.is_optional),
        lambda a: TypeError(
            f"store_const flag '{a.name}' has no value when absent: give it a default or annotate it as "
            f"'{_type_name(a.inner_type)} | None'."
        ),
    ),
    (
        # action='store' WITH const is ambiguous, not merely redundant: plain 'store' ignores const
        # unless paired with nargs='?', so the intent cannot be inferred -- a value-less const flag
        # (store_const) or an optional value (nargs='?'+const)?  Reported before the const-type-mismatch
        # row below so the ambiguity wins even when the const's type also happens to mismatch.
        lambda a: a._meta_action == "store" and a._has_const,
        lambda a: TypeError(
            f"Option(action='store', const=...) on '{a.name}' is ambiguous: 'store' ignores const unless "
            f"combined with nargs='?', so the intent cannot be inferred. Use action='store_const' for a "
            f"value-less const flag, or Option(nargs='?', const=...) (no action=) for an optional value."
        ),
    ),
    (
        # A supplied const must match the declared (element) type, keeping the parsed-value guarantee.
        _const_mismatches_type,
        lambda a: TypeError(
            f"const={a._const_value!r} on '{a.name}' does not match the declared type '{_type_name(_const_element_type(a))}'."
        ),
    ),
    (
        # An unknown string action (class actions pass through verbatim).  Checked before the
        # collection-shape row below so an unsupported action reports "not supported", not the
        # misleading "cannot be combined with a collection type".
        lambda a: isinstance(a._meta_action, str) and a._meta_action not in _ACTION_TABLE,
        lambda a: TypeError(
            f"Option(action={a._meta_action!r}) is not supported by @with_annotated. Supported actions are "
            f"store_true, store_false, count, append, extend, store_const, and append_const."
        ),
    ),
    (
        # A (known) string action on a collection type must be one of the list actions; a class action
        # owns storage and is exempt.
        lambda a: isinstance(a._meta_action, str) and a.is_collection and a._meta_action not in _LIST_ACTIONS,
        lambda a: TypeError(
            f"Option(action={a._meta_action!r}) cannot be combined with a collection type, which installs its "
            f"own action. Use action='append'/'extend'/'append_const' with list[T], or drop action= to collect via nargs."
        ),
    ),
    (
        # A user-supplied completer / choices_provider on a value-less action (store_true / store_false /
        # count / store_const / append_const) has nothing to complete: the action consumes no command-line
        # value.  Raw cmd2 raises here, so fail loud rather than silently dropping the user's request.  A
        # type-*inferred* completer (e.g. Path's) is still dropped silently by _apply_action -- only an
        # explicit one is rejected.  A class action owns its storage (no _policy), so it is exempt.
        lambda a: a._policy is not None and a._policy.drop_converter and a._has_user_completion,
        lambda a: TypeError(
            f"completer=/choices_provider= on '{a.name}' cannot be used with action={a._effective_action!r}, "
            f"which takes no value from the command line, so there is nothing to tab-complete. Remove the "
            f"completer/choices_provider, or use a value-consuming action."
        ),
    ),
    (
        lambda a: a._policy is not None and a._policy.requires is not None and not a._policy.requires(a),
        lambda a: TypeError(
            f"Option(action={a._meta_action!r}) yields {a._policy.requires_label if a._policy else ''}; "
            f"annotate the parameter as {a._policy.requires_label if a._policy else ''}."
        ),
    ),
    (
        lambda a: a._meta_action == "append" and a._meta_nargs is not None,
        _const(
            TypeError(
                "Option(action='append') collects one value per flag and cannot set nargs; "
                "use action='extend' to take multiple values per flag."
            )
        ),
    ),
    (
        lambda a: a._meta_nargs is not None and a.fixed_arity is not None and a._meta_nargs != a.fixed_arity,
        lambda a: TypeError(
            f"nargs={a._meta_nargs!r} conflicts with the fixed arity of "
            f"'{_type_name(a.inner_type)}' (expected nargs={a.fixed_arity})."
        ),
    ),
    (
        # A user nargs that collects a list on a non-collection annotation.  A nargs yields a list
        # when it is '*'/'+'/REMAINDER, an int >= 1 (argparse returns [value] even for nargs=1), or a
        # cmd2 ranged tuple other than (0, 1)
        lambda a: (
            a._meta_nargs is not None
            and not a.is_collection
            and (
                a._meta_nargs in ("*", "+", argparse.REMAINDER)
                or (isinstance(a._meta_nargs, int) and a._meta_nargs >= 1)
                or (isinstance(a._meta_nargs, tuple) and tuple(a._meta_nargs) != (0, 1))
            )
        ),
        lambda a: TypeError(
            f"nargs={a._meta_nargs!r} produces a list of values, but the annotation "
            f"'{_type_name(a.inner_type)}' is not a collection type. "
            f"Use list[T], tuple[T, ...], or set[T] (optionally with | None) to match."
        ),
    ),
    (
        lambda a: a.is_positional and a.omittable and isinstance(a.nargs, int),
        lambda a: TypeError(
            f"A fixed-arity positional (nargs={a.nargs}) cannot be optional; argparse always "
            f"requires it. Drop the default or '| None', make it an option (give it a default without "
            f"Argument()), or use a variable-arity type such as tuple[T, ...]."
        ),
    ),
    (
        # Conflict: both the signature and the metadata supplied a default.  These are two
        # sources of truth for the same value; refuse rather than silently pick a winner.
        lambda a: a.has_default and a._has_meta_default,
        lambda a: TypeError(
            f"parameter '{a.name}' in {a.func_qualname} has a default in both the function signature "
            f"({a.param_default!r}) and the metadata ({a._meta_default!r}); specify it in only one place."
        ),
    ),
    (
        # argparse.SUPPRESS removes the attribute from the parsed namespace when absent, so the
        # function would be called without the kwarg it expects.  Reject from either source.
        lambda a: a._effective_has_default and a._effective_param_default == argparse.SUPPRESS,
        lambda a: TypeError(
            f"parameter '{a.name}' in {a.func_qualname} uses argparse.SUPPRESS as a default, which is "
            f"not supported by @with_annotated: SUPPRESS removes '{a.name}' from the parsed namespace "
            f"when absent, but the function expects it as a keyword argument. Use a real default or "
            f"annotate the type as '{_type_name(a.inner_type)} | None'."
        ),
    ),
    (
        lambda a: (
            a._effective_has_default
            and a._effective_param_default is None
            and not a.is_optional
            and a.inner_type not in (object, Any, inspect.Parameter.empty)
        ),
        lambda a: TypeError(
            f"parameter '{a.name}' in {a.func_qualname} declared as '{_type_name(a.inner_type)}' has a "
            f"default of None, but '{_type_name(a.inner_type)}' is not Optional, so omitting it would pass None "
            f"and violate the type hint. Annotate it as '{_type_name(a.inner_type)} | None' to allow None, or "
            f"give it a non-None default."
        ),
    ),
    (
        # Cross-argument: a variable-arity positional must be last, else argparse cannot split
        # tokens unambiguously (``def f(self, a: str, *rest: str)`` is fine -- the variadic is last).
        # ``has_following_positional`` is linked by _resolve_parameters before this table runs.
        lambda a: (
            a.is_positional and a.has_following_positional and (a.nargs in _VARIABLE_NARGS or isinstance(a.nargs, tuple))
        ),
        lambda a: TypeError(
            f"Parameter '{a.name}' in {a.func_qualname} has variable arity (nargs={a.nargs!r}) "
            f"but is followed by another positional argument, so argparse cannot assign command-line "
            f"tokens unambiguously. Make it the last positional, give the following positional(s) a "
            f"default, or make them options."
        ),
    ),
    (
        # base_command only: its parameters become subcommand-level options, so a positional
        # conflicts with subcommand dispatch. ``is_base_command`` is set from the decorator's role;
        # non-base arguments skip these rows on the first conjunct.
        lambda a: a.is_base_command and a.is_positional and not isinstance(a.metadata, Argument),
        lambda a: TypeError(
            f"Parameter '{a.name}' in {a.func_qualname} is positional, "
            f"which conflicts with subcommand parsing. "
            f"Use a keyword-only parameter (after *) or give it a default value."
        ),
    ),
    (
        lambda a: a.is_base_command and isinstance(a.metadata, Argument),
        lambda a: TypeError(
            f"Parameter '{a.name}' in {a.func_qualname} uses Argument() metadata, "
            f"which creates a positional argument that conflicts with subcommand parsing."
        ),
    ),
    (
        # Cross-config: a parameter assigned to two argument groups is ambiguous. The membership
        # indices are linked by _resolve_parameters from the decorator's groups= before this runs.
        lambda a: len(a.argument_group_indices) > 1,
        lambda a: ValueError(
            f"parameter {a.name!r} cannot be assigned to both argument "
            f"group {a.argument_group_indices[0]} and argument group {a.argument_group_indices[1]}"
        ),
    ),
    (
        # Cross-config: a parameter cannot belong to two mutually exclusive groups.
        lambda a: len(a.mutex_group_indices) > 1,
        lambda a: ValueError(f"parameter {a.name!r} cannot be assigned to multiple mutually exclusive groups"),
    ),
    (
        # Cross-config: a required member is incompatible with a mutex group -- only one member is
        # supplied, so the others arrive as None (violating its non-Optional type), and argparse forbids
        # it.  This is an argument-typing rule (required-ness comes from the annotation), so it lives here
        # rather than with the group graph construction.
        lambda a: a.required and bool(a.mutex_group_indices),
        lambda a: ValueError(
            f"parameter {a.name!r} in mutually exclusive group {a.mutex_group_indices[0]} is required (no default "
            f"and not Optional), but mutually exclusive group members must be optional because "
            f"only one is supplied on the command line and the others arrive as None. "
            f"Give it a default or annotate it as 'T | None'."
        ),
    ),
    (
        # Type resolution failed during build (captured by _apply_type so build order does not pick
        # the message).  Raised last, so a more specific rule above wins; otherwise the raw type error.
        lambda a: a.build_error is not None,
        lambda a: a.build_error,
    ),
    (_always, _const(None)),  # no violation
]


# ---------------------------------------------------------------------------
# Signature → Parser conversion
# ---------------------------------------------------------------------------


# Parameters handled specially by the decorator and not added to the parser.  The first positional
# parameter (self/cls) is always skipped by position; these cover additional decorator-managed names.
_SKIP_PARAMS = frozenset({"cmd2_handler", "cmd2_statement"})


def _link_group_membership(
    by_name: dict[str, _ArgparseArgument],
    specs: tuple[Group, ...] | None,
    select: Callable[[_ArgparseArgument], list[int]],
) -> None:
    """Append each spec's 1-based index to the *select*-ed membership list of each member argument.

    :func:`_resolve_parameters` validates member references via :meth:`Group._validate_members`
    before calling this, so every member name resolves to a built argument.
    """
    if not specs:
        return
    for index, spec in enumerate(specs, start=1):
        for name in spec.members:
            select(by_name[name]).append(index)


def _resolve_parameters(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str] = _SKIP_PARAMS,
    base_command: bool = False,
    groups: tuple[Group, ...] | None = None,
    mutually_exclusive_groups: tuple[Group, ...] | None = None,
) -> list[_ArgparseArgument]:
    """Resolve a function signature into a list of argparse-argument builders.

    ``base_command`` marks each argument's context so the base-command rows in :data:`_CONSTRAINTS`
    fire (a base command's parameters become subcommand-level options, so positionals are rejected),
    and drives the function-level ``cmd2_handler`` check below (a plain ``if``, not a table row,
    because its subject is the whole function rather than a single argument).
    ``groups``/``mutually_exclusive_groups`` are linked onto each argument as membership facts so the
    cross-config rows in :data:`_CONSTRAINTS` (double-assignment, required-member) fire from the one
    validity pass.
    """
    sig = inspect.signature(func)
    # Function-level check, before any argument is built: base_command dispatches to subcommands
    # through its cmd2_handler parameter, so without one there is nothing to dispatch to.  Checked
    # here rather than in the per-argument _CONSTRAINTS loop so it also fires when the function
    # declares zero parameters, and wins over any per-argument rule on the same function.
    if base_command and "cmd2_handler" not in sig.parameters:
        raise TypeError(f"with_annotated(base_command=True) requires a 'cmd2_handler' parameter in {func.__qualname__}")
    try:
        hints = get_type_hints(func, include_extras=True)
    except (NameError, AttributeError, TypeError) as exc:
        raise TypeError(
            f"Failed to resolve type hints for {func.__qualname__}. Ensure all annotations use valid, importable types."
        ) from exc

    resolved: list[_ArgparseArgument] = []

    # Skip the first parameter by position (self/cls for methods)
    params = list(sig.parameters.items())
    if params:
        params = params[1:]

    for name, param in params:
        if name in skip_params:
            continue

        # *args has no default and is never keyword-only; its hint is the element type (default str).
        is_variadic = param.kind == inspect.Parameter.VAR_POSITIONAL
        has_default = param.default is not inspect.Parameter.empty
        # Peel Annotated then Optional.  For *args the annotation is the element type T, modeled as a
        # variadic tuple[T, ...]; its own optionality is dropped (*args is always a possibly-empty tuple).
        inner_type, metadata, is_optional = _normalize_annotation(hints.get(name, str if is_variadic else param.annotation))
        if is_variadic:
            inner_type = types.GenericAlias(tuple, (inner_type, ...))
            is_optional = False
        arg = _ArgparseArgument(
            name=name,
            func_qualname=func.__qualname__,
            has_default=has_default,
            param_default=param.default if has_default else None,
            is_kw_only=param.kind == inspect.Parameter.KEYWORD_ONLY,
            is_variadic=is_variadic,
            inner_type=inner_type,
            metadata=metadata,
            is_optional=is_optional,
            kind=param.kind,
            is_base_command=base_command,
        )
        resolved.append(arg)

    # Validate the whole list at once (per-argument + cross-argument rules) now that every
    # argument is built and its cross-argument facts can be linked.
    positionals = [arg for arg in resolved if arg.is_positional]
    for arg in positionals[:-1]:  # every positional except the last has a following positional
        arg.has_following_positional = True
    by_name = {arg.name: arg for arg in resolved}
    # Reject group references to nonexistent parameters before the constraint table runs.
    all_param_names = set(by_name)
    for spec in groups or ():
        spec._validate_members(all_param_names=all_param_names, group_type="groups")
    for spec in mutually_exclusive_groups or ():
        spec._validate_members(all_param_names=all_param_names, group_type="mutually_exclusive_groups")
    _link_group_membership(by_name, groups, lambda a: a.argument_group_indices)
    _link_group_membership(by_name, mutually_exclusive_groups, lambda a: a.mutex_group_indices)
    for arg in resolved:
        arg._check_constraints()
    return resolved


def _var_positional_call_plan(func: Callable[..., Any]) -> tuple[list[str], str | None]:
    """Return ``(leading_positional_names, var_positional_name)`` for unpacking ``*args``.

    ``leading_positional_names`` are the positional-or-keyword parameters that
    precede ``*args`` (they must be passed positionally, in order, so ``*args``
    can follow). ``var_positional_name`` is the ``*args`` parameter name, or
    ``None`` when the function has no ``*args``.
    """
    params = list(inspect.signature(func).parameters.values())[1:]  # skip self/cls
    leading: list[str] = []
    for param in params:
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            return leading, param.name
        if param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD:
            leading.append(param.name)
    return leading, None


def _invoke_command_func(
    func: Callable[..., Any],
    self_arg: Any,
    func_kwargs: dict[str, Any],
    *,
    leading_names: list[str],
    var_positional_name: str | None,
) -> Any:
    """Call *func* from parsed kwargs, unpacking ``*args`` positionally when present."""
    if var_positional_name is None:
        return func(self_arg, **func_kwargs)
    positional = [func_kwargs.pop(name) for name in leading_names]
    var_values = func_kwargs.pop(var_positional_name, None) or ()
    return func(self_arg, *positional, *var_values, **func_kwargs)


def _filtered_namespace_kwargs(
    ns: argparse.Namespace,
    *,
    accepted: Container[str] | None = None,
    exclude_subcommand: bool = False,
) -> dict[str, Any]:
    """Filter a parsed Namespace down to user-visible kwargs."""
    from .constants import NS_ATTR_SUBCMD_HANDLER

    filtered: dict[str, Any] = {}
    for key, value in vars(ns).items():
        if accepted is not None and key not in accepted:
            continue
        if key == NS_ATTR_SUBCMD_HANDLER:
            continue
        if exclude_subcommand and key == "subcommand":
            continue
        filtered[key] = value

    return filtered


def _build_argument_group_targets(
    parser: argparse.ArgumentParser,
    *,
    groups: tuple[Group, ...] | None,
) -> tuple[dict[str, _ArgumentTarget], dict[str, argparse._ArgumentGroup]]:
    """Build argument groups and return add_argument targets for their members.

    Member references and double-assignment are validated upstream by :func:`_resolve_parameters`
    (via :meth:`Group._validate_members`) and :data:`_CONSTRAINTS` (the ``argument_group_indices``
    fact), so construction can assign each member unconditionally.
    """
    target_for: dict[str, _ArgumentTarget] = {}
    argument_group_for: dict[str, argparse._ArgumentGroup] = {}

    if not groups:
        return target_for, argument_group_for

    for spec in groups:
        if spec.required:
            raise ValueError(
                "Group(required=True) is only valid in mutually_exclusive_groups; "
                "argparse's add_argument_group has no 'required' flag"
            )
        group = parser.add_argument_group(title=spec.title, description=spec.description)
        for name in spec.members:
            argument_group_for[name] = group
            target_for[name] = group

    return target_for, argument_group_for


def _apply_mutex_group_targets(
    parser: argparse.ArgumentParser,
    *,
    target_for: dict[str, _ArgumentTarget],
    argument_group_for: dict[str, argparse._ArgumentGroup],
    mutually_exclusive_groups: tuple[Group, ...] | None,
) -> None:
    """Build mutually exclusive groups and update add_argument targets for their members.

    Member references, double-assignment, and required-member rejections are validated upstream by
    :func:`_resolve_parameters` and :data:`_CONSTRAINTS` (the ``mutex_group_indices`` fact); the
    remaining check -- a mutex group spanning different argument groups -- stays here because its
    subject is the group, not an argument.
    """
    if not mutually_exclusive_groups:
        return

    for index, spec in enumerate(mutually_exclusive_groups, start=1):
        member_names = spec.members

        parent_groups = {argument_group_for[name] for name in member_names if name in argument_group_for}
        if len(parent_groups) > 1:
            raise ValueError(
                f"mutually exclusive group {index} spans parameters in different argument groups, "
                "which argparse cannot represent cleanly"
            )

        mutex_parent: _ArgumentTarget = next(iter(parent_groups)) if parent_groups else parser
        mutex_group = mutex_parent.add_mutually_exclusive_group(required=spec.required)
        for name in member_names:
            target_for[name] = mutex_group


def _docstring_first_paragraph(doc: str | None) -> str | None:
    """Return the first paragraph of *doc* (everything before the first blank line), or ``None``.

    Used to auto-fill ``description`` from ``func.__doc__`` when the caller didn't pass one.
    Subsequent paragraphs are intentionally ignored: rst field directives (``:param:``, ``:return:``)
    routinely live below the summary and would render as nonsense in ``--help``.
    """
    if not doc:
        return None
    cleaned = inspect.cleandoc(doc).strip()
    if not cleaned:
        return None
    # Stop at the first blank line OR the first rst field directive (``:param:``, ``:return:``, ...);
    # a directive that immediately follows the summary with no blank line would otherwise leak into --help.
    summary_lines: list[str] = []
    for line in cleaned.splitlines():
        if not line.strip() or line.lstrip().startswith(":"):
            break
        summary_lines.append(line)
    return "\n".join(summary_lines).strip() or None


def build_parser_from_function(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str] = _SKIP_PARAMS,
    groups: tuple[Group, ...] | None = None,
    mutually_exclusive_groups: tuple[Group, ...] | None = None,
    parser_class: type[Cmd2ArgumentParser] | None = None,
    **parser_kwargs: Unpack[Cmd2ParserKwargs],
) -> Cmd2ArgumentParser:
    """Inspect a function's signature and build a ``Cmd2ArgumentParser``.

    Parameters without defaults become positional arguments.
    Parameters with defaults become ``--option`` flags.
    ``Annotated[T, Argument(...)]`` or ``Annotated[T, Option(...)]``
    overrides the default behavior.

    Any kwarg accepted by :class:`~cmd2.Cmd2ArgumentParser`'s constructor
    (``description``, ``epilog``, ``prog``, ``usage``, ``parents``,
    ``argument_default``, ``prefix_chars``, ``fromfile_prefix_chars``,
    ``conflict_handler``, ``add_help``, ``allow_abbrev``, ``exit_on_error``,
    ``formatter_class``, ``ap_completer_type``, plus Python >= 3.14's
    ``suggest_on_error`` and ``color``) is forwarded via ``**parser_kwargs``;
    see :class:`Cmd2ParserKwargs` for the canonical list and IDE
    autocomplete.

    When ``description`` is omitted from ``parser_kwargs``, the first paragraph
    of ``func.__doc__`` (up to the first blank line) is used.

    :param func: the command function to inspect
    :param skip_params: parameter names to exclude from the parser
    :param groups: :class:`Group` instances assigning parameter names to argument
                   groups (for help display)
    :param mutually_exclusive_groups: :class:`Group` instances of mutually exclusive parameters
    :param parser_class: custom parser class (defaults to the configured default).
                         The chosen class must accept whatever subset of
                         :class:`Cmd2ParserKwargs` you pass.
    :param parser_kwargs: forwarded :class:`Cmd2ParserKwargs`
    :return: a fully configured ``Cmd2ArgumentParser``
    """
    parser_cls = parser_class or DEFAULT_ARGUMENT_PARSER
    if "description" not in parser_kwargs:
        auto_description = _docstring_first_paragraph(func.__doc__)
        if auto_description is not None:
            parser_kwargs["description"] = auto_description
    parser = parser_cls(**parser_kwargs)

    # _resolve_parameters validates each argument and the cross-argument/cross-config rules (e.g. a
    # variable-arity positional must be last; double-assignment and required-mutex-member) once the
    # whole list is built and the group memberships are linked.
    resolved = _resolve_parameters(
        func,
        skip_params=skip_params,
        groups=groups,
        mutually_exclusive_groups=mutually_exclusive_groups,
    )

    # ``argument_default=argparse.SUPPRESS`` removes an absent argument from the parsed namespace.
    # That is safe only for arguments that are always supplied (required) or carry their own default;
    # an *omittable* argument with no default (e.g. a ``T | None`` positional -> nargs='?') would be
    # dropped when absent, leaving the function without a keyword argument it expects.  ``*args`` is
    # exempt: the invocation path substitutes an empty tuple for it.  Reject the combination here,
    # mirroring the per-argument ``default=argparse.SUPPRESS`` rejection.
    if parser_kwargs.get("argument_default") is argparse.SUPPRESS:
        dropped = [
            arg.name
            for arg in resolved
            if arg.default is _UNSET and arg.omittable and not arg.required and not arg.is_variadic
        ]
        if dropped:
            raise TypeError(
                f"argument_default=argparse.SUPPRESS is not supported by @with_annotated for {func.__qualname__}: "
                f"it would drop {dropped!r} from the parsed namespace when absent, but the function expects "
                f"{'them' if len(dropped) > 1 else 'it'} as a keyword argument. Give each an explicit default or "
                f"make it required, or drop argument_default=argparse.SUPPRESS."
            )

    # Build the group lookup (member references already validated by _resolve_parameters).
    target_for, argument_group_for = _build_argument_group_targets(parser, groups=groups)
    _apply_mutex_group_targets(
        parser,
        target_for=target_for,
        argument_group_for=argument_group_for,
        mutually_exclusive_groups=mutually_exclusive_groups,
    )

    # Add each argument to its target (its group/mutex group if assigned, else the parser).
    for arg in resolved:
        arg.add_to(target_for.get(arg.name, parser))

    return parser


def _derive_subcommand_name(func: Callable[..., Any], subcommand_to: str) -> str:
    """Derive the subcommand name from the function name and validate the naming convention.

    ``subcommand_to='team member'`` + ``func.__name__='team_member_add'`` -> ``'add'``.
    """
    expected_prefix = subcommand_to.replace(" ", "_") + "_"
    if not func.__name__.startswith(expected_prefix):
        raise TypeError(
            f"Function '{func.__name__}' must be named '{expected_prefix}<subcommand>' "
            f"when using subcommand_to='{subcommand_to}'"
        )
    return func.__name__[len(expected_prefix) :]


@dataclass(frozen=True)
class _ParserBuildOptions:
    """The parser/subcommand configuration shared by every ``with_annotated`` build path.

    These options are a data clump threaded identically through the regular-command and subcommand
    builders; bundling them lets :func:`_make_parser_builder` host the single deferred build flow.
    """

    groups: tuple[Group, ...] | None = None
    mutually_exclusive_groups: tuple[Group, ...] | None = None
    parser_class: type[Cmd2ArgumentParser] | None = None
    #: Forwarded :class:`Cmd2ParserKwargs` (description, epilog, prog, ...).
    #: Stored as a plain ``dict`` so missing keys yield argparse's defaults
    #: rather than this layer second-guessing them.
    parser_kwargs: dict[str, Any] = field(default_factory=dict)
    subcommand_required: bool = True
    subcommand_metavar: str = "SUBCOMMAND"
    subcommand_title: str | None = None
    subcommand_description: str | None = None


def _make_parser_builder(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str],
    base_command: bool,
    options: _ParserBuildOptions,
) -> Callable[[], Cmd2ArgumentParser]:
    """Return the deferred builder for *func*'s parser (adds the subcommands group when ``base_command``).

    Shared by the regular-command and subcommand decorators so the build flow lives in one place.
    """

    def parser_builder() -> Cmd2ArgumentParser:
        parser = build_parser_from_function(
            func,
            skip_params=skip_params,
            groups=options.groups,
            mutually_exclusive_groups=options.mutually_exclusive_groups,
            parser_class=options.parser_class,
            **options.parser_kwargs,
        )
        if base_command:
            # dict[str, Any] is load-bearing: the typeshed stub types title/metavar as non-None,
            # but argparse accepts None at runtime, so splatting avoids a false overload error.
            kwargs: dict[str, Any] = {
                "dest": "subcommand",
                "metavar": options.subcommand_metavar,
                "required": options.subcommand_required,
                "title": options.subcommand_title,
                "description": options.subcommand_description,
            }
            parser.add_subparsers(**kwargs)
        return parser

    return parser_builder


def _build_subcommand_handler(
    func: Callable[..., Any],
    subcommand_to: str,
    *,
    base_command: bool = False,
    options: _ParserBuildOptions,
) -> tuple[Callable[..., Any], str, Callable[[], Cmd2ArgumentParser]]:
    """Build a subcommand handler wrapper and its parser from type annotations.

    Validates the naming convention, builds a parser from annotations, and
    returns a wrapper that unpacks ``argparse.Namespace`` into typed kwargs
    before calling the original function.

    :param func: the subcommand handler function
    :param subcommand_to: parent command name (space-delimited for nesting)
    :param base_command: if True, the parser also gets ``add_subparsers()``
    :param options: shared parser/subcommand configuration (see :class:`_ParserBuildOptions`)
    :return: ``(handler, subcommand_name, parser_builder)``
    """
    subcmd_name = _derive_subcommand_name(func, subcommand_to)

    if base_command:
        # Validate eagerly (decoration time); the base-command rows in _CONSTRAINTS fire here.
        _resolve_parameters(func, base_command=True)

    _accepted = set(list(inspect.signature(func).parameters.keys())[1:])
    _leading_names, _var_positional_name = _var_positional_call_plan(func)

    @functools.wraps(func)
    def handler(self_arg: Any, ns: Any) -> Any:
        """Unpack Namespace into typed kwargs for the subcommand handler."""
        filtered = _filtered_namespace_kwargs(ns, accepted=_accepted)
        return _invoke_command_func(
            func, self_arg, filtered, leading_names=_leading_names, var_positional_name=_var_positional_name
        )

    parser_builder = _make_parser_builder(func, skip_params=_SKIP_PARAMS, base_command=base_command, options=options)
    return handler, subcmd_name, parser_builder


@overload
def with_annotated(func: Callable[..., Any]) -> Callable[..., Any]: ...


@overload
def with_annotated(
    func: None = ...,
    *,
    ns_provider: Callable[..., argparse.Namespace] | None = ...,
    preserve_quotes: bool = ...,
    with_unknown_args: bool = ...,
    base_command: bool = ...,
    subcommand_to: str | None = ...,
    help: str | None = ...,
    aliases: Sequence[str] = ...,
    deprecated: bool = ...,
    groups: tuple[Group, ...] | None = ...,
    mutually_exclusive_groups: tuple[Group, ...] | None = ...,
    parser_class: type[Cmd2ArgumentParser] | None = ...,
    subcommand_required: bool = ...,
    subcommand_metavar: str = ...,
    subcommand_title: str | None = ...,
    subcommand_description: str | None = ...,
    **parser_kwargs: Unpack[Cmd2ParserKwargs],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def with_annotated(
    func: Callable[..., Any] | None = None,
    *,
    ns_provider: Callable[..., argparse.Namespace] | None = None,
    preserve_quotes: bool = False,
    with_unknown_args: bool = False,
    base_command: bool = False,
    subcommand_to: str | None = None,
    help: str | None = None,  # noqa: A002
    aliases: Sequence[str] = (),
    deprecated: bool = False,
    groups: tuple[Group, ...] | None = None,
    mutually_exclusive_groups: tuple[Group, ...] | None = None,
    parser_class: type[Cmd2ArgumentParser] | None = None,
    subcommand_required: bool = True,
    subcommand_metavar: str = "SUBCOMMAND",
    subcommand_title: str | None = None,
    subcommand_description: str | None = None,
    **parser_kwargs: Unpack[Cmd2ParserKwargs],
) -> Callable[..., Any] | Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a ``do_*`` method to build its argparse parser from type annotations.

    :param func: the command function (when used without parentheses)
    :param ns_provider: optional callable returning a prepopulated argparse.Namespace.
                        Not supported with ``subcommand_to``.
    :param preserve_quotes: if True, preserve quotes in arguments.
                            Not supported with ``subcommand_to``.
    :param with_unknown_args: if True, capture unknown args (passed as extra kwarg ``_unknown``).
                              Not supported with ``subcommand_to``.
    :param base_command: if True, this command has subcommands (adds ``add_subparsers()``).
                         Requires a ``cmd2_handler`` parameter and no positional arguments.
    :param subcommand_to: parent command name (e.g. ``'team'`` or ``'team member'``).
                          Function must be named ``{parent_underscored}_{subcommand}``.
    :param help: help text for the subcommand (only valid with ``subcommand_to``)
    :param aliases: alternative names for the subcommand (only valid with ``subcommand_to``)
    :param deprecated: mark the subcommand as deprecated in ``--help`` (only valid with ``subcommand_to``)
    :param groups: :class:`Group` instances assigning parameter names to argument
                   groups (pass ``title``/``description`` for a titled section)
    :param mutually_exclusive_groups: :class:`Group` instances of mutually exclusive parameters
    :param parser_class: custom parser class (defaults to the configured default)
    :param subcommand_required: whether a subcommand must be supplied (only with ``base_command``)
    :param subcommand_metavar: metavar shown for the subcommands group (only with ``base_command``)
    :param subcommand_title: title for the subcommands ``--help`` section (only with ``base_command``)
    :param subcommand_description: description for the subcommands ``--help`` section (only with ``base_command``)
    :param parser_kwargs: any kwarg accepted by :class:`~cmd2.Cmd2ArgumentParser`'s
                          constructor (see :class:`Cmd2ParserKwargs` for the full list and
                          per-field types). IDEs/type-checkers surface these on the call
                          site via PEP 692 ``Unpack``. Notable behaviors layered on top of
                          the raw passthrough:

                          - ``description`` -- when omitted, the first paragraph of the
                            function's docstring (up to the first blank line) is used;
                            pass an explicit value to override that.
                          - ``prog`` -- rejected when ``subcommand_to`` is set, because
                            cmd2's subcommand machinery rewrites ``prog`` from the parent
                            command hierarchy and any value here would be silently
                            overwritten.

    Example::

        class MyApp(cmd2.Cmd):
            @with_annotated
            def do_greet(self, name: str, count: int = 1): ...

            @with_annotated(base_command=True)
            def do_team(self, *, cmd2_handler): ...

            @with_annotated(subcommand_to='team', help='create a team')
            def team_create(self, name: str): ...

    """
    if (help is not None or aliases or deprecated) and subcommand_to is None:
        raise TypeError("'help', 'aliases', and 'deprecated' are only valid with subcommand_to")
    if subcommand_to is not None:
        unsupported: list[str] = []
        if ns_provider is not None:
            unsupported.append("ns_provider")
        if preserve_quotes:
            unsupported.append("preserve_quotes")
        if with_unknown_args:
            unsupported.append("with_unknown_args")
        if "prog" in parser_kwargs:
            # cmd2's subcommand machinery (``update_prog``) rewrites prog from the parent
            # command hierarchy, so any value supplied here would be silently overwritten.
            unsupported.append("prog")
        if unsupported:
            names = ", ".join(unsupported)
            raise TypeError(
                f"{names} {'is' if len(unsupported) == 1 else 'are'} not supported with subcommand_to. "
                "Configure these behaviors on the base command instead."
            )

    options = _ParserBuildOptions(
        groups=groups,
        mutually_exclusive_groups=mutually_exclusive_groups,
        parser_class=parser_class,
        parser_kwargs=dict(parser_kwargs),
        subcommand_required=subcommand_required,
        subcommand_metavar=subcommand_metavar,
        subcommand_title=subcommand_title,
        subcommand_description=subcommand_description,
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if with_unknown_args:
            unknown_param = inspect.signature(fn).parameters.get("_unknown")
            if unknown_param is None:
                raise TypeError("with_annotated(with_unknown_args=True) requires a parameter named _unknown")
            if unknown_param.kind is inspect.Parameter.POSITIONAL_ONLY:
                raise TypeError("Parameter _unknown must be keyword-compatible when with_unknown_args=True")

        if not base_command and "cmd2_handler" in inspect.signature(fn).parameters:
            raise TypeError(
                f"Parameter 'cmd2_handler' in {fn.__qualname__} is only valid when with_annotated(base_command=True) is used."
            )

        if subcommand_to is not None:
            handler, subcmd_name, subcmd_parser_builder = _build_subcommand_handler(
                fn,
                subcommand_to,
                base_command=base_command,
                options=options,
            )
            spec = SubcommandSpec(
                name=subcmd_name,
                command=subcommand_to,
                help=help,
                aliases=tuple(aliases),
                deprecated=deprecated,
                parser_source=subcmd_parser_builder,
            )
            setattr(handler, constants.SUBCMD_ATTR_SPEC, spec)
            return handler

        command_name = fn.__name__[len(constants.COMMAND_FUNC_PREFIX) :]

        skip_params = _SKIP_PARAMS | ({"_unknown"} if with_unknown_args else frozenset())
        if base_command:
            # Validate eagerly (decoration time); the base-command rows in _CONSTRAINTS fire here.
            _resolve_parameters(fn, skip_params=skip_params, base_command=True)

        # Cache signature introspection at decoration time, not per-invocation
        accepted = set(list(inspect.signature(fn).parameters.keys())[1:])
        leading_names, var_positional_name = _var_positional_call_plan(fn)

        parser_builder = _make_parser_builder(fn, skip_params=skip_params, base_command=base_command, options=options)

        @functools.wraps(fn)
        def cmd_wrapper(*args: Any, **kwargs: Any) -> bool | None:
            cmd2_app, statement_arg = _parse_positionals(args)
            owner = args[0]  # Cmd or CommandSet instance
            statement, parsed_arglist = cmd2_app.statement_parser.get_command_arg_list(
                command_name, statement_arg, preserve_quotes
            )

            arg_parser = cmd2_app.command_parsers.get(cmd_wrapper)
            if arg_parser is None:
                raise ValueError(f"No argument parser found for {command_name}")

            if ns_provider is None:
                namespace = None
            else:
                provider_self = cmd2_app._resolve_func_self(ns_provider, args[0])
                namespace = ns_provider(provider_self if provider_self is not None else cmd2_app)

            try:
                if with_unknown_args:
                    ns, unknown = arg_parser.parse_known_args(parsed_arglist, namespace)
                else:
                    ns = arg_parser.parse_args(parsed_arglist, namespace)
                    unknown = None
            except SystemExit as exc:
                raise Cmd2ArgparseError from exc

            setattr(ns, constants.NS_ATTR_STATEMENT, statement)
            handler = getattr(ns, constants.NS_ATTR_SUBCMD_HANDLER, None)
            if base_command and handler is not None:
                handler = functools.partial(handler, ns)
            ns.cmd2_handler = handler

            func_kwargs = _filtered_namespace_kwargs(ns, accepted=accepted, exclude_subcommand=base_command)

            if with_unknown_args:
                func_kwargs["_unknown"] = unknown

            func_kwargs.update(kwargs)
            result: bool | None = _invoke_command_func(
                fn, owner, func_kwargs, leading_names=leading_names, var_positional_name=var_positional_name
            )
            return result

        setattr(cmd_wrapper, constants.CMD_ATTR_PARSER_SOURCE, parser_builder)
        setattr(cmd_wrapper, constants.CMD_ATTR_PRESERVE_QUOTES, preserve_quotes)

        return cmd_wrapper

    # Support both @with_annotated and @with_annotated(...)
    if func is not None:
        return decorator(func)
    return decorator
