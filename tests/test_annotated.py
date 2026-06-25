"""Unit tests for cmd2.annotated -- verify build_parser_from_function produces correct actions.

The focus is on testing that type annotations are correctly translated into
argparse action attributes (option_strings, type, nargs, choices, action, default, etc.).
We do NOT re-test argparse parsing logic or cmd2 integration here.
"""

import argparse
import datetime
import decimal
import enum
import functools
import inspect
import types
import uuid
from dataclasses import (
    InitVar,
    dataclass,
    field,
)
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Literal,
    Optional,
)

import pytest

import cmd2
from cmd2 import (
    CompletionItem,
    constants,
)
from cmd2.annotated import (
    Argument,
    ArgumentBlock,
    Group,
    Option,
    _apply_mutex_group_targets,
    _ArgparseArgument,
    _BlockSpec,
    _build_argument_group_targets,
    _CollectionCastingAction,
    _invoke_command_func,
    _make_enum_type,
    _make_literal_type,
    _normalize_annotation,
    _parse_bool,
    _reconstruct_dataclass_blocks,
    _validate_group_specs,
    build_parser_from_function,
    with_annotated,
)
from cmd2.argparse_utils import register_argparse_argument_parameter

from .conftest import run_cmd


def _resolve_annotation(annotation: Any, *, has_default: bool = False, default: Any = None) -> _ArgparseArgument:
    """Build and validate a single argument from a bare annotation (test helper).

    The library builds a whole parameter list in ``_resolve_parameters``; these unit tests exercise one
    annotation in isolation, mirroring that step: peel the annotation, populate the builder, run the
    validity table.  A lone argument has no following positional or group membership, so the
    cross-argument/cross-config rows in ``_CONSTRAINTS`` are naturally inert.
    """
    inner_type, metadata, is_optional = _normalize_annotation(annotation)
    arg = _ArgparseArgument(
        name="arg",
        func_qualname="<function>",
        has_default=has_default,
        param_default=default,
        is_kw_only=False,
        is_variadic=False,
        inner_type=inner_type,
        metadata=metadata,
        is_optional=is_optional,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        is_base_command=False,
    )
    arg._check_constraints()
    return arg


# ---------------------------------------------------------------------------
# Test enums
# ---------------------------------------------------------------------------


class _Color(enum.StrEnum):
    red = "red"
    green = "green"
    blue = "blue"


class _IntColor(enum.IntEnum):
    red = 1
    green = 2
    blue = 3


class _PlainColor(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


_COLOR_CHOICE_ITEMS = [
    CompletionItem(_Color.red, text="red", display_meta="red"),
    CompletionItem(_Color.green, text="green", display_meta="green"),
    CompletionItem(_Color.blue, text="blue", display_meta="blue"),
]

_INT_COLOR_CHOICE_ITEMS = [
    CompletionItem(_IntColor.red, text="1", display_meta="red"),
    CompletionItem(_IntColor.green, text="2", display_meta="green"),
    CompletionItem(_IntColor.blue, text="3", display_meta="blue"),
]

_PLAIN_COLOR_CHOICE_ITEMS = [
    CompletionItem(_PlainColor.RED, text="red", display_meta="RED"),
    CompletionItem(_PlainColor.GREEN, text="green", display_meta="GREEN"),
    CompletionItem(_PlainColor.BLUE, text="blue", display_meta="BLUE"),
]


class _Port(int):
    """Subclass of ``int`` used to verify subclass fallback in type resolution."""


# ---------------------------------------------------------------------------
# Single-parameter test functions for build_parser_from_function.
# Each has exactly one param (besides self) so dest is auto-derived.
# ---------------------------------------------------------------------------


def _func_empty(self) -> None: ...
def _func_var_keyword(self, name: str, **kwargs: str) -> None: ...
def _func_multi(self, a: str, b: int, c: int = 1) -> None: ...
def _func_grouped(
    self,
    *,
    local: str | None = None,
    remote: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> None: ...


def _func_positional_only(self, name: str, /) -> None: ...
def _func_positional_only_xy(self, x: str, /, y: int) -> None: ...
def _func_positional_only_mixed(self, x: str, /, y: int, *, z: int = 0) -> None: ...


# Forward references with no matching name in this module's globals, so they are unresolvable at
# runtime. They exercise type-hint resolution: hints on parameters that never become arguments
# (``self``/``cls`` and the injected, skipped ``cmd2_statement``/``cmd2_subcommand_func``) must be tolerated,
# while hints on real arguments must still raise. ``noqa: F821`` marks the intentionally-undefined names.
def _func_unresolvable_self(self: "UnimportableCmd", name: str, count: int = 1) -> None: ...  # noqa: F821
def _func_unresolvable_cmd2_statement(self, cmd2_statement: "UnimportableStatement", name: str, count: int = 1) -> None: ...  # noqa: F821
def _func_unresolvable_cmd2_subcommand_func(
    self,
    cmd2_subcommand_func: "UnimportableHandler",  # noqa: F821
    verbose: bool = False,
) -> None: ...
def _func_unresolvable_return(self, name: str) -> "UnimportableReturn": ...  # noqa: F821
def _func_unresolvable_argument(self, name: "NonExistentType") -> None: ...  # noqa: F821
def _func_unresolvable_argument_base(self, cmd2_subcommand_func, name: "NonExistentType") -> None: ...  # noqa: F821


def _arg_names_via_parser(func: Any) -> set[str]:
    """Resolve argument names through the public ``build_parser_from_function`` entry point."""
    parser = build_parser_from_function(func)
    return {action.dest for action in parser._actions if action.dest != "help"}


def _arg_names_via_base_command(func: Any) -> set[str]:
    """Resolve a base command's argument names (``base_command`` is not exposed on the public builder)."""
    from cmd2.annotated import _resolve_parameters

    resolved, _base_args_types = _resolve_parameters(func, base_command=True)
    return {arg.name for arg in resolved}


def _wrap_in_foreign_module(func: Any) -> Any:
    """Wrap *func* as a ``functools.wraps`` decorator would, but give the wrapper a ``__globals__``
    that lacks this module's names. This mimics a user decorator defined in *another* module and
    stacked under ``@with_annotated``: ``functools.wraps`` copies ``__annotations__`` but not
    ``__globals__``, so a forward reference can only be resolved via ``__wrapped__`` (the original
    function's module), not the wrapper's. Rebinding the wrapper's globals is the single-module way
    to recreate that cross-module split.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    foreign = types.FunctionType(
        wrapper.__code__, {"__builtins__": __builtins__}, func.__name__, wrapper.__defaults__, wrapper.__closure__
    )
    functools.update_wrapper(foreign, func)  # copies __annotations__ etc. and sets __wrapped__ = func
    return foreign


def _provider(cmd: cmd2.Cmd):
    return []


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_param_action(func: object) -> argparse.Action:
    """Build parser from a single-param function and return its action."""
    sig = inspect.signature(func)  # type: ignore[arg-type]
    param_names = [n for n in sig.parameters if n != "self"]
    assert len(param_names) == 1, f"Expected 1 param besides self, got {param_names}"
    parser = build_parser_from_function(func)  # type: ignore[arg-type]
    for action in parser._actions:
        if action.dest == param_names[0]:
            return action
    raise ValueError(f"No action with dest={param_names[0]!r}")


# Templates used by ``_make_func``: one per parameter kind. ``code.replace`` swaps
# the literal name ``value`` for whatever ``name=`` the caller asks for, so the
# resulting signature carries the right dest without resorting to ``exec``.
def _stub_pos(self, value): ...  # type: ignore[no-untyped-def]
def _stub_kw(self, *, value): ...  # type: ignore[no-untyped-def]
def _stub_var(self, *value): ...  # type: ignore[no-untyped-def]


_STUB_TEMPLATES = {"pos": _stub_pos, "kw": _stub_kw, "var": _stub_var}
_MISSING: Any = object()


def _make_func(
    annotation: Any,
    *,
    name: str = "value",
    default: Any = _MISSING,
    kind: str = "pos",
) -> Any:
    """Construct a one-parameter ``self``-method carrying just an annotation.

    ``kind`` is ``"pos"`` (positional-or-keyword), ``"kw"`` (keyword-only), or
    ``"var"`` (``*args``).  Used by tests as a stand-in for the throwaway
    ``def do_x(self, value: T): ...`` stubs that only exist to be fed to
    ``build_parser_from_function``.
    """
    template = _STUB_TEMPLATES[kind]
    code = template.__code__
    new_varnames = tuple(n if n != "value" else name for n in code.co_varnames)
    new_code = code.replace(co_varnames=new_varnames)
    f = types.FunctionType(new_code, template.__globals__, name=f"_stub_{name}")
    # ``_MISSING`` for ``annotation`` produces an unannotated parameter (still ``-> None``).
    f.__annotations__ = {"return": type(None)} if annotation is _MISSING else {name: annotation, "return": type(None)}
    if default is not _MISSING:
        if kind == "pos":
            f.__defaults__ = (default,)
        elif kind == "kw":
            f.__kwdefaults__ = {name: default}
        else:
            raise ValueError(f"default not supported for kind={kind!r}")
    return f


def _action_for(annotation: Any, **kwargs: Any) -> argparse.Action:
    """Build a one-param function with the given annotation and return its action."""
    return _get_param_action(_make_func(annotation, **kwargs))


def _assert_build_error(annotation: Any, *, match: str | None = None, **kwargs: Any) -> None:
    """Assert ``build_parser_from_function`` rejects a one-param function with this annotation."""
    with pytest.raises(TypeError, match=match):
        build_parser_from_function(_make_func(annotation, **kwargs))


def _complete_cmd(app: cmd2.Cmd, line: str, text: str) -> list[str]:
    begidx = len(line) - len(text)
    endidx = len(line)
    completions = app.complete(text, line, begidx, endidx)
    return list(completions.to_strings())


# Register a custom add_argument parameter so we can verify that Argument()/Option()
# forward arbitrary registered parameters (parity with hand-built parsers).
register_argparse_argument_parameter("annotated_custom_attr")


# ---------------------------------------------------------------------------
# Core: build_parser_from_function produces correct action attributes
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Verify action attributes produced by build_parser_from_function."""

    @pytest.mark.parametrize(
        ("func", "expected"),
        [
            # --- Positionals ---
            pytest.param(_make_func(str, name="name"), {"option_strings": [], "type": None}, id="str_positional"),
            pytest.param(_make_func(Path, name="file"), {"option_strings": [], "type": Path}, id="path_positional"),
            pytest.param(
                _make_func(decimal.Decimal, name="amount"),
                {"option_strings": [], "type": decimal.Decimal},
                id="decimal_positional",
            ),
            pytest.param(_make_func(bool, name="flag"), {"option_strings": [], "type": _parse_bool}, id="bool_positional"),
            pytest.param(
                _make_func(_Color, name="color"), {"option_strings": [], "choices": _COLOR_CHOICE_ITEMS}, id="enum_positional"
            ),
            pytest.param(
                _make_func(Literal["fast", "slow"], name="mode"),
                {"option_strings": [], "choices": ["fast", "slow"]},
                id="literal_positional",
            ),
            pytest.param(
                _make_func(Literal[1, 2, 3], name="level"),
                {"option_strings": [], "choices": [1, 2, 3]},
                id="literal_int_positional",
            ),
            pytest.param(
                _make_func(_IntColor, name="color"),
                {"option_strings": [], "choices": _INT_COLOR_CHOICE_ITEMS},
                id="int_enum_positional",
            ),
            pytest.param(
                _make_func(_PlainColor, name="color"),
                {"option_strings": [], "choices": _PLAIN_COLOR_CHOICE_ITEMS},
                id="plain_enum_positional",
            ),
            pytest.param(_make_func(list[int], name="nums"), {"option_strings": [], "nargs": "+", "type": int}, id="list_int"),
            pytest.param(_make_func(set[int], name="nums"), {"option_strings": [], "nargs": "+", "type": int}, id="set_int"),
            pytest.param(
                _make_func(frozenset[int], name="nums"),
                {"option_strings": [], "nargs": "+", "type": int},
                id="frozenset_int",
            ),
            pytest.param(
                _make_func(tuple[int, int, int], name="triple"),
                {"option_strings": [], "nargs": 3, "type": int},
                id="tuple_fixed_triple",
            ),
            pytest.param(_make_func(list[str], name="files"), {"option_strings": [], "nargs": "+"}, id="list_positional"),
            pytest.param(_make_func(set[str], name="tags"), {"option_strings": [], "nargs": "+"}, id="set_positional"),
            pytest.param(
                _make_func(frozenset[str], name="tags"), {"option_strings": [], "nargs": "+"}, id="frozenset_positional"
            ),
            pytest.param(
                _make_func(tuple[int, ...], name="values"),
                {"option_strings": [], "nargs": "+", "type": int},
                id="tuple_ellipsis",
            ),
            pytest.param(
                _make_func(tuple[int, int], name="pair"), {"option_strings": [], "nargs": 2, "type": int}, id="tuple_fixed"
            ),
            pytest.param(_make_func(list, name="items"), {"option_strings": [], "nargs": "+"}, id="bare_list"),
            pytest.param(_make_func(frozenset, name="items"), {"option_strings": [], "nargs": "+"}, id="bare_frozenset"),
            pytest.param(_make_func(tuple, name="items"), {"option_strings": [], "nargs": "+"}, id="bare_tuple"),
            pytest.param(
                _make_func(Annotated[int | None, Argument()], name="val"),
                {"option_strings": [], "nargs": "?", "type": int},
                id="optional_positional",
            ),
            pytest.param(
                _make_func(Annotated[str, Argument()], name="arg", default="foo"),
                {"option_strings": [], "nargs": "?", "default": "foo"},
                id="positional_with_default",
            ),
            pytest.param(
                _make_func(int | None, name="val"), {"option_strings": [], "nargs": "?", "type": int}, id="optional_plain"
            ),
            pytest.param(
                _make_func(list[int] | None, name="vals"),
                {"option_strings": [], "nargs": "*", "type": int},
                id="optional_list",
            ),
            pytest.param(
                _make_func(tuple[int, ...] | None, name="vals"),
                {"option_strings": [], "nargs": "*", "type": int},
                id="optional_tuple_ellipsis",
            ),
            # --- Options ---
            pytest.param(
                _make_func(int, name="count", default=1),
                {"option_strings": ["--count"], "type": int, "default": 1},
                id="int_option",
            ),
            pytest.param(
                _make_func(float, name="rate", default=1.0),
                {"option_strings": ["--rate"], "type": float, "default": 1.0},
                id="float_option",
            ),
            pytest.param(
                _make_func(bool, name="verbose", default=False),
                {"option_strings": ["--verbose", "--no-verbose"], "default": False},
                id="bool_optional_action",
            ),
            pytest.param(
                _make_func(bool, name="debug", default=True),
                {"option_strings": ["--debug", "--no-debug"], "default": True},
                id="bool_optional_action_true",
            ),
            pytest.param(
                _make_func(Path, name="file", default=Path(".")),
                {"option_strings": ["--file"], "type": Path},
                id="path_option",
            ),
            pytest.param(
                _make_func(_Color, name="color", default=_Color.blue),
                {"option_strings": ["--color"], "choices": _COLOR_CHOICE_ITEMS, "default": _Color.blue},
                id="enum_option",
            ),
            pytest.param(
                _make_func(Literal["fast", "slow"], name="mode", default="fast"),
                {"option_strings": ["--mode"], "choices": ["fast", "slow"]},
                id="literal_option",
            ),
            pytest.param(
                _make_func(str | None, name="name", default=None),
                {"option_strings": ["--name"], "default": None},
                id="optional_str",
            ),
            pytest.param(
                _make_func(list[str] | None, name="items", default=None),
                {"option_strings": ["--items"], "nargs": "*"},
                id="list_with_default",
            ),
            # --- Annotated metadata ---
            pytest.param(
                _make_func(Annotated[str, Argument(help_text="Your name")], name="name"),
                {"option_strings": [], "help": "Your name"},
                id="annotated_help",
            ),
            pytest.param(
                _make_func(Annotated[str, Option("--color", "-c", help_text="Pick")], name="color", default="blue"),
                {"option_strings": ["--color", "-c"], "help": "Pick"},
                id="annotated_custom_flags",
            ),
            pytest.param(
                _make_func(Annotated[str, Argument(metavar="NAME")], name="name"),
                {"option_strings": [], "metavar": "NAME"},
                id="annotated_metavar",
            ),
            pytest.param(
                # argparse accepts a tuple metavar to label each value of a multi-value argument.
                _make_func(Annotated[tuple[int, int], Argument(metavar=("LO", "HI"))], name="span"),
                {"option_strings": [], "metavar": ("LO", "HI")},
                id="annotated_tuple_metavar",
            ),
            pytest.param(
                _make_func(Annotated[tuple[str, ...], Argument(nargs=2)], name="names"),
                {"option_strings": [], "nargs": 2},
                id="annotated_nargs",
            ),
            pytest.param(
                _make_func(Annotated[str, Option("--name", required=True)], name="name"),
                {"option_strings": ["--name"], "required": True},
                id="annotated_required",
            ),
            pytest.param(
                _make_func(Annotated[str, Option(required=True)], name="name"),
                {"option_strings": ["--name"], "required": True},
                id="annotated_required_auto_flag",
            ),
            # A value option with no default and no ``| None`` must be required (else omitting it
            # would pass None, violating the non-Optional type hint).
            pytest.param(
                _make_func(Annotated[str, Option("-c")], name="color"),
                {"option_strings": ["-c"], "required": True},
                id="option_no_default_required",
            ),
            # A bool option is a flag, not a value: absence means ``False``, so it defaults to False
            # and is NOT required (a required bool flag would be unsatisfiable for a short-only flag).
            pytest.param(
                _make_func(Annotated[bool, Option("-f")], name="flag"),
                {"option_strings": ["-f"], "required": False, "default": False},
                id="bool_option_no_default_defaults_false",
            ),
            # ``| None`` opts out of required: None is a valid value when omitted.
            pytest.param(
                _make_func(Annotated[str | None, Option("-c")], name="color"),
                {"option_strings": ["-c"], "required": False, "default": None},
                id="option_optional_no_default_not_required",
            ),
            pytest.param(
                _make_func(str | None, name="name", kind="kw"),
                {"option_strings": ["--name"], "required": False, "default": None},
                id="kw_only_optional_not_required",
            ),
            pytest.param(
                _make_func(Annotated[str, Argument(choices=["a", "b"])], name="food"),
                {"option_strings": [], "choices": ["a", "b"]},
                id="annotated_choices",
            ),
            pytest.param(
                _make_func(str, name="args", kind="var"), {"option_strings": [], "type": None, "nargs": "*"}, id="star_args"
            ),
            pytest.param(
                _make_func(int, name="args", kind="var"), {"option_strings": [], "type": int, "nargs": "*"}, id="star_args_int"
            ),
            # --- Keyword-only ---
            pytest.param(
                _make_func(str, name="name", kind="kw"),
                {"option_strings": ["--name"], "required": True},
                id="kw_only_required",
            ),
            pytest.param(
                _make_func(str, name="name", default="world", kind="kw"),
                {"option_strings": ["--name"], "default": "world"},
                id="kw_only_default",
            ),
            # --- Underscore in flag names ---
            pytest.param(
                _make_func(str, name="my_param", default="x"),
                {"option_strings": ["--my-param"], "default": "x"},
                id="underscore_flag",
            ),
            # --- Default type preservation ---
            pytest.param(
                _make_func(int, name="count", default="1"),
                {"option_strings": ["--count"], "default": "1"},
                id="default_not_coerced",
            ),
            pytest.param(
                _make_func(Path, name="file", default=Path("/tmp")),
                {"option_strings": ["--file"], "default": Path("/tmp")},
                id="path_default",
            ),
            # --- Optional + Annotated (union inside) ---
            pytest.param(
                _make_func(Annotated[str | None, Option("--name")], name="name", default=None),
                {"option_strings": ["--name"], "default": None},
                id="optional_annotated_inside",
            ),
            # --- Collections of complex element types ---
            pytest.param(
                _make_func(list[bool], name="flags"), {"option_strings": [], "nargs": "+", "type": _parse_bool}, id="list_bool"
            ),
            pytest.param(
                _make_func(set[bool], name="flags"), {"option_strings": [], "nargs": "+", "type": _parse_bool}, id="set_bool"
            ),
            pytest.param(
                _make_func(list[Path], name="files"), {"option_strings": [], "nargs": "+", "type": Path}, id="list_path"
            ),
            pytest.param(
                _make_func(list[Literal["fast", "slow"]], name="modes"),
                {"option_strings": [], "nargs": "+", "choices": ["fast", "slow"]},
                id="list_literal",
            ),
            pytest.param(
                _make_func(list[_Color], name="colors"),
                {"option_strings": [], "nargs": "+", "choices": _COLOR_CHOICE_ITEMS},
                id="list_enum",
            ),
            pytest.param(
                _make_func(tuple[Path, Path], name="src_dst"),
                {"option_strings": [], "nargs": 2, "type": Path},
                id="tuple_paths",
            ),
            pytest.param(
                _make_func(tuple[_Color, _Color], name="pair"),
                {"option_strings": [], "nargs": 2, "choices": _COLOR_CHOICE_ITEMS},
                id="tuple_enums",
            ),
            # --- Subclass fallback (Port(int) uses int converter) ---
            pytest.param(_make_func(_Port, name="port"), {"option_strings": [], "type": int}, id="int_subclass"),
            # --- Optional with non-None default ---
            pytest.param(
                _make_func(str | None, name="name", default="world"),
                {"option_strings": ["--name"], "default": "world"},
                id="optional_str_nondefault",
            ),
            # --- typing.Optional[T] (vs T | None) end-to-end ---
            pytest.param(
                _make_func(Optional[int], name="count", default=None),  # noqa: UP045
                {"option_strings": ["--count"], "type": int, "default": None},
                id="typing_optional",
            ),
        ],
    )
    def test_action_attributes(self, func, expected) -> None:
        action = _get_param_action(func)
        for key, value in expected.items():
            assert getattr(action, key) == value, f"{key}: expected {value!r}, got {getattr(action, key)!r}"

    def test_annotated_action_count(self) -> None:
        action = _get_param_action(
            _make_func(Annotated[int, Option("--verbose", "-v", action="count")], name="verbose", default=0)
        )
        assert isinstance(action, argparse._CountAction)

    def test_annotated_action_count_non_bool(self) -> None:
        action = _get_param_action(_make_func(Annotated[int, Option("--count", action="count")], name="count", default=0))
        assert isinstance(action, argparse._CountAction)
        assert action.default == 0

    def test_annotated_action_store_true(self) -> None:
        """``action='store_true'`` strips the inferred bool converter."""
        action = _get_param_action(
            _make_func(Annotated[bool, Option("--verbose", action="store_true")], name="verbose", default=False)
        )
        assert isinstance(action, argparse._StoreTrueAction)
        assert action.type is None
        assert action.default is False

    def test_annotated_action_store_false(self) -> None:
        """``action='store_false'`` strips the inferred bool converter."""
        action = _get_param_action(
            _make_func(Annotated[bool, Option("--quiet", action="store_false")], name="quiet", default=True)
        )
        assert isinstance(action, argparse._StoreFalseAction)
        assert action.type is None
        assert action.default is True

    def test_annotated_action_append(self) -> None:
        """``action='append'`` collects repeated flag values into a list."""
        action = _get_param_action(_make_func(Annotated[list[str], Option("--tag", action="append")], name="tag"))
        assert isinstance(action, argparse._AppendAction)
        assert action.option_strings == ["--tag"]

    def test_positional_with_default_is_optional(self) -> None:
        """A positional with a default takes 0-or-1 tokens and falls back to the default when absent."""
        parser = build_parser_from_function(_make_func(Annotated[str, Argument()], name="arg", default="foo"))
        assert parser.parse_args([]).arg == "foo"
        assert parser.parse_args(["bar"]).arg == "bar"

    def test_str_default_on_int_option_coerced_at_parse(self) -> None:
        """The decorator stores the default literally ('1', see ``default_not_coerced``); at parse
        time argparse applies ``type=int`` to the string default, so an absent ``--count`` yields int 1.
        """
        parser = build_parser_from_function(_make_func(int, name="count", default="1"))
        assert parser.parse_args([]).count == 1
        assert parser.parse_args(["--count", "5"]).count == 5

    def test_typing_optional_parses_end_to_end(self) -> None:
        """typing.Optional[int] yields None when absent and coerces to int when provided."""
        parser = build_parser_from_function(_make_func(Optional[int], name="count", default=None))  # noqa: UP045
        assert parser.parse_args([]).count is None
        parsed = parser.parse_args(["--count", "5"]).count
        assert parsed == 5
        assert isinstance(parsed, int)

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(_make_func(set[str], name="tags"), id="set"),
            pytest.param(_make_func(tuple[int, ...], name="values"), id="tuple"),
            pytest.param(_make_func(str, name="args", kind="var"), id="star_args"),
        ],
    )
    def test_collection_uses_casting_action(self, func) -> None:
        action = _get_param_action(func)
        assert isinstance(action, _CollectionCastingAction)

    def test_star_args_bare_defaults_to_str(self) -> None:
        """A bare ``*args`` (no element annotation) is treated as ``*args: str``."""
        action = _get_param_action(_make_func(_MISSING, name="args", kind="var"))
        assert action.option_strings == []
        assert action.nargs == "*"
        assert action.type is None

    def test_star_args_parses_to_tuple(self) -> None:
        """``*args: int`` accepts zero or more values, coerced and collected into a tuple."""
        parser = build_parser_from_function(_make_func(int, name="args", kind="var"))
        assert parser.parse_args([]).args == ()
        parsed = parser.parse_args(["1", "2", "3"]).args
        assert parsed == (1, 2, 3)
        assert isinstance(parsed, tuple)

    def test_self_skipped(self) -> None:
        parser = build_parser_from_function(_make_func(str, name="name"))
        dests = {a.dest for a in parser._actions}
        assert "self" not in dests

    def test_no_params_produces_empty_parser(self) -> None:
        """A function with zero parameters (not even self) produces a parser with no actions."""

        def bare() -> None: ...

        parser = build_parser_from_function(bare)
        dests = {a.dest for a in parser._actions if a.dest != "help"}
        assert dests == set()

    def test_self_only_method_produces_empty_parser(self) -> None:
        """A method whose only parameter is ``self`` produces a parser with no actions."""
        parser = build_parser_from_function(_func_empty)
        dests = {a.dest for a in parser._actions if a.dest != "help"}
        assert dests == set()
        assert parser.parse_args([]) == argparse.Namespace()

    @pytest.mark.parametrize(
        ("func", "resolve_arg_names", "expected_args"),
        [
            pytest.param(_func_unresolvable_self, _arg_names_via_parser, {"name", "count"}, id="self"),
            pytest.param(_func_unresolvable_cmd2_statement, _arg_names_via_parser, {"name", "count"}, id="cmd2_statement"),
            pytest.param(
                _func_unresolvable_cmd2_subcommand_func, _arg_names_via_base_command, {"verbose"}, id="cmd2_subcommand_func"
            ),
            pytest.param(_func_unresolvable_return, _arg_names_via_parser, {"name"}, id="return"),
        ],
    )
    def test_unresolvable_hint_on_ignored_param_is_tolerated(self, func, resolve_arg_names, expected_args) -> None:
        """An unresolvable forward reference on an annotation that never becomes an argument must not
        abort parser generation -- the bound ``self``/``cls``, the injected, skipped
        ``cmd2_statement``/``cmd2_subcommand_func`` parameters, and the function's ``return`` annotation. This
        is the common case of annotating with a type only importable under ``TYPE_CHECKING``. Only
        hints for parameters that actually become arguments are resolved; without that filtering each
        case raises "Failed to resolve type hints".
        """
        assert resolve_arg_names(func) == expected_args

    @pytest.mark.parametrize(
        ("func", "resolve_arg_names"),
        [
            pytest.param(_func_unresolvable_argument, _arg_names_via_parser, id="non_base"),
            pytest.param(_func_unresolvable_argument_base, _arg_names_via_base_command, id="base_command"),
        ],
    )
    def test_unresolvable_hint_on_real_argument_raises(self, func, resolve_arg_names) -> None:
        """An unresolvable forward reference on a parameter that *does* become an argument must abort
        with a clear, actionable error rather than being silently swallowed -- for both plain commands
        and base commands.
        """
        with pytest.raises(TypeError, match="Failed to resolve type hints"):
            resolve_arg_names(func)

    def test_forward_ref_resolves_through_functools_wraps_wrapper(self) -> None:
        """A forward reference must resolve against the *original* function's module even when the
        function reaching the parser builder is a ``functools.wraps`` wrapper defined in another
        module (e.g. a user decorator stacked under ``@with_annotated``). ``functools.wraps`` copies
        ``__annotations__`` but not ``__globals__``, so resolution must follow ``__wrapped__`` --
        mirroring what ``typing.get_type_hints`` does for a bare function.
        """

        def do_path(self, target: "Path", count: int = 1):
            pass

        # The wrapper carries a foreign global namespace lacking ``Path``; resolution must use the
        # unwrapped function's globals (this module) instead, or it raises "Failed to resolve".
        wrapped = _wrap_in_foreign_module(do_path)
        parser = build_parser_from_function(wrapped)
        dests = {action.dest for action in parser._actions if action.dest != "help"}
        assert dests == {"target", "count"}

    def test_dest_param_raises(self) -> None:
        with pytest.raises(ValueError, match="dest"):
            build_parser_from_function(_make_func(str, name="dest"))

    def test_subcommand_param_raises(self) -> None:
        def func(self, subcommand: str) -> None: ...

        with pytest.raises(ValueError, match="subcommand"):
            build_parser_from_function(func)

    def test_with_annotated_positional_only_param_raises(self) -> None:
        with pytest.raises(TypeError, match="positional-only"):
            build_parser_from_function(_func_positional_only)

    def test_with_annotated_positional_only_two_params_raises(self) -> None:
        with pytest.raises(TypeError, match="positional-only"):
            build_parser_from_function(_func_positional_only_xy)

    def test_with_annotated_positional_only_mixed_params_raises(self) -> None:
        with pytest.raises(TypeError, match="positional-only"):
            build_parser_from_function(_func_positional_only_mixed)

    def test_var_keyword_raises(self) -> None:
        """``**kwargs`` cannot be mapped to command-line arguments and is rejected."""
        with pytest.raises(TypeError, match=r"variadic keyword"):
            build_parser_from_function(_func_var_keyword)

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(_make_func(tuple[str, ...], name="files", kind="var"), id="tuple[str, ...]"),
            pytest.param(_make_func(list[str], name="xs", kind="var"), id="list[str]"),
            pytest.param(_make_func(list, name="xs", kind="var"), id="bare_list"),
        ],
    )
    def test_star_args_collection_element_raises(self, func) -> None:
        """``*args`` annotated with a collection element is rejected with a targeted hint.

        The annotation on ``*args`` is each value's type, so a collection element (e.g.
        ``*files: tuple[str, ...]``) would mean a tuple-of-collections.  The error must steer
        the user toward annotating the element type.
        """
        with pytest.raises(TypeError, match=r"the type of each value"):
            build_parser_from_function(func)

    def test_star_args_honors_argument_metadata(self) -> None:
        """``Annotated[T, Argument(...)]`` on ``*args`` applies help/metavar to the variadic positional."""
        action = _get_param_action(
            _make_func(Annotated[str, Argument(help_text="a file", metavar="FILE")], name="files", kind="var")
        )
        assert action.option_strings == []
        assert action.nargs == "*"
        assert action.help == "a file"
        assert action.metavar == "FILE"

    def test_star_args_honors_argument_choices(self) -> None:
        """``Argument(choices=...)`` on ``*args`` restricts every value to the choices."""
        parser = build_parser_from_function(_make_func(Annotated[str, Argument(choices=["a", "b"])], name="modes", kind="var"))
        assert parser.parse_args(["a", "b", "a"]).modes == ("a", "b", "a")
        with pytest.raises(SystemExit):
            parser.parse_args(["a", "nope"])

    def test_star_args_option_metadata_raises(self) -> None:
        """``Option()`` on ``*args`` is rejected; *args is always positional."""
        with pytest.raises(TypeError, match=r"\*args is always a positional"):
            build_parser_from_function(_make_func(Annotated[str, Option("--files")], name="files", kind="var"))

    def test_star_args_nargs_metadata_raises(self) -> None:
        """An explicit ``nargs`` on ``*args`` is rejected; its arity is fixed to ``'*'``."""
        with pytest.raises(TypeError, match=r"arity cannot be overridden"):
            build_parser_from_function(_make_func(Annotated[str, Argument(nargs=2)], name="files", kind="var"))

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(_make_func(Annotated[str, Argument()], name="name", kind="kw"), id="no_default"),
            pytest.param(_make_func(Annotated[str, Argument()], name="name", default="x", kind="kw"), id="with_default"),
        ],
    )
    def test_kw_only_with_argument_metadata_raises(self, func) -> None:
        """A keyword-only parameter cannot use ``Argument()`` (which marks a positional)."""
        with pytest.raises(TypeError, match=r"keyword-only but uses Argument\(\)"):
            build_parser_from_function(func)

    def test_option_no_default_is_enforced_at_parse_time(self) -> None:
        """Omitting a no-default, non-Optional option errors instead of silently passing None."""
        parser = build_parser_from_function(_make_func(Annotated[str, Option("-c")], name="color"))
        with pytest.raises(SystemExit):
            parser.parse_args([])
        assert parser.parse_args(["-c", "red"]).color == "red"

    def test_optional_option_no_default_yields_none_when_omitted(self) -> None:
        """``| None`` opts out of required: omitting it yields None, a valid value for the hint."""
        parser = build_parser_from_function(_make_func(Annotated[str | None, Option("-c")], name="color"))
        assert parser.parse_args([]).color is None
        assert parser.parse_args(["-c", "red"]).color == "red"

    def test_generator_choices_are_materialized(self) -> None:
        """A single-use iterable (generator) as choices must survive repeated argparse iteration."""
        parser = build_parser_from_function(
            _make_func(Annotated[str, Argument(choices=(c for c in ["a", "b"]))]),
        )
        assert parser.parse_args(["a"]).value == "a"
        assert parser.parse_args(["b"]).value == "b"
        with pytest.raises(SystemExit):
            parser.parse_args(["c"])

    @pytest.mark.parametrize(
        ("func", "dest", "default"),
        [
            pytest.param(
                _make_func(Annotated[bool, Option("-v", action="store_true")], name="verbose"),
                "verbose",
                False,
                id="store_true",
            ),
            pytest.param(_make_func(Annotated[int, Option("-l", action="count")], name="level"), "level", 0, id="count"),
        ],
    )
    def test_flag_action_no_default_not_required(self, func, dest, default) -> None:
        """Flag-style actions carry their own implicit default, so a missing default does not force required."""
        parser = build_parser_from_function(func)
        action = _get_param_action(func)
        assert action.required is False
        assert getattr(parser.parse_args([]), dest) == default

    def test_bool_option_no_default_is_usable_flag(self) -> None:
        """A bool option is a flag (absence -> False), not a required value.

        Marking it required would make a short-only flag unsatisfiable: ``-f`` can only set True
        and there is no negation form, so a required ``-f`` could never be False.
        """
        parser = build_parser_from_function(_make_func(Annotated[bool, Option("-f")], name="flag"))
        action = _get_param_action(_make_func(Annotated[bool, Option("-f")], name="flag"))
        assert action.required is False
        assert parser.parse_args([]).flag is False
        assert parser.parse_args(["-f"]).flag is True

    def test_optional_annotated_outside_raises(self) -> None:
        with pytest.raises(TypeError, match="Annotated"):
            build_parser_from_function(_make_func(Annotated[str, Option("--name")] | None, name="name", default=None))

    def test_annotated_ambiguous_union_raises(self) -> None:
        """Annotated[str | int, meta] must raise -- ambiguous inner union."""
        with pytest.raises(TypeError, match="ambiguous"):
            _resolve_annotation(Annotated[str | int, Option("--name")])

    def test_multi_param_order_and_presence(self) -> None:
        """Positional order preserved, options generated correctly."""
        parser = build_parser_from_function(_func_multi)
        positionals = [a.dest for a in parser._actions if not a.option_strings and a.dest != "help"]
        assert positionals == ["a", "b"]
        dests = {a.dest for a in parser._actions}
        assert "c" in dests


