"""Build argparse parsers from type-annotated function signatures.

This module provides the :func:`with_annotated` decorator that inspects a
command function's type hints and default values to automatically construct
a ``Cmd2ArgumentParser``.  It also provides :class:`Argument` and
:class:`Option` metadata classes for use with ``typing.Annotated`` when
finer control is needed.

Basic usage -- parameters without defaults become positional arguments,
parameters with defaults become ``--option`` flags::

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
- ``bool`` with default ``False`` -- ``--flag`` with ``store_true``
- ``bool`` with default ``True`` -- ``--no-flag`` with ``store_false``
- ``pathlib.Path`` -- sets ``type=Path``
- ``enum.Enum`` subclass -- ``type=converter``, ``choices`` from member values
- ``list[T]`` -- ``nargs='+'`` (or ``'*'`` if has a default)
- ``T | None`` -- unwrapped to ``T``, treated as optional

Note: ``Path`` and ``Enum`` types also get automatic tab completion via
``ArgparseCompleter`` type inference. This works for both ``@with_annotated``
and ``@with_argparser`` -- see the ``argparse_completer`` module.
"""

import argparse
import enum
import inspect
import pathlib
import types
from collections.abc import Callable
from typing import (
    Annotated,
    Any,
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
        suppress_tab_hint: bool = False,
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


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

_NoneType = type(None)


def _make_enum_type(enum_class: type[enum.Enum]) -> Callable[[str], enum.Enum]:
    """Create an argparse *type* converter for an Enum class.

    Accepts both member *values* and member *names*.
    """
    # Pre-build a value→member lookup for O(1) conversion
    _value_map = {str(m.value): m for m in enum_class}

    def _convert(value: str) -> enum.Enum:
        member = _value_map.get(value)
        if member is not None:
            return member
        # Fallback to name lookup
        try:
            return enum_class[value]
        except KeyError as err:
            valid = ', '.join(_value_map)
            raise argparse.ArgumentTypeError(f"invalid choice: {value!r} (choose from {valid})") from err

    _convert.__name__ = enum_class.__name__
    return _convert


def _unwrap_type(annotation: Any) -> tuple[Any, Argument | Option | None]:
    """Unwrap ``Annotated[T, metadata]`` and return ``(base_type, metadata)``.

    Returns ``(annotation, None)`` when there is no ``Annotated`` wrapper or
    no ``Argument``/``Option`` metadata inside it.
    """
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        base_type = args[0]
        for meta in args[1:]:
            if isinstance(meta, (Argument, Option)):
                return base_type, meta
        return base_type, None
    return annotation, None


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """Strip ``Optional[T]`` / ``T | None`` and return ``(inner_type, is_optional)``."""
    origin = get_origin(tp)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(tp) if a is not _NoneType]
        if len(args) == 1:
            return args[0], True
    return tp, False


def _unwrap_list(tp: Any) -> tuple[Any, bool]:
    """Strip ``list[T]`` and return ``(inner_type, is_list)``."""
    if get_origin(tp) is list:
        args = get_args(tp)
        if args:
            return args[0], True
    return tp, False


# ---------------------------------------------------------------------------
# Signature → Parser conversion
# ---------------------------------------------------------------------------


def build_parser_from_function(func: Callable[..., Any]) -> argparse.ArgumentParser:
    """Inspect a function's signature and build a ``Cmd2ArgumentParser``.

    Parameters without defaults become positional arguments.
    Parameters with defaults become ``--option`` flags.
    ``Annotated[T, Argument(...)]`` or ``Annotated[T, Option(...)]``
    overrides the default behaviour.

    :param func: the command function to inspect
    :return: a fully configured ``Cmd2ArgumentParser``
    """
    from .argparse_custom import DEFAULT_ARGUMENT_PARSER

    parser = DEFAULT_ARGUMENT_PARSER()

    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func, include_extras=True)
    except (NameError, AttributeError, TypeError):
        hints = {}

    for name, param in sig.parameters.items():
        if name == 'self':
            continue

        annotation = hints.get(name, param.annotation)
        has_default = param.default is not inspect.Parameter.empty
        default = param.default if has_default else None

        # 1. Unwrap Annotated[T, metadata]
        base_type, metadata = _unwrap_type(annotation)

        # 2. Unwrap Optional[T] / T | None
        base_type, is_optional = _unwrap_optional(base_type)

        # 3. Unwrap list[T]
        inner_type, is_list = _unwrap_list(base_type)
        if is_list:
            base_type = inner_type

        # 4. Determine positional vs option
        if isinstance(metadata, Argument):
            is_positional = True
        elif isinstance(metadata, Option):
            is_positional = False
        elif not has_default and not is_optional:
            is_positional = True
        else:
            is_positional = False

        # 5. Build add_argument kwargs
        kwargs: dict[str, Any] = {}

        # Help text
        help_text = metadata.help_text if metadata else None
        if help_text:
            kwargs['help'] = help_text

        # Metavar
        metavar = metadata.metavar if metadata else None
        if metavar:
            kwargs['metavar'] = metavar

        # Nargs from metadata
        explicit_nargs = metadata.nargs if metadata else None
        if explicit_nargs is not None:
            kwargs['nargs'] = explicit_nargs
        elif is_list:
            kwargs['nargs'] = '*' if has_default else '+'

        # Type-specific handling
        is_bool_flag = False
        if base_type is bool and not is_list and not is_positional:
            is_bool_flag = True
            action_str = getattr(metadata, 'action', None) if metadata else None
            if action_str:
                kwargs['action'] = action_str
            elif has_default and default is True:
                kwargs['action'] = 'store_false'
            else:
                kwargs['action'] = 'store_true'
        elif isinstance(base_type, type) and issubclass(base_type, enum.Enum):
            kwargs['type'] = _make_enum_type(base_type)
            kwargs['choices'] = [m.value for m in base_type]
        elif base_type is pathlib.Path or (isinstance(base_type, type) and issubclass(base_type, pathlib.Path)):
            kwargs['type'] = pathlib.Path
        elif base_type in (int, float, str):
            if base_type is not str:
                kwargs['type'] = base_type

        if has_default:
            kwargs['default'] = default

        # Static choices from metadata (unless already set by enum inference)
        explicit_choices = getattr(metadata, 'choices', None)
        if explicit_choices is not None and 'choices' not in kwargs:
            kwargs['choices'] = explicit_choices

        # cmd2-specific fields from metadata
        choices_provider = getattr(metadata, 'choices_provider', None)
        completer_func = getattr(metadata, 'completer', None)
        table_columns = getattr(metadata, 'table_columns', None)
        suppress_tab_hint = getattr(metadata, 'suppress_tab_hint', False)

        if choices_provider:
            kwargs['choices_provider'] = choices_provider
        if completer_func:
            kwargs['completer'] = completer_func
        if table_columns:
            kwargs['table_columns'] = table_columns
        if suppress_tab_hint:
            kwargs['suppress_tab_hint'] = suppress_tab_hint

        # 6. Call add_argument
        if is_positional:
            parser.add_argument(name, **kwargs)
        else:
            # Option
            option_metadata = metadata if isinstance(metadata, Option) else None
            if option_metadata and option_metadata.names:
                flag_names = list(option_metadata.names)
            else:
                flag_names = [f'--{name}']
                if is_bool_flag and has_default and default is True:
                    flag_names = [f'--no-{name}']

            if option_metadata and option_metadata.required:
                kwargs['required'] = True

            # Set dest explicitly so it matches the parameter name
            kwargs['dest'] = name

            parser.add_argument(*flag_names, **kwargs)

    return parser
