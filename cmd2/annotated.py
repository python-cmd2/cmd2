"""Build argparse parsers from type-annotated function signatures.

.. warning:: Experimental

   This module is experimental and its behavior may change in future releases.

This module provides the :func:`with_annotated` decorator that inspects a
command function's type hints and default values to automatically construct
a ``Cmd2ArgumentParser``.  It also provides :class:`Argument` and
:class:`Option` metadata classes for use with ``typing.Annotated`` when
finer control is needed.

Basic usage -- parameters without defaults become positional arguments,
parameters with defaults become ``--option`` flags.  Keyword-only
parameters (after ``*``) always become options; without a default they
are required.  A ``*args`` parameter becomes a variadic positional that
accepts zero or more values (``nargs='*'``), collected into a tuple.
Underscores in parameter names are auto-converted to
dashes in the generated flag (``dry_run`` -> ``--dry-run``); pass
explicit names via ``Option("--my_flag")`` to opt out.  The parameter
name ``dest`` is reserved and cannot be used.  Positional-only
parameters (before ``/``) and ``**kwargs`` are not supported and raise
``TypeError``::

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
- ``int``, ``float`` -- sets ``type=`` for argparse
- ``bool`` with default -- ``--flag / --no-flag`` via ``BooleanOptionalAction``
- positional ``bool`` -- parsed from ``true/false``, ``yes/no``, ``on/off``, ``1/0``
- ``pathlib.Path`` -- sets ``type=Path``
- ``enum.Enum`` subclass -- ``type=converter``, ``choices`` from member values
- ``decimal.Decimal`` -- sets ``type=Decimal``
- ``Literal[...]`` -- sets ``type=converter`` and ``choices`` from literal values
- ``list[T]`` / ``set[T]`` / ``tuple[T, ...]`` -- ``nargs='+'`` (or ``'*'`` if has a default or is ``| None``)
- ``tuple[T, T]`` (fixed arity, same type) -- ``nargs=N`` with ``type=T``
- ``*args: T`` -- variadic positional with ``nargs='*'`` (zero or more), collected into a tuple.
  ``T`` is the type of each value (a scalar), not the collected tuple
- ``T | None`` (no default) -- positional with ``nargs='?'`` (accepts 0-or-1 tokens)
- ``T | None = None`` -- ``--flag`` option with ``default=None``

Action compatibility note:

- Some argparse actions (``count``, ``store_true``, ``store_false``,
  ``store_const``, ``help``, ``version``) do not accept ``type=``.
  If one of these actions is selected via ``Option(action=...)``, any
  inferred ``type`` converter is removed before calling ``add_argument()``.

Unsupported patterns (raise ``TypeError``):

- A scalar type with no converter (e.g. ``datetime.datetime``, ``uuid.UUID``,
  ``bytes``, or any custom class).  Without a converter the command-line value
  would silently arrive as a plain string, so it is rejected.  Supported scalar
  types are ``str``, ``int``, ``float``, ``bool``, ``decimal.Decimal``,
  ``pathlib.Path``, ``enum.Enum`` subclasses, and ``Literal[...]`` (or a subclass
  of one).  ``str``/``Any``/``object`` and unannotated parameters pass through as
  raw strings.
- ``str | int`` -- union of multiple non-None types is ambiguous
- ``tuple[int, str, float]`` -- mixed element types are not currently supported
  because argparse can only apply a single ``type=`` converter per argument
- ``*args: tuple[T, ...]`` (or ``*args: list[T]`` / any collection element) -- on ``*args``
  the annotation is the type of each value, so a collection element would mean a
  tuple-of-collections.  Annotate the element type instead, e.g. ``*args: str``
- ``Annotated[T, Argument(nargs=N)]`` where ``N`` produces a list (``'*'``, ``'+'``,
  or integer ``>= 1``) and ``T`` is not a collection type.  Use ``list[T]`` or
  ``tuple[T, ...]`` to match the runtime shape.
- ``Annotated[tuple[T, T], Argument(nargs=N)]`` where ``N`` differs from the number of
  elements declared by the tuple type.  The tuple already pins ``nargs``.

When combining ``Annotated`` with ``Optional``, the union must go
*inside*: ``Annotated[T | None, meta]``.  Writing
``Annotated[T, meta] | None`` is ambiguous and raises ``TypeError``.

Note: ``Path`` and ``Enum`` annotations with ``@with_annotated`` also get
automatic tab completion via generated parser metadata.
If a user-supplied ``choices_provider`` or ``completer`` is set on an argument,
it drives completion in place of the inferred static ``choices``.  The inferred
``type`` converter is kept, so values still coerce to the declared type (an
``Enum`` to its member, ``Literal[1, 2]`` to ``int``) and values outside the
declared type are rejected at parse time.

The parameter name ``cmd2_handler`` is reserved for base commands declared with
``with_annotated(base_command=True)`` and may not be used elsewhere.
"""