class TestTypeInferenceBuildParser:
    """Type-inference behavior and override precedence when building parser actions."""

    def test_choices_provider_overrides_inferred_enum_choices(self) -> None:
        action = _get_param_action(_make_func(Annotated[_Color, Argument(choices_provider=_provider)], name="color"))
        assert action.choices is None
        assert action.get_choices_provider() is _provider  # type: ignore[attr-defined]
        assert action.get_completer() is None  # type: ignore[attr-defined]

    def test_choices_provider_keeps_enum_coercion(self) -> None:
        """A choices_provider on an Enum keeps the converter so values still coerce to the member."""
        action = _get_param_action(_make_func(Annotated[_Color, Argument(choices_provider=_provider)], name="color"))
        assert action.type is not None
        assert action.type("red") is _Color.red

    def test_choices_provider_keeps_literal_coercion(self) -> None:
        """A choices_provider on a Literal keeps the converter (coercion) but drops the static choices."""

        def func(
            self,
            level: Annotated[Literal[1, 2], Argument(choices_provider=_provider)],
        ) -> None: ...

        action = _get_param_action(func)
        assert action.choices is None
        assert action.type is not None
        assert action.type("1") == 1

    def test_choices_provider_enum_coerces_at_parse(self) -> None:
        """End-to-end: an Enum with a choices_provider still parses to the enum member, not a str."""
        parser = build_parser_from_function(_make_func(Annotated[_Color, Argument(choices_provider=_provider)], name="color"))
        assert parser.parse_args(["red"]).color is _Color.red

    def test_choices_provider_literal_int_coerces_at_parse(self) -> None:
        """End-to-end: a Literal[int] with a choices_provider parses to int, not a str."""

        def func(
            self,
            level: Annotated[Literal[1, 2], Argument(choices_provider=_provider)],
        ) -> None: ...

        parser = build_parser_from_function(func)
        parsed = parser.parse_args(["1"]).level
        assert parsed == 1
        assert isinstance(parsed, int)

    def test_bare_enum_literal_coerce_at_parse(self) -> None:
        """Bare Enum/Literal positionals and options coerce to the declared type at parse time.

        Uses identity / isinstance (not ``==``) so a stripped converter returning a raw ``str``
        cannot hide behind StrEnum/IntEnum equality.
        """
        assert build_parser_from_function(_make_func(Literal["fast", "slow"], name="mode")).parse_args(["fast"]).mode == "fast"
        assert (
            build_parser_from_function(_make_func(Literal["fast", "slow"], name="mode", default="fast"))
            .parse_args(["--mode", "slow"])
            .mode
            == "slow"
        )

        level = build_parser_from_function(_make_func(Literal[1, 2, 3], name="level")).parse_args(["2"]).level
        assert level == 2
        assert isinstance(level, int)

        assert build_parser_from_function(_make_func(_Color, name="color")).parse_args(["red"]).color is _Color.red
        assert (
            build_parser_from_function(_make_func(_Color, name="color", default=_Color.blue))
            .parse_args(["--color", "red"])
            .color
            is _Color.red
        )
        # Non-StrEnum cases: identity defeats the StrEnum/IntEnum ``==`` masking property.
        assert build_parser_from_function(_make_func(_IntColor, name="color")).parse_args(["1"]).color is _IntColor.red
        assert build_parser_from_function(_make_func(_PlainColor, name="color")).parse_args(["red"]).color is _PlainColor.RED

    def test_completer_keeps_path_converter(self) -> None:
        """User-supplied completer on Path preserves the (non-restrictive) Path converter."""
        action = _get_param_action(_make_func(Annotated[Path, Argument(completer=cmd2.Cmd.path_complete)], name="file"))
        assert action.type is Path

    def test_completer_overrides_inferred_path_completion(self) -> None:
        action = _get_param_action(_make_func(Annotated[Path, Argument(completer=cmd2.Cmd.path_complete)], name="file"))
        assert action.get_choices_provider() is None  # type: ignore[attr-defined]
        assert action.get_completer() is cmd2.Cmd.path_complete  # type: ignore[attr-defined]

    def test_inferred_enum_choices_match_type_converter(self) -> None:
        """Enum choices must be convertible by the type converter."""
        action = _get_param_action(_make_func(_Color, name="color"))
        converter = action.type
        for choice in action.choices:
            assert isinstance(converter(str(choice)), _Color)

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(_make_func(Path, name="file"), id="path_positional"),
            pytest.param(_make_func(Path, name="file", default=Path(".")), id="path_option"),
            pytest.param(_make_func(list[Path], name="files"), id="list_path"),
            pytest.param(_make_func(tuple[Path, Path], name="src_dst"), id="tuple_paths"),
        ],
    )
    def test_path_annotation_wires_path_completer(self, func) -> None:
        """A bare ``Path`` annotation (no user metadata) auto-wires ``Cmd.path_complete``."""
        action = _get_param_action(func)
        assert action.get_completer() is cmd2.Cmd.path_complete  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Argument groups and mutually exclusive groups
# ---------------------------------------------------------------------------


class TestArgumentGroups:
    def test_groups_and_mutex_applied(self) -> None:
        parser = build_parser_from_function(
            _func_grouped,
            groups=(Group("local", "remote"), Group("force", "dry_run")),
            mutually_exclusive_groups=(Group("local", "remote"), Group("force", "dry_run")),
        )

        nonempty_groups = [group for group in parser._action_groups if group._group_actions]
        grouped_dests = [{action.dest for action in group._group_actions} for group in nonempty_groups]
        assert {"local", "remote"} in grouped_dests
        assert {"force", "dry_run"} in grouped_dests

        mutex_groups = [{action.dest for action in group._group_actions} for group in parser._mutually_exclusive_groups]
        assert {"local", "remote"} in mutex_groups
        assert {"force", "dry_run"} in mutex_groups

    def test_group_nonexistent_param_raises(self) -> None:
        with pytest.raises(ValueError, match="nonexistent parameter"):
            build_parser_from_function(_func_grouped, groups=(Group("missing"),))

    def test_param_in_multiple_groups_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be assigned to both argument group"):
            build_parser_from_function(_func_grouped, groups=(Group("local"), Group("local", "remote")))

    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_mutex_group_nests_inside_argument_group(self) -> None:
        """A mutex group whose members all sit in one Group(...) is created inside that argument group.

        This is the one nesting direction argparse supports: ``group.add_mutually_exclusive_group()``.
        The Python 3.11 deprecations cover the other three directions (group-in-group, group-in-mutex,
        mutex-in-mutex) -- group-in-group is a hard ``ValueError`` on current Python.  The
        ``filterwarnings`` marker turns any future argparse deprecation of this direction into a
        test failure.
        """
        parser = build_parser_from_function(
            _func_grouped,
            groups=(Group("local", "remote", "force", title="Location"),),
            mutually_exclusive_groups=(Group("local", "remote"),),
        )
        assert len(parser._mutually_exclusive_groups) == 1
        mutex = parser._mutually_exclusive_groups[0]
        location = next(g for g in parser._action_groups if g.title == "Location")
        # The mutex group's container is the titled argument group, so its members render under it.
        assert mutex._container is location
        mutex_dests = {action.dest for action in mutex._group_actions}
        assert mutex_dests == {"local", "remote"}
        # The non-mutex member still lands in the argument group.
        assert {action.dest for action in location._group_actions} == {"local", "remote", "force"}
        assert "Location" in parser.format_help()
        # Exclusivity is enforced.
        with pytest.raises(SystemExit):
            parser.parse_args(["--local", "a", "--remote", "b"])

    def test_mutex_group_spanning_different_argument_groups_raises(self) -> None:
        with pytest.raises(ValueError, match="spans parameters in different argument groups"):
            build_parser_from_function(
                _func_grouped,
                groups=(Group("local"), Group("remote")),
                mutually_exclusive_groups=(Group("local", "remote"),),
            )

    def test_mutex_group_partially_in_argument_group_raises(self) -> None:
        # ``local`` is in the titled group, ``remote`` is not: nesting the whole mutex inside the group
        # would silently pull ``remote`` into its section, so all-or-none membership is required.
        with pytest.raises(ValueError, match="mixes members in a titled argument group"):
            build_parser_from_function(
                _func_grouped,
                groups=(Group("local", title="Location"),),
                mutually_exclusive_groups=(Group("local", "remote"),),
            )

    def test_mutex_group_title_creates_titled_section(self) -> None:
        # title/description on the mutex itself build the titled section and nest the mutex inside it,
        # so no paired groups= entry is needed.
        parser = build_parser_from_function(
            _func_grouped,
            mutually_exclusive_groups=(Group("local", "remote", title="Location", description="where"),),
        )
        section = next(g for g in parser._action_groups if g.title == "Location")
        assert section.description == "where"
        assert len(parser._mutually_exclusive_groups) == 1
        mutex = parser._mutually_exclusive_groups[0]
        assert mutex._container is section
        assert {action.dest for action in mutex._group_actions} == {"local", "remote"}
        with pytest.raises(SystemExit):
            parser.parse_args(["--local", "a", "--remote", "b"])

    def test_mutex_group_title_with_members_in_argument_group_raises(self) -> None:
        # Declaring the titled section in both places (groups= and the mutex) is ambiguous.
        with pytest.raises(ValueError, match="declare the titled section in one place only"):
            build_parser_from_function(
                _func_grouped,
                groups=(Group("local", "remote", title="A"),),
                mutually_exclusive_groups=(Group("local", "remote", title="B"),),
            )

    def test_mutually_exclusive_group(self) -> None:
        """Mutually exclusive params cannot be used together."""

        def func(self, verbose: bool = False, quiet: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "quiet"),))
        assert len(parser._mutually_exclusive_groups) == 1
        group_dests = {a.dest for a in parser._mutually_exclusive_groups[0]._group_actions}
        assert group_dests == {"verbose", "quiet"}
        with pytest.raises(SystemExit):
            parser.parse_args(["--verbose", "--quiet"])

    def test_multiple_mutually_exclusive_groups(self) -> None:
        """Multiple mutually exclusive groups."""

        def func(self, verbose: bool = False, quiet: bool = False, json: bool = False, csv: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "quiet"), Group("json", "csv")))
        assert len(parser._mutually_exclusive_groups) == 2

    def test_required_member_in_mutex_group_raises(self) -> None:
        """A required (no default, non-Optional) option in a mutex group is rejected with a clear error.

        argparse forbids required members in a mutex group, and it would be type-unsafe: only one
        member is supplied, so the others arrive as None. The message must steer toward making it optional.
        """

        def func(self, local: Annotated[str, Option("--local")], remote: str | None = None) -> None: ...

        with pytest.raises(ValueError, match=r"mutually exclusive group members must be optional"):
            build_parser_from_function(func, mutually_exclusive_groups=(Group("local", "remote"),))

    def test_required_positional_member_in_mutex_group_raises(self) -> None:
        """A required *positional* mutex member is rejected with the same clear, type-safety message.

        Positionals never carry argparse's ``required=`` flag, so the check keys on the parameter
        being non-omittable, not on ``required`` (which is always False for a positional).
        """

        def func(self, a: int, b: Annotated[int, Option("--b")] = 0) -> None: ...

        with pytest.raises(ValueError, match=r"mutually exclusive group members must be optional"):
            build_parser_from_function(func, mutually_exclusive_groups=(Group("a", "b"),))

    def test_optional_members_in_mutex_group_build(self) -> None:
        """Mutex members that are Optional or have defaults build fine (the regression guard)."""

        def func(self, local: Annotated[str | None, Option("--local")] = None, remote: str = "x") -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("local", "remote"),))
        assert len(parser._mutually_exclusive_groups) == 1

    def test_bool_flag_members_in_mutex_group_build(self) -> None:
        """Plain bool flags (no default) are not required, so they belong in a mutex group."""

        def func(self, verbose: Annotated[bool, Option("--verbose")], quiet: Annotated[bool, Option("--quiet")]) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "quiet"),))
        assert len(parser._mutually_exclusive_groups) == 1

    def test_nonexistent_member_reported_over_required_member(self) -> None:
        """A typo'd member name surfaces as 'nonexistent', not masked by the required-member check."""

        def func(self, local: Annotated[str, Option("--local")], remote: str | None = None) -> None: ...

        with pytest.raises(ValueError, match=r"nonexistent parameter 'ghost'"):
            build_parser_from_function(func, mutually_exclusive_groups=(Group("local", "ghost"),))

    def test_argument_group(self) -> None:
        """Arguments in a group appear under a shared heading in help."""

        def func(self, src: str, dst: str, recursive: bool = False, verbose: bool = False) -> None: ...

        parser = build_parser_from_function(func, groups=(Group("src", "dst"),))
        default_titles = {"Positional Arguments", "options"}
        custom_groups = [g for g in parser._action_groups if g.title not in default_titles]
        assert len(custom_groups) >= 1
        all_custom_dests = {a.dest for g in custom_groups for a in g._group_actions}
        assert {"src", "dst"} <= all_custom_dests

    def test_mutually_exclusive_via_decorator(self) -> None:
        """@with_annotated(mutually_exclusive_groups=...) works end-to-end."""

        class App(cmd2.Cmd):
            @with_annotated(mutually_exclusive_groups=(Group("verbose", "quiet"),))
            def do_run(self, verbose: bool = False, quiet: bool = False) -> None:
                if verbose:
                    self.poutput("verbose")
                elif quiet:
                    self.poutput("quiet")
                else:
                    self.poutput("normal")

        app = App()
        out, _err = run_cmd(app, "run --verbose")
        assert out == ["verbose"]

        _out, err = run_cmd(app, "run --verbose --quiet")
        assert any("not allowed" in line.lower() for line in err)

    def test_group_and_mutex_can_overlap(self) -> None:
        def func(self, json: bool = False, csv: bool = False, plain: bool = False) -> None: ...

        parser = build_parser_from_function(
            func,
            groups=(Group("json", "csv"),),
            mutually_exclusive_groups=(Group("json", "csv"),),
        )
        custom_groups = [g for g in parser._action_groups if g.title not in {"Positional Arguments", "options"}]
        all_custom_dests = {a.dest for g in custom_groups for a in g._group_actions}
        assert {"json", "csv"} <= all_custom_dests
        with pytest.raises(SystemExit):
            parser.parse_args(["--json", "--csv"])


