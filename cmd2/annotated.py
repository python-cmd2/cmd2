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
are required.  The parameter name ``dest`` is reserved and cannot be
used::

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
- ``list[T]`` / ``set[T]`` / ``tuple[T, ...]`` -- ``nargs='+'`` (or ``'*'`` if has a default)
- ``tuple[T, T]`` (fixed arity, same type) -- ``nargs=N`` with ``type=T``
- ``T | None`` -- unwrapped to ``T``, treated as optional

Unsupported patterns (raise ``TypeError``):

- ``str | int`` -- union of multiple non-None types is ambiguous
- ``tuple[int, str, float]`` -- mixed element types are not currently supported
  because argparse can only apply a single ``type=`` converter per argument

When combining ``Annotated`` with ``Optional``, the union must go
*inside*: ``Annotated[T | None, meta]``.  Writing
``Annotated[T, meta] | None`` is ambiguous and raises ``TypeError``.

Note: ``Path`` and ``Enum`` types also get automatic tab completion via
``ArgparseCompleter`` type inference. This works for both ``@with_annotated``
and ``@with_argparser`` -- see the ``argparse_completer`` module.
If a user-supplied ``choices_provider`` or ``completer`` is set on an argument,
it always takes priority over the type-inferred completion.
"""

import argparse
import decimal
import enum
import functools
import inspect
import pathlib
import types
from collections.abc import Callable, Container
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .types import ChoicesProviderUnbound, CmdOrSet, CompleterUnbound

# ---------------------------------------------------------------------------
# Metadata classes
# ---------------------------------------------------------------------------


class _BaseArgMetadata:
    """Shared fields for ``Argument`` and ``Option`` metadata."""

    _KWARGS_MAP: ClassVar[dict[str, str]] = {
        'help_text': 'help',
        'metavar': 'metavar',
        'choices': 'choices',
        'choices_provider': 'choices_provider',
        'completer': 'completer',
        'table_columns': 'table_columns',
        'suppress_tab_hint': 'suppress_tab_hint',
    }

    def __init__(
        self,
        *,
        help_text: str | None = None,
        metavar: str | None = None,
        nargs: int | str | tuple[int, ...] | None = None,
        choices: list[Any] | None = None,
        choices_provider: ChoicesProviderUnbound[CmdOrSet] | None = None,
        completer: CompleterUnbound[CmdOrSet] | None = None,
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
    When omitted, the decorator auto-generates ``--param_name``.

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

_BOOL_TRUE_VALUES = {'1', 'true', 't', 'yes', 'y', 'on'}
_BOOL_FALSE_VALUES = {'0', 'false', 'f', 'no', 'n', 'off'}


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

        if bool_value is not None and bool_value in literal_values:
            return bool_value

        valid = ', '.join(str(v) for v in literal_values)
        raise argparse.ArgumentTypeError(f"invalid choice: {value!r} (choose from {valid})")

    _convert.__name__ = 'literal'
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
            valid = ', '.join(_value_map)
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
        return {'type': converter}

    return _resolve


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
        action_str = getattr(metadata, 'action', None) if metadata else None
        if action_str:
            return {'action': action_str, 'is_bool_flag': True}
        return {'action': argparse.BooleanOptionalAction, 'is_bool_flag': True}
    return {'type': _parse_bool}


def _resolve_element(tp: Any) -> tuple[Any, dict[str, Any]]:
    """Resolve a collection element type and reject nested collections."""
    element_type, inner = _resolve_type(tp, is_positional=True)
    if inner.get('is_collection'):
        raise TypeError("Nested collections are not supported")
    return element_type, inner


def _make_collection_resolver(collection_type: type) -> Callable[..., dict[str, Any]]:
    """Create a resolver for single-arg collections (list[T], set[T])."""

    def _resolve(_tp: Any, args: tuple[Any, ...], *, has_default: bool = False, **_ctx: Any) -> dict[str, Any]:
        nargs = '*' if has_default else '+'
        if len(args) == 0:
            # Bare list/tuple without type args -- treat as list[str]/set[str]
            return {
                'is_collection': True,
                'nargs': nargs,
                'base_type': str,
                'action': _CollectionCastingAction,
                'container_factory': collection_type,
            }
        if len(args) != 1:
            return {}  # pragma: no cover
        element_type, inner = _resolve_element(args[0])
        return {
            **inner,
            'is_collection': True,
            'nargs': nargs,
            'base_type': element_type,
            'action': _CollectionCastingAction,
            'container_factory': collection_type,
        }

    return _resolve


def _resolve_tuple(_tp: Any, args: tuple[Any, ...], *, has_default: bool = False, **_ctx: Any) -> dict[str, Any]:
    """Resolve tuple[T, ...] and tuple[T1, T2, ...]."""
    cast_kwargs = {'action': _CollectionCastingAction, 'container_factory': tuple}

    nargs = '*' if has_default else '+'
    if not args:
        # Bare tuple without type args -- treat as tuple[str, ...]
        return {'is_collection': True, 'nargs': nargs, 'base_type': str, **cast_kwargs}

    if len(args) == 2 and args[1] is Ellipsis:
        element_type, inner = _resolve_element(args[0])
        return {**inner, 'is_collection': True, 'nargs': nargs, 'base_type': element_type, **cast_kwargs}

    if Ellipsis not in args:
        first = args[0]
        if not all(a == first for a in args[1:]):
            raise TypeError(
                f"tuple[{', '.join(a.__name__ if hasattr(a, '__name__') else str(a) for a in args)}] "
                f"has mixed element types which is not currently supported because argparse "
                f"can only apply a single type= converter per argument. "
                f"Use tuple[T, T] (same type) or tuple[T, ...] instead."
            )
        _, inner = _resolve_element(first)
        return {**inner, 'is_collection': True, 'nargs': len(args), 'base_type': first, **cast_kwargs}

    return {}  # pragma: no cover


def _resolve_literal(_tp: Any, args: tuple[Any, ...], **_ctx: Any) -> dict[str, Any]:
    """Resolve Literal["a", "b", ...] into converter + choices."""
    literal_values = list(args)
    return {'type': _make_literal_type(literal_values), 'choices': literal_values}


def _resolve_enum(tp: Any, _args: tuple[Any, ...], **_ctx: Any) -> dict[str, Any]:
    """Resolve Enum subclasses into converter + choices."""
    return {'type': _make_enum_type(tp), 'choices': [m.value for m in tp]}


# -- Registry -----------------------------------------------------------------

_TYPE_RESOLVERS: dict[Any, Callable[..., dict[str, Any]]] = {
    # Subclass-matchable entries first -- iteration order matters for the
    # issubclass fallback. enum.Enum must precede int (IntEnum <: int).
    enum.Enum: _resolve_enum,
    pathlib.Path: _make_simple_resolver(pathlib.Path),
    # Exact-match entries (order among these doesn't affect subclass lookup).
    bool: _resolve_bool,
    int: _make_simple_resolver(int),
    float: _make_simple_resolver(float),
    decimal.Decimal: _make_simple_resolver(decimal.Decimal),
    list: _make_collection_resolver(list),
    set: _make_collection_resolver(set),
    tuple: _resolve_tuple,
    Literal: _resolve_literal,
}


def _resolve_type(
    tp: type,
    *,
    is_positional: bool = False,
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
    resolver_has_default = has_default or is_kw_only
    ctx: dict[str, Any] = {
        'is_positional': is_positional,
        'has_default': resolver_has_default,
        'default': default,
        'metadata': metadata,
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
        base_type = kwargs.pop('base_type', tp)
    else:
        base_type = tp
        kwargs = {}

    if metadata:
        kwargs.update(metadata.to_kwargs())
        if metadata.nargs is not None:
            kwargs['nargs'] = metadata.nargs

    if (has_default and default is not None) or has_default:
        kwargs['default'] = default

    if (is_kw_only and not has_default) or (isinstance(metadata, Option) and metadata.required):
        kwargs['required'] = True

    if kwargs.get('choices_provider') or kwargs.get('completer'):
        kwargs.pop('choices', None)

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
            # Single-element union without None shouldn't happen, pass through
            return non_none[0], False  # pragma: no cover
        type_names = ' | '.join(a.__name__ if hasattr(a, '__name__') else str(a) for a in non_none)
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
    annotation: type,
    *,
    has_default: bool = False,
    default: Any = None,
    is_kw_only: bool = False,
) -> tuple[dict[str, Any], ArgMetadata, bool, bool]:
    """Decompose a type annotation into ``(type_kwargs, metadata, is_positional, is_bool_flag)``.

    Peels ``Annotated`` then ``Optional``.  The only supported way to combine
    ``Annotated`` with ``Optional`` is ``Annotated[T | None, meta]``.
    Writing ``Annotated[T, meta] | None`` is ambiguous and raises ``TypeError``.
    """
    tp, metadata, is_optional = _normalize_annotation(annotation)

    is_positional = isinstance(metadata, Argument) or (
        not isinstance(metadata, Option) and not has_default and not is_optional and not is_kw_only
    )

    # 4. Resolve type and finalize argparse kwargs
    tp, type_kwargs = _resolve_type(
        tp,
        is_positional=is_positional,
        has_default=has_default,
        default=default,
        metadata=metadata,
        is_kw_only=is_kw_only,
    )

    # Strip internal keys not meant for argparse
    is_bool_flag = type_kwargs.pop('is_bool_flag', False)
    type_kwargs.pop('is_collection', None)
    type_kwargs.pop('base_type', None)

    return type_kwargs, metadata, is_positional, is_bool_flag


# Parameter names that conflict with argparse internals and cannot be used
# as annotated parameter names.
_RESERVED_PARAM_NAMES = frozenset({'dest', 'subcommand'})


# ---------------------------------------------------------------------------
# Signature → Parser conversion
# ---------------------------------------------------------------------------


def _validate_base_command_params(
    func: Callable[..., Any],
    *,
    skip_params: frozenset[str] | None = None,
) -> None:
    """Validate a ``base_command=True`` function has ``cmd2_handler`` and no positional args."""
    sig = inspect.signature(func)

    if 'cmd2_handler' not in sig.parameters:
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
# be added to the argparse parser.
_SKIP_PARAMS = frozenset({'self', 'cmd2_handler', 'cmd2_statement'})


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

    for name, param in sig.parameters.items():
        if name in skip_params:
            continue

        if name in _RESERVED_PARAM_NAMES:
            raise ValueError(
                f"Parameter name {name!r} in {func.__qualname__} is reserved by argparse "
                f"and cannot be used as an annotated parameter name."
            )

        annotation = hints.get(name, param.annotation)
        has_default = param.default is not inspect.Parameter.empty
        default = param.default if has_default else None
        is_kw_only = param.kind == inspect.Parameter.KEYWORD_ONLY

        kwargs, metadata, positional, _is_bool_flag = _resolve_annotation(
            annotation,
            has_default=has_default,
            default=default,
            is_kw_only=is_kw_only,
        )

        if positional:
            flags: list[str] = []
        else:
            flags = list(metadata.names) if isinstance(metadata, Option) and metadata.names else [f'--{name}']
            kwargs['dest'] = name

        resolved.append((name, metadata, positional, flags, kwargs))

    return resolved


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
        if exclude_subcommand and key == 'subcommand':
            continue
        filtered[key] = value

    return filtered


def _validate_group_members(
    member_names: tuple[str, ...],
    *,
    all_param_names: set[str],
    group_type: str,
) -> None:
    """Validate that all referenced group members exist."""
    for name in member_names:
        if name not in all_param_names:
            raise ValueError(f"{group_type} references nonexistent parameter {name!r}")


def _build_argument_group_targets(
    parser: argparse.ArgumentParser,
    *,
    groups: tuple[tuple[str, ...], ...] | None,
    all_param_names: set[str],
) -> tuple[dict[str, _ArgumentTarget], dict[str, argparse._ArgumentGroup]]:
    """Build argument groups and return add_argument targets for their members."""
    target_for: dict[str, _ArgumentTarget] = {}
    argument_group_for: dict[str, argparse._ArgumentGroup] = {}
    argument_group_index_for: dict[str, int] = {}

    if not groups:
        return target_for, argument_group_for

    for index, member_names in enumerate(groups, start=1):
        _validate_group_members(member_names, all_param_names=all_param_names, group_type='groups')
        for name in member_names:
            if name in argument_group_for:
                raise ValueError(
                    f"parameter {name!r} cannot be assigned to both argument "
                    f"group {argument_group_index_for[name]} and argument group {index}"
                )

        group = parser.add_argument_group()
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
    mutually_exclusive_groups: tuple[tuple[str, ...], ...] | None,
    all_param_names: set[str],
) -> None:
    """Build mutually exclusive groups and update add_argument targets for their members."""
    mutex_target_for: dict[str, argparse._MutuallyExclusiveGroup] = {}

    if not mutually_exclusive_groups:
        return

    for index, member_names in enumerate(mutually_exclusive_groups, start=1):
        _validate_group_members(
            member_names,
            all_param_names=all_param_names,
            group_type='mutually_exclusive_groups',
        )
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
    groups: tuple[tuple[str, ...], ...] | None = None,
    mutually_exclusive_groups: tuple[tuple[str, ...], ...] | None = None,
) -> argparse.ArgumentParser:
    """Inspect a function's signature and build a ``Cmd2ArgumentParser``.

    Parameters without defaults become positional arguments.
    Parameters with defaults become ``--option`` flags.
    ``Annotated[T, Argument(...)]`` or ``Annotated[T, Option(...)]``
    overrides the default behaviour.

    :param func: the command function to inspect
    :param skip_params: parameter names to exclude from the parser
    :param groups: tuples of parameter names to place in argument groups (for help display)
    :param mutually_exclusive_groups: tuples of parameter names that are mutually exclusive
    :return: a fully configured ``Cmd2ArgumentParser``
    """
    from .argparse_custom import DEFAULT_ARGUMENT_PARSER

    parser = DEFAULT_ARGUMENT_PARSER()

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

    ``subcommand_to='team member'`` + ``func.__name__='team_member_add'`` → ``'add'``.
    """
    expected_prefix = subcommand_to.replace(' ', '_') + '_'
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
    groups: tuple[tuple[str, ...], ...] | None = None,
    mutually_exclusive_groups: tuple[tuple[str, ...], ...] | None = None,
) -> tuple[Callable[..., Any], str, Callable[[], argparse.ArgumentParser]]:
    """Build a subcommand handler wrapper and its parser from type annotations.

    Validates the naming convention, builds a parser from annotations, and
    returns a wrapper that unpacks ``argparse.Namespace`` into typed kwargs
    before calling the original function.

    :param func: the subcommand handler function
    :param subcommand_to: parent command name (space-delimited for nesting)
    :param base_command: if True, the parser also gets ``add_subparsers()``
    :return: ``(handler, subcommand_name, parser_builder)``
    """
    subcmd_name = _derive_subcommand_name(func, subcommand_to)

    if base_command:
        _validate_base_command_params(func)

    _accepted = set(inspect.signature(func).parameters.keys()) - {'self'}

    @functools.wraps(func)
    def handler(self_arg: Any, ns: Any) -> Any:
        """Unpack Namespace into typed kwargs for the subcommand handler."""
        filtered = _filtered_namespace_kwargs(ns, accepted=_accepted)
        return func(self_arg, **filtered)

    def parser_builder() -> argparse.ArgumentParser:
        parser = build_parser_from_function(func, groups=groups, mutually_exclusive_groups=mutually_exclusive_groups)
        if base_command:
            parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND', required=True)
        return parser

    return handler, subcmd_name, parser_builder