import argparse
import decimal
import enum
import functools
import inspect
import types
from collections.abc import Callable, Container, Sequence
from pathlib import Path
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from . import constants
from .argparse_utils import Cmd2ArgumentParser, SubcommandSpec
from .completion import CompletionItem
from .decorators import _parse_positionals
from .exceptions import Cmd2ArgparseError
from .rich_utils import Cmd2HelpFormatter
from .types import CmdOrSetT, UnboundChoicesProvider, UnboundCompleter

# ---------------------------------------------------------------------------
# Metadata classes
# ---------------------------------------------------------------------------


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

    def __init__(
        self,
        *,
        help_text: str | None = None,
        metavar: str | None = None,
        nargs: int | str | tuple[int, ...] | None = None,
        choices: list[Any] | None = None,
        choices_provider: UnboundChoicesProvider[CmdOrSetT] | None = None,
        completer: UnboundCompleter[CmdOrSetT] | None = None,
        table_columns: tuple[str, ...] | None = None,
        suppress_tab_hint: bool | None = None,
    ) -> None:
        """Initialise shared metadata fields."""
        self.help_text = help_text
        self.metavar = metavar
        self.nargs = nargs
        self.choices = choices
        self.choices_provider = choices_provider
        self.completer = completer
        self.table_columns = table_columns
        self.suppress_tab_hint = suppress_tab_hint

    def to_kwargs(self) -> dict[str, Any]:
        """Return non-None fields as an argparse kwargs dict."""
        return {kwarg: val for attr, kwarg in self._KWARGS_MAP.items() if (val := getattr(self, attr)) is not None}


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

    Example::

        def do_paint(
            self,
            color: Annotated[str, Option("--color", "-c", help_text="Color")] = "blue",
        ):
            ...
    """

    def __init__(
        self,
        *names: str,
        action: str | None = None,
        required: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialise Option metadata."""
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

    def __init__(self, *members: str, title: str | None = None, description: str | None = None) -> None:
        """Initialise an argument group definition.

        :param members: parameter names to place in the group (at least one)
        :param title: optional group title shown as a section header in help
        :param description: optional group description shown under the title
        """
        if not members:
            raise ValueError("Group requires at least one member parameter name")
        self.members = members
        self.title = title
        self.description = description

    def _validate_members(self, *, all_param_names: set[str], group_type: str) -> None:
        """Validate that every referenced member parameter exists."""
        for name in self.members:
            if name not in all_param_names:
                raise ValueError(f"{group_type} references nonexistent parameter {name!r}")


#: Metadata extracted from ``Annotated[T, meta]``, or ``None`` for plain types.
ArgMetadata = Argument | Option | None

_NormalizedAnnotation = tuple[Any, ArgMetadata, bool]
_ResolvedParam = tuple[str, ArgMetadata, bool, list[str], dict[str, Any]]
_ArgumentTarget = argparse.ArgumentParser | argparse._MutuallyExclusiveGroup | argparse._ArgumentGroup


# ---------------------------------------------------------------------------
# Type resolvers
# ---------------------------------------------------------------------------
#
# Each resolver: (tp, args, *, is_positional, has_default, default, metadata) -> dict
# The returned dict is merged into the argparse kwargs.
# Internal keys ('base_type', 'is_collection', 'is_bool_flag') are stripped
# before passing to argparse.
# ---------------------------------------------------------------------------

_BOOL_TRUE_VALUES = ["1", "true", "t", "yes", "y", "on"]
_BOOL_FALSE_VALUES = ["0", "false", "f", "no", "n", "off"]
_ACTIONS_DISALLOW_TYPE = frozenset({"count", "store_true", "store_false", "store_const", "help", "version"})
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