class TestParserCustomization:
    """description / epilog / formatter_class / parser_class and titled Group."""

    def test_titled_group(self) -> None:
        """Group(title=..., description=...) renders a titled help section."""

        def func(self, host: str, port: int = 22, verbose: bool = False) -> None: ...

        parser = build_parser_from_function(
            func,
            groups=(Group("host", "port", title="connection", description="where to connect"),),
        )
        titled = [g for g in parser._action_groups if g.title == "connection"]
        assert len(titled) == 1
        assert titled[0].description == "where to connect"
        assert {a.dest for a in titled[0]._group_actions} == {"host", "port"}

    def test_group_requires_members(self) -> None:
        with pytest.raises(ValueError, match="at least one member"):
            Group(title="empty")

    def test_description_and_epilog(self) -> None:
        parser = build_parser_from_function(_make_func(str), description="my description", epilog="my epilog")
        assert parser.description == "my description"
        assert parser.epilog == "my epilog"

    def test_custom_formatter_class(self) -> None:
        from cmd2.rich_utils import Cmd2HelpFormatter

        class MyFormatter(Cmd2HelpFormatter):
            pass

        parser = build_parser_from_function(_make_func(str), formatter_class=MyFormatter)
        assert parser.formatter_class is MyFormatter

    def test_custom_parser_class(self) -> None:
        class MyParser(cmd2.Cmd2ArgumentParser):
            pass

        parser = build_parser_from_function(_make_func(str), parser_class=MyParser)
        assert isinstance(parser, MyParser)

    def test_default_parser_class(self) -> None:
        """With no parser_class, the parser is an instance of the configured default."""
        from cmd2 import argparse_utils

        parser = build_parser_from_function(_make_func(str))
        assert type(parser) is argparse_utils.DEFAULT_ARGUMENT_PARSER

    def test_default_parser_class_follows_current_default(self, monkeypatch) -> None:
        """The default is resolved at call time, never a copy captured at import.

        ``set_default_argument_parser`` rebinds ``argparse_utils.DEFAULT_ARGUMENT_PARSER`` at runtime;
        a build issued afterwards must honor the new value.
        """
        from cmd2 import argparse_utils

        class MyDefaultParser(cmd2.Cmd2ArgumentParser):
            pass

        monkeypatch.setattr(argparse_utils, "DEFAULT_ARGUMENT_PARSER", MyDefaultParser)
        parser = build_parser_from_function(_make_func(str))
        assert type(parser) is MyDefaultParser

    def test_completer_class(self) -> None:
        from cmd2.argparse_completer import ArgparseCompleter

        class MyCompleter(ArgparseCompleter):
            pass

        parser = build_parser_from_function(_make_func(str), completer_class=MyCompleter)
        assert parser.completer_class is MyCompleter

    def test_default_completer_class(self) -> None:
        from cmd2 import argparse_completer

        assert build_parser_from_function(_make_func(str)).completer_class is argparse_completer.DEFAULT_ARGPARSE_COMPLETER

    def test_completer_class_via_decorator(self) -> None:
        from cmd2.argparse_completer import ArgparseCompleter

        class MyCompleter(ArgparseCompleter):
            pass

        @with_annotated(completer_class=MyCompleter)
        def do_run(self, name: str) -> None: ...

        builder = getattr(do_run, constants.ARGPARSE_COMMAND_ATTR_SPEC).parser_source
        assert builder().completer_class is MyCompleter

    def test_completer_class_threads_to_subcommand(self) -> None:
        from cmd2.argparse_completer import ArgparseCompleter

        class MyCompleter(ArgparseCompleter):
            pass

        @with_annotated(subcommand_to="team", completer_class=MyCompleter)
        def team_create(self, name: str) -> None: ...

        spec = getattr(team_create, constants.SUBCOMMAND_ATTR_SPEC)
        assert spec.parser_source().completer_class is MyCompleter

    def test_customization_via_decorator(self) -> None:
        """description/epilog/titled Group flow through @with_annotated end-to-end."""

        class App(cmd2.Cmd):
            @with_annotated(
                description="run the thing",
                epilog="see docs for more",
                groups=(Group("name", title="inputs"),),
            )
            def do_run(self, name: str) -> None:
                self.poutput(f"ran {name}")

        app = App()
        out, _err = run_cmd(app, "run alice")
        assert out == ["ran alice"]

        help_out, _ = run_cmd(app, "help run")
        joined = "\n".join(help_out).lower()
        assert "run the thing" in joined
        assert "see docs for more" in joined
        assert "inputs" in joined

    def test_customization_via_subcommand(self) -> None:
        """description/epilog flow through subcommand parsers."""

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_team(self, *, cmd2_subcommand_func=None) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="team", help="add a member", description="add desc", epilog="add epilog")
            def team_add(self, name: str) -> None:
                self.poutput(f"added {name}")

        app = App()
        out, _err = run_cmd(app, "team add bob")
        assert out == ["added bob"]

        spec = getattr(App.team_add, constants.SUBCOMMAND_ATTR_SPEC)
        subparser = spec.parser_source()
        assert subparser.description == "add desc"
        assert subparser.epilog == "add epilog"


class TestGroupHelpers:
    def test_validate_group_members_rejects_nonexistent_param(self) -> None:
        with pytest.raises(ValueError, match="nonexistent"):
            Group("verbose", "nonexistent")._validate_members(all_param_names={"verbose"}, group_type="groups")

    def test_build_argument_group_targets(self) -> None:
        parser = argparse.ArgumentParser()
        target_for, argument_group_for = _build_argument_group_targets(parser, groups=(Group("src", "dst"),))
        assert set(target_for) == {"src", "dst"}
        assert set(argument_group_for) == {"src", "dst"}
        assert target_for["src"] is argument_group_for["src"]
        assert target_for["dst"] is argument_group_for["dst"]

    def test_duplicate_argument_group_assignment_raises(self) -> None:
        # Double-assignment is enforced by _validate_group_specs, which the build path runs first.
        def func(self, *, verbose: bool = False) -> None: ...

        with pytest.raises(ValueError, match="argument group 1 and argument group 2"):
            build_parser_from_function(func, groups=(Group("verbose"), Group("verbose")))

    def test_apply_mutex_group_targets(self) -> None:
        parser = argparse.ArgumentParser()
        target_for, argument_group_for = _build_argument_group_targets(parser, groups=(Group("json", "csv"),))

        _apply_mutex_group_targets(
            parser,
            target_for=target_for,
            argument_group_for=argument_group_for,
            mutually_exclusive_groups=(Group("json", "csv"),),
        )

        assert target_for["json"] is target_for["csv"]
        assert isinstance(target_for["json"], argparse._MutuallyExclusiveGroup)

    def test_duplicate_mutex_group_assignment_raises(self) -> None:
        # Double-assignment is enforced by _validate_group_specs, which the build path runs first.
        def func(self, *, verbose: bool = False) -> None: ...

        with pytest.raises(ValueError, match="multiple mutually exclusive groups"):
            build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose"), Group("verbose")))

    def test_repeated_member_in_one_argument_group_raises(self) -> None:
        # A name listed twice in a single Group is a distinct mistake from cross-group assignment
        # and gets its own message (not the misleading "both group 1 and group 1").
        def func(self, *, verbose: bool = False) -> None: ...

        with pytest.raises(ValueError, match="listed more than once in argument group 1"):
            build_parser_from_function(func, groups=(Group("verbose", "verbose"),))

    def test_repeated_member_in_one_mutex_group_raises(self) -> None:
        def func(self, *, verbose: bool = False) -> None: ...

        with pytest.raises(ValueError, match="listed more than once in mutually exclusive group 1"):
            build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "verbose"),))

    def test_validate_group_specs_rejects_cross_group_members(self) -> None:
        # The spec validator owns the group-shaped rules; construction trusts it.
        def func(self, src: str = "a", dst: str = "b") -> None: ...

        with pytest.raises(ValueError, match="different argument groups"):
            _validate_group_specs(
                func,
                skip_params=frozenset(),
                groups=(Group("src"), Group("dst")),
                mutually_exclusive_groups=(Group("src", "dst"),),
            )


class TestEagerGroupSpecValidation:
    """Group specs hard-fail at decoration time (class definition), not on first command use.

    The decorator runs the name-only spec checks before deferring the parser build, so a
    misconfigured group raises while the class body executes instead of surfacing as a swallowed
    runtime error the first time the command runs.  Type hints are never resolved by these checks,
    so forward-referenced annotations still decorate (the parser build stays deferred for them).
    """

    def test_member_typo_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v") -> None: ...

        with pytest.raises(ValueError, match="groups references nonexistent parameter 'typo'"):
            with_annotated(groups=(Group("typo"),))(do_x)

    def test_mutex_member_typo_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v") -> None: ...

        with pytest.raises(ValueError, match="mutually_exclusive_groups references nonexistent parameter 'typo'"):
            with_annotated(mutually_exclusive_groups=(Group("typo"),))(do_x)

    def test_param_in_two_argument_groups_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v") -> None: ...

        with pytest.raises(ValueError, match="argument group 1 and argument group 2"):
            with_annotated(groups=(Group("a"), Group("a")))(do_x)

    def test_param_in_two_mutex_groups_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v", b: str = "w") -> None: ...

        with pytest.raises(ValueError, match="multiple mutually exclusive groups"):
            with_annotated(mutually_exclusive_groups=(Group("a", "b"), Group("a")))(do_x)

    def test_required_on_plain_group_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v") -> None: ...

        with pytest.raises(ValueError, match="only valid in mutually_exclusive_groups"):
            with_annotated(groups=(Group("a", required=True),))(do_x)

    def test_mutex_spanning_argument_groups_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v", b: str = "w") -> None: ...

        with pytest.raises(ValueError, match="spans parameters in different argument groups"):
            with_annotated(groups=(Group("a"), Group("b")), mutually_exclusive_groups=(Group("a", "b"),))(do_x)

    def test_mutex_partially_in_argument_group_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v", b: str = "w") -> None: ...

        with pytest.raises(ValueError, match="mixes members in a titled argument group"):
            with_annotated(groups=(Group("a", title="T"),), mutually_exclusive_groups=(Group("a", "b"),))(do_x)

    def test_titled_section_declared_twice_fails_at_decoration(self) -> None:
        def do_x(self, a: str = "v", b: str = "w") -> None: ...

        with pytest.raises(ValueError, match="declare the titled section in one place only"):
            with_annotated(
                groups=(Group("a", "b", title="T"),),
                mutually_exclusive_groups=(Group("a", "b", title="U"),),
            )(do_x)

    def test_subcommand_group_typo_fails_at_decoration(self) -> None:
        def team_add(self, a: str = "v") -> None: ...

        with pytest.raises(ValueError, match="nonexistent parameter 'typo'"):
            with_annotated(subcommand_to="team", groups=(Group("typo"),))(team_add)

    def test_eager_validation_does_not_resolve_type_hints(self) -> None:
        # The group error fires even though the annotation can never resolve: the checks read
        # parameter names only, so the unresolvable hint is not touched.
        def do_x(self, a: "NoSuchType" = None) -> None: ...  # noqa: F821

        with pytest.raises(ValueError, match="nonexistent parameter 'typo'"):
            with_annotated(groups=(Group("typo"),))(do_x)

    def test_unresolvable_hints_with_valid_groups_decorate(self) -> None:
        # Valid specs + an unresolvable annotation must decorate without raising; type resolution
        # stays deferred to the parser build, preserving forward-reference support.
        def do_x(self, a: "NoSuchType" = None) -> None: ...  # noqa: F821

        with_annotated(groups=(Group("a", title="T"),))(do_x)

    def test_valid_nested_config_decorates_cleanly(self) -> None:
        def do_x(
            self,
            a: Annotated[bool, Option(action="store_true")] = False,
            b: Annotated[bool, Option(action="store_true")] = False,
            c: Annotated[bool, Option(action="store_true")] = False,
            d: Annotated[bool, Option(action="store_true")] = False,
        ) -> None: ...

        # A nested mutex plus a separately titled mutex must decorate without raising.
        with_annotated(
            groups=(Group("a", "b", title="T"),),
            mutually_exclusive_groups=(Group("a", "b"), Group("c", "d", title="U")),
        )(do_x)


# ---------------------------------------------------------------------------
# _resolve_annotation: positional vs option classification
# ---------------------------------------------------------------------------

_ARG_META = Argument(help_text="Name")
_OPT_META = Option("--color", "-c", help_text="Pick")


class TestResolveAnnotation:
    @pytest.mark.parametrize(
        ("annotation", "has_default", "expected_positional"),
        [
            pytest.param(str, False, True, id="plain_str"),
            pytest.param(str | None, False, True, id="optional_str_positional"),
            pytest.param(str | None, True, False, id="optional_str_with_default"),
            pytest.param(Annotated[str, _ARG_META], False, True, id="annotated_argument"),
            pytest.param(Annotated[str, _OPT_META], False, False, id="annotated_option"),
            pytest.param(Annotated[str, "some doc"], False, True, id="annotated_no_meta"),
            pytest.param(str, True, False, id="has_default"),
            pytest.param(bool, True, False, id="bool_flag"),
        ],
    )
    def test_classification(self, annotation, has_default, expected_positional) -> None:
        # A non-None default is supplied when has_default (default=None on a non-Optional type
        # is itself rejected); classification depends only on whether a default exists, not its value.
        extra = {"default": 0} if has_default else {}
        arg = _resolve_annotation(annotation, has_default=has_default, **extra)
        assert arg.is_positional is expected_positional

    def test_optional_wrapping_annotated_with_none_inside(self) -> None:
        """Optional[Annotated[T | None, meta]] is allowed (inner type contains None)."""
        ann = Annotated[str | None, _OPT_META] | None
        arg = _resolve_annotation(ann)
        assert arg.metadata is _OPT_META
        assert arg.is_positional is False

    def test_typing_union_optional(self) -> None:
        ns: dict = {}
        exec("import typing; t = typing.Union[str, None]", ns)
        assert _resolve_annotation(ns["t"]).is_positional is True

    def test_typing_union_optional_with_default(self) -> None:
        ns: dict = {}
        exec("import typing; t = typing.Union[str, None]", ns)
        assert _resolve_annotation(ns["t"], has_default=True, default=None).is_positional is False

    def test_annotated_multiple_metadata_picks_first(self) -> None:
        meta1 = Argument(help_text="first")
        meta2 = Option("--x", help_text="second")
        arg = _resolve_annotation(Annotated[str, meta1, meta2])
        assert arg.metadata is meta1
        assert arg.extras.get("help") == "first"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestUnsupportedPatterns:
    def test_union_raises_with_diagnostic_message(self) -> None:
        with pytest.raises(TypeError, match=r"str.*int") as exc_info:
            _resolve_annotation(str | int)
        assert "Union" in str(exc_info.value)

    def test_tuple_mixed_raises(self) -> None:
        with pytest.raises(TypeError, match="mixed element types"):
            _resolve_annotation(tuple[int, str, float])

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(Annotated[str, Argument(nargs=2)], id="str_nargs_2"),
            pytest.param(Annotated[int | None, Argument(nargs="+")], id="optional_int_nargs_plus"),
            pytest.param(Annotated[int, Argument(nargs="*")], id="int_nargs_star"),
            pytest.param(Annotated[str, Argument(nargs=1)], id="str_nargs_1"),
        ],
    )
    def test_multi_nargs_on_scalar_raises(self, annotation) -> None:
        with pytest.raises(TypeError, match=r"nargs=.* not a collection type"):
            _resolve_annotation(annotation)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(Annotated[tuple[str, str], Argument(nargs=1)], id="tuple2_nargs_1"),
            pytest.param(Annotated[tuple[str, str], Argument(nargs=3)], id="tuple2_nargs_3"),
            pytest.param(Annotated[tuple[int, int, int], Argument(nargs="+")], id="tuple3_nargs_plus"),
            pytest.param(Annotated[tuple[str, str], Argument(nargs="?")], id="tuple2_nargs_optional"),
        ],
    )
    def test_nargs_overrides_fixed_arity_raises(self, annotation) -> None:
        with pytest.raises(TypeError, match=r"conflicts with the fixed arity"):
            _resolve_annotation(annotation)

    @pytest.mark.parametrize(
        ("annotation", "resolve_kwargs"),
        [
            pytest.param(
                Annotated[tuple[int, int], Argument()],
                {"has_default": True, "default": (1, 2)},
                id="fixed_tuple_with_default",
            ),
            pytest.param(Annotated[tuple[int, int] | None, Argument()], {}, id="fixed_tuple_optional"),
            pytest.param(
                Annotated[tuple[int, ...], Argument(nargs=2)],
                {"has_default": True, "default": (1, 2)},
                id="explicit_nargs_with_default",
            ),
            pytest.param(Annotated[tuple[int, ...] | None, Argument(nargs=2)], {}, id="explicit_nargs_optional"),
        ],
    )
    def test_optional_fixed_arity_positional_raises(self, annotation, resolve_kwargs) -> None:
        """argparse cannot make a fixed-arity positional optional, so the combination is rejected."""
        with pytest.raises(TypeError, match=r"fixed-arity positional"):
            _resolve_annotation(annotation, **resolve_kwargs)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(list[set[int]], id="list_of_set"),
            pytest.param(set[list[str]], id="set_of_list"),
            pytest.param(tuple[list[int], ...], id="tuple_of_list"),
            pytest.param(frozenset[list[int]], id="frozenset_of_list"),
            pytest.param(list[frozenset[int]], id="list_of_frozenset"),
        ],
    )
    def test_nested_collection_raises(self, annotation) -> None:
        with pytest.raises(TypeError, match="Nested collections are not supported"):
            _resolve_annotation(annotation)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(dict[str, int], id="dict"),
        ],
    )
    def test_unsupported_subscripted_generic_raises(self, annotation) -> None:
        """An unsupported subscripted generic must raise, not silently arrive as a plain str."""
        with pytest.raises(TypeError, match=r"Unsupported parameter type"):
            _resolve_annotation(annotation)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(Annotated[list[int] | None, Argument(nargs="?")], id="list_q"),
            pytest.param(Annotated[list[int] | None, Argument(nargs=(0, 1))], id="list_0_1"),
            pytest.param(Annotated[set[str] | None, Argument(nargs="?")], id="set_q"),
        ],
    )
    def test_optional_single_nargs_on_collection_raises(self, annotation) -> None:
        """nargs='?'/(0,1) on a collection yields a single value the casting action cannot wrap."""
        with pytest.raises(TypeError, match=r"single value"):
            _resolve_annotation(annotation)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(datetime.datetime, id="datetime"),
            pytest.param(datetime.date, id="date"),
            pytest.param(uuid.UUID, id="uuid"),
            pytest.param(bytes, id="bytes"),
            pytest.param(complex, id="complex"),
        ],
    )
    def test_unsupported_scalar_type_raises(self, annotation) -> None:
        """A type with no converter must not silently arrive as a plain string."""
        with pytest.raises(TypeError, match="Unsupported parameter type"):
            _resolve_annotation(annotation)

    def test_unsupported_custom_class_raises(self) -> None:
        class Money:
            def __init__(self, raw: str) -> None:
                self.raw = raw

        with pytest.raises(TypeError, match="Unsupported parameter type"):
            _resolve_annotation(Money)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(str, id="str"),
            pytest.param(Any, id="any"),
            pytest.param(object, id="object"),
        ],
    )
    def test_passthrough_scalar_types_keep_no_converter(self, annotation) -> None:
        """str / Any / object are stored as the raw string (type stays None)."""
        _flags, kwargs = _resolve_annotation(annotation)._emit()
        assert "type" not in kwargs

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(list[int, str], id="list_multi_args"),
            pytest.param(set[int, str], id="set_multi_args"),
        ],
    )
    def test_collection_multiple_type_args_raises(self, annotation) -> None:
        with pytest.raises(TypeError, match="type arguments is not supported"):
            _resolve_annotation(annotation)

    def test_tuple_ellipsis_wrong_position_raises(self) -> None:
        with pytest.raises(TypeError, match="Ellipsis in an unexpected position"):
            _resolve_annotation(tuple[..., int])

    def test_single_element_union_without_none_raises(self) -> None:
        """Union with one non-None type and no None should raise."""
        from typing import Union
        from unittest.mock import patch

        from cmd2.annotated import _unwrap_optional

        # Python normalizes Union[str] to str, so we can't construct this
        # through normal typing. Patch get_origin/get_args to simulate it.
        sentinel = object()
        with (
            patch("cmd2.annotated.get_origin", return_value=Union),
            patch("cmd2.annotated.get_args", return_value=(str,)),
            pytest.raises(TypeError, match="single-element Union"),
        ):
            _unwrap_optional(sentinel)


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------


class TestParseBool:
    @pytest.mark.parametrize("value", ["1", "true", "True", "t", "yes", "y", "on"])
    def test_true(self, value) -> None:
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "f", "no", "n", "off"])
    def test_false(self, value) -> None:
        assert _parse_bool(value) is False

    def test_invalid(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="invalid boolean"):
            _parse_bool("maybe")


class TestEnumConverter:
    @pytest.mark.parametrize(
        ("enum_cls", "input_val", "expected"),
        [
            pytest.param(_Color, "red", _Color.red, id="str_by_value"),
            pytest.param(_IntColor, "1", _IntColor.red, id="int_by_value"),
            pytest.param(_IntColor, "red", _IntColor.red, id="int_by_name"),
            pytest.param(_PlainColor, "red", _PlainColor.RED, id="plain_by_value"),
            pytest.param(_PlainColor, "BLUE", _PlainColor.BLUE, id="plain_by_name"),
        ],
    )
    def test_convert(self, enum_cls, input_val, expected) -> None:
        assert _make_enum_type(enum_cls)(input_val) is expected

    def test_invalid(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="invalid choice"):
            _make_enum_type(_Color)("purple")

    def test_preserves_class(self) -> None:
        assert _make_enum_type(_Color)._cmd2_enum_class is _Color


class TestLiteralConverter:
    @pytest.mark.parametrize(
        ("values", "input_val", "expected"),
        [
            pytest.param(["fast", "slow"], "fast", "fast", id="str_match"),
            pytest.param([1, 2, 3], "2", 2, id="int_match"),
            pytest.param([True, False], "yes", True, id="bool_true_coercion"),
            pytest.param([True, False], "0", False, id="bool_false_coercion"),
        ],
    )
    def test_convert(self, values, input_val, expected) -> None:
        assert _make_literal_type(values)(input_val) == expected

    @pytest.mark.parametrize(
        ("values", "input_val"),
        [
            pytest.param(["fast", "slow"], "medium", id="non_bool_string"),
            # bool-like input ("yes"/"on") must still be rejected when the Literal has no bool member
            pytest.param(["fast", "slow"], "yes", id="bool_like_no_bool_member"),
            pytest.param([1, 2], "on", id="bool_like_int_literal"),
        ],
    )
    def test_invalid(self, values, input_val) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="invalid choice"):
            _make_literal_type(values)(input_val)

    def test_direct_match_before_bool_coercion(self) -> None:
        assert _make_literal_type(["yes", "no"])("yes") == "yes"

    def test_colliding_str_representations_raises(self) -> None:
        with pytest.raises(TypeError, match="same string representation"):
            _make_literal_type(["1", 1])


# ---------------------------------------------------------------------------
# Metadata classes
# ---------------------------------------------------------------------------


class TestMetadata:
    @pytest.mark.parametrize(
        ("meta_kwargs", "expected"),
        [
            pytest.param({}, {}, id="empty"),
            pytest.param({"help_text": "Name"}, {"help": "Name"}, id="help_text"),
            pytest.param({"metavar": "NAME"}, {"metavar": "NAME"}, id="metavar"),
            pytest.param({"choices": ["a", "b"]}, {"choices": ["a", "b"]}, id="choices"),
            pytest.param({"table_columns": ("Name", "Age")}, {"table_columns": ("Name", "Age")}, id="table_columns"),
            pytest.param({"suppress_tab_hint": True}, {"suppress_tab_hint": True}, id="suppress_tab_hint"),
        ],
    )
    def test_to_kwargs(self, meta_kwargs, expected) -> None:
        assert Argument(**meta_kwargs).to_kwargs() == expected

    def test_to_kwargs_preserves_empty_string(self) -> None:
        """Explicit empty string help_text should not be silently dropped."""
        assert Argument(help_text="").to_kwargs() == {"help": ""}

    def test_to_kwargs_preserves_empty_choices(self) -> None:
        """Explicit empty choices list should not be silently dropped."""
        assert Argument(choices=[]).to_kwargs() == {"choices": []}

    def test_option_to_kwargs_includes_action_and_required(self) -> None:
        opt = Option("--color", "-c", action="count", required=True, help_text="Pick")
        kwargs = opt.to_kwargs()
        assert "names" not in kwargs
        assert "flags" not in kwargs
        assert kwargs["action"] == "count"
        assert kwargs["required"] is True
        assert kwargs["help"] == "Pick"

    def test_choices_provider_in_kwargs(self) -> None:
        def provider(cmd):
            return []

        assert Argument(choices_provider=provider).to_kwargs()["choices_provider"] is provider

    def test_completer_in_kwargs(self) -> None:
        assert Argument(completer=cmd2.Cmd.path_complete).to_kwargs()["completer"] is cmd2.Cmd.path_complete

    def test_extra_kwarg_forwarded_in_to_kwargs(self) -> None:
        """A registered custom add_argument parameter is forwarded via **kwargs."""
        assert Argument(annotated_custom_attr="v").to_kwargs()["annotated_custom_attr"] == "v"
        assert Option("--x", annotated_custom_attr="v").to_kwargs()["annotated_custom_attr"] == "v"

    def test_registered_custom_param_set_on_action(self) -> None:
        """A registered custom parameter reaches the resulting argparse Action."""
        action = _action_for(Annotated[str, Argument(annotated_custom_attr="v")])
        assert action.get_annotated_custom_attr() == "v"  # type: ignore[attr-defined]

    def test_unregistered_kwarg_raises_at_build(self) -> None:
        """An unknown (unregistered) keyword is rejected when the parser is built."""
        _assert_build_error(Annotated[str, Argument(definitely_not_registered="v")])


# ---------------------------------------------------------------------------
# _CollectionCastingAction
# ---------------------------------------------------------------------------


class TestCollectionCastingAction:
    def test_casts_list_to_container(self) -> None:
        action = _CollectionCastingAction(
            option_strings=[],
            dest="items",
            nargs="+",
            container_factory=set,
        )
        ns = argparse.Namespace()
        action(argparse.ArgumentParser(), ns, ["a", "b", "a"])
        assert ns.items == {"a", "b"}

    def test_non_list_passthrough(self) -> None:
        action = _CollectionCastingAction(
            option_strings=[],
            dest="items",
            nargs="?",
            container_factory=set,
        )
        ns = argparse.Namespace()
        action(argparse.ArgumentParser(), ns, "single_value")
        assert ns.items == "single_value"


class TestCollectionRuntimeCast:
    """End-to-end verify ``parse_args`` returns the declared container type, not a plain list."""

    @pytest.mark.parametrize(
        ("annotation", "name", "args", "container", "expected"),
        [
            pytest.param(frozenset[int], "nums", ["1", "2", "2", "3"], frozenset, frozenset({1, 2, 3}), id="frozenset_int"),
            pytest.param(set[int], "nums", ["1", "2", "2", "3"], set, {1, 2, 3}, id="set_int"),
            pytest.param(tuple[int, ...], "values", ["1", "2", "3"], tuple, (1, 2, 3), id="tuple_ellipsis"),
            pytest.param(tuple[int, int], "pair", ["5", "10"], tuple, (5, 10), id="tuple_fixed"),
            pytest.param(list[bool], "flags", ["true", "no", "on"], list, [True, False, True], id="list_bool"),
            pytest.param(
                tuple[Path, Path],
                "src_dst",
                ["/tmp/a", "/tmp/b"],
                tuple,
                (Path("/tmp/a"), Path("/tmp/b")),
                id="tuple_paths",
            ),
        ],
    )
    def test_returns_declared_container(self, annotation, name, args, container, expected) -> None:
        parser = build_parser_from_function(_make_func(annotation, name=name))
        value = getattr(parser.parse_args(args), name)
        assert isinstance(value, container)
        assert value == expected

    def test_append_action_collects_values(self) -> None:
        parser = build_parser_from_function(_make_func(Annotated[list[str], Option("--tag", action="append")], name="tag"))
        ns = parser.parse_args(["--tag", "a", "--tag", "b"])
        assert ns.tag == ["a", "b"]

    def test_int_subclass_uses_int_converter(self) -> None:
        """``Port(int)`` falls back to ``int`` converter; argparse returns ``int``, not ``Port``."""
        parser = build_parser_from_function(_make_func(_Port, name="port"))
        ns = parser.parse_args(["8080"])
        assert ns.port == 8080


# ---------------------------------------------------------------------------
# _filtered_namespace_kwargs edge cases
# ---------------------------------------------------------------------------


class TestFilteredNamespaceKwargs:
    def test_excludes_subcommand_key(self) -> None:
        from cmd2.annotated import _filtered_namespace_kwargs

        ns = argparse.Namespace(subcommand="add", name="Alice")
        result = _filtered_namespace_kwargs(ns, exclude_subcommand=True)
        assert "subcommand" not in result
        assert result == {"name": "Alice"}


# ---------------------------------------------------------------------------
# _parse_positionals edge case
# ---------------------------------------------------------------------------


class TestParsePositionals:
    def test_skips_non_statement_next_arg(self) -> None:
        """When next_arg after Cmd is not Statement/str, loop continues."""
        from cmd2.decorators import _parse_positionals

        app = cmd2.Cmd()
        # Two Cmd-like objects: first has non-str next, second has str next
        result_cmd, result_stmt = _parse_positionals((app, 42, app, "hello"))
        assert result_cmd is app
        assert result_stmt == "hello"

    def test_matches_statement_type(self) -> None:
        """When next_arg is a Statement, it is accepted."""
        from cmd2.decorators import _parse_positionals
        from cmd2.parsing import Statement

        app = cmd2.Cmd()
        stmt = Statement("hello")
        result_cmd, result_stmt = _parse_positionals((app, stmt))
        assert result_cmd is app
        assert result_stmt is stmt


# ---------------------------------------------------------------------------
# Runtime coverage
# ---------------------------------------------------------------------------


class _Sport(enum.StrEnum):
    football = "football"
    basketball = "basketball"
    tennis = "tennis"


class _RuntimeAnnotatedApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self._items = ["apple", "banana", "cherry"]

    def item_choices(self) -> list[cmd2.CompletionItem]:
        return [cmd2.CompletionItem(item) for item in self._items]

    @with_annotated
    def do_greet(self, name: str, count: int = 1) -> None:
        for _ in range(count):
            self.poutput(f"Hello {name}")

    @with_annotated
    def do_add(self, a: int, b: int = 0) -> None:
        self.poutput(str(a + b))

    @with_annotated
    def do_paint(
        self,
        item: str,
        color: Annotated[_Color, Option("--color", "-c", help_text="Color to use")] = _Color.blue,
        verbose: bool = False,
    ) -> None:
        msg = f"Painting {item} {color.value}"
        if verbose:
            msg += " (verbose)"
        self.poutput(msg)

    @with_annotated
    def do_pick(self, item: Annotated[str, Argument(choices_provider=item_choices)]) -> None:
        self.poutput(f"Picked: {item}")

    @with_annotated
    def do_open(self, path: Path) -> None:
        self.poutput(f"Opening: {path}")

    @with_annotated
    def do_sport(self, sport: _Sport) -> None:
        self.poutput(f"Playing: {sport.value}")

    @with_annotated
    def do_toggle(self, enabled: bool) -> None:
        self.poutput(f"Enabled: {enabled}")

    @with_annotated(preserve_quotes=True)
    def do_raw(self, text: str) -> None:
        self.poutput(f"raw: {text}")

    @with_annotated
    def do_echo_all(self, *words: str) -> None:
        self.poutput(f"words={list(words)}")

    @with_annotated
    def do_total(self, label: str, *nums: int) -> None:
        self.poutput(f"{label}={sum(nums)}")

    @with_annotated
    def do_cat(self, *files: str, upper: bool = False) -> None:
        joined = " ".join(files)
        self.poutput(joined.upper() if upper else joined)

    @with_annotated
    def do_ping(self) -> None:
        self.poutput("pong")


@pytest.fixture
def runtime_app() -> _RuntimeAnnotatedApp:
    app = _RuntimeAnnotatedApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestRuntimeExecution:
    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            pytest.param("greet Alice", ["Hello Alice"], id="greet_basic"),
            pytest.param("greet Alice --count 3", ["Hello Alice", "Hello Alice", "Hello Alice"], id="greet_count"),
            pytest.param("add 2 --b 3", ["5"], id="add"),
            pytest.param("add 10", ["10"], id="add_default"),
            pytest.param("paint wall", ["Painting wall blue"], id="paint_default_color"),
            pytest.param("paint wall --color red", ["Painting wall red"], id="paint_color"),
            pytest.param("paint wall --verbose", ["Painting wall blue (verbose)"], id="paint_verbose"),
            pytest.param("sport football", ["Playing: football"], id="sport_enum"),
            pytest.param("echo_all a b c", ["words=['a', 'b', 'c']"], id="star_args_values"),
            pytest.param("echo_all", ["words=[]"], id="star_args_empty"),
            pytest.param("total score 1 2 3", ["score=6"], id="leading_plus_star_args"),
            pytest.param("total score", ["score=0"], id="leading_plus_empty_star_args"),
            pytest.param("cat a b c", ["a b c"], id="star_args_with_kwonly_opt"),
            pytest.param("cat a b c --upper", ["A B C"], id="star_args_with_kwonly_opt_set"),
            pytest.param("ping", ["pong"], id="no_args_command"),
        ],
    )
    def test_command_execution(self, runtime_app, command, expected) -> None:
        out, _err = run_cmd(runtime_app, command)
        assert out == expected

    def test_no_args_command_rejects_extra_args(self, runtime_app) -> None:
        """A no-parameter command accepts no positionals and errors on extras."""
        _out, err = run_cmd(runtime_app, "ping extra")
        assert any("unrecognized" in line.lower() or "error" in line.lower() for line in err)

    def test_help_shows_arguments(self, runtime_app) -> None:
        out, _ = run_cmd(runtime_app, "help greet")
        assert "name" in "\n".join(out).lower()

    def test_help_shows_option_help(self, runtime_app) -> None:
        out, _ = run_cmd(runtime_app, "help paint")
        help_text = "\n".join(out)
        assert "Color to use" in help_text


class TestRuntimeCompletion:
    def test_enum_completion(self, runtime_app) -> None:
        assert sorted(_complete_cmd(runtime_app, "paint wall --color ", "")) == ["blue", "green", "red"]

    def test_enum_completion_partial(self, runtime_app) -> None:
        assert _complete_cmd(runtime_app, "paint wall --color r", "r") == ["red"]

    def test_choices_provider_completion(self, runtime_app) -> None:
        assert sorted(_complete_cmd(runtime_app, "pick ", "")) == ["apple", "banana", "cherry"]

    def test_positional_enum_completion(self, runtime_app) -> None:
        assert _complete_cmd(runtime_app, "sport foot", "foot") == ["football"]

    def test_path_completion_from_annotation(self, runtime_app, tmp_path) -> None:
        test_file = tmp_path / "annotated-path.txt"
        test_file.touch()
        text = str(tmp_path) + "/"
        result_strings = _complete_cmd(runtime_app, f"open {text}", text)
        assert any("annotated-path.txt" in item for item in result_strings)

    def test_positional_bool_completion_from_annotation(self, runtime_app) -> None:
        completions = set(_complete_cmd(runtime_app, "toggle ", ""))
        assert {"true", "false", "yes", "no", "on", "off", "1", "0"}.issubset(completions)


class _AnnotatedCommandSet(cmd2.CommandSet):
    def __init__(self) -> None:
        super().__init__()
        self._sports = ["football", "baseball"]

    def sport_choices(self) -> list[cmd2.CompletionItem]:
        return [cmd2.CompletionItem(sport) for sport in self._sports]

    @with_annotated
    def do_play(self, sport: Annotated[str, Argument(choices_provider=sport_choices)]) -> None:
        self._cmd.poutput(f"Playing {sport}")


@pytest.fixture
def cmdset_app() -> cmd2.Cmd:
    cmdset = _AnnotatedCommandSet()
    app = cmd2.Cmd(command_sets=[cmdset])
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestCommandSet:
    def test_command_set_execution(self, cmdset_app) -> None:
        out, _err = run_cmd(cmdset_app, "play football")
        assert out == ["Playing football"]

    def test_command_set_completion(self, cmdset_app) -> None:
        assert sorted(_complete_cmd(cmdset_app, "play ", "")) == ["baseball", "football"]


# ---------------------------------------------------------------------------
# Integration: with_annotated decorator runs commands through cmd2
# ---------------------------------------------------------------------------


class _IntegrationApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.ns_calls = 0

    def namespace_provider(self) -> argparse.Namespace:
        self.ns_calls += 1
        ns = argparse.Namespace()
        ns.custom_stuff = "custom"
        return ns

    @with_annotated
    def do_greet(self, name: str, count: int = 1, loud: bool = False, *, keyword_arg: str | None = None) -> None:
        """Greet someone."""
        for _ in range(count):
            msg = f"Hello {name}"
            self.poutput(msg.upper() if loud else msg)
        if keyword_arg is not None:
            self.poutput(keyword_arg)

    @with_annotated(with_unknown_args=True)
    def do_flex(self, name: str, _unknown: list[str] | None = None) -> None:
        self.poutput(f"name={name}")
        if _unknown:
            self.poutput(f"unknown={_unknown}")

    @with_annotated(preserve_quotes=True)
    def do_raw(self, text: str) -> None:
        self.poutput(f"raw: {text}")

    @with_annotated(ns_provider=namespace_provider)
    def do_ns_test(self, cmd2_statement=None) -> None:
        self.poutput("ok")

    @with_annotated
    def do_prefixed(self, cmd2_mode: int = 1) -> None:
        self.poutput(f"cmd2_mode={cmd2_mode}")


class _GroupedParserApp(cmd2.Cmd):
    @with_annotated(
        groups=(Group("local", "remote"), Group("force", "dry_run")),
        mutually_exclusive_groups=(Group("local", "remote"), Group("force", "dry_run")),
    )
    def do_transfer(
        self,
        *,
        local: str | None = None,
        remote: str | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> None:
        target = local if local is not None else remote
        mode = "force" if force else "dry-run" if dry_run else "normal"
        self.poutput(f"Transfer {target} in {mode} mode")


@pytest.fixture
def app() -> _IntegrationApp:
    app = _IntegrationApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


@pytest.fixture
def grouped_app() -> _GroupedParserApp:
    return _GroupedParserApp()


class TestWithAnnotatedIntegration:
    """Integration tests covering the decorator's cmd_wrapper runtime paths."""

    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            pytest.param("greet Alice", ["Hello Alice"], id="basic"),
            pytest.param("greet Alice --count 2 --loud", ["HELLO ALICE", "HELLO ALICE"], id="options"),
            pytest.param("greet Alice --no-loud", ["Hello Alice"], id="bool_no_flag"),
            pytest.param("greet Alice --loud", ["HELLO ALICE"], id="bool_flag"),
            pytest.param("flex Alice", ["name=Alice"], id="unknown_args_empty"),
        ],
    )
    def test_command_execution(self, app, command, expected) -> None:
        out, _err = run_cmd(app, command)
        assert out == expected

    def test_with_unknown_args(self, app) -> None:
        out, _err = run_cmd(app, "flex Alice --extra stuff")
        assert out[0] == "name=Alice"
        assert "unknown=" in out[1]

    def test_preserve_quotes(self, app) -> None:
        out, _err = run_cmd(app, 'raw "hello world"')
        assert out == ['raw: "hello world"']

    def test_error_produces_stderr(self, app) -> None:
        _out, err = run_cmd(app, "greet")
        assert any("error" in line.lower() or "usage" in line.lower() for line in err)

    def test_no_args_raises_type_error(self, app) -> None:
        with pytest.raises(TypeError, match="Expected arguments"):
            app.do_greet()

    def test_with_unknown_args_requires_param(self) -> None:
        with pytest.raises(TypeError, match="_unknown"):

            @with_annotated(with_unknown_args=True)
            def do_broken(self, name: str) -> None:
                pass

    def test_positional_only_unknown_rejected(self) -> None:
        with pytest.raises(TypeError, match="keyword-compatible"):

            @with_annotated(with_unknown_args=True)
            def do_broken(self, _unknown: list[str], /) -> None:
                pass

    def test_ns_provider(self, app) -> None:
        out, _err = run_cmd(app, "ns_test")
        assert out == ["ok"]
        assert app.ns_calls == 1

    def test_cmd2_prefixed_param_is_preserved(self, app) -> None:
        out, _err = run_cmd(app, "prefixed --cmd2-mode 5")
        assert out == ["cmd2_mode=5"]

    def test_kwargs_passthrough(self, app) -> None:
        app.do_greet("Alice", keyword_arg="kwarg_value")

    def test_direct_call_with_positional_only(self, app) -> None:
        """Calling do_* directly with a single statement string parses normally."""
        app.do_greet("Alice")
        assert app.stdout.getvalue().splitlines()[-1] == "Hello Alice"

    def test_direct_call_with_options(self, app) -> None:
        """Direct call with a full statement string including options."""
        app.do_greet("Alice --count 2 --loud")
        out = app.stdout.getvalue().splitlines()
        assert out[-2:] == ["HELLO ALICE", "HELLO ALICE"]

    def test_direct_call_kwargs_override_parsed(self, app) -> None:
        """Explicit kwargs on a direct call override parsed values."""
        app.do_greet("Alice", count=3)
        out = app.stdout.getvalue().splitlines()
        assert out[-3:] == ["Hello Alice", "Hello Alice", "Hello Alice"]

    def test_direct_call_no_arg_command(self) -> None:
        """A no-parameter command parses an (empty) statement string on a direct call."""

        class App(cmd2.Cmd):
            @with_annotated
            def do_ping(self) -> None:
                self.poutput("pong")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        app.do_ping("")
        assert app.stdout.getvalue().splitlines()[-1] == "pong"

    def test_direct_call_star_args_command(self) -> None:
        """A *args command parses a statement string positionally on a direct call."""

        class App(cmd2.Cmd):
            @with_annotated
            def do_cat(self, *files: str, upper: bool = False) -> None:
                joined = "|".join(files)
                self.poutput(joined.upper() if upper else joined)

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        app.do_cat("a b c")
        assert app.stdout.getvalue().splitlines()[-1] == "a|b|c"
        app.do_cat("a b --upper")
        assert app.stdout.getvalue().splitlines()[-1] == "A|B"

    def test_invoke_missing_leading_positional_raises(self) -> None:
        """A leading positional missing from func_kwargs fails loud instead of shifting *args.

        ``*positional`` is unpacked by index, so silently skipping a missing leading
        name would slide ``*var_values`` into the wrong parameter. Fail with KeyError.
        """

        def fn(self, first: str, *rest: str) -> None: ...

        with pytest.raises(KeyError, match="first"):
            _invoke_command_func(
                fn,
                None,
                {"rest": ("x", "y")},
                leading_names=["first"],
                var_positional_name="rest",
            )

    def test_invoke_missing_var_positional_raises(self) -> None:
        """A *args name missing from func_kwargs fails loud instead of defaulting to empty.

        argparse always populates the ``*args`` attribute (an empty list when nothing is
        given), so a missing key signals a bug and must not be silently swallowed.
        """

        def fn(self, *rest: str) -> None: ...

        with pytest.raises(KeyError, match="rest"):
            _invoke_command_func(fn, None, {}, leading_names=[], var_positional_name="rest")

    def test_bare_call_decorator(self) -> None:
        """@with_annotated() with empty parens works same as @with_annotated."""

        class App(cmd2.Cmd):
            @with_annotated()
            def do_echo(self, text: str) -> None:
                self.poutput(text)

        out, _err = run_cmd(App(), "echo hi")
        assert out == ["hi"]

    def test_missing_parser_raises(self, app) -> None:
        from unittest.mock import patch

        with (
            patch.object(app.command_parsers, "get", return_value=None),
            pytest.raises(ValueError, match="No argument parser found"),
        ):
            app.do_greet("Alice")


class TestGroupedParserIntegration:
    def test_grouped_command_executes(self, grouped_app) -> None:
        out, _err = run_cmd(grouped_app, "transfer --local build.tar.gz --dry-run")
        assert out == ["Transfer build.tar.gz in dry-run mode"]

    def test_grouped_command_mutex_error(self, grouped_app) -> None:
        _out, err = run_cmd(grouped_app, "transfer --local a --remote b")
        assert any("not allowed with argument" in line.lower() for line in err)

    def test_grouped_command_help_lists_flags(self, grouped_app) -> None:
        out, _err = run_cmd(grouped_app, "help transfer")
        help_text = "\n".join(out)
        assert "--local" in help_text
        assert "--remote" in help_text
        assert "--force" in help_text
        assert "--dry-run" in help_text


# ---------------------------------------------------------------------------
# Subcommands: @with_annotated(base_command=True) + @with_annotated(subcommand_to=...)
# ---------------------------------------------------------------------------


class _SubcommandApp(cmd2.Cmd):
    # Level 1: base command
    @with_annotated(base_command=True)
    def do_manage(self, cmd2_subcommand_func, verbose: bool = False) -> None:
        """Management command with subcommands."""
        if verbose:
            self.poutput("verbose mode")
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    # Level 2: leaf subcommands
    @with_annotated(subcommand_to="manage", help="add something")
    def manage_add(self, value: str) -> None:
        self.poutput(f"added: {value}")

    @with_annotated(subcommand_to="manage", help="sum values")
    def manage_sum(self, *nums: int) -> None:
        self.poutput(f"sum: {sum(nums)}")

    @with_annotated(subcommand_to="manage", help="list things", aliases=["ls"])
    def manage_list(self) -> None:
        self.poutput("listing all")

    # Level 2: intermediate subcommand (also a base for level 3)
    @with_annotated(subcommand_to="manage", base_command=True, help="manage members")
    def manage_member(self, cmd2_subcommand_func) -> None:
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    # Level 3: nested subcommand
    @with_annotated(subcommand_to="manage member", help="add a member")
    def manage_member_add(self, name: str) -> None:
        self.poutput(f"member added: {name}")


@pytest.fixture
def subcmd_app() -> _SubcommandApp:
    return _SubcommandApp()