def _make_simple_resolver(converter: Callable[..., Any] | type) -> Callable[..., dict[str, Any]]:
    """Create a resolver for types that just need ``type=converter``."""

    def _resolve(_tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> dict[str, Any]:
        return {"type": converter}

    return _resolve


def _resolve_path(_tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> dict[str, Any]:
    """Resolve Path and add completer."""
    from .cmd2 import Cmd

    return {"type": Path, "completer": Cmd.path_complete}


def _resolve_bool(
    _tp: Any,
    _args: tuple[Any, ...],
    *,
    is_positional: bool,
    metadata: ArgMetadata,
    **_ctx: Any,
) -> dict[str, Any]:
    """Resolve bool -- flag or positional depending on context."""
    if not is_positional:
        action_str = getattr(metadata, "action", None) if metadata else None
        if action_str:
            return {"action": action_str}
        return {"action": argparse.BooleanOptionalAction}
    return {"type": _parse_bool, "choices": list(_BOOL_CHOICES)}


def _resolve_element(tp: Any) -> tuple[Any, dict[str, Any]]:
    """Resolve a collection element type and reject nested collections."""
    element_type, inner = _resolve_type(tp, is_positional=True)
    if inner.get("is_collection"):
        raise TypeError("Nested collections are not supported")
    return element_type, inner


def _make_collection_resolver(collection_type: type) -> Callable[..., dict[str, Any]]:
    """Create a resolver for single-arg collections (list[T], set[T])."""

    def _resolve(_tp: Any, args: tuple[Any, ...], *, has_default: bool = False, **_ctx: Any) -> dict[str, Any]:
        nargs = "*" if has_default else "+"
        if len(args) == 0:
            # Bare list/tuple without type args -- treat as list[str]/set[str]
            return {
                "is_collection": True,
                "nargs": nargs,
                "base_type": str,
                "action": _CollectionCastingAction,
                "container_factory": collection_type,
            }
        if len(args) != 1:
            raise TypeError(
                f"{collection_type.__name__}[...] with {len(args)} type arguments is not supported; "
                f"use {collection_type.__name__}[T] with a single element type."
            )
        element_type, inner = _resolve_element(args[0])
        return {
            **inner,
            "is_collection": True,
            "nargs": nargs,
            "base_type": element_type,
            "action": _CollectionCastingAction,
            "container_factory": collection_type,
        }

    return _resolve


def _resolve_tuple(_tp: Any, args: tuple[Any, ...], *, has_default: bool = False, **_ctx: Any) -> dict[str, Any]:
    """Resolve tuple[T, ...] and tuple[T1, T2, ...]."""
    cast_kwargs = {"action": _CollectionCastingAction, "container_factory": tuple}

    nargs = "*" if has_default else "+"
    if not args:
        # Bare tuple without type args -- treat as tuple[str, ...]
        return {"is_collection": True, "nargs": nargs, "base_type": str, **cast_kwargs}

    if len(args) == 2 and args[1] is Ellipsis:
        element_type, inner = _resolve_element(args[0])
        return {**inner, "is_collection": True, "nargs": nargs, "base_type": element_type, **cast_kwargs}

    if Ellipsis not in args:
        first = args[0]
        if not all(a == first for a in args[1:]):
            raise TypeError(
                f"tuple[{', '.join(_type_name(a) for a in args)}] "
                f"has mixed element types which is not currently supported because argparse "
                f"can only apply a single type= converter per argument. "
                f"Use tuple[T, T] (same type) or tuple[T, ...] instead."
            )
        _, inner = _resolve_element(first)
        return {**inner, "is_collection": True, "nargs": len(args), "base_type": first, **cast_kwargs}

    raise TypeError(
        "tuple with Ellipsis in an unexpected position is not supported; "
        "use tuple[T, ...] for variable-length or tuple[T, T] for fixed-arity."
    )


def _resolve_literal(_tp: Any, args: tuple[Any, ...], **_ctx: Any) -> dict[str, Any]:
    """Resolve Literal["a", "b", ...] into converter + choices."""
    literal_values = list(args)
    return {"type": _make_literal_type(literal_values), "choices": literal_values}


def _resolve_enum(tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> dict[str, Any]:
    """Resolve Enum subclasses into converter + choices."""
    return {
        "type": _make_enum_type(tp),
        "choices": [CompletionItem(m, text=str(m.value), display_meta=m.name) for m in tp],
    }


# -- Registry -----------------------------------------------------------------

_TYPE_RESOLVERS: dict[Any, Callable[..., dict[str, Any]]] = {
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


def _is_passthrough_type(tp: Any) -> bool:
    """Return ``True`` for types stored as a raw string without a dedicated converter.

    Covers ``str`` / ``Any`` / ``object`` / unannotated parameters, and any parametrized
    generic we do not specialize (e.g. ``frozenset[T]``, ``dict[K, V]``, ``Sequence[T]``),
    which keep their existing scalar-passthrough behavior.
    """
    return tp in _PASSTHROUGH_TYPES or get_origin(tp) is not None


def _nargs_yields_list(nargs: Any) -> bool:
    """Return ``True`` when an argparse ``nargs`` value produces a list at parse time.

    ``nargs=1`` is included: argparse returns ``[value]``, not the bare value.
    """
    return nargs in ("*", "+", argparse.REMAINDER) or (isinstance(nargs, int) and nargs >= 1)


def _resolve_type(
    tp: type,
    *,
    is_positional: bool = False,
    is_optional: bool = False,
    has_default: bool = False,
    default: Any = None,
    metadata: ArgMetadata = None,
    is_kw_only: bool = False,
) -> tuple[type, dict[str, Any]]:
    """Resolve a type into argparse kwargs via the registry.

    Lookup order: ``get_origin(tp)`` → ``tp`` → ``issubclass`` fallback.

    Returns ``(base_type, kwargs_dict)``.
    """
    args = get_args(tp)
    # ``has_default``, ``is_kw_only``, and ``is_optional`` all mean "this argument may be absent",
    # so collection resolvers should pick ``nargs='*'`` instead of ``'+'``.
    resolver_has_default = has_default or is_kw_only or is_optional
    ctx: dict[str, Any] = {
        "is_positional": is_positional,
        "has_default": resolver_has_default,
        "default": default,
        "metadata": metadata,
    }

    resolver = _TYPE_RESOLVERS.get(get_origin(tp)) or _TYPE_RESOLVERS.get(tp)

    # Subclass fallback (e.g. MyEnum → enum.Enum, MyPath → pathlib.Path)
    if resolver is None and isinstance(tp, type):
        for parent, candidate in _TYPE_RESOLVERS.items():
            if isinstance(parent, type) and issubclass(tp, parent):
                resolver = candidate
                break

    if resolver is not None:
        kwargs = resolver(tp, args, **ctx)
        base_type = kwargs.pop("base_type", tp)
    elif _is_passthrough_type(tp):
        base_type = tp
        kwargs = {}
    else:
        raise TypeError(
            f"Unsupported parameter type {_type_name(tp)!r} for @with_annotated: there is no converter "
            f"for it, so command-line values would silently arrive as plain strings. Supported scalar types "
            f"are str, int, float, bool, decimal.Decimal, pathlib.Path, enum.Enum subclasses, and Literal[...]; "
            f"use one of these (optionally in list/set/tuple) or a subclass of one."
        )

    resolver_nargs = kwargs.get("nargs")

    if metadata:
        kwargs.update(metadata.to_kwargs())

    nargs_val = kwargs.get("nargs")

    # A fixed-arity type (e.g. ``tuple[T, T]``) declares its own nargs;
    # user metadata cannot override it to a different value.
    if isinstance(resolver_nargs, int) and nargs_val != resolver_nargs:
        raise TypeError(
            f"nargs={nargs_val!r} conflicts with the fixed arity of '{_type_name(tp)}' (expected nargs={resolver_nargs})."
        )

    # nargs that produces a list of values requires a collection annotation.
    if not kwargs.get("is_collection") and _nargs_yields_list(nargs_val):
        raise TypeError(
            f"nargs={nargs_val!r} produces a list of values, but the annotation '{_type_name(tp)}' is not a collection type. "
            f"Use list[T], tuple[T, ...], or set[T] (optionally with | None) to match."
        )

    # Some argparse actions (e.g. count/store_true) do not accept a type converter.
    action_name = kwargs.get("action")
    if isinstance(action_name, str) and action_name in _ACTIONS_DISALLOW_TYPE:
        kwargs.pop("type", None)

    if has_default:
        kwargs["default"] = default

    if is_kw_only and not has_default:
        kwargs["required"] = True

    # An optional positional scalar takes 0-or-1 tokens. This covers both ``T | None``
    # (no default) and a positional given an explicit default; without ``nargs='?'``
    # argparse would still require the latter, contradicting its default value.
    if (is_optional or has_default) and is_positional and "nargs" not in kwargs and not kwargs.get("is_collection"):
        kwargs["nargs"] = "?"

    if is_positional and (is_optional or has_default) and isinstance(kwargs.get("nargs"), int):
        raise TypeError(
            f"A fixed-arity positional (nargs={kwargs['nargs']}) cannot be optional; argparse always "
            f"requires it. Drop the default or '| None', make it an option (give it a default without "
            f"Argument()), or use a variable-arity type such as tuple[T, ...]."
        )

    # A user-supplied completer/choices_provider drives completion, so drop the inferred
    # static ``choices`` list.
    if kwargs.get("choices_provider") or kwargs.get("completer"):
        kwargs.pop("choices", None)

    return base_type, kwargs


def _unwrap_optional(tp: type) -> tuple[type, bool]:
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


def _normalize_annotation(annotation: type) -> _NormalizedAnnotation:
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
# Annotation resolution
# ---------------------------------------------------------------------------


def _resolve_annotation(
    annotation: Any,
    *,
    has_default: bool = False,
    default: Any = None,
    is_kw_only: bool = False,
    is_variadic: bool = False,
) -> tuple[dict[str, Any], ArgMetadata, bool]:
    """Decompose a type annotation into ``(type_kwargs, metadata, is_positional)``.

    Peels ``Annotated`` then ``Optional``.  The only supported way to combine
    ``Annotated`` with ``Optional`` is ``Annotated[T | None, meta]``.
    Writing ``Annotated[T, meta] | None`` is ambiguous and raises ``TypeError``.

    ``is_variadic`` marks a ``*args`` parameter: it is always positional and
    accepts zero or more values (``nargs='*'``).
    """
    tp, metadata, is_optional = _normalize_annotation(annotation)

    # ``*args`` is always a positional that accepts zero or more values.
    is_positional = is_variadic or isinstance(metadata, Argument) or (metadata is None and not has_default and not is_kw_only)

    tp, type_kwargs = _resolve_type(
        tp,
        is_positional=is_positional,
        is_optional=is_optional or is_variadic,
        has_default=has_default,
        default=default,
        metadata=metadata,
        is_kw_only=is_kw_only,
    )

    type_kwargs.pop("is_collection", None)
    type_kwargs.pop("base_type", None)

    return type_kwargs, metadata, is_positional


# Parameter names that conflict with argparse internals and cannot be used
# as annotated parameter names.
_RESERVED_PARAM_NAMES = frozenset({"dest", "subcommand"})


# ---------------------------------------------------------------------------
# Signature → Parser conversion
# ---------------------------------------------------------------------------


def _validate_base_command_params(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str] | None = None,
) -> None:
    """Validate a ``base_command=True`` function has ``cmd2_handler`` and no positional args."""
    if "cmd2_handler" not in inspect.signature(func).parameters:
        raise TypeError(f"with_annotated(base_command=True) requires a 'cmd2_handler' parameter in {func.__qualname__}")

    if skip_params is None:
        skip_params = _SKIP_PARAMS

    for name, metadata, positional, _flags, _kwargs in _resolve_parameters(func, skip_params=skip_params):
        if positional and not isinstance(metadata, Argument):
            raise TypeError(
                f"Parameter '{name}' in {func.__qualname__} is positional, "
                f"which conflicts with subcommand parsing. "
                f"Use a keyword-only parameter (after *) or give it a default value."
            )
        if isinstance(metadata, Argument):
            raise TypeError(
                f"Parameter '{name}' in {func.__qualname__} uses Argument() metadata, "
                f"which creates a positional argument that conflicts with subcommand parsing."
            )


# Parameters that are handled specially by the decorator and should not
# be added to the argparse parser.  The first positional parameter (self/cls)
# is always skipped by position; these cover additional decorator-managed names.
_SKIP_PARAMS = frozenset({"cmd2_handler", "cmd2_statement"})


def _resolve_parameters(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str] = _SKIP_PARAMS,
) -> list[_ResolvedParam]:
    """Resolve a function signature into parser-ready parameter records."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func, include_extras=True)
    except (NameError, AttributeError, TypeError) as exc:
        raise TypeError(
            f"Failed to resolve type hints for {func.__qualname__}. Ensure all annotations use valid, importable types."
        ) from exc

    resolved: list[_ResolvedParam] = []

    # Skip the first parameter by position (self/cls for methods)
    params = list(sig.parameters.items())
    if params:
        params = params[1:]

    for name, param in params:
        if name in skip_params:
            continue

        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            raise TypeError(
                f"Parameter {name!r} in {func.__qualname__} is positional-only, "
                "which is not supported by @with_annotated because parameters are passed as keyword arguments."
            )

        if param.kind == inspect.Parameter.VAR_KEYWORD:
            raise TypeError(
                f"Parameter '**{name}' in {func.__qualname__} is variadic keyword (**kwargs), "
                "which is not supported by @with_annotated because there is no native way to map "
                "command-line arguments onto arbitrary keyword names."
            )

        if name in _RESERVED_PARAM_NAMES:
            raise ValueError(
                f"Parameter name {name!r} in {func.__qualname__} is reserved by argparse "
                f"and cannot be used as an annotated parameter name."
            )

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            # ``*args: T`` is a variadic positional: zero or more values (nargs='*')
            # collected into a tuple. The hint gives the element type T (the type of
            # each value), so annotating *args with a collection -- e.g.
            # ``*args: tuple[str, ...]`` -- would mean each value is itself a tuple
            # (a tuple-of-tuples), which cannot be mapped onto a flat command line.
            element = hints.get(name, str)
            _, element_kwargs = _resolve_type(element, is_positional=True)
            if element_kwargs.get("is_collection"):
                # Show the parametrized form (e.g. ``tuple[str, ...]``), not the bare origin.
                element_display = str(element) if get_origin(element) is not None else _type_name(element)
                raise TypeError(
                    f"Parameter '*{name}' in {func.__qualname__} is annotated with the collection type "
                    f"'{element_display}'. For *args the annotation is the type of each value, not the "
                    f"collected tuple, so '*{name}: {element_display}' would mean a tuple of "
                    f"'{element_display}'. Annotate the element type instead "
                    f"(e.g. '*{name}: str'); values are always collected into a tuple."
                )
            variadic_annotation = types.GenericAlias(tuple, (element, ...))
            kwargs, metadata, positional = _resolve_annotation(variadic_annotation, is_variadic=True)
        else:
            annotation = hints.get(name, param.annotation)
            has_default = param.default is not inspect.Parameter.empty
            default = param.default if has_default else None
            is_kw_only = param.kind == inspect.Parameter.KEYWORD_ONLY

            kwargs, metadata, positional = _resolve_annotation(
                annotation,
                has_default=has_default,
                default=default,
                is_kw_only=is_kw_only,
            )

        if positional:
            flags: list[str] = []
        else:
            flags = (
                list(metadata.names) if isinstance(metadata, Option) and metadata.names else [f"--{name.replace('_', '-')}"]
            )
            kwargs["dest"] = name

        resolved.append((name, metadata, positional, flags, kwargs))

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
    positional = [func_kwargs.pop(name) for name in leading_names if name in func_kwargs]
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
    all_param_names: set[str],
) -> tuple[dict[str, _ArgumentTarget], dict[str, argparse._ArgumentGroup]]:
    """Build argument groups and return add_argument targets for their members."""
    target_for: dict[str, _ArgumentTarget] = {}
    argument_group_for: dict[str, argparse._ArgumentGroup] = {}
    argument_group_index_for: dict[str, int] = {}

    if not groups:
        return target_for, argument_group_for

    for index, spec in enumerate(groups, start=1):
        spec._validate_members(all_param_names=all_param_names, group_type="groups")
        member_names = spec.members
        for name in member_names:
            if name in argument_group_for:
                raise ValueError(
                    f"parameter {name!r} cannot be assigned to both argument "
                    f"group {argument_group_index_for[name]} and argument group {index}"
                )

        group = parser.add_argument_group(title=spec.title, description=spec.description)
        for name in member_names:
            argument_group_for[name] = group
            argument_group_index_for[name] = index
            target_for[name] = group

    return target_for, argument_group_for


def _apply_mutex_group_targets(
    parser: argparse.ArgumentParser,
    *,
    target_for: dict[str, _ArgumentTarget],
    argument_group_for: dict[str, argparse._ArgumentGroup],
    mutually_exclusive_groups: tuple[Group, ...] | None,
    all_param_names: set[str],
) -> None:
    """Build mutually exclusive groups and update add_argument targets for their members."""
    mutex_target_for: dict[str, argparse._MutuallyExclusiveGroup] = {}

    if not mutually_exclusive_groups:
        return

    for index, spec in enumerate(mutually_exclusive_groups, start=1):
        spec._validate_members(all_param_names=all_param_names, group_type="mutually_exclusive_groups")
        member_names = spec.members
        for name in member_names:
            if name in mutex_target_for:
                raise ValueError(f"parameter {name!r} cannot be assigned to multiple mutually exclusive groups")

        parent_groups = {argument_group_for[name] for name in member_names if name in argument_group_for}
        if len(parent_groups) > 1:
            raise ValueError(
                f"mutually exclusive group {index} spans parameters in different argument groups, "
                "which argparse cannot represent cleanly"
            )

        mutex_parent: _ArgumentTarget = next(iter(parent_groups)) if parent_groups else parser
        mutex_group = mutex_parent.add_mutually_exclusive_group()
        for name in member_names:
            mutex_target_for[name] = mutex_group
            target_for[name] = mutex_group


def build_parser_from_function(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str] = _SKIP_PARAMS,
    groups: tuple[Group, ...] | None = None,
    mutually_exclusive_groups: tuple[Group, ...] | None = None,
    description: str | None = None,
    epilog: str | None = None,
    formatter_class: type[Cmd2HelpFormatter] | None = None,
    parser_class: type[Cmd2ArgumentParser] | None = None,
) -> Cmd2ArgumentParser:
    """Inspect a function's signature and build a ``Cmd2ArgumentParser``.

    Parameters without defaults become positional arguments.
    Parameters with defaults become ``--option`` flags.
    ``Annotated[T, Argument(...)]`` or ``Annotated[T, Option(...)]``
    overrides the default behavior.

    :param func: the command function to inspect
    :param skip_params: parameter names to exclude from the parser
    :param groups: :class:`Group` instances assigning parameter names to argument
                   groups (for help display)
    :param mutually_exclusive_groups: :class:`Group` instances of mutually exclusive parameters
    :param description: parser description (shown in ``--help``)
    :param epilog: parser epilog text (shown at the end of ``--help``)
    :param formatter_class: custom help formatter class for the parser
    :param parser_class: custom parser class (defaults to the configured default)
    :return: a fully configured ``Cmd2ArgumentParser``
    """
    from .argparse_utils import DEFAULT_ARGUMENT_PARSER

    parser_cls = parser_class or DEFAULT_ARGUMENT_PARSER
    parser_kwargs: dict[str, Any] = {}
    if description is not None:
        parser_kwargs["description"] = description
    if epilog is not None:
        parser_kwargs["epilog"] = epilog
    if formatter_class is not None:
        parser_kwargs["formatter_class"] = formatter_class
    parser = parser_cls(**parser_kwargs)

    resolved = _resolve_parameters(func, skip_params=skip_params)

    # Phase 2: build group lookup
    all_param_names = {name for name, *_rest in resolved}
    target_for, argument_group_for = _build_argument_group_targets(
        parser,
        groups=groups,
        all_param_names=all_param_names,
    )
    _apply_mutex_group_targets(
        parser,
        target_for=target_for,
        argument_group_for=argument_group_for,
        mutually_exclusive_groups=mutually_exclusive_groups,
        all_param_names=all_param_names,
    )

    # Phase 3: add arguments to appropriate targets
    for name, _metadata, positional, flags, kwargs in resolved:
        target = target_for.get(name, parser)
        if positional:
            target.add_argument(name, **kwargs)
        else:
            target.add_argument(*flags, **kwargs)

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


def build_subcommand_handler(
    func: Callable[..., Any],
    subcommand_to: str,
    *,
    base_command: bool = False,
    groups: tuple[Group, ...] | None = None,
    mutually_exclusive_groups: tuple[Group, ...] | None = None,
    description: str | None = None,
    epilog: str | None = None,
    formatter_class: type[Cmd2HelpFormatter] | None = None,
    parser_class: type[Cmd2ArgumentParser] | None = None,
) -> tuple[Callable[..., Any], str, Callable[[], Cmd2ArgumentParser]]:
    """Build a subcommand handler wrapper and its parser from type annotations.

    Validates the naming convention, builds a parser from annotations, and
    returns a wrapper that unpacks ``argparse.Namespace`` into typed kwargs
    before calling the original function.

    :param func: the subcommand handler function
    :param subcommand_to: parent command name (space-delimited for nesting)
    :param base_command: if True, the parser also gets ``add_subparsers()``
    :param groups: :class:`Group` instances assigning parameter names to argument groups
    :param mutually_exclusive_groups: :class:`Group` instances of mutually exclusive parameters
    :param description: parser description (shown in ``--help``)
    :param epilog: parser epilog text (shown at the end of ``--help``)
    :param formatter_class: custom help formatter class for the parser
    :param parser_class: custom parser class (defaults to the configured default)
    :return: ``(handler, subcommand_name, parser_builder)``
    """
    subcmd_name = _derive_subcommand_name(func, subcommand_to)

    if base_command:
        _validate_base_command_params(func)

    _accepted = set(list(inspect.signature(func).parameters.keys())[1:])
    _leading_names, _var_positional_name = _var_positional_call_plan(func)

    @functools.wraps(func)
    def handler(self_arg: Any, ns: Any) -> Any:
        """Unpack Namespace into typed kwargs for the subcommand handler."""
        filtered = _filtered_namespace_kwargs(ns, accepted=_accepted)
        return _invoke_command_func(
            func, self_arg, filtered, leading_names=_leading_names, var_positional_name=_var_positional_name
        )

    def parser_builder() -> Cmd2ArgumentParser:
        parser = build_parser_from_function(
            func,
            groups=groups,
            mutually_exclusive_groups=mutually_exclusive_groups,
            description=description,
            epilog=epilog,
            formatter_class=formatter_class,
            parser_class=parser_class,
        )
        if base_command:
            parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND", required=True)
        return parser

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
    groups: tuple[Group, ...] | None = ...,
    mutually_exclusive_groups: tuple[Group, ...] | None = ...,
    description: str | None = ...,
    epilog: str | None = ...,
    formatter_class: type[Cmd2HelpFormatter] | None = ...,
    parser_class: type[Cmd2ArgumentParser] | None = ...,
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
    groups: tuple[Group, ...] | None = None,
    mutually_exclusive_groups: tuple[Group, ...] | None = None,
    description: str | None = None,
    epilog: str | None = None,
    formatter_class: type[Cmd2HelpFormatter] | None = None,
    parser_class: type[Cmd2ArgumentParser] | None = None,
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
    :param groups: :class:`Group` instances assigning parameter names to argument
                   groups (pass ``title``/``description`` for a titled section)
    :param mutually_exclusive_groups: :class:`Group` instances of mutually exclusive parameters
    :param description: parser description (shown in ``--help``)
    :param epilog: parser epilog text (shown at the end of ``--help``)
    :param formatter_class: custom help formatter class for the parser
    :param parser_class: custom parser class (defaults to the configured default)

    Example::

        class MyApp(cmd2.Cmd):
            @with_annotated
            def do_greet(self, name: str, count: int = 1): ...

            @with_annotated(base_command=True)
            def do_team(self, *, cmd2_handler): ...

            @with_annotated(subcommand_to='team', help='create a team')
            def team_create(self, name: str): ...

    """
    if (help is not None or aliases) and subcommand_to is None:
        raise TypeError("'help' and 'aliases' are only valid with subcommand_to")
    if subcommand_to is not None:
        unsupported: list[str] = []
        if ns_provider is not None:
            unsupported.append("ns_provider")
        if preserve_quotes:
            unsupported.append("preserve_quotes")
        if with_unknown_args:
            unsupported.append("with_unknown_args")
        if unsupported:
            names = ", ".join(unsupported)
            raise TypeError(
                f"{names} {'is' if len(unsupported) == 1 else 'are'} not supported with subcommand_to. "
                "Configure these behaviors on the base command instead."
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
            handler, subcmd_name, subcmd_parser_builder = build_subcommand_handler(
                fn,
                subcommand_to,
                base_command=base_command,
                groups=groups,
                mutually_exclusive_groups=mutually_exclusive_groups,
                description=description,
                epilog=epilog,
                formatter_class=formatter_class,
                parser_class=parser_class,
            )
            spec = SubcommandSpec(
                name=subcmd_name,
                command=subcommand_to,
                help=help,
                aliases=tuple(aliases),
                parser_source=subcmd_parser_builder,
            )
            setattr(handler, constants.SUBCMD_ATTR_SPEC, spec)
            return handler

        command_name = fn.__name__[len(constants.COMMAND_FUNC_PREFIX) :]

        skip_params = _SKIP_PARAMS | ({"_unknown"} if with_unknown_args else frozenset())
        if base_command:
            _validate_base_command_params(fn, skip_params=skip_params)

        # Cache signature introspection at decoration time, not per-invocation
        accepted = set(list(inspect.signature(fn).parameters.keys())[1:])
        leading_names, var_positional_name = _var_positional_call_plan(fn)

        def parser_builder() -> Cmd2ArgumentParser:
            parser = build_parser_from_function(
                fn,
                skip_params=skip_params,
                groups=groups,
                mutually_exclusive_groups=mutually_exclusive_groups,
                description=description,
                epilog=epilog,
                formatter_class=formatter_class,
                parser_class=parser_class,
            )
            if base_command:
                parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND", required=True)
            return parser

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