class TestSubcommands:
    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            pytest.param("manage add hello", ["added: hello"], id="add"),
            pytest.param("manage list", ["listing all"], id="list"),
            pytest.param("manage ls", ["listing all"], id="list_alias"),
            pytest.param("manage member add Alice", ["member added: Alice"], id="nested_3_levels"),
            pytest.param("manage sum 1 2 3", ["sum: 6"], id="subcommand_star_args"),
            pytest.param("manage sum", ["sum: 0"], id="subcommand_star_args_empty"),
        ],
    )
    def test_subcommand_executes(self, subcmd_app, command, expected) -> None:
        out, _err = run_cmd(subcmd_app, command)
        assert out == expected

    @pytest.mark.parametrize(
        ("command", "expected_error"),
        [
            pytest.param("manage", "the following arguments are required: SUBCOMMAND", id="missing_subcmd"),
            pytest.param("manage delete", "invalid choice: 'delete'", id="invalid_subcmd"),
            pytest.param("manage member", "the following arguments are required: SUBCOMMAND", id="missing_nested_subcmd"),
        ],
    )
    def test_subcommand_errors(self, subcmd_app, command, expected_error) -> None:
        _out, err = run_cmd(subcmd_app, command)
        assert any(expected_error in line for line in err), f"expected {expected_error!r} in {err}"

    def test_subcommand_help(self, subcmd_app) -> None:
        out, _err = run_cmd(subcmd_app, "help manage")
        help_text = "\n".join(out)
        assert "add" in help_text
        assert "list" in help_text
        assert "member" in help_text


class _OptionalIntermediateApp(cmd2.Cmd):
    """An intermediate subcommand that is itself a base command with an *optional* subcommand."""

    @with_annotated(base_command=True)
    def do_opt(self, cmd2_subcommand_func) -> None:
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    @with_annotated(subcommand_to="opt", base_command=True, subcommand_required=False, help="optional middle")
    def opt_mid(self, cmd2_subcommand_func) -> None:
        # The guard must blank out the self-referential handler so this runs exactly once.
        self.poutput("mid:none" if cmd2_subcommand_func is None else "mid:recurse")
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    @with_annotated(subcommand_to="opt mid", help="leaf")
    def opt_mid_leaf(self, name: str) -> None:
        self.poutput(f"leaf:{name}")


@pytest.fixture
def opt_app() -> _OptionalIntermediateApp:
    return _OptionalIntermediateApp()


class TestOptionalIntermediateSubcommand:
    def test_intermediate_without_deeper_subcommand_runs_once(self, opt_app) -> None:
        """The recursion guard blanks the self-referential handler: the body runs once with None."""
        out, _err = run_cmd(opt_app, "opt mid")
        assert out == ["mid:none"]

    def test_deeper_subcommand_still_dispatches(self, opt_app) -> None:
        """Blanking the self-reference must not break dispatch to a genuine deeper subcommand."""
        out, _err = run_cmd(opt_app, "opt mid leaf Bob")
        assert out == ["leaf:Bob"]

    def test_guard_blanks_only_subcommand_func(self) -> None:
        """The guard must null *only* cmd2_subcommand_func, leaving the intermediate's own args intact."""

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_opt(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="opt", base_command=True, subcommand_required=False)
            def opt_mid(self, cmd2_subcommand_func, verbose: bool = False) -> None:
                self.poutput(f"none={cmd2_subcommand_func is None}:verbose={verbose}")
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

        out, _err = run_cmd(App(), "opt mid --verbose")
        assert out == ["none=True:verbose=True"]

    def test_guard_fires_at_deeper_nesting_level(self) -> None:
        """The guard must work past two levels: the deepest *selected* optional base runs once."""

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_a(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="a", base_command=True, subcommand_required=False)
            def a_b(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="a b", base_command=True, subcommand_required=False)
            def a_b_c(self, cmd2_subcommand_func) -> None:
                self.poutput(f"c:none={cmd2_subcommand_func is None}")
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="a b c", help="leaf")
            def a_b_c_leaf(self, name: str) -> None:
                self.poutput(f"leaf:{name}")

        app = App()
        assert run_cmd(app, "a b c")[0] == ["c:none=True"]
        assert run_cmd(app, "a b c leaf Z")[0] == ["leaf:Z"]

    def test_guard_works_for_commandset_subcommand(self) -> None:
        """The handler is a CommandSet-bound method here; unwrapping to __func__ must still match."""

        class _Grp(cmd2.CommandSet):
            @cmd2.with_category("grp")
            @with_annotated(base_command=True)
            def do_grp(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="grp", base_command=True, subcommand_required=False)
            def grp_mid(self, cmd2_subcommand_func) -> None:
                self._cmd.poutput(f"mid:none={cmd2_subcommand_func is None}")
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="grp mid", help="leaf")
            def grp_mid_leaf(self, name: str) -> None:
                self._cmd.poutput(f"leaf:{name}")

        app = cmd2.Cmd(auto_load_commands=False)
        app.register_command_set(_Grp())
        assert run_cmd(app, "grp mid")[0] == ["mid:none=True"]
        assert run_cmd(app, "grp mid leaf Q")[0] == ["leaf:Q"]


class TestSubcommandValidation:
    def test_subcommand_aliases_none_raises(self) -> None:
        """aliases=None is off-spec (it must be a Sequence[str]); reject it with a clear message."""
        with pytest.raises(TypeError, match=r"aliases must be a sequence"):
            with_annotated(subcommand_to="team", aliases=None)

    def test_base_command_positional_str_raises(self) -> None:
        """Positional str param conflicts with subcommand name."""
        with pytest.raises(TypeError, match="positional"):

            @with_annotated(base_command=True)
            def do_bad(self, name: str, cmd2_subcommand_func) -> None:
                pass

    def test_base_command_positional_annotated_raises(self) -> None:
        """Explicit Argument() metadata forces positional -- conflict."""
        with pytest.raises(TypeError, match="positional"):

            @with_annotated(base_command=True)
            def do_bad(self, a: Annotated[str, Argument(help_text="x")], cmd2_subcommand_func) -> None:
                pass

    def test_base_command_missing_subcommand_func_raises(self) -> None:
        with pytest.raises(TypeError, match=constants.NS_ATTR_SUBCOMMAND_FUNC):

            @with_annotated(base_command=True)
            def do_bad(self, verbose: bool = False) -> None:
                pass

    def test_base_command_missing_subcommand_func_raises_with_no_parameters(self) -> None:
        """A zero-parameter base command with no cmd2_subcommand_func must still raise.

        Guards the function-level ``cmd2_subcommand_func`` check (a plain ``if`` in ``_resolve_parameters``,
        not a :data:`_CONSTRAINTS` row): the per-argument :data:`_CONSTRAINTS` loop never runs when
        no arguments exist, so this case is the sole reason the missing-handler check lives at
        function scope.
        """
        with pytest.raises(TypeError, match=constants.NS_ATTR_SUBCOMMAND_FUNC):

            @with_annotated(base_command=True)
            def do_bad(self) -> None:
                pass

    def test_cmd2_subcommand_func_without_base_command_raises(self) -> None:
        """A 'cmd2_subcommand_func' parameter is only valid when base_command=True."""
        with pytest.raises(TypeError, match="base_command=True"):

            @with_annotated
            def do_bad(self, cmd2_subcommand_func, name: str = "") -> None:
                pass

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"help": "not allowed"}, id="help_only"),
            pytest.param({"aliases": ["x"]}, id="aliases_only"),
            pytest.param({"deprecated": True}, id="deprecated_only"),
        ],
    )
    def test_subcmd_only_params_without_subcommand_to_raises(self, kwargs) -> None:
        with pytest.raises(TypeError, match="subcommand_to"):

            @with_annotated(**kwargs)
            def do_bad(self, name: str) -> None:
                pass

    @pytest.mark.parametrize(
        ("kwargs", "pattern"),
        [
            pytest.param({"with_unknown_args": True}, "with_unknown_args", id="with_unknown_args"),
            pytest.param({"preserve_quotes": True}, "preserve_quotes", id="preserve_quotes"),
            pytest.param({"ns_provider": lambda self: argparse.Namespace()}, "ns_provider", id="ns_provider"),
        ],
    )
    def test_subcommand_rejects_unsupported_runtime_options(self, kwargs, pattern) -> None:
        with pytest.raises(TypeError, match=pattern):

            @with_annotated(subcommand_to="team", **kwargs)
            def team_add(self, name: str, _unknown: list[str] | None = None) -> None:
                pass

    def test_subcommand_with_mutually_exclusive_groups(self) -> None:
        """mutually_exclusive_groups should work on subcommands."""

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_fmt(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="fmt", help="output", mutually_exclusive_groups=(Group("json", "csv"),))
            def fmt_out(self, msg: str, json: bool = False, csv: bool = False) -> None:
                self.poutput(f"json={json} csv={csv} {msg}")

        app = App()
        out, _err = run_cmd(app, "fmt out hello --json")
        assert out == ["json=True csv=False hello"]
        _out, err = run_cmd(app, "fmt out hello --json --csv")
        assert any("not allowed" in line.lower() for line in err)

    def test_intermediate_base_command_positional_raises(self) -> None:
        with pytest.raises(TypeError, match="positional"):

            @with_annotated(subcommand_to="team", base_command=True)
            def team_member(self, name: str, cmd2_subcommand_func) -> None:
                pass

    def test_intermediate_base_command_missing_subcommand_func_raises(self) -> None:
        with pytest.raises(TypeError, match=constants.NS_ATTR_SUBCOMMAND_FUNC):

            @with_annotated(subcommand_to="team", base_command=True)
            def team_member(self) -> None:
                pass

    @pytest.mark.parametrize(
        ("subcommand_to", "func_name"),
        [
            pytest.param("team", "wrong_name", id="wrong_prefix"),
            pytest.param("team member", "team_wrong", id="wrong_nested_prefix"),
        ],
    )
    def test_subcommand_naming_enforced(self, subcommand_to, func_name) -> None:
        ns: dict = {}
        exec(f"def {func_name}(self, x: str) -> None: ...", ns)
        with pytest.raises(TypeError, match="must be named"):
            with_annotated(subcommand_to=subcommand_to)(ns[func_name])

    @pytest.mark.parametrize(
        ("decorator_kwargs", "expected_help", "expected_aliases"),
        [
            pytest.param({"help": "create", "aliases": ["c"]}, "create", ("c",), id="with_help_and_aliases"),
            pytest.param({}, None, (), id="without_help_or_aliases"),
        ],
    )
    def test_subcommand_spec_attributes(self, decorator_kwargs, expected_help, expected_aliases) -> None:
        @with_annotated(subcommand_to="team", **decorator_kwargs)
        def team_create(self, name: str = "") -> None: ...

        spec = getattr(team_create, constants.SUBCOMMAND_ATTR_SPEC)
        assert spec.command == "team"
        assert spec.name == "create"
        assert spec.help == expected_help
        assert spec.aliases == expected_aliases
        assert isinstance(spec.parser_source(), argparse.ArgumentParser)

    @pytest.mark.parametrize("deprecated", [True, False])
    def test_subcommand_deprecated_flows_to_spec(self, deprecated) -> None:
        @with_annotated(subcommand_to="team", deprecated=deprecated)
        def team_create(self, name: str = "") -> None: ...

        spec = getattr(team_create, constants.SUBCOMMAND_ATTR_SPEC)
        assert spec.deprecated is deprecated


# ---------------------------------------------------------------------------
# A non-Optional type with a None default is rejected (None would violate the hint)
# ---------------------------------------------------------------------------


class TestNoneDefaultRejection:
    @pytest.mark.parametrize(
        ("annotation", "kind"),
        [
            pytest.param(str, "pos", id="str"),
            pytest.param(int, "pos", id="int"),
            pytest.param(list[str], "pos", id="list"),
            pytest.param(Annotated[str, Option("-n")], "pos", id="option"),
            pytest.param(Annotated[str, Argument()], "pos", id="argument"),
            pytest.param(str, "kw", id="kw_only"),
        ],
    )
    def test_none_default_raises(self, annotation, kind) -> None:
        _assert_build_error(annotation, default=None, kind=kind, match="not Optional")

    def test_optional_none_default_builds(self) -> None:
        parser = build_parser_from_function(_make_func(str | None, default=None))
        assert parser.parse_args([]).value is None

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(Any, id="any"),
            pytest.param(object, id="object"),
            pytest.param(_MISSING, id="unannotated"),
        ],
    )
    def test_none_accepting_types_exempt(self, annotation) -> None:
        assert build_parser_from_function(_make_func(annotation, default=None)).parse_args([]).value is None


# ---------------------------------------------------------------------------
# Tightened action= contract (result type must match the declared type)
# ---------------------------------------------------------------------------


class TestActionTightening:
    @pytest.mark.parametrize(
        ("annotation", "pattern"),
        [
            pytest.param(Annotated[str, Option("-t", action="append")], "list", id="append_on_scalar"),
            pytest.param(Annotated[set[str], Option("-t", action="append")], "list", id="append_on_set"),
            pytest.param(Annotated[tuple[str, str], Option("-t", action="append")], "list", id="append_on_tuple"),
            pytest.param(Annotated[str, Option("-t", action="extend")], "list", id="extend_on_scalar"),
            pytest.param(Annotated[bool, Option("-c", action="count")], "int", id="count_on_bool"),
            pytest.param(Annotated[str, Option("-c", action="store_const")], "const", id="store_const"),
            pytest.param(Annotated[list[str], Option("-c", action="append_const")], "const", id="append_const"),
            pytest.param(Annotated[str, Option("-c", action="frobnicate")], "not supported", id="unknown_action"),
            pytest.param(Annotated[list[str], Option("-c", action="store_true")], "collection", id="noncollection_action"),
            pytest.param(Annotated[int, Option("-c", action="store")], "not supported", id="explicit_store"),
            pytest.param(Annotated[int, Option("-c", action="store", const=5)], "ambiguous", id="store_with_const"),
            # The ambiguity wins even when the const's type also mismatches the declared type.
            pytest.param(Annotated[int, Option("-c", action="store", const="x")], "ambiguous", id="store_with_mistyped_const"),
        ],
    )
    def test_action_type_mismatch_raises(self, annotation, pattern) -> None:
        _assert_build_error(annotation, match=pattern)

    def test_append_on_list_accumulates(self) -> None:
        parser = build_parser_from_function(_make_func(Annotated[list[str], Option("--tag", action="append")]))
        assert parser.parse_args([]).value == []
        assert parser.parse_args(["--tag", "a", "--tag", "b"]).value == ["a", "b"]

    def test_extend_on_list_flattens_and_converts(self) -> None:
        parser = build_parser_from_function(_make_func(Annotated[list[int], Option("-n", action="extend")]))
        assert parser.parse_args([]).value == []
        assert parser.parse_args(["-n", "1", "2", "-n", "3"]).value == [1, 2, 3]

    def test_count_no_default_yields_zero(self) -> None:
        annotation = Annotated[int, Option("-l", action="count")]
        action = _action_for(annotation)
        assert action.required is False
        assert build_parser_from_function(_make_func(annotation)).parse_args([]).value == 0

    def test_append_with_nargs_raises(self) -> None:
        _assert_build_error(Annotated[list[str], Option("--tag", action="append", nargs=2)], match="nargs")

    @pytest.mark.parametrize(
        ("annotation", "omit_value"),
        [
            pytest.param(Annotated[int | None, Option("-c", action="count")], None, id="count_optional"),
            pytest.param(Annotated[list[str] | None, Option("-t", action="append")], None, id="append_optional"),
            pytest.param(Annotated[bool | None, Option("-v", action="store_true")], None, id="store_true_optional"),
            pytest.param(Annotated[bool | None, Option("-q", action="store_false")], None, id="store_false_optional"),
        ],
    )
    def test_self_defaulting_action_optional_yields_none(self, annotation, omit_value) -> None:
        assert build_parser_from_function(_make_func(annotation)).parse_args([]).value is omit_value

    @pytest.mark.parametrize(
        ("annotation", "omit_value"),
        [
            pytest.param(Annotated[bool, Option("-v", action="store_true")], False, id="store_true"),
            pytest.param(Annotated[bool, Option("-q", action="store_false")], True, id="store_false"),
        ],
    )
    def test_store_bool_action_non_optional_default(self, annotation, omit_value) -> None:
        """A non-Optional store_true/store_false still defaults to its natural absence value."""
        assert build_parser_from_function(_make_func(annotation)).parse_args([]).value is omit_value


# ---------------------------------------------------------------------------
# const= on Option (store_const / append_const), inferred from the declared type
# ---------------------------------------------------------------------------


class TestConstOption:
    def test_const_to_kwargs(self) -> None:
        assert Option("-c", const=5).to_kwargs()["const"] == 5

    def test_const_none_to_kwargs_preserved(self) -> None:
        """An explicit const=None is kept (distinct from no const given)."""
        assert Option("-c", const=None).to_kwargs()["const"] is None
        assert "const" not in Option("-c").to_kwargs()

    def test_const_on_scalar_infers_store_const(self) -> None:
        p = build_parser_from_function(_make_func(Annotated[int, Option("-v", const=2)], default=0))
        assert p.parse_args([]).value == 0
        assert p.parse_args(["-v"]).value == 2

    def test_const_on_list_infers_append_const(self) -> None:
        p = build_parser_from_function(_make_func(Annotated[list[str], Option("--tag", const="x")]))
        assert p.parse_args([]).value == []
        assert p.parse_args(["--tag", "--tag"]).value == ["x", "x"]

    def test_explicit_store_const(self) -> None:
        annotation = Annotated[int, Option("-v", action="store_const", const=2)]
        assert build_parser_from_function(_make_func(annotation, default=0)).parse_args(["-v"]).value == 2

    def test_explicit_append_const(self) -> None:
        annotation = Annotated[list[str], Option("--tag", action="append_const", const="x")]
        assert build_parser_from_function(_make_func(annotation)).parse_args(["--tag"]).value == ["x"]

    def test_store_const_optional_absent_is_none(self) -> None:
        p = build_parser_from_function(_make_func(Annotated[str | None, Option("-m", const="fast")], default=None))
        assert p.parse_args([]).value is None
        assert p.parse_args(["-m"]).value == "fast"

    def test_const_enum_member_stored_as_member(self) -> None:
        class Color(enum.Enum):
            RED = "red"
            GREEN = "green"

        annotation = Annotated[Color | None, Option("-c", const=Color.RED)]
        assert build_parser_from_function(_make_func(annotation, default=None)).parse_args(["-c"]).value is Color.RED

    @pytest.mark.parametrize(
        ("annotation", "default", "expected"),
        [
            # const matching the declared (non-str) scalar type is accepted and stored verbatim.
            pytest.param(Annotated[float, Option("-x", const=1.5)], 0.0, 1.5, id="float_const"),
            pytest.param(Annotated[float, Option("-x", const=5)], 0.0, 5, id="float_const_int_ok"),
            pytest.param(
                Annotated[decimal.Decimal, Option("-x", const=decimal.Decimal("1.5"))],
                decimal.Decimal(0),
                decimal.Decimal("1.5"),
                id="decimal_const",
            ),
            pytest.param(Annotated[Path, Option("-x", const=Path("/tmp"))], Path("."), Path("/tmp"), id="path_const"),
        ],
    )
    def test_const_matching_scalar_type_accepted(self, annotation, default, expected) -> None:
        p = build_parser_from_function(_make_func(annotation, default=default))
        assert p.parse_args(["-x"]).value == expected

    def test_path_store_const_drops_inferred_completer(self) -> None:
        """A Path const infers store_const (a zero-arg action); the inferred path completer must be
        dropped, else argparse rejects a completer on an action that takes no value."""
        p = build_parser_from_function(_make_func(Annotated[Path, Option("-x", const=Path("/tmp"))], default=Path(".")))
        assert p.parse_args([]).value == Path(".")
        assert p.parse_args(["-x"]).value == Path("/tmp")

    def test_path_append_const_drops_inferred_completer(self) -> None:
        """append_const on list[Path] is also a zero-arg action; its inferred completer is dropped too."""
        p = build_parser_from_function(
            _make_func(Annotated[list[Path], Option("-x", action="append_const", const=Path("/tmp"))])
        )
        assert p.parse_args(["-x", "-x"]).value == [Path("/tmp"), Path("/tmp")]

    # --- error cases ---

    @pytest.mark.parametrize(
        ("annotation", "default", "match"),
        [
            pytest.param(Annotated[int, Option("-n", const="notanint")], 0, "const", id="type_mismatch_scalar"),
            pytest.param(Annotated[Literal["a", "b"], Option("-m", const="c")], "a", "const", id="not_a_literal_member"),
            pytest.param(Annotated[float, Option("-x", const="s")], 0.0, "const", id="type_mismatch_float"),
            pytest.param(Annotated[float, Option("-x", const=True)], 0.0, "const", id="float_const_rejects_bool"),
            pytest.param(
                Annotated[decimal.Decimal, Option("-x", const=5)], decimal.Decimal(0), "const", id="type_mismatch_decimal"
            ),
            pytest.param(Annotated[Path, Option("-x", const="/tmp")], Path("."), "const", id="type_mismatch_path"),
            pytest.param(
                Annotated[list[str], Option("-x", action="store_const", const="v")],
                _MISSING,
                "'list' is a collection",
                id="store_const_on_list",
            ),
            pytest.param(
                Annotated[str, Option("-x", action="append_const", const="v")],
                "",
                "'str' is not a list",
                id="append_const_on_scalar",
            ),
            pytest.param(Annotated[str, Option("-x", action="store_const")], "", "const", id="action_without_const"),
            pytest.param(Annotated[int, Option("-x", action="count", const=2)], 0, "const", id="incompatible_action"),
            pytest.param(Annotated[set[str] | None, Option("-x", const="v")], None, "'set' is not a list", id="const_on_set"),
            pytest.param(Annotated[int, Option("-x", const=5)], _MISSING, "default", id="non_optional_no_default"),
        ],
    )
    def test_const_error(self, annotation, default, match) -> None:
        _assert_build_error(annotation, default=default, match=match)


class TestNargsOptionalConst:
    """A scalar Option with an explicit nargs + const is argparse's optional-value-with-fallback idiom.

    It must NOT collapse to a value-less store_const (which would drop the explicit nargs and the type
    converter); it keeps the ``store`` action so absent -> default, bare flag -> const, flag VALUE -> value.
    """

    def test_str_optional_nargs_const_three_way(self) -> None:
        annotation = Annotated[str | None, Option("--log", nargs="?", const="CONSOLE")]
        p = build_parser_from_function(_make_func(annotation, name="log", default="OFF"))
        act = next(a for a in p._actions if a.dest == "log")
        assert isinstance(act, argparse._StoreAction)  # not _StoreConstAction
        assert act.nargs == "?"
        assert act.const == "CONSOLE"
        assert p.parse_args([]).log == "OFF"  # absent -> default
        assert p.parse_args(["--log"]).log == "CONSOLE"  # bare flag -> const
        assert p.parse_args(["--log", "FILE"]).log == "FILE"  # flag VALUE -> value

    def test_int_optional_nargs_const_converts_supplied_value(self) -> None:
        """The supplied VALUE still runs through the inferred converter; the const is stored verbatim."""
        annotation = Annotated[int | None, Option("--n", nargs="?", const=99)]
        p = build_parser_from_function(_make_func(annotation, name="n", default=0))
        assert p.parse_args([]).n == 0
        assert p.parse_args(["--n"]).n == 99
        assert p.parse_args(["--n", "7"]).n == 7  # type=int applied to the value

    def test_nargs_const_still_validates_const_type(self) -> None:
        """const must still match the declared type even on the nargs='?' path (stored verbatim)."""
        _assert_build_error(Annotated[int, Option("--n", nargs="?", const="notint")], name="n", default=0, match="const")

    def test_scalar_const_without_nargs_still_store_const(self) -> None:
        """Regression guard: const alone (no nargs) keeps inferring the value-less store_const."""
        p = build_parser_from_function(_make_func(Annotated[str, Option("--log", const="X")], name="log", default="off"))
        act = next(a for a in p._actions if a.dest == "log")
        assert isinstance(act, argparse._StoreConstAction)
        assert p.parse_args(["--log"]).log == "X"
        with pytest.raises(SystemExit):
            p.parse_args(["--log", "Y"])  # value-less action rejects a supplied value


class TestZeroArgActionRejectsUserCompletion:
    """A user-supplied completer/choices_provider on a value-less action has nothing to complete.

    Raw cmd2 raises in this case, so @with_annotated must fail loud rather than silently dropping the
    user's request. A *type-inferred* completer (e.g. Path's) is still dropped silently -- only an
    explicit one is rejected.
    """

    def _provider(self) -> list[str]:
        return ["a", "b"]

    @pytest.mark.parametrize("action", ["store_true", "store_false"])
    def test_bool_flag_action_rejects_user_completer(self, action) -> None:
        annotation = Annotated[bool, Option("--flag", action=action, completer=cmd2.Cmd.path_complete)]
        _assert_build_error(annotation, name="flag", default=False, match="cannot be used with action")

    def test_count_action_rejects_user_choices_provider(self) -> None:
        annotation = Annotated[
            int, Option("-v", action="count", choices_provider=TestZeroArgActionRejectsUserCompletion._provider)
        ]
        _assert_build_error(annotation, name="v", default=0, match="cannot be used with action")

    def test_store_const_rejects_user_completer(self) -> None:
        annotation = Annotated[str, Option("-m", action="store_const", const="x", completer=cmd2.Cmd.path_complete)]
        _assert_build_error(annotation, name="m", default="off", match="cannot be used with action")

    def test_append_const_rejects_user_choices_provider(self) -> None:
        annotation = Annotated[
            list[str],
            Option(
                "--tag", action="append_const", const="x", choices_provider=TestZeroArgActionRejectsUserCompletion._provider
            ),
        ]
        _assert_build_error(annotation, name="tag", match="cannot be used with action")

    def test_value_action_keeps_user_completer(self) -> None:
        """Control: a value-consuming option still accepts a user completer (not a zero-arg action)."""
        annotation = Annotated[str, Option("--path", completer=cmd2.Cmd.path_complete)]
        p = build_parser_from_function(_make_func(annotation, name="path", default=""))
        act = next(a for a in p._actions if a.dest == "path")
        assert act.get_completer() is cmd2.Cmd.path_complete


class TestConstArgumentRejected:
    def test_argument_const_raises(self) -> None:
        _assert_build_error(Annotated[str, Argument(const="x")], match="const")

    def test_positional_const_via_no_metadata_path(self) -> None:
        """A const on a parameter that resolves to a positional is rejected, not silently ignored."""

        def do_x(self, name: Annotated[str, Argument(const="x")], other: str = "y") -> None: ...

        with pytest.raises(TypeError, match="const"):
            build_parser_from_function(do_x)


# ---------------------------------------------------------------------------
# Custom ``argparse.Action`` subclasses pass through to ``add_argument``
# ---------------------------------------------------------------------------


class _UpperAction(argparse.Action):
    """Test action: store the upper-case value."""

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        ns: argparse.Namespace,
        values: Any,
        _option_string: str | None = None,
    ) -> None:
        setattr(ns, self.dest, values.upper() if isinstance(values, str) else values)


class _FlagAction(argparse.Action):
    """Test action: a presence-flag that takes no command-line value."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(nargs=0, **kwargs)

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        ns: argparse.Namespace,
        _values: Any,
        _option_string: str | None = None,
    ) -> None:
        setattr(ns, self.dest, True)


class _ListAction(argparse.Action):
    """Test action: store values as a plain list (no container_factory wrap)."""

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        ns: argparse.Namespace,
        values: Any,
        _option_string: str | None = None,
    ) -> None:
        setattr(ns, self.dest, list(values))


class _ConstAction(argparse.Action):
    """Test action: store ``self.const`` on presence."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(nargs=0, **kwargs)

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        ns: argparse.Namespace,
        _values: Any,
        _option_string: str | None = None,
    ) -> None:
        setattr(ns, self.dest, self.const)


class TestCustomActionClass:
    def test_scalar_class_action_passes_through(self) -> None:
        """A class action runs verbatim; the type-inferred passthrough doesn't get in the way."""

        def f(self, name: Annotated[str, Option("--name", action=_UpperAction)] = "") -> None: ...

        parser = build_parser_from_function(f)
        assert parser.parse_args(["--name", "hi"]).name == "HI"

    def test_class_action_overrides_inferred_boolean_optional(self) -> None:
        """A class action on a bool option replaces the inferred ``BooleanOptionalAction``."""

        def f(self, loud: Annotated[bool, Option("--loud", action=_FlagAction)] = False) -> None: ...

        parser = build_parser_from_function(f)
        assert parser.parse_args(["--loud"]).loud is True

    def test_class_action_on_list_drops_container_factory(self) -> None:
        """A class action on ``list[T]`` doesn't receive the casting action's ``container_factory``."""

        def f(self, xs: Annotated[list[str], Option("--xs", action=_ListAction, nargs="+")] = ()) -> None: ...

        parser = build_parser_from_function(f)
        assert parser.parse_args(["--xs", "a", "b"]).xs == ["a", "b"]

    def test_class_action_with_const_skips_type_check(self) -> None:
        """``const`` paired with a class action is not validated against the declared type."""
        sentinel = object()

        def f(self, mode: Annotated[str, Option("-m", action=_ConstAction, const=sentinel)] = "x") -> None: ...

        parser = build_parser_from_function(f)
        assert parser.parse_args(["-m"]).mode is sentinel

    def test_class_action_uses_inferred_converter_on_scalar(self) -> None:
        """The inferred ``type=int`` reaches the class action so values still coerce."""

        class CaptureAction(argparse.Action):
            def __call__(self, _p: Any, ns: Any, values: Any, _o: str | None = None) -> None:
                setattr(ns, self.dest, ("seen", values))

        def f(self, n: Annotated[int, Option("-n", action=CaptureAction)] = 0) -> None: ...

        parser = build_parser_from_function(f)
        assert parser.parse_args(["-n", "5"]).n == ("seen", 5)

    def test_unknown_string_action_still_rejected(self) -> None:
        """A typo in an action string is still caught -- only class actions are exempt."""
        _assert_build_error(Annotated[str, Option("-x", action="frobnicate")], match="not supported")


# ---------------------------------------------------------------------------
# ``extra_kwargs`` rejects argparse kwargs that the decorator derives elsewhere
# ---------------------------------------------------------------------------


class TestReservedExtraKwargs:
    @pytest.mark.parametrize("kw", ["type", "dest", "action", "required"])
    def test_argument_rejects_reserved_kwarg(self, kw: str) -> None:
        with pytest.raises(TypeError, match=kw):
            Argument(**{kw: "x"})

    @pytest.mark.parametrize("kw", ["type", "dest"])
    def test_option_rejects_reserved_kwarg(self, kw: str) -> None:
        with pytest.raises(TypeError, match=kw):
            Option("--x", **{kw: "x"})

    def test_option_keeps_named_action_and_required(self) -> None:
        """``action=`` and ``required=`` are named parameters of ``Option`` and must still work."""
        opt = Option("--x", action="store_true", required=True)
        assert opt.action == "store_true"
        assert opt.required is True

    def test_error_message_includes_remediation_hint(self) -> None:
        """The error names the offending kwarg and points at the signature-derived source."""
        with pytest.raises(TypeError) as excinfo:
            Option("--x", type=int)
        msg = str(excinfo.value)
        assert "type" in msg
        assert "annotation" in msg

    def test_unknown_registered_kwarg_still_passes_through(self) -> None:
        """A user-registered custom add_argument kwarg still flows through ``extra_kwargs``."""
        # The custom parameter ``annotated_custom_attr`` is registered at module import.
        action = _action_for(Annotated[str, Argument(annotated_custom_attr="value")])
        assert action.get_annotated_custom_attr() == "value"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# ``default=`` as a metadata kwarg: equivalent to a signature default, with conflict and
# SUPPRESS rejected.
# ---------------------------------------------------------------------------


class TestMetadataDefault:
    def test_option_metadata_default_equivalent_to_signature_default(self) -> None:
        """``Option(default=v)`` (no sig default) behaves the same as ``Option() = v``."""

        def f_meta(self, name: Annotated[str, Option("--name", default="HI")]) -> None: ...
        def f_sig(self, name: Annotated[str, Option("--name")] = "HI") -> None: ...

        p_meta = build_parser_from_function(f_meta)
        p_sig = build_parser_from_function(f_sig)
        assert p_meta.parse_args([]).name == p_sig.parse_args([]).name == "HI"
        assert p_meta.parse_args(["--name", "X"]).name == p_sig.parse_args(["--name", "X"]).name == "X"

    def test_argument_metadata_default_equivalent_to_signature_default(self) -> None:
        """``Argument(default=v)`` (no sig default) behaves the same as ``Argument() = v``."""

        def f_meta(self, name: Annotated[str, Argument(default="POS")]) -> None: ...
        def f_sig(self, name: Annotated[str, Argument()] = "POS") -> None: ...

        p_meta = build_parser_from_function(f_meta)
        p_sig = build_parser_from_function(f_sig)
        assert p_meta.parse_args([]).name == p_sig.parse_args([]).name == "POS"
        assert p_meta.parse_args(["X"]).name == p_sig.parse_args(["X"]).name == "X"

    def test_metadata_default_makes_option_not_required(self) -> None:
        """A metadata default removes ``required`` -- same as a signature default."""
        action = _action_for(Annotated[str, Option("--x", default="HI")])
        assert action.required is False

    def test_metadata_default_makes_positional_nargs_optional(self) -> None:
        """A metadata default on a positional sets ``nargs='?'`` -- same as a signature default."""
        action = _action_for(Annotated[str, Argument(default="HI")])
        assert action.nargs == "?"

    def test_default_conflict_signature_and_metadata_raises(self) -> None:
        """Both a signature default and a metadata default is a conflict."""

        def f(self, name: Annotated[str, Option("--name", default="HI")] = "hello") -> None: ...

        with pytest.raises(TypeError, match="default in both"):
            build_parser_from_function(f)

    def test_default_conflict_message_names_both_values(self) -> None:
        """The conflict error message includes both candidate values."""

        def f(self, name: Annotated[str, Option("--name", default="meta")] = "sig") -> None: ...

        with pytest.raises(TypeError) as excinfo:
            build_parser_from_function(f)
        msg = str(excinfo.value)
        assert "'sig'" in msg
        assert "'meta'" in msg

    def test_argparse_suppress_metadata_default_rejected(self) -> None:
        """``default=argparse.SUPPRESS`` in metadata is rejected (kwarg would vanish)."""

        def f(self, name: Annotated[str, Option("--name", default=argparse.SUPPRESS)]) -> None: ...

        with pytest.raises(TypeError, match="SUPPRESS"):
            build_parser_from_function(f)

    def test_argparse_suppress_signature_default_rejected(self) -> None:
        """``= argparse.SUPPRESS`` in the signature is rejected as well."""

        def f(self, name: str = argparse.SUPPRESS) -> None: ...

        with pytest.raises(TypeError, match="SUPPRESS"):
            build_parser_from_function(f)

    def test_metadata_default_none_on_non_optional_rejected(self) -> None:
        """The 'None default on non-Optional' rule applies to a metadata default as well."""
        _assert_build_error(Annotated[str, Option("--x", default=None)], match="None")

    def test_metadata_default_none_on_optional_accepted(self) -> None:
        """``default=None`` on a ``T | None`` annotation is fine (consistent with signature defaults)."""
        action = _action_for(Annotated[str | None, Option("--x", default=None)])
        assert action.default is None
        assert action.required is False

    def test_metadata_default_with_explicit_action(self) -> None:
        """A metadata default flows through to the action layer (here: store_const)."""
        annotation = Annotated[int, Option("-v", action="store_const", const=2, default=0)]
        parser = build_parser_from_function(_make_func(annotation))
        assert parser.parse_args([]).value == 0
        assert parser.parse_args(["-v"]).value == 2


# ---------------------------------------------------------------------------
# A variable-arity positional must be the last positional
# ---------------------------------------------------------------------------


class TestPositionalOrdering:
    def test_optional_positional_before_required_raises(self) -> None:
        def do_x(self, a: str | None, b: str) -> None: ...

        with pytest.raises(TypeError, match="variable arity"):
            build_parser_from_function(do_x)

    def test_list_positional_before_positional_raises(self) -> None:
        def do_x(self, items: list[str], b: str) -> None: ...

        with pytest.raises(TypeError, match="variable arity"):
            build_parser_from_function(do_x)

    def test_required_positional_before_star_args_builds(self) -> None:
        def do_x(self, a: str, *args: str) -> None: ...

        parser = build_parser_from_function(do_x)
        ns = parser.parse_args(["one", "two", "three"])
        assert ns.a == "one"
        assert ns.args == ("two", "three")

    def test_ranged_nargs_collection_before_positional_raises(self) -> None:
        def do_x(self, items: Annotated[list[str], Argument(nargs=(1, 3))], b: str) -> None: ...

        with pytest.raises(TypeError, match="variable arity"):
            build_parser_from_function(do_x)


# ---------------------------------------------------------------------------
# Ranged nargs (min, max) tuples
# ---------------------------------------------------------------------------


class TestRangedNargs:
    def test_ranged_nargs_on_scalar_raises(self) -> None:
        _assert_build_error(Annotated[str, Argument(nargs=(2, 4))], match="not a collection type")

    def test_ranged_nargs_on_list_builds(self) -> None:
        parser = build_parser_from_function(_make_func(Annotated[list[str], Argument(nargs=(2, 4))]))
        assert parser.parse_args(["a", "b", "c"]).value == ["a", "b", "c"]

    def test_ranged_nargs_zero_one_on_scalar_builds(self) -> None:
        # cmd2 collapses the (0, 1) range to OPTIONAL ('?'), which yields a single optional value
        # (not a list), so it is allowed on a scalar, like nargs='?'.  Absent -> None.
        parser = build_parser_from_function(_make_func(Annotated[str, Argument(nargs=(0, 1))]))
        assert parser.parse_args(["x"]).value == "x"
        assert parser.parse_args([]).value is None

    def test_optional_scalar_positional_nargs_question_builds(self) -> None:
        # An explicit nargs='?' on a scalar positional is the standard argparse optional-positional;
        # it is allowed (absent -> None). Developers wanting type-safe absence use 'T | None'.
        parser = build_parser_from_function(_make_func(Annotated[int, Argument(nargs="?")]))
        assert parser.parse_args(["5"]).value == 5
        assert parser.parse_args([]).value is None


# ---------------------------------------------------------------------------
# Subcommands group configuration (required / metavar / title / description)
# ---------------------------------------------------------------------------


class TestSubcommandGroupConfig:
    @staticmethod
    def _base_parser(**subcommand_kwargs):
        @with_annotated(base_command=True, **subcommand_kwargs)
        def do_root(self, cmd2_subcommand_func) -> None: ...

        builder = getattr(do_root, constants.ARGPARSE_COMMAND_ATTR_SPEC).parser_source
        return builder()

    @staticmethod
    def _subparsers_action(parser):
        return next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))

    def test_defaults_required_with_subcommand_metavar(self) -> None:
        action = self._subparsers_action(self._base_parser())
        assert action.required is True
        assert action.metavar == "SUBCOMMAND"

    def test_subcommand_required_false(self) -> None:
        action = self._subparsers_action(self._base_parser(subcommand_required=False))
        assert action.required is False

    def test_subcommand_metavar_override(self) -> None:
        action = self._subparsers_action(self._base_parser(subcommand_metavar="CMD"))
        assert action.metavar == "CMD"

    def test_subcommand_title_and_description(self) -> None:
        parser = self._base_parser(subcommand_title="Commands", subcommand_description="pick one")
        group = next((g for g in parser._action_groups if g.title == "Commands"), None)
        assert group is not None
        assert group.description == "pick one"


# ---------------------------------------------------------------------------
# Rich objects are accepted for description / epilog (HelpContent)
# ---------------------------------------------------------------------------


class TestRichHelpContent:
    def test_rich_description_and_epilog_accepted(self) -> None:
        from rich.text import Text

        desc = Text("a rich description")
        parser = build_parser_from_function(_make_func(str), description=desc, epilog=Text("epilog"))
        assert parser.description is desc


# ---------------------------------------------------------------------------
# Docstring auto-extraction for parser description
# ---------------------------------------------------------------------------


class TestDocstringDescription:
    """The first paragraph of ``func.__doc__`` fills ``description`` when none is given."""

    def test_first_paragraph_used_when_no_description(self) -> None:
        def func(self, name: str) -> None:
            """Summary line for the command.

            More detail here that should not appear in description.

            :param name: a name
            """

        parser = build_parser_from_function(func)
        assert parser.description == "Summary line for the command."

    def test_multiline_first_paragraph_preserved(self) -> None:
        def func(self, name: str) -> None:
            """First line continues
            onto the second line without a blank gap.

            Detail paragraph below the blank line is dropped.
            """

        parser = build_parser_from_function(func)
        assert parser.description == "First line continues\nonto the second line without a blank gap."

    def test_explicit_description_overrides_docstring(self) -> None:
        def func(self, name: str) -> None:
            """Auto summary."""

        parser = build_parser_from_function(func, description="explicit")
        assert parser.description == "explicit"

    def test_no_docstring_means_no_description(self) -> None:
        def func(self, name: str) -> None: ...

        parser = build_parser_from_function(func)
        assert parser.description is None

    def test_empty_docstring_means_no_description(self) -> None:
        def func(self, name: str) -> None:
            """ """

        parser = build_parser_from_function(func)
        assert parser.description is None

    def test_field_directive_without_blank_line_does_not_leak(self) -> None:
        """A ``:param:`` directly under the summary (no blank line) is stripped, not leaked."""

        def func(self, name: str) -> None:
            """Summary line.
            :param name: should not leak into the description
            """

        parser = build_parser_from_function(func)
        assert parser.description == "Summary line."

    def test_decorator_uses_docstring(self) -> None:
        @with_annotated
        def do_run(self, name: str) -> None:
            """Run the thing.

            Extra detail.
            """

        builder = getattr(do_run, constants.ARGPARSE_COMMAND_ATTR_SPEC).parser_source
        assert builder().description == "Run the thing."

    def test_subcommand_uses_docstring(self) -> None:
        @with_annotated(subcommand_to="team")
        def team_add(self, name: str) -> None:
            """Add a member to the team."""

        spec = getattr(team_add, constants.SUBCOMMAND_ATTR_SPEC)
        assert spec.parser_source().description == "Add a member to the team."


# ---------------------------------------------------------------------------
# Group(required=...) for mutually exclusive groups
# ---------------------------------------------------------------------------


class TestMutuallyExclusiveGroupRequired:
    """``Group(required=True)`` reaches ``add_mutually_exclusive_group(required=True)``."""

    def test_required_mutex_group_flag_set(self) -> None:
        def func(self, verbose: bool = False, quiet: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "quiet", required=True),))
        assert parser._mutually_exclusive_groups[0].required is True

    def test_default_mutex_group_not_required(self) -> None:
        def func(self, verbose: bool = False, quiet: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "quiet"),))
        assert parser._mutually_exclusive_groups[0].required is False

    def test_required_mutex_group_argparse_enforces(self) -> None:
        def func(self, verbose: bool = False, quiet: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(Group("verbose", "quiet", required=True),))
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_required_on_plain_group_rejected(self) -> None:
        """``required=True`` is only valid in mutex groups; argparse doesn't support it elsewhere."""

        def func(self, host: str, port: int = 22) -> None: ...

        with pytest.raises(ValueError, match="only valid in mutually_exclusive_groups"):
            build_parser_from_function(func, groups=(Group("host", "port", required=True),))


# ---------------------------------------------------------------------------
# Parser-level kwargs: prog / usage / parents / argument_default
# ---------------------------------------------------------------------------


class TestParserLevelKwargs:
    """Forward ``prog``, ``usage``, ``parents``, ``argument_default`` to the parser ctor."""

    def test_prog_passthrough(self) -> None:
        parser = build_parser_from_function(_make_func(str), prog="myprog")
        assert parser.prog == "myprog"

    def test_usage_passthrough(self) -> None:
        parser = build_parser_from_function(_make_func(str), usage="usage: do stuff")
        assert parser.usage == "usage: do stuff"

    def test_parents_passthrough(self) -> None:
        """argparse ``parents=`` copies argument actions from each parent into the new parser."""
        parent = argparse.ArgumentParser(add_help=False)
        parent.add_argument("--shared", help="from parent")

        parser = build_parser_from_function(_make_func(str), parents=[parent])
        dests = {a.dest for a in parser._actions}
        assert "shared" in dests

    def test_argument_default_passthrough(self) -> None:
        sentinel = "DEFAULT_FROM_PARSER"
        parser = build_parser_from_function(_make_func(str), argument_default=sentinel)
        assert parser.argument_default == sentinel

    def test_decorator_passes_parser_kwargs(self) -> None:
        @with_annotated(prog="myprog", usage="usage line")
        def do_run(self, name: str) -> None: ...

        builder = getattr(do_run, constants.ARGPARSE_COMMAND_ATTR_SPEC).parser_source
        parser = builder()
        assert parser.prog == "myprog"
        assert parser.usage == "usage line"

    def test_prog_rejected_with_subcommand_to(self) -> None:
        """cmd2's subcommand machinery rewrites ``prog`` from the parent hierarchy."""
        with pytest.raises(TypeError, match=r"prog .* not supported with subcommand_to"):

            @with_annotated(subcommand_to="team", prog="something")
            def team_add(self, name: str) -> None: ...

    def test_usage_allowed_on_subcommand(self) -> None:
        """``usage`` doesn't conflict with subcommand prog rewriting."""

        @with_annotated(subcommand_to="team", usage="team add NAME")
        def team_add(self, name: str) -> None: ...

        spec = getattr(team_add, constants.SUBCOMMAND_ATTR_SPEC)
        assert spec.parser_source().usage == "team add NAME"

    def test_parents_allowed_on_subcommand(self) -> None:
        parent = argparse.ArgumentParser(add_help=False)
        parent.add_argument("--shared")

        @with_annotated(subcommand_to="team", parents=[parent])
        def team_add(self, name: str) -> None: ...

        spec = getattr(team_add, constants.SUBCOMMAND_ATTR_SPEC)
        dests = {a.dest for a in spec.parser_source()._actions}
        assert "shared" in dests


# ---------------------------------------------------------------------------
# Less-common parser-level kwargs: prefix_chars / fromfile_prefix_chars /
# conflict_handler / add_help / allow_abbrev / exit_on_error
# ---------------------------------------------------------------------------


class TestParserLowLevelKwargs:
    """Forward the remaining argparse parser ctor kwargs."""

    def test_prefix_chars_passthrough(self) -> None:
        """A non-default ``prefix_chars`` propagates so ``Option('+flag')`` would be legal."""
        parser = build_parser_from_function(_make_func(str), prefix_chars="+-")
        assert parser.prefix_chars == "+-"

    def test_fromfile_prefix_chars_enables_argument_files(self) -> None:
        """argparse loads tokens from a file when an arg starts with the prefix char."""
        import tempfile

        def func(self, name: str) -> None: ...

        parser = build_parser_from_function(func, fromfile_prefix_chars="@")
        with tempfile.NamedTemporaryFile("w", suffix=".args", delete=False) as fh:
            fh.write("alice\n")
            path = fh.name
        try:
            ns = parser.parse_args([f"@{path}"])
            assert ns.name == "alice"
        finally:
            Path(path).unlink()

    def test_conflict_handler_resolve_lets_parents_be_overridden(self) -> None:
        """``conflict_handler='resolve'`` allows a parent's ``--flag`` to be redefined."""
        parent = argparse.ArgumentParser(add_help=False)
        parent.add_argument("--mode", default="parent")

        def func(self, mode: str = "child") -> None: ...

        parser = build_parser_from_function(func, parents=[parent], conflict_handler="resolve")
        ns = parser.parse_args([])
        # The locally-declared --mode wins after the resolve.
        assert ns.mode == "child"

    def test_add_help_false_drops_help_action(self) -> None:
        parser = build_parser_from_function(_make_func(str), add_help=False)
        assert all(not isinstance(a, argparse._HelpAction) for a in parser._actions)

    def test_allow_abbrev_false_rejects_prefix_match(self) -> None:
        """With abbreviations off, ``--verb`` no longer matches ``--verbose``."""

        def func(self, verbose: bool = False) -> None: ...

        parser = build_parser_from_function(func, allow_abbrev=False)
        with pytest.raises(SystemExit):
            parser.parse_args(["--verb"])

    def test_exit_on_error_false_raises_argument_error(self) -> None:
        """``exit_on_error=False`` surfaces parse failures as exceptions instead of sys.exit."""

        def func(self, count: int) -> None: ...

        parser = build_parser_from_function(func, exit_on_error=False)
        with pytest.raises(argparse.ArgumentError):
            parser.parse_args(["not-an-int"])

    def test_decorator_threads_all_low_level_kwargs(self) -> None:
        """End-to-end: each kwarg lands on the parser when set on the decorator."""

        @with_annotated(
            prefix_chars="+-",
            conflict_handler="resolve",
            add_help=False,
            allow_abbrev=False,
            exit_on_error=False,
            fromfile_prefix_chars="@",
        )
        def do_run(self, name: str) -> None: ...

        builder = getattr(do_run, constants.ARGPARSE_COMMAND_ATTR_SPEC).parser_source
        parser = builder()
        assert parser.prefix_chars == "+-"
        assert parser.fromfile_prefix_chars == "@"
        assert parser.conflict_handler == "resolve"
        assert all(not isinstance(a, argparse._HelpAction) for a in parser._actions)
        assert parser.allow_abbrev is False
        assert parser.exit_on_error is False


class TestExplicitChoicesValueSpace:
    """Explicit ``choices=`` are reconciled with the inferred type converter and completer."""

    def test_string_choices_converted_to_declared_type(self) -> None:
        """choices=['1','2'] on an int parameter match after argparse runs the int converter."""
        p = build_parser_from_function(_make_func(Annotated[int, Option("--x", choices=["1", "2"])], default=1, name="x"))
        action = next(a for a in p._actions if a.dest == "x")
        assert action.choices == [1, 2]
        assert p.parse_args(["--x", "1"]).x == 1
        with pytest.raises(SystemExit):
            p.parse_args(["--x", "3"])

    def test_already_typed_choices_left_untouched(self) -> None:
        p = build_parser_from_function(_make_func(Annotated[int, Option("--x", choices=[1, 2])], default=1, name="x"))
        action = next(a for a in p._actions if a.dest == "x")
        assert action.choices == [1, 2]

    def test_choice_invalid_for_type_is_build_error(self) -> None:
        _assert_build_error(Annotated[int, Option("--x", choices=["1", "nope"])], default=1, match="not a valid")

    def test_explicit_choices_kept_over_inferred_path_completer(self) -> None:
        """An explicit choices= on a Path is retained (and the inferred path completer dropped)."""
        p = build_parser_from_function(_make_func(Annotated[Path, Argument(choices=[Path("/a"), Path("/b")])], name="p"))
        action = next(a for a in p._actions if a.dest == "p")
        assert action.choices == [Path("/a"), Path("/b")]
        assert getattr(action, "completer", None) is None
        assert p.parse_args(["/a"]).p == Path("/a")
        with pytest.raises(SystemExit):
            p.parse_args(["/c"])

    def test_user_completer_still_overrides_choices(self) -> None:
        """A user-supplied completer continues to drive completion in place of static choices."""

        def completer(self, *args: Any) -> list[str]:
            return ["x"]

        p = build_parser_from_function(
            _make_func(Annotated[str, Option("--x", choices=["a", "b"], completer=completer)], default="a", name="x")
        )
        action = next(a for a in p._actions if a.dest == "x")
        assert action.choices is None


class TestStrConstValidation:
    """A const on a str parameter must itself be a str (it is stored verbatim, not converted)."""

    def test_non_str_const_on_str_rejected(self) -> None:
        _assert_build_error(Annotated[str, Option("--x", const=123)], default="a", match="does not match")

    def test_str_const_on_str_accepted(self) -> None:
        p = build_parser_from_function(_make_func(Annotated[str, Option("--x", const="fast")], default="slow", name="x"))
        assert p.parse_args(["--x"]).x == "fast"

    def test_const_on_untyped_param_not_validated(self) -> None:
        """Any/object/unannotated are genuinely untyped, so a const of any type is accepted."""
        p = build_parser_from_function(_make_func(Annotated[Any, Option("--x", const=123)], default=None, name="x"))
        assert p.parse_args(["--x"]).x == 123


class TestArgumentDefaultSuppressGuard:
    """``argument_default=argparse.SUPPRESS`` is rejected outright by @with_annotated.

    SUPPRESS drops an absent argument from the parsed namespace, but @with_annotated builds the call
    from the signature, so every declared parameter is expected at invocation -- a vanished argument
    can never be valid.  The rejection is unconditional (it never inspects the signature), so one
    direct-build case and one subcommand-registration case cover it.
    """

    def test_suppress_rejected(self) -> None:
        def do_t(self, a: int, b: str = "x"): ...

        with pytest.raises(TypeError, match="SUPPRESS"):
            build_parser_from_function(do_t, argument_default=argparse.SUPPRESS)

    def test_suppress_rejected_in_subcommand(self) -> None:
        """The subcommand path shares the same builder, so the rejection fires at registration too."""

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_calc(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="calc", argument_default=argparse.SUPPRESS, help="sum values")
            def calc_sum(self, value: str = "x") -> None: ...

        with pytest.raises(TypeError, match="SUPPRESS"):
            App()


class TestHelpKwargReserved:
    """Raw ``help=`` is rejected so it cannot silently shadow the mapped ``help_text=``."""

    def test_raw_help_rejected(self) -> None:
        with pytest.raises(TypeError, match="help_text"):
            Option("--x", help="raw")

    def test_help_text_still_works(self) -> None:
        action = _action_for(Annotated[str, Option("--x", help_text="mapped")], default="a")
        assert action.help == "mapped"


class TestEnumAcceptsNameAndValue:
    """Enum parameters accept member values AND names (documented behavior, locked here)."""

    def test_enum_accepts_both_name_and_value(self) -> None:
        class Color(enum.Enum):
            RED = "r"
            GREEN = "g"

        p = build_parser_from_function(_make_func(Color, name="c"))
        assert p.parse_args(["r"]).c is Color.RED
        assert p.parse_args(["RED"]).c is Color.RED


class _AliasColor(enum.Enum):
    """An enum that maps extra command-line spellings to members via the standard ``_missing_`` hook."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"

    @classmethod
    def _missing_(cls, value: object) -> "_AliasColor | None":
        return {"auto": cls.RED, "default": cls.RED}.get(str(value).lower())


class TestAllowUnknownEntry:
    """``allow_unknown_entry=True`` lets an Enum's ``_missing_`` hook resolve otherwise-unknown tokens."""

    def test_missing_not_consulted_without_flag(self) -> None:
        """By default the converter ignores ``_missing_`` -- an alias is rejected (current behavior)."""
        parser = build_parser_from_function(_make_func(_AliasColor, name="c"))
        with pytest.raises(SystemExit):
            parser.parse_args(["auto"])

    def test_flag_consults_missing(self) -> None:
        """With the flag, an unknown token is resolved through the enum's ``_missing_`` hook."""
        parser = build_parser_from_function(_make_func(Annotated[_AliasColor, Argument(allow_unknown_entry=True)], name="c"))
        assert parser.parse_args(["auto"]).c is _AliasColor.RED
        assert parser.parse_args(["default"]).c is _AliasColor.RED

    def test_flag_still_accepts_canonical_value_and_name(self) -> None:
        """Enabling the flag does not regress value or name lookup; ``_missing_`` is only a fallback."""
        parser = build_parser_from_function(_make_func(Annotated[_AliasColor, Argument(allow_unknown_entry=True)], name="c"))
        assert parser.parse_args(["red"]).c is _AliasColor.RED  # by value
        assert parser.parse_args(["GREEN"]).c is _AliasColor.GREEN  # by name

    def test_flag_preserves_intenum_value_bridge(self) -> None:
        """An IntEnum value typed as a string still resolves with the flag on (str-bridge intact)."""

        class IntColor(enum.IntEnum):
            red = 1
            green = 2

            @classmethod
            def _missing_(cls, value: object) -> "IntColor | None":
                return cls.red if str(value).lower() == "auto" else None

        parser = build_parser_from_function(_make_func(Annotated[IntColor, Argument(allow_unknown_entry=True)], name="c"))
        assert parser.parse_args(["1"]).c is IntColor.red  # int value via str-bridge
        assert parser.parse_args(["auto"]).c is IntColor.red  # _missing_

    def test_flag_unknown_without_missing_match_still_errors(self) -> None:
        """A token neither matched nor rescued by ``_missing_`` is still rejected with the choices."""
        parser = build_parser_from_function(_make_func(Annotated[_AliasColor, Argument(allow_unknown_entry=True)], name="c"))
        with pytest.raises(SystemExit):
            parser.parse_args(["bogus"])

    def test_flag_on_option(self) -> None:
        """The flag also works on an ``Option`` (keyword) parameter."""
        parser = build_parser_from_function(
            _make_func(Annotated[_AliasColor | None, Option("--c", allow_unknown_entry=True)], name="c", default=None)
        )
        assert parser.parse_args(["--c", "auto"]).c is _AliasColor.RED

    def test_flag_on_collection_element(self) -> None:
        """The flag propagates to an Enum used as a collection element."""
        parser = build_parser_from_function(
            _make_func(Annotated[list[_AliasColor], Argument(allow_unknown_entry=True)], name="cs")
        )
        assert parser.parse_args(["auto", "blue"]).cs == [_AliasColor.RED, _AliasColor.BLUE]

    def test_make_enum_type_flag_directly(self) -> None:
        """Unit-level: ``_make_enum_type`` honors ``_missing_`` only when ``allow_unknown_entry`` is set."""
        without = _make_enum_type(_AliasColor)
        with pytest.raises(argparse.ArgumentTypeError):
            without("auto")
        with_flag = _make_enum_type(_AliasColor, allow_unknown_entry=True)
        assert with_flag("auto") is _AliasColor.RED

    def test_missing_exception_propagates_not_swallowed(self) -> None:
        """A ``_missing_`` that raises is surfaced, not masked as an 'invalid choice' error."""

        class Raises(enum.Enum):
            a = "a"

            @classmethod
            def _missing_(cls, value: object) -> "Raises | None":
                raise ValueError("boom in _missing_")

        conv = _make_enum_type(Raises, allow_unknown_entry=True)
        with pytest.raises(ValueError, match="boom in _missing_"):
            conv("zzz")

    def test_flag_without_missing_handler_is_inert(self) -> None:
        """An Enum with no ``_missing_`` override inherits the default (returns None), so the flag is inert."""

        class NoHandler(enum.Enum):
            a = "a"

        parser = build_parser_from_function(_make_func(Annotated[NoHandler, Argument(allow_unknown_entry=True)], name="c"))
        assert parser.parse_args(["a"]).c is NoHandler.a  # canonical value still works
        with pytest.raises(SystemExit):
            parser.parse_args(["zzz"])  # unknown token still rejected; the flag added nothing


class _OtherColor(enum.Enum):
    """A third, disjoint Enum used to exercise multi-member unions."""

    cyan = "cyan"
    magenta = "magenta"


class _StrictColor(enum.Enum):
    """An Enum whose ``_missing_`` *raises* on an unknown token, as a strict enum typically does."""

    crimson = "crimson"

    @classmethod
    def _missing_(cls, value: object) -> "_StrictColor | None":
        raise ValueError(f"{value!r} is not a valid _StrictColor")


class TestEnumUnion:
    """A union of Enums (``EnumA | EnumB``) resolves by trying each member's converter in order."""

    @pytest.mark.parametrize(
        ("annotation", "token", "expected"),
        [
            pytest.param(_Color | _IntColor, "red", _Color.red, id="first-member-value"),
            pytest.param(_Color | _IntColor, "2", _IntColor.green, id="second-member-value"),
            pytest.param(_IntColor | _Color, "1", _IntColor.red, id="intenum-value"),
            pytest.param(_IntColor | _Color, "green", _IntColor.green, id="member-name-first-wins"),
            pytest.param(_Color | _PlainColor, "red", _Color.red, id="shared-repr-first-wins"),
            pytest.param(_PlainColor | _Color, "red", _PlainColor.RED, id="shared-repr-order-flips"),
            pytest.param(_Color | _IntColor | _OtherColor, "blue", _Color.blue, id="three-member-first"),
            pytest.param(_Color | _IntColor | _OtherColor, "2", _IntColor.green, id="three-member-middle"),
            pytest.param(_Color | _IntColor | _OtherColor, "cyan", _OtherColor.cyan, id="three-member-last"),
        ],
    )
    def test_resolution(self, annotation: Any, token: str, expected: enum.Enum) -> None:
        """A token resolves to the first union member whose converter accepts it."""
        parser = build_parser_from_function(_make_func(annotation, name="c"))
        assert parser.parse_args([token]).c is expected

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(_Color | Literal["auto"], id="literal-member"),
            pytest.param(_Color | int, id="non-enum-member"),
            pytest.param(str | int, id="plain-scalars"),
            # `... | None` is stripped and the remaining union rebuilt, so the same rule applies.
            pytest.param(_Color | int | None, id="non-enum-member-optional"),
            pytest.param(_Color | Literal["auto"] | None, id="literal-member-optional"),
        ],
    )
    def test_out_of_scope_union_rejected(self, annotation: Any) -> None:
        """Scope is Enum-only: a union with a Literal or non-Enum member is rejected as ambiguous."""
        with pytest.raises(TypeError, match="ambiguous"):
            build_parser_from_function(_make_func(annotation, name="c"))

    def test_invalid_value_rejected(self) -> None:
        """A token no member accepts is rejected at parse time."""
        parser = build_parser_from_function(_make_func(_Color | _IntColor, name="c"))
        with pytest.raises(SystemExit):
            parser.parse_args(["bogus"])

    def test_optional_union_without_default_is_optional_positional(self) -> None:
        """``A | B | None`` with no default is a positional ``nargs='?'`` yielding None when absent."""
        action = _get_param_action(_make_func(_Color | _IntColor | None, name="c"))
        assert action.option_strings == []  # positional
        assert action.nargs == "?"
        parser = build_parser_from_function(_make_func(_Color | _IntColor | None, name="c"))
        assert parser.parse_args([]).c is None
        assert parser.parse_args(["red"]).c is _Color.red

    def test_optional_union_with_default_is_option(self) -> None:
        """``A | B | None = None`` becomes a ``--flag`` option."""
        parser = build_parser_from_function(_make_func(_Color | _IntColor | None, name="c", default=None))
        assert parser.parse_args([]).c is None
        assert parser.parse_args(["--c", "blue"]).c is _Color.blue

    def test_union_as_collection_element(self) -> None:
        """A union works as a collection element type."""
        parser = build_parser_from_function(_make_func(list[_Color | _IntColor], name="cs"))
        assert parser.parse_args(["red", "2"]).cs == [_Color.red, _IntColor.green]

    def test_allow_unknown_entry_threads_into_union_members(self) -> None:
        """``allow_unknown_entry`` propagates to each member, so a member's ``_missing_`` still fires."""
        parser = build_parser_from_function(
            _make_func(Annotated[_AliasColor | _IntColor, Argument(allow_unknown_entry=True)], name="c")
        )
        assert parser.parse_args(["auto"]).c is _AliasColor.RED  # _AliasColor._missing_
        assert parser.parse_args(["2"]).c is _IntColor.green

    def test_shared_representation_choices_are_deduped(self) -> None:
        """When members share a text representation the merged choices show it once (not once per member)."""
        # _Color and _PlainColor both spell their members "red"/"green"/"blue".
        action = _get_param_action(_make_func(_Color | _PlainColor, name="c"))
        texts = [c.text if isinstance(c, CompletionItem) else str(c) for c in action.choices]
        assert texts == ["red", "green", "blue"]  # deduped, order preserved (first member wins)

    def test_member_whose_missing_raises_does_not_preempt_later_members(self) -> None:
        """A member whose ``_missing_`` *raises* declines the token; the union keeps trying later members.

        A strict Enum (one whose ``_missing_`` raises rather than returning ``None``) listed before a
        member that accepts the token must not abort the whole union -- the raise means "not mine",
        same as a clean rejection, so resolution falls through to the next member.
        """
        parser = build_parser_from_function(
            _make_func(Annotated[_StrictColor | _IntColor, Argument(allow_unknown_entry=True)], name="c")
        )
        # _StrictColor._missing_("2") raises, but _IntColor accepts "2" -- the later member still wins.
        assert parser.parse_args(["2"]).c is _IntColor.green
        # The strict member still claims its own token first.
        assert parser.parse_args(["crimson"]).c is _StrictColor.crimson

    def test_all_members_declining_reports_invalid_choice_not_member_error(self) -> None:
        """When every member declines -- even one whose ``_missing_`` raises -- the union reports invalid choice.

        The deferred member error must not surface as-is; the user sees the standard merged-choices
        rejection, raised only after all members have been tried.
        """
        converter = _get_param_action(
            _make_func(Annotated[_StrictColor | _IntColor, Argument(allow_unknown_entry=True)], name="c")
        ).type
        with pytest.raises(argparse.ArgumentTypeError, match="invalid choice"):
            converter("bogus")

    def test_union_choices_preserve_display_meta(self) -> None:
        """Merged union choices keep each member's ``display_meta`` (the per-member tab-completion hint)."""
        action = _get_param_action(_make_func(_Color | _IntColor, name="c"))
        meta = {c.text: c.display_meta for c in action.choices if isinstance(c, CompletionItem)}
        assert meta == {"red": "red", "green": "green", "blue": "blue", "1": "red", "2": "green", "3": "blue"}


# ---------------------------------------------------------------------------
# converter / preprocess metadata
# ---------------------------------------------------------------------------


def _hex(value: str) -> int:
    """Parse a hexadecimal integer (test converter)."""
    return int(value, 16)


def _csv_ints(value: str) -> set[int]:
    """Parse a comma-separated list of ints into a set (single token -> collection)."""
    return {int(piece) for piece in value.split(",")}


def _parse_iso(value: str) -> datetime.datetime:
    """Parse an ISO-8601 timestamp (test converter for an otherwise-unsupported type)."""
    return datetime.datetime.fromisoformat(value)


class TestConverter:
    """`Argument`/`Option` ``converter=`` replaces the inferred ``type=`` converter."""

    def test_converter_becomes_type(self) -> None:
        """A supplied converter is emitted as argparse ``type=``, replacing the inferred one."""
        action = _action_for(Annotated[int, Argument(converter=_hex)])
        assert action.type is _hex

    def test_converter_allows_unsupported_annotation_type(self) -> None:
        """A converter suppresses the 'unsupported scalar type' error: the annotation may be anything."""
        action = _action_for(Annotated[datetime.datetime, Argument(converter=_parse_iso)])
        assert action.type is _parse_iso

    def test_converter_parses_end_to_end(self) -> None:
        """The converter runs at parse time, producing its own value-space."""
        parser = build_parser_from_function(_make_func(Annotated[int, Argument(converter=_hex)], name="addr"))
        assert parser.parse_args(["ff"]).addr == 255

    def test_converter_drops_inferred_enum_choices(self) -> None:
        """Replacing the converter on an Enum drops the inferred choices (user owns the value-space)."""
        action = _action_for(Annotated[_Color, Argument(converter=str)])
        assert action.choices is None

    def test_converter_drops_inferred_path_completer(self) -> None:
        """Replacing the converter on a Path drops the inferred path completer."""
        action = _action_for(Annotated[Path, Argument(converter=str)])
        assert action.get_completer() is None  # type: ignore[attr-defined]

    def test_converter_applies_per_element_on_collection(self) -> None:
        """On a ``list[T]`` the converter runs per token (argparse applies ``type=`` per value)."""
        parser = build_parser_from_function(_make_func(Annotated[list[int], Option("--n", converter=_hex)], name="n"))
        assert parser.parse_args(["--n", "ff", "10"]).n == [255, 16]

    def test_converter_single_token_to_collection(self) -> None:
        """A non-collection annotation (Any) keeps a single token, so the converter may return a collection."""
        parser = build_parser_from_function(_make_func(Annotated[Any, Option("--idx", converter=_csv_ints)], name="idx"))
        assert parser.parse_args(["--idx", "1,3,5"]).idx == {1, 3, 5}

    def test_converter_runs_explicit_choices_through_itself(self) -> None:
        """Explicit ``choices`` are run through the user converter for argparse's post-conversion match."""
        action = _action_for(Annotated[int, Argument(converter=_hex, choices=["ff", "10"])])
        assert action.choices == [255, 16]

    def test_converter_allows_unsupported_collection_element(self) -> None:
        """A converter on ``list[Unsupported]`` keeps the collection shape and suppresses the element error."""
        parser = build_parser_from_function(
            _make_func(Annotated[list[datetime.datetime], Option("--ts", converter=_parse_iso)], name="ts")
        )
        parsed = parser.parse_args(["--ts", "2020-01-01", "2021-06-15"]).ts
        assert parsed == [_parse_iso("2020-01-01"), _parse_iso("2021-06-15")]

    def test_converter_allows_ambiguous_union(self) -> None:
        """A converter suppresses the 'ambiguous union' error: a multi-member union is legal."""
        parser = build_parser_from_function(_make_func(Annotated[int | str, Argument(converter=_hex)], name="addr"))
        assert parser.parse_args(["ff"]).addr == 255

    def test_converter_on_optional_single_member(self) -> None:
        """A converter legalizes ``T | None``: the optional collapses to ``T`` and the converter owns conversion."""
        parser = build_parser_from_function(
            _make_func(
                Annotated[datetime.datetime | None, Option("--until", converter=_parse_iso)],
                name="until",
                kind="kw",
                default=None,
            )
        )
        assert parser.parse_args(["--until", "2020-01-01"]).until == _parse_iso("2020-01-01")
        assert parser.parse_args([]).until is None

    def test_converter_keeps_user_completer(self) -> None:
        """``converter=`` drops the *inferred* completer, but a user-supplied ``completer=`` survives."""
        action = _action_for(Annotated[Path, Argument(converter=str, completer=cmd2.Cmd.path_complete)])
        assert action.get_completer() is cmd2.Cmd.path_complete  # type: ignore[attr-defined]

    def test_converter_rejects_invalid_explicit_choice(self) -> None:
        """A choice the user converter rejects is a build-time error (run through the converter, not the inferred type)."""
        _assert_build_error(
            Annotated[int, Argument(converter=_hex, choices=["ff", "zz"])],
            match="not a valid",
        )


class TestPreprocess:
    """`Argument`/`Option` ``preprocess=`` runs before the inferred converter, keeping inference."""

    def test_preprocess_runs_before_inferred_converter(self) -> None:
        """The token is transformed before the inferred Enum converter sees it."""
        parser = build_parser_from_function(_make_func(Annotated[_Color, Argument(preprocess=str.lower)], name="c"))
        assert parser.parse_args(["RED"]).c is _Color.red

    def test_preprocess_keeps_inferred_choices(self) -> None:
        """The inferred Enum choices survive (preprocess composes with, not replaces, the converter)."""
        action = _action_for(Annotated[_Color, Argument(preprocess=str.lower)])
        assert action.choices == _COLOR_CHOICE_ITEMS

    def test_preprocess_keeps_inferred_path_completer(self) -> None:
        """The inferred path completer survives a preprocess hook."""
        action = _action_for(Annotated[Path, Argument(preprocess=str.strip)])
        assert action.get_completer() is cmd2.Cmd.path_complete  # type: ignore[attr-defined]

    def test_preprocess_on_str_passthrough_becomes_type(self) -> None:
        """With no inferred converter (plain ``str``), preprocess becomes the ``type=`` directly."""
        parser = build_parser_from_function(_make_func(Annotated[str, Argument(preprocess=str.upper)], name="s"))
        assert parser.parse_args(["abc"]).s == "ABC"

    def test_preprocess_applies_per_element_on_collection(self) -> None:
        """On a ``list[T]`` preprocess runs per token, before the per-token inferred converter."""
        parser = build_parser_from_function(_make_func(Annotated[list[_Color], Option("--c", preprocess=str.lower)], name="c"))
        assert parser.parse_args(["--c", "RED", "Blue"]).c == [_Color.red, _Color.blue]

    def test_preprocess_keeps_enum_class_introspection(self) -> None:
        """The wrapped converter still exposes ``_cmd2_enum_class`` for introspection."""
        action = _action_for(Annotated[_Color, Argument(preprocess=str.lower)])
        assert action.type._cmd2_enum_class is _Color

    def test_preprocess_keeps_inferred_converter_name(self) -> None:
        """The wrapper copies the inner converter's ``__name__`` so argparse error messages stay meaningful."""
        action = _action_for(Annotated[_Color, Argument(preprocess=str.lower)])
        assert action.type.__name__ == _Color.__name__

    def test_preprocess_runs_explicit_choices_through_composed_type(self) -> None:
        """Explicit ``choices`` are run through the preprocess+converter wrapper (``RED`` -> lower -> Enum)."""
        action = _action_for(Annotated[_Color, Argument(preprocess=str.lower, choices=["RED"])])
        assert action.choices == [_Color.red]


class TestConverterPreprocessConstraints:
    """Build-time rejections for ``converter=`` / ``preprocess=`` misuse."""

    def test_converter_and_preprocess_together_rejected(self) -> None:
        """Supplying both is ambiguous -- fold the preprocessing into the converter."""
        _assert_build_error(
            Annotated[int, Argument(converter=_hex, preprocess=str.strip)],
            match="converter= and preprocess=",
        )

    def test_converter_on_value_less_action_rejected(self) -> None:
        """A converter on a zero-argument action has nothing to convert."""
        _assert_build_error(
            Annotated[bool, Option("--flag", action="store_true", converter=_hex)],
            match="takes no value",
            kind="kw",
        )

    def test_preprocess_on_value_less_action_rejected(self) -> None:
        """A preprocess hook on a zero-argument action has nothing to transform."""
        _assert_build_error(
            Annotated[bool, Option("--flag", action="store_true", preprocess=str.strip)],
            match="takes no value",
            kind="kw",
        )

    def test_reserved_type_hint_points_at_converter(self) -> None:
        """A raw ``type=`` is still rejected, now pointing the user at ``converter=``."""
        with pytest.raises(TypeError, match="converter="):
            Argument(type=int)


# ---------------------------------------------------------------------------
# Dataclass argument blocks (#1689): a dataclass-typed parameter expands its
# fields into the parser (flat: field name == arg name) and is reconstructed
# into an instance at call time.
# ---------------------------------------------------------------------------


@dataclass
class _CommonArgs(ArgumentBlock):
    verbose: Annotated[bool, Option("-v", "--verbose")] = False
    output: Annotated[Path | None, Option("--output")] = None


@dataclass
class _TracedArgs(_CommonArgs):
    """Inheritance is the "shared base block" reuse mechanism (and carries the ArgumentBlock trait)."""

    trace: bool = False


class TestDataclassBlockParser:
    """A dataclass-typed parameter expands its fields into flat parser arguments."""

    def test_block_fields_become_arguments(self) -> None:
        def do_build(self, target: str, common: _CommonArgs) -> None: ...

        parser = build_parser_from_function(do_build)
        dests = {action.dest for action in parser._actions}
        assert {"target", "verbose", "output"} <= dests
        # The block parameter itself is a container, not an argument.
        assert "common" not in dests

    def test_block_field_option_strings_preserved(self) -> None:
        def do_build(self, target: str, common: _CommonArgs) -> None: ...

        parser = build_parser_from_function(do_build)
        # A field's Annotated Option metadata drives its flags exactly as a top-level option would
        # (a bool option expands to --verbose/--no-verbose via BooleanOptionalAction).
        verbose = next(a for a in parser._actions if a.dest == "verbose")
        assert "-v" in verbose.option_strings
        assert "--verbose" in verbose.option_strings
        output = next(a for a in parser._actions if a.dest == "output")
        assert output.option_strings == ["--output"]

    def test_inherited_block_fields_expand(self) -> None:
        def do_build(self, target: str, opts: _TracedArgs) -> None: ...

        parser = build_parser_from_function(do_build)
        dests = {action.dest for action in parser._actions}
        assert {"target", "verbose", "output", "trace"} <= dests


class _DataclassBlockApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.last_block: object = None

    @with_annotated
    def do_build(self, target: str, common: _CommonArgs) -> None:
        self.last_block = common
        self.poutput(f"target={target} verbose={common.verbose} output={common.output}")

    @with_annotated
    def do_test(self, suite: str, opts: _TracedArgs) -> None:
        self.poutput(f"suite={suite} verbose={opts.verbose} trace={opts.trace}")


@pytest.fixture
def block_app() -> _DataclassBlockApp:
    app = _DataclassBlockApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestDataclassBlockRuntime:
    """The block is reconstructed into a dataclass instance and passed to the command."""

    def test_block_reconstructed_with_defaults(self, block_app) -> None:
        out, _err = run_cmd(block_app, "build app")
        assert out == ["target=app verbose=False output=None"]

    def test_block_field_from_command_line(self, block_app) -> None:
        out, _err = run_cmd(block_app, "build app --verbose --output /tmp/x")
        assert out == [f"target=app verbose=True output={Path('/tmp/x')}"]

    def test_block_instance_type(self, block_app) -> None:
        """The reconstructed argument is an actual instance of the declared dataclass."""
        run_cmd(block_app, "build app --verbose")
        assert isinstance(block_app.last_block, _CommonArgs)
        assert block_app.last_block.verbose is True

    def test_block_field_values_and_types(self, block_app) -> None:
        """Each field on the reconstructed instance holds the converted value at its declared type."""
        run_cmd(block_app, "build app --verbose --output /tmp/x")
        block = block_app.last_block
        assert block.verbose is True
        assert isinstance(block.output, Path)  # converted from str to Path, not left as a string
        assert block.output == Path("/tmp/x")

    def test_block_field_defaults_on_instance(self, block_app) -> None:
        """An omitted field is filled by the dataclass constructor, not left absent on the instance."""
        run_cmd(block_app, "build app")
        block = block_app.last_block
        assert block.verbose is False
        assert block.output is None

    def test_inherited_block_runtime(self, block_app) -> None:
        out, _err = run_cmd(block_app, "test smoke --trace")
        assert out == ["suite=smoke verbose=False trace=True"]


@dataclass
class _PositionalBlock(ArgumentBlock):
    """A field with no default becomes a positional argument."""

    name: str
    count: int = 1


@dataclass
class _FactoryBlock(ArgumentBlock):
    tags: Annotated[list[str], Option("--tag", action="append")] = field(default_factory=list)


@dataclass
class _NestedBlock(ArgumentBlock):
    inner: _CommonArgs = field(default_factory=_CommonArgs)


@dataclass
class _ForwardFieldBlock(ArgumentBlock):
    # Stringized field annotations exercise the same get_type_hints() resolution path as a dataclass
    # defined in a module using ``from __future__ import annotations``.
    verbose: "Annotated[bool, Option('-v', '--verbose')]" = False
    tags: "Annotated[list[str], Option('--tag', action='append')]" = field(default_factory=list)


class TestDataclassBlockEdgeCases:
    def test_block_positional_field(self) -> None:
        def do_x(self, common: _PositionalBlock) -> None: ...

        parser = build_parser_from_function(do_x)
        name = next(a for a in parser._actions if a.dest == "name")
        assert name.option_strings == []  # positional
        count = next(a for a in parser._actions if a.dest == "count")
        assert count.option_strings == ["--count"]

    def test_block_positional_field_runtime(self) -> None:
        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, common: _PositionalBlock) -> None:
                self.poutput(f"{common.name}:{common.count}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        assert run_cmd(app, "x bob --count 3")[0] == ["bob:3"]

    def test_block_default_factory(self) -> None:
        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, opts: _FactoryBlock) -> None:
                self.poutput(f"tags={opts.tags}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        assert run_cmd(app, "x")[0] == ["tags=[]"]
        assert run_cmd(app, "x --tag a --tag b")[0] == ["tags=['a', 'b']"]

    def test_default_factory_not_shared_across_calls(self) -> None:
        """Each invocation gets a fresh default_factory value (no shared-mutable-default bug)."""

        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, opts: _FactoryBlock) -> None:
                opts.tags.append("mutated")
                self.poutput(f"tags={opts.tags}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        # First call mutates its (default) list; the second call must not see that mutation.
        assert run_cmd(app, "x")[0] == ["tags=['mutated']"]
        assert run_cmd(app, "x")[0] == ["tags=['mutated']"]

    def test_block_field_default_emits_suppress(self) -> None:
        """A field-default block field emits SUPPRESS so the dataclass constructor fills the default."""

        def do_x(self, common: _CommonArgs) -> None: ...

        parser = build_parser_from_function(do_x)
        verbose = next(a for a in parser._actions if a.dest == "verbose")
        assert verbose.default is argparse.SUPPRESS
        # An absent field stays out of the parsed namespace entirely.
        assert not hasattr(parser.parse_args([]), "verbose")

    def test_nested_dataclass_field_rejected(self) -> None:
        """A dataclass field whose type is itself a dataclass is not a supported scalar (no recursion)."""

        def do_x(self, opts: _NestedBlock) -> None: ...

        with pytest.raises(TypeError, match="Unsupported parameter type"):
            build_parser_from_function(do_x)

    def test_field_name_collides_with_explicit_param(self) -> None:
        """A block field whose name collides with an explicit parameter is a clear build error."""

        @dataclass
        class Blk(ArgumentBlock):
            target: Annotated[str, Option("--target")] = "z"

        def do_x(self, target: str, blk: Blk) -> None: ...

        with pytest.raises(TypeError, match=r"target.*more than once"):
            build_parser_from_function(do_x)

    def test_field_name_collides_across_two_blocks(self) -> None:
        """Two blocks sharing a field name collide regardless of flags (same namespace dest)."""

        @dataclass
        class BlkA(ArgumentBlock):
            x: Annotated[int, Option("--x")] = 0

        @dataclass
        class BlkB(ArgumentBlock):
            x: Annotated[int, Option("--xx")] = 0  # different flag, same field/dest name

        def do_x(self, a: BlkA, b: BlkB) -> None: ...

        with pytest.raises(TypeError, match=r"x.*more than once"):
            build_parser_from_function(do_x)

    def test_post_init_runs(self) -> None:
        """Reconstruction goes through the dataclass constructor, so __post_init__ runs."""

        @dataclass
        class PostInit(ArgumentBlock):
            width: int = 2
            doubled: int = 0

            def __post_init__(self) -> None:
                self.doubled = self.width * 2

        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, opts: PostInit) -> None:
                self.poutput(f"doubled={opts.doubled}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        assert run_cmd(app, "x --width 5")[0] == ["doubled=10"]
        assert run_cmd(app, "x")[0] == ["doubled=4"]

    def test_required_field_errors_when_omitted(self) -> None:
        """A field with no default is a required argument."""

        @dataclass
        class Req(ArgumentBlock):
            host: Annotated[str, Option("--host")]

        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, opts: Req) -> None:
                self.poutput(opts.host)

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        _out, err = run_cmd(app, "x")
        assert any("host" in line.lower() and ("required" in line.lower() or "error" in line.lower()) for line in err)
        assert run_cmd(app, "x --host db")[0] == ["db"]

    def test_plain_dataclass_is_not_a_block(self) -> None:
        """A plain @dataclass (no ArgumentBlock trait) is never expanded; it is an ordinary value."""

        @dataclass
        class Plain:
            x: int = 0
            y: int = 0

        def do_x(self, p: Plain) -> None: ...

        # Without the trait it falls through to the normal type path: a dataclass scalar with no converter
        # is an unsupported type (it is not silently decomposed into x/y).
        with pytest.raises(TypeError, match="Unsupported parameter type"):
            build_parser_from_function(do_x)

    def test_plain_dataclass_with_converter_is_single_value(self) -> None:
        """A plain @dataclass used as a single value (via a converter) is one argument, not a block."""

        @dataclass
        class Point:
            x: int = 0
            y: int = 0

        def parse_point(s: str) -> Point:
            a, b = s.split(",")
            return Point(int(a), int(b))

        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, p: Annotated[Point, Argument(converter=parse_point)]) -> None:
                self.poutput(f"{type(p).__name__}({p.x},{p.y})")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        parser = build_parser_from_function(App.do_x.__wrapped__)  # single 'p' arg, not decomposed
        assert [a.dest for a in parser._actions if a.dest != "help"] == ["p"]
        assert run_cmd(app, "x 3,4")[0] == ["Point(3,4)"]

    def test_optional_block_rejected(self) -> None:
        """An ArgumentBlock combined with Optional (``Block | None``) is rejected with a clear message."""

        @dataclass
        class Blk(ArgumentBlock):
            x: int = 0

        def do_x(self, blk: Blk | None) -> None: ...

        with pytest.raises(TypeError, match="bare annotation"):
            build_parser_from_function(do_x)

    def test_union_of_blocks_rejected(self) -> None:
        """A union of ArgumentBlocks (``BlockA | BlockB``) is rejected with a clear message."""

        @dataclass
        class BlkA(ArgumentBlock):
            x: int = 0

        @dataclass
        class BlkB(ArgumentBlock):
            y: int = 0

        def do_x(self, blk: BlkA | BlkB) -> None: ...

        with pytest.raises(TypeError, match="bare annotation"):
            build_parser_from_function(do_x)

    def test_annotated_block_rejected(self) -> None:
        """An ArgumentBlock wrapped in Annotated is rejected (a block must be the bare annotation)."""

        @dataclass
        class Blk(ArgumentBlock):
            x: int = 0

        def do_x(self, blk: Annotated[Blk, "doc"]) -> None: ...

        with pytest.raises(TypeError, match="bare annotation"):
            build_parser_from_function(do_x)

    def test_argument_block_without_dataclass_rejected(self) -> None:
        """An ArgumentBlock subclass that is not a @dataclass has no fields; reject with guidance."""

        class NotADataclass(ArgumentBlock):
            x: int = 0

        def do_x(self, blk: NotADataclass) -> None: ...

        with pytest.raises(TypeError, match="must be decorated with @dataclass"):
            build_parser_from_function(do_x)

    def test_stringized_field_annotations_resolve(self) -> None:
        """A block whose field hints are strings (forward refs / ``from __future__ import annotations``)
        resolves through get_type_hints and behaves identically.
        """

        class App(cmd2.Cmd):
            @with_annotated
            def do_x(self, target: "str", common: "_ForwardFieldBlock") -> None:
                self.poutput(f"{target} verbose={common.verbose} tags={common.tags}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        assert run_cmd(app, "x app --verbose --tag a --tag b")[0] == ["app verbose=True tags=['a', 'b']"]
        assert run_cmd(app, "x app2")[0] == ["app2 verbose=False tags=[]"]

    def test_block_parameter_default_rejected(self) -> None:
        """The dataclass owns its fields' defaults, so a default on the block parameter is rejected."""

        @dataclass
        class Blk(ArgumentBlock):
            verbose: Annotated[bool, Option("-v")] = False

        def do_x(self, blk: Blk = Blk()) -> None: ...  # noqa: B008 — the block-param default is the thing under test

        with pytest.raises(TypeError, match="cannot have a default value"):
            build_parser_from_function(do_x)

    def test_field_name_collides_with_reserved_namespace_attr(self) -> None:
        """A field named like a cmd2-injected namespace attr would be overwritten at parse time; reject it."""

        @dataclass
        class Blk(ArgumentBlock):
            cmd2_statement: Annotated[str, Option("--stmt")] = "x"

        def do_x(self, blk: Blk) -> None: ...

        with pytest.raises(TypeError, match="reserved cmd2 namespace attribute"):
            build_parser_from_function(do_x)

    def test_block_field_both_defaults_error_names_dataclass_source(self) -> None:
        """A field with both a dataclass default and a metadata default is rejected, naming the right source.

        The block field's signature default lives on the dataclass (its internal ``param_default`` is a
        placeholder ``None``), so the conflict message must say "dataclass field", not "function signature (None)".
        """

        @dataclass
        class Blk(ArgumentBlock):
            level: Annotated[int, Option("--level", default=5)] = 2

        def do_x(self, blk: Blk) -> None: ...

        with pytest.raises(TypeError, match=r"both the dataclass field and the metadata \(5\)"):
            build_parser_from_function(do_x)

    def test_initvar_field_rejected(self) -> None:
        """An InitVar is required by the constructor but never becomes a CLI argument; reject it clearly."""

        @dataclass
        class Blk(ArgumentBlock):
            ratio: InitVar[int]
            name: Annotated[str, Option("--name")] = "n"

            def __post_init__(self, ratio: int) -> None:
                self.ratio = ratio

        def do_x(self, blk: Blk) -> None: ...

        with pytest.raises(TypeError, match="InitVar"):
            build_parser_from_function(do_x)


class _SubcommandBlockApp(cmd2.Cmd):
    @with_annotated(base_command=True)
    def do_db(self, cmd2_subcommand_func) -> None:
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    @with_annotated(subcommand_to="db")
    def db_migrate(self, name: str, common: _CommonArgs) -> None:
        self.poutput(f"migrate {name} verbose={common.verbose}")


class TestDataclassBlockSubcommand:
    def test_subcommand_block_reconstructed(self) -> None:
        app = _SubcommandBlockApp()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        out, _err = run_cmd(app, "db migrate users --verbose")
        assert out == ["migrate users verbose=True"]


# ---------------------------------------------------------------------------
# Shared blocks: a command declares an inheritable block as ``cmd2_base_args``
# and its subcommands receive it as ``cmd2_parent_args`` instead of re-declaring
# the arguments.  This is the typed answer to passing parent-level args down to
# subcommands (#1690).
# ---------------------------------------------------------------------------


@dataclass
class _SharedOpts(ArgumentBlock):
    verbose: Annotated[bool, Option("-v", "--verbose")] = False
    level: Annotated[int, Option("--level")] = 1


class _InheritBlockApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.received: object = None

    @with_annotated(base_command=True)
    def do_root(self, cmd2_subcommand_func, cmd2_base_args: _SharedOpts) -> None:
        """Parent declares the inheritable block, so its fields land on the base parser."""
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    @with_annotated(subcommand_to="root", help="show the inherited block")
    def root_show(self, cmd2_parent_args: _SharedOpts) -> None:
        self.received = cmd2_parent_args
        self.poutput(f"verbose={cmd2_parent_args.verbose} level={cmd2_parent_args.level}")


@pytest.fixture
def inherit_app() -> _InheritBlockApp:
    app = _InheritBlockApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestParentArgsInheritance:
    def test_subcommand_inherits_parent_block_values(self, inherit_app) -> None:
        """Values parsed on the parent flow into the subcommand's inherited block."""
        out, _err = run_cmd(inherit_app, "root --verbose --level 5 show")
        assert out == ["verbose=True level=5"]

    def test_inherited_block_uses_parent_defaults_when_omitted(self, inherit_app) -> None:
        """An option the parent did not receive arrives at its declared default, not absent."""
        out, _err = run_cmd(inherit_app, "root show")
        assert out == ["verbose=False level=1"]

    def test_inherited_block_reconstructed_instance(self, inherit_app) -> None:
        """The subcommand receives a real dataclass instance, not loose values."""
        run_cmd(inherit_app, "root --verbose show")
        assert isinstance(inherit_app.received, _SharedOpts)
        assert inherit_app.received.verbose is True

    def test_inherited_block_fields_not_re_added_to_subparser(self, inherit_app) -> None:
        """The inherited block adds no arguments to the subparser; its flags live only on the parent."""
        _out, err = run_cmd(inherit_app, "root show --verbose")
        assert any("unrecognized arguments" in line for line in err), err

    def test_grandparent_declares_leaf_inherits(self) -> None:
        """A leaf subcommand inherits a block its grandparent declared (an intermediate level in between)."""

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_root(self, cmd2_subcommand_func, cmd2_base_args: _SharedOpts) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="root", base_command=True)
            def root_show(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="root show")
            def root_show_detail(self, cmd2_parent_args: _SharedOpts) -> None:
                self.poutput(f"verbose={cmd2_parent_args.verbose}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        assert run_cmd(app, "root --verbose show detail")[0] == ["verbose=True"]

    def test_intermediate_declares_leaf_inherits(self) -> None:
        """An intermediate command declares the block and a deeper subcommand inherits it.

        The intermediate command's handler never runs in the dispatch chain (only the entry base command
        and the leaf do), so the marker must come from the *parser* at parse time, not a running handler.
        """

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_root(self, cmd2_subcommand_func) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="root", base_command=True)
            def root_show(self, cmd2_subcommand_func, cmd2_base_args: _SharedOpts) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="root show")
            def root_show_detail(self, cmd2_parent_args: _SharedOpts) -> None:
                self.poutput(f"verbose={cmd2_parent_args.verbose}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        assert run_cmd(app, "root show --verbose detail")[0] == ["verbose=True"]

    def test_inherited_field_colliding_with_own_arg_rejected(self) -> None:
        """An inherited field that also names the subcommand's own argument is rejected at build time."""

        def root_show(self, verbose: str, cmd2_parent_args: _SharedOpts) -> None: ...

        with pytest.raises(TypeError, match="inherited ArgumentBlock field"):
            build_parser_from_function(root_show)

    def test_parent_args_must_be_bare_block(self) -> None:
        """``cmd2_parent_args`` must be annotated with a bare ArgumentBlock subclass."""

        def root_show(self, cmd2_parent_args: int) -> None: ...

        with pytest.raises(TypeError, match="must be annotated with a bare ArgumentBlock"):
            build_parser_from_function(root_show)

    def test_parent_args_default_rejected(self) -> None:
        """An inherited block always comes from the parent, so a default on it is rejected."""

        def root_show(self, cmd2_parent_args: _SharedOpts = _SharedOpts()) -> None: ...  # noqa: B008

        with pytest.raises(TypeError, match="cannot have a default value"):
            build_parser_from_function(root_show)

    def test_base_args_must_be_block(self) -> None:
        """``cmd2_base_args`` must be annotated with a bare ArgumentBlock subclass."""

        def do_root(self, cmd2_base_args: int) -> None: ...

        with pytest.raises(TypeError, match="must be annotated with a bare ArgumentBlock"):
            build_parser_from_function(do_root)

    def test_missing_parent_declaration_errors_at_runtime(self) -> None:
        """A cmd2_parent_args subcommand whose ancestors never declare cmd2_base_args errors when first run.

        Registration succeeds (the misconfiguration is detectable only once the shared namespace exists), so
        the app constructs cleanly and the clear error surfaces on first invocation of the subcommand.
        """

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_root(self, cmd2_subcommand_func) -> None:  # parent does NOT declare cmd2_base_args
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="root")
            def root_show(self, cmd2_parent_args: _SharedOpts) -> None: ...

        app = App()  # construction must NOT raise
        app.stdout = cmd2.utils.StdSim(app.stdout)
        _out, err = run_cmd(app, "root show")
        assert any("no ancestor command declares" in line for line in err), err

    def test_type_mismatch_errors_at_runtime(self) -> None:
        """A cmd2_parent_args whose type no ancestor declared as cmd2_base_args errors when first run."""

        @dataclass
        class _OtherOpts(ArgumentBlock):
            level: Annotated[int, Option("--level")] = 0

        class App(cmd2.Cmd):
            @with_annotated(base_command=True)
            def do_root(self, cmd2_subcommand_func, cmd2_base_args: _SharedOpts) -> None:
                if cmd2_subcommand_func:
                    cmd2_subcommand_func()

            @with_annotated(subcommand_to="root")
            def root_show(self, cmd2_parent_args: _OtherOpts) -> None: ...

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        _out, err = run_cmd(app, "root show")
        assert any("no ancestor command declares" in line for line in err), err

    def test_directly_supplied_inherited_block_skips_reconstruction_and_check(self) -> None:
        """A block already supplied (a direct call passing the instance) is used as-is.

        Reconstruction is skipped, and for an inherited block so is the ancestor-presence check -- the
        caller provided the instance, so there is nothing to reconstruct or verify.
        """
        spec = _BlockSpec(_SharedOpts, ["verbose", "level"], inherited=True)
        provided = _SharedOpts(verbose=True, level=9)
        func_kwargs = {"cmd2_parent_args": provided}
        # An empty namespace carries no presence marker; the directly-supplied instance must bypass it.
        _reconstruct_dataclass_blocks(func_kwargs, {"cmd2_parent_args": spec}, argparse.Namespace())
        assert func_kwargs["cmd2_parent_args"] is provided

    def test_directly_supplied_block_pops_stray_field_values(self) -> None:
        """A directly-supplied instance wins, and parsed field values are dropped (not stranded as stray kwargs).

        A programmatic call may pass the block instance while the command line also parsed some of its fields
        into the namespace.  Those expanded field names are not parameters of the command function, so they must
        be popped even though reconstruction is skipped -- otherwise the call fails with an unexpected keyword.
        """
        spec = _BlockSpec(_SharedOpts, ["verbose", "level"], inherited=False)
        provided = _SharedOpts(verbose=True, level=9)
        # 'verbose' was parsed from the command line; 'cmd2_parent_args'/'common' supplied directly.
        func_kwargs = {"common": provided, "verbose": False, "target": "app"}
        _reconstruct_dataclass_blocks(func_kwargs, {"common": spec}, argparse.Namespace())
        assert func_kwargs["common"] is provided
        assert "verbose" not in func_kwargs  # the stray parsed field value was dropped
        assert func_kwargs["target"] == "app"  # an unrelated command parameter is untouched

    def test_directly_supplied_block_via_command_does_not_strand_fields(self) -> None:
        """End-to-end: passing a block instance to a decorated command while the line parses a field succeeds."""

        class App(cmd2.Cmd):
            @with_annotated
            def do_build(self, target: str, common: _CommonArgs) -> None:
                self.poutput(f"target={target} verbose={common.verbose}")

        app = App()
        app.stdout = cmd2.utils.StdSim(app.stdout)
        # The directly-supplied instance is used; the parsed --verbose does not crash the call as a stray kwarg.
        app.do_build("app --verbose", common=_CommonArgs(verbose=False))
        assert app.stdout.getvalue().splitlines() == ["target=app verbose=False"]
