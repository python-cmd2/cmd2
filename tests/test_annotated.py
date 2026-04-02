"""Unit tests for cmd2.annotated -- verify build_parser_from_function produces correct actions.

The focus is on testing that type annotations are correctly translated into
argparse action attributes (option_strings, type, nargs, choices, action, default, etc.).
We do NOT re-test argparse parsing logic or cmd2 integration here.
"""

import argparse
import decimal
import enum
from pathlib import Path
from typing import (
    Annotated,
    ClassVar,
    Literal,
)

import pytest

import cmd2
from cmd2 import Cmd2ArgumentParser
from cmd2.annotated import (
    Argument,
    Option,
    _apply_mutex_group_targets,
    _build_argument_group_targets,
    _CollectionCastingAction,
    _make_enum_type,
    _make_literal_type,
    _parse_bool,
    _resolve_annotation,
    _validate_group_members,
    build_parser_from_function,
)

from .conftest import run_cmd

# ---------------------------------------------------------------------------
# Test enums
# ---------------------------------------------------------------------------


class _Color(str, enum.Enum):
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


# ---------------------------------------------------------------------------
# Single-parameter test functions for build_parser_from_function.
# Each has exactly one param (besides self) so dest is auto-derived.
# ---------------------------------------------------------------------------


def _func_str(self, name: str) -> None: ...
def _func_int_option(self, count: int = 1) -> None: ...
def _func_float_option(self, rate: float = 1.0) -> None: ...
def _func_bool_false(self, verbose: bool = False) -> None: ...
def _func_bool_true(self, debug: bool = True) -> None: ...
def _func_bool_positional(self, flag: bool) -> None: ...
def _func_path(self, file: Path) -> None: ...
def _func_path_option(self, file: Path = Path(".")) -> None: ...
def _func_decimal(self, amount: decimal.Decimal) -> None: ...
def _func_enum(self, color: _Color) -> None: ...
def _func_enum_option(self, color: _Color = _Color.blue) -> None: ...
def _func_literal(self, mode: Literal["fast", "slow"]) -> None: ...
def _func_literal_option(self, mode: Literal["fast", "slow"] = "fast") -> None: ...
def _func_literal_int(self, level: Literal[1, 2, 3]) -> None: ...
def _func_optional(self, name: str | None = None) -> None: ...
def _func_list(self, files: list[str]) -> None: ...
def _func_list_default(self, items: list[str] | None = None) -> None: ...
def _func_set(self, tags: set[str]) -> None: ...
def _func_tuple_ellipsis(self, values: tuple[int, ...]) -> None: ...
def _func_tuple_fixed(self, pair: tuple[int, int]) -> None: ...
def _func_bare_list(self, items: list) -> None: ...
def _func_bare_tuple(self, items: tuple) -> None: ...
def _func_annotated_arg(self, name: Annotated[str, Argument(help_text="Your name")]) -> None: ...
def _func_annotated_option(self, color: Annotated[str, Option("--color", "-c", help_text="Pick")] = "blue") -> None: ...
def _func_annotated_metavar(self, name: Annotated[str, Argument(metavar="NAME")]) -> None: ...
def _func_annotated_nargs(self, names: Annotated[str, Argument(nargs=2)]) -> None: ...
def _func_annotated_action(self, verbose: Annotated[bool, Option("--verbose", "-v", action="count")] = False) -> None: ...
def _func_annotated_required(self, name: Annotated[str, Option("--name", required=True)]) -> None: ...
def _func_annotated_required_auto_flag(self, name: Annotated[str, Option(required=True)]) -> None: ...
def _func_annotated_choices(self, food: Annotated[str, Argument(choices=["a", "b"])]) -> None: ...
def _func_dest_param(self, dest: str) -> None: ...
def _func_kw_only(self, *, name: str) -> None: ...
def _func_kw_only_with_default(self, *, name: str = "world") -> None: ...
def _func_underscore_option(self, my_param: str = "x") -> None: ...
def _func_default_type_mismatch(self, count: int = "1") -> None: ...  # type: ignore[assignment]
def _func_path_default(self, file: Path = Path("/tmp")) -> None: ...
def _func_optional_annotated_inside(self, name: Annotated[str | None, Option("--name")] = None) -> None: ...
def _func_optional_annotated_outside(self, name: Annotated[str, Option("--name")] | None = None) -> None: ...
def _func_int_enum(self, color: _IntColor) -> None: ...
def _func_plain_enum(self, color: _PlainColor) -> None: ...
def _func_list_int(self, nums: list[int]) -> None: ...
def _func_set_int(self, nums: set[int]) -> None: ...
def _func_tuple_fixed_triple(self, triple: tuple[int, int, int]) -> None: ...
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


def _provider(cmd: cmd2.Cmd):
    return []


def _func_choices_provider_on_enum(
    self,
    color: Annotated[_Color, Argument(choices_provider=_provider)],
) -> None: ...


def _func_completer_on_path(
    self,
    file: Annotated[Path, Argument(completer=cmd2.Cmd.path_complete)],
) -> None: ...


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_param_action(func: object) -> argparse.Action:
    """Build parser from a single-param function and return its action."""
    import inspect

    sig = inspect.signature(func)  # type: ignore[arg-type]
    param_names = [n for n in sig.parameters if n != 'self']
    assert len(param_names) == 1, f"Expected 1 param besides self, got {param_names}"
    parser = build_parser_from_function(func)  # type: ignore[arg-type]
    for action in parser._actions:
        if action.dest == param_names[0]:
            return action
    raise ValueError(f"No action with dest={param_names[0]!r}")


def _complete_cmd(app: cmd2.Cmd, line: str, text: str) -> list[str]:
    begidx = len(line) - len(text)
    endidx = len(line)
    completions = app.complete(text, line, begidx, endidx)
    return list(completions.to_strings())


# ---------------------------------------------------------------------------
# Core: build_parser_from_function produces correct action attributes
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Verify action attributes produced by build_parser_from_function."""

    @pytest.mark.parametrize(
        ("func", "expected"),
        [
            # --- Positionals ---
            pytest.param(_func_str, {"option_strings": [], "type": None}, id="str_positional"),
            pytest.param(_func_path, {"option_strings": [], "type": Path}, id="path_positional"),
            pytest.param(_func_decimal, {"option_strings": [], "type": decimal.Decimal}, id="decimal_positional"),
            pytest.param(_func_bool_positional, {"option_strings": [], "type": _parse_bool}, id="bool_positional"),
            pytest.param(_func_enum, {"option_strings": [], "choices": ["red", "green", "blue"]}, id="enum_positional"),
            pytest.param(_func_literal, {"option_strings": [], "choices": ["fast", "slow"]}, id="literal_positional"),
            pytest.param(_func_literal_int, {"option_strings": [], "choices": [1, 2, 3]}, id="literal_int_positional"),
            pytest.param(_func_int_enum, {"option_strings": [], "choices": [1, 2, 3]}, id="int_enum_positional"),
            pytest.param(
                _func_plain_enum, {"option_strings": [], "choices": ["red", "green", "blue"]}, id="plain_enum_positional"
            ),
            pytest.param(_func_list_int, {"option_strings": [], "nargs": "+", "type": int}, id="list_int"),
            pytest.param(_func_set_int, {"option_strings": [], "nargs": "+", "type": int}, id="set_int"),
            pytest.param(_func_tuple_fixed_triple, {"option_strings": [], "nargs": 3, "type": int}, id="tuple_fixed_triple"),
            pytest.param(_func_list, {"option_strings": [], "nargs": "+"}, id="list_positional"),
            pytest.param(_func_set, {"option_strings": [], "nargs": "+"}, id="set_positional"),
            pytest.param(_func_tuple_ellipsis, {"option_strings": [], "nargs": "+", "type": int}, id="tuple_ellipsis"),
            pytest.param(_func_tuple_fixed, {"option_strings": [], "nargs": 2, "type": int}, id="tuple_fixed"),
            pytest.param(_func_bare_list, {"option_strings": [], "nargs": "+"}, id="bare_list"),
            pytest.param(_func_bare_tuple, {"option_strings": [], "nargs": "+"}, id="bare_tuple"),
            # --- Options ---
            pytest.param(_func_int_option, {"option_strings": ["--count"], "type": int, "default": 1}, id="int_option"),
            pytest.param(_func_float_option, {"option_strings": ["--rate"], "type": float, "default": 1.0}, id="float_option"),
            pytest.param(_func_bool_false, {"option_strings": ["--verbose", "--no-verbose"]}, id="bool_optional_action"),
            pytest.param(
                _func_bool_true,
                {"option_strings": ["--debug", "--no-debug"], "default": True},
                id="bool_optional_action_true",
            ),
            pytest.param(_func_path_option, {"option_strings": ["--file"], "type": Path}, id="path_option"),
            pytest.param(
                _func_enum_option,
                {"option_strings": ["--color"], "choices": ["red", "green", "blue"], "default": _Color.blue},
                id="enum_option",
            ),
            pytest.param(
                _func_literal_option, {"option_strings": ["--mode"], "choices": ["fast", "slow"]}, id="literal_option"
            ),
            pytest.param(_func_optional, {"option_strings": ["--name"], "default": None}, id="optional_str"),
            pytest.param(_func_list_default, {"option_strings": ["--items"], "nargs": "*"}, id="list_with_default"),
            # --- Annotated metadata ---
            pytest.param(_func_annotated_arg, {"option_strings": [], "help": "Your name"}, id="annotated_help"),
            pytest.param(
                _func_annotated_option, {"option_strings": ["--color", "-c"], "help": "Pick"}, id="annotated_custom_flags"
            ),
            pytest.param(_func_annotated_metavar, {"option_strings": [], "metavar": "NAME"}, id="annotated_metavar"),
            pytest.param(_func_annotated_nargs, {"option_strings": [], "nargs": 2}, id="annotated_nargs"),
            pytest.param(_func_annotated_required, {"option_strings": ["--name"], "required": True}, id="annotated_required"),
            pytest.param(
                _func_annotated_required_auto_flag,
                {"option_strings": ["--name"], "required": True},
                id="annotated_required_auto_flag",
            ),
            pytest.param(_func_annotated_choices, {"option_strings": [], "choices": ["a", "b"]}, id="annotated_choices"),
            # --- Keyword-only ---
            pytest.param(_func_kw_only, {"option_strings": ["--name"], "required": True}, id="kw_only_required"),
            pytest.param(_func_kw_only_with_default, {"option_strings": ["--name"], "default": "world"}, id="kw_only_default"),
            # --- Underscore in flag names ---
            pytest.param(_func_underscore_option, {"option_strings": ["--my_param"], "default": "x"}, id="underscore_flag"),
            # --- Default type preservation ---
            pytest.param(
                _func_default_type_mismatch, {"option_strings": ["--count"], "default": "1"}, id="default_not_coerced"
            ),
            pytest.param(_func_path_default, {"option_strings": ["--file"], "default": Path("/tmp")}, id="path_default"),
            # --- Optional + Annotated (union inside) ---
            pytest.param(
                _func_optional_annotated_inside,
                {"option_strings": ["--name"], "default": None},
                id="optional_annotated_inside",
            ),
        ],
    )
    def test_action_attributes(self, func, expected) -> None:
        action = _get_param_action(func)
        for key, value in expected.items():
            assert getattr(action, key) == value, f"{key}: expected {value!r}, got {getattr(action, key)!r}"

    def test_annotated_action_count(self) -> None:
        action = _get_param_action(_func_annotated_action)
        assert isinstance(action, argparse._CountAction)

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(_func_set, id="set"),
            pytest.param(_func_tuple_ellipsis, id="tuple"),
        ],
    )
    def test_collection_uses_casting_action(self, func) -> None:
        action = _get_param_action(func)
        assert isinstance(action, _CollectionCastingAction)

    def test_self_skipped(self) -> None:
        parser = build_parser_from_function(_func_str)
        dests = {a.dest for a in parser._actions}
        assert 'self' not in dests

    def test_no_params_produces_empty_parser(self) -> None:
        """A function with zero parameters (not even self) produces a parser with no actions."""

        def bare() -> None: ...

        parser = build_parser_from_function(bare)
        dests = {a.dest for a in parser._actions if a.dest != 'help'}
        assert dests == set()

    def test_get_type_hints_failure_raises(self) -> None:
        def do_broken(self, name: 'NonExistentType'):  # noqa: F821
            pass

        with pytest.raises(TypeError, match="Failed to resolve type hints"):
            build_parser_from_function(do_broken)

    def test_validate_base_command_type_hints_failure_raises(self) -> None:
        """_validate_base_command_params should raise, not swallow, type hint failures."""
        from cmd2.annotated import _validate_base_command_params

        def do_broken(self, cmd2_handler, name: 'NonExistentType'):  # noqa: F821
            pass

        with pytest.raises(TypeError, match="Failed to resolve type hints"):
            _validate_base_command_params(do_broken)

    def test_dest_param_raises(self) -> None:
        with pytest.raises(ValueError, match="dest"):
            build_parser_from_function(_func_dest_param)

    def test_subcommand_param_raises(self) -> None:
        def func(self, subcommand: str) -> None: ...

        with pytest.raises(ValueError, match="subcommand"):
            build_parser_from_function(func)

    def test_with_annotated_positional_only_param_raises(self) -> None:
        with pytest.raises(TypeError, match="positional-only"):
            build_parser_from_function(_func_positional_only)

    def test_optional_annotated_outside_raises(self) -> None:
        with pytest.raises(TypeError, match="Annotated"):
            build_parser_from_function(_func_optional_annotated_outside)

    def test_annotated_ambiguous_union_raises(self) -> None:
        """Annotated[str | int, meta] must raise -- ambiguous inner union."""
        with pytest.raises(TypeError, match="ambiguous"):
            _resolve_annotation(Annotated[str | int, Option("--name")])

    def test_multi_param_order_and_presence(self) -> None:
        """Positional order preserved, options generated correctly."""
        parser = build_parser_from_function(_func_multi)
        positionals = [a.dest for a in parser._actions if not a.option_strings and a.dest != 'help']
        assert positionals == ["a", "b"]
        dests = {a.dest for a in parser._actions}
        assert 'c' in dests


class TestTypeInferenceBuildParser:
    """Type-inference behavior and override precedence when building parser actions."""

    def test_choices_provider_overrides_inferred_enum_choices(self) -> None:
        action = _get_param_action(_func_choices_provider_on_enum)
        assert action.choices is None
        assert action.get_choices_provider() is not None  # type: ignore[attr-defined]
        assert action.get_completer() is None  # type: ignore[attr-defined]

    def test_completer_overrides_inferred_path_completion(self) -> None:
        action = _get_param_action(_func_completer_on_path)
        assert action.get_choices_provider() is None  # type: ignore[attr-defined]
        assert action.get_completer() is cmd2.Cmd.path_complete  # type: ignore[attr-defined]

    def test_inferred_enum_choices_match_type_converter(self) -> None:
        """Enum choices must be convertible by the type converter."""
        action = _get_param_action(_func_enum)
        converter = action.type
        for choice in action.choices:
            assert isinstance(converter(str(choice)), _Color)


# ---------------------------------------------------------------------------
# Argument groups and mutually exclusive groups
# ---------------------------------------------------------------------------


class TestArgumentGroups:
    def test_groups_and_mutex_applied(self) -> None:
        parser = build_parser_from_function(
            _func_grouped,
            groups=(("local", "remote"), ("force", "dry_run")),
            mutually_exclusive_groups=(("local", "remote"), ("force", "dry_run")),
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
            build_parser_from_function(_func_grouped, groups=(("missing",),))

    def test_param_in_multiple_groups_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be assigned to both argument group"):
            build_parser_from_function(_func_grouped, groups=(("local",), ("local", "remote")))

    def test_mutex_group_spanning_different_argument_groups_raises(self) -> None:
        with pytest.raises(ValueError, match="spans parameters in different argument groups"):
            build_parser_from_function(
                _func_grouped,
                groups=(("local",), ("remote",)),
                mutually_exclusive_groups=(("local", "remote"),),
            )

    def test_mutually_exclusive_group(self) -> None:
        """Mutually exclusive params cannot be used together."""

        def func(self, verbose: bool = False, quiet: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(("verbose", "quiet"),))
        assert len(parser._mutually_exclusive_groups) == 1
        group_dests = {a.dest for a in parser._mutually_exclusive_groups[0]._group_actions}
        assert group_dests == {"verbose", "quiet"}
        with pytest.raises(SystemExit):
            parser.parse_args(["--verbose", "--quiet"])

    def test_multiple_mutually_exclusive_groups(self) -> None:
        """Multiple mutually exclusive groups."""

        def func(self, verbose: bool = False, quiet: bool = False, json: bool = False, csv: bool = False) -> None: ...

        parser = build_parser_from_function(func, mutually_exclusive_groups=(("verbose", "quiet"), ("json", "csv")))
        assert len(parser._mutually_exclusive_groups) == 2

    def test_argument_group(self) -> None:
        """Arguments in a group appear under a shared heading in help."""

        def func(self, src: str, dst: str, recursive: bool = False, verbose: bool = False) -> None: ...

        parser = build_parser_from_function(func, groups=(("src", "dst"),))
        default_titles = {'Positional Arguments', 'options'}
        custom_groups = [g for g in parser._action_groups if g.title not in default_titles]
        assert len(custom_groups) >= 1
        all_custom_dests = {a.dest for g in custom_groups for a in g._group_actions}
        assert {"src", "dst"} <= all_custom_dests

    def test_mutually_exclusive_via_decorator(self) -> None:
        """@with_annotated(mutually_exclusive_groups=...) works end-to-end."""

        class App(cmd2.Cmd):
            @cmd2.with_annotated(mutually_exclusive_groups=(("verbose", "quiet"),))
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
            groups=(("json", "csv"),),
            mutually_exclusive_groups=(("json", "csv"),),
        )
        custom_groups = [g for g in parser._action_groups if g.title not in {'Positional Arguments', 'options'}]
        all_custom_dests = {a.dest for g in custom_groups for a in g._group_actions}
        assert {"json", "csv"} <= all_custom_dests
        with pytest.raises(SystemExit):
            parser.parse_args(["--json", "--csv"])


class TestGroupHelpers:
    def test_validate_group_members_rejects_nonexistent_param(self) -> None:
        with pytest.raises(ValueError, match="nonexistent"):
            _validate_group_members(("verbose", "nonexistent"), all_param_names={"verbose"}, group_type="groups")

    def test_build_argument_group_targets(self) -> None:
        parser = argparse.ArgumentParser()
        target_for, argument_group_for = _build_argument_group_targets(
            parser,
            groups=(("src", "dst"),),
            all_param_names={"src", "dst", "recursive"},
        )
        assert set(target_for) == {"src", "dst"}
        assert set(argument_group_for) == {"src", "dst"}
        assert target_for["src"] is argument_group_for["src"]
        assert target_for["dst"] is argument_group_for["dst"]

    def test_build_argument_group_targets_rejects_duplicate_assignment(self) -> None:
        parser = argparse.ArgumentParser()
        with pytest.raises(ValueError, match="argument group 1 and argument group 2"):
            _build_argument_group_targets(
                parser,
                groups=(("verbose",), ("verbose",)),
                all_param_names={"verbose"},
            )

    def test_apply_mutex_group_targets(self) -> None:
        parser = argparse.ArgumentParser()
        target_for, argument_group_for = _build_argument_group_targets(
            parser,
            groups=(("json", "csv"),),
            all_param_names={"json", "csv", "plain"},
        )

        _apply_mutex_group_targets(
            parser,
            target_for=target_for,
            argument_group_for=argument_group_for,
            mutually_exclusive_groups=(("json", "csv"),),
            all_param_names={"json", "csv", "plain"},
        )

        assert target_for["json"] is target_for["csv"]
        assert isinstance(target_for["json"], argparse._MutuallyExclusiveGroup)

    def test_apply_mutex_group_targets_rejects_duplicate_assignment(self) -> None:
        parser = argparse.ArgumentParser()
        with pytest.raises(ValueError, match="multiple mutually exclusive groups"):
            _apply_mutex_group_targets(
                parser,
                target_for={},
                argument_group_for={},
                mutually_exclusive_groups=(("verbose",), ("verbose",)),
                all_param_names={"verbose"},
            )

    def test_apply_mutex_group_targets_rejects_cross_group_members(self) -> None:
        parser = argparse.ArgumentParser()
        _target_for, argument_group_for = _build_argument_group_targets(
            parser,
            groups=(("src",), ("dst",)),
            all_param_names={"src", "dst"},
        )

        with pytest.raises(ValueError, match="different argument groups"):
            _apply_mutex_group_targets(
                parser,
                target_for={},
                argument_group_for=argument_group_for,
                mutually_exclusive_groups=(("src", "dst"),),
                all_param_names={"src", "dst"},
            )


# ---------------------------------------------------------------------------
# _resolve_annotation: positional vs option classification + bool flag
# ---------------------------------------------------------------------------

_ARG_META = Argument(help_text="Name")
_OPT_META = Option("--color", "-c", help_text="Pick")


class TestResolveAnnotation:
    @pytest.mark.parametrize(
        ("annotation", "has_default", "expected_positional", "expected_bool_flag"),
        [
            pytest.param(str, False, True, False, id="plain_str"),
            pytest.param(str | None, False, False, False, id="optional_str"),
            pytest.param(Annotated[str, _ARG_META], False, True, False, id="annotated_argument"),
            pytest.param(Annotated[str, _OPT_META], False, False, False, id="annotated_option"),
            pytest.param(Annotated[str, "some doc"], False, True, False, id="annotated_no_meta"),
            pytest.param(str, True, False, False, id="has_default"),
            pytest.param(bool, True, False, True, id="bool_flag"),
        ],
    )
    def test_classification(self, annotation, has_default, expected_positional, expected_bool_flag) -> None:
        _kwargs, _meta, positional, is_bool_flag = _resolve_annotation(annotation, has_default=has_default)
        assert positional is expected_positional
        assert is_bool_flag is expected_bool_flag

    def test_optional_wrapping_annotated_with_none_inside(self) -> None:
        """Optional[Annotated[T | None, meta]] is allowed (inner type contains None)."""
        ann = Annotated[str | None, _OPT_META] | None
        _kwargs, meta, positional, _bf = _resolve_annotation(ann)
        assert meta is _OPT_META
        assert positional is False

    def test_typing_union_optional(self) -> None:
        ns: dict = {}
        exec("import typing; t = typing.Union[str, None]", ns)
        _kwargs, _meta, positional, _bool_flag = _resolve_annotation(ns["t"])
        assert positional is False

    def test_annotated_multiple_metadata_picks_first(self) -> None:
        meta1 = Argument(help_text="first")
        meta2 = Option("--x", help_text="second")
        kwargs, meta, _, _ = _resolve_annotation(Annotated[str, meta1, meta2])
        assert meta is meta1
        assert kwargs.get('help') == "first"


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
            pytest.param(list[set[int]], id="list_of_set"),
            pytest.param(set[list[str]], id="set_of_list"),
            pytest.param(tuple[list[int], ...], id="tuple_of_list"),
        ],
    )
    def test_nested_collection_raises(self, annotation) -> None:
        with pytest.raises(TypeError, match="Nested collections are not supported"):
            _resolve_annotation(annotation)

    @pytest.mark.parametrize(
        "annotation",
        [
            pytest.param(frozenset[str], id="frozenset"),
            pytest.param(dict[str, int], id="dict"),
        ],
    )
    def test_unsupported_collection_no_nargs(self, annotation) -> None:
        kwargs, _, _, _ = _resolve_annotation(annotation)
        assert 'nargs' not in kwargs
        assert 'action' not in kwargs

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
            patch('cmd2.annotated.get_origin', return_value=Union),
            patch('cmd2.annotated.get_args', return_value=(str,)),
            pytest.raises(TypeError, match="single-element Union"),
        ):
            _unwrap_optional(sentinel)


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------


class TestParseBool:
    @pytest.mark.parametrize("value", ['1', 'true', 'True', 't', 'yes', 'y', 'on'])
    def test_true(self, value) -> None:
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ['0', 'false', 'False', 'f', 'no', 'n', 'off'])
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

    def test_invalid(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError, match="invalid choice"):
            _make_literal_type(["fast", "slow"])("medium")

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
            pytest.param({'help_text': "Name"}, {'help': 'Name'}, id="help_text"),
            pytest.param({'metavar': "NAME"}, {'metavar': 'NAME'}, id="metavar"),
            pytest.param({'choices': ["a", "b"]}, {'choices': ['a', 'b']}, id="choices"),
            pytest.param({'table_columns': ("Name", "Age")}, {'table_columns': ("Name", "Age")}, id="table_columns"),
            pytest.param({'suppress_tab_hint': True}, {'suppress_tab_hint': True}, id="suppress_tab_hint"),
        ],
    )
    def test_to_kwargs(self, meta_kwargs, expected) -> None:
        assert Argument(**meta_kwargs).to_kwargs() == expected

    def test_nargs_not_in_to_kwargs(self) -> None:
        """nargs is set directly by the resolver, not via to_kwargs."""
        assert 'nargs' not in Argument(nargs=2).to_kwargs()

    def test_to_kwargs_preserves_empty_string(self) -> None:
        """Explicit empty string help_text should not be silently dropped."""
        assert Argument(help_text="").to_kwargs() == {'help': ''}

    def test_to_kwargs_preserves_empty_choices(self) -> None:
        """Explicit empty choices list should not be silently dropped."""
        assert Argument(choices=[]).to_kwargs() == {'choices': []}

    def test_option_excludes_names_action_required(self) -> None:
        opt = Option("--color", "-c", action="count", required=True, help_text="Pick")
        kwargs = opt.to_kwargs()
        assert 'names' not in kwargs
        assert 'action' not in kwargs
        assert 'required' not in kwargs
        assert kwargs['help'] == "Pick"

    def test_choices_provider_in_kwargs(self) -> None:
        def provider(cmd):
            return []

        assert Argument(choices_provider=provider).to_kwargs()['choices_provider'] is provider

    def test_completer_in_kwargs(self) -> None:
        assert Argument(completer=cmd2.Cmd.path_complete).to_kwargs()['completer'] is cmd2.Cmd.path_complete


# ---------------------------------------------------------------------------
# _CollectionCastingAction
# ---------------------------------------------------------------------------


class TestCollectionCastingAction:
    def test_casts_list_to_container(self) -> None:
        action = _CollectionCastingAction(
            option_strings=[],
            dest='items',
            nargs='+',
            container_factory=set,
        )
        ns = argparse.Namespace()
        action(argparse.ArgumentParser(), ns, ["a", "b", "a"])
        assert ns.items == {"a", "b"}

    def test_non_list_passthrough(self) -> None:
        action = _CollectionCastingAction(
            option_strings=[],
            dest='items',
            nargs='?',
            container_factory=set,
        )
        ns = argparse.Namespace()
        action(argparse.ArgumentParser(), ns, "single_value")
        assert ns.items == "single_value"


# ---------------------------------------------------------------------------
# _filtered_namespace_kwargs edge cases
# ---------------------------------------------------------------------------


class TestFilteredNamespaceKwargs:
    def test_excludes_subcmd_handler_key(self) -> None:
        from cmd2.annotated import _filtered_namespace_kwargs
        from cmd2.constants import NS_ATTR_SUBCMD_HANDLER

        ns = argparse.Namespace(**{NS_ATTR_SUBCMD_HANDLER: lambda: None, 'name': 'Alice'})
        result = _filtered_namespace_kwargs(ns)
        assert NS_ATTR_SUBCMD_HANDLER not in result
        assert result == {'name': 'Alice'}

    def test_excludes_subcommand_key(self) -> None:
        from cmd2.annotated import _filtered_namespace_kwargs

        ns = argparse.Namespace(subcommand='add', name='Alice')
        result = _filtered_namespace_kwargs(ns, exclude_subcommand=True)
        assert 'subcommand' not in result
        assert result == {'name': 'Alice'}


# ---------------------------------------------------------------------------
# _parse_positionals edge case
# ---------------------------------------------------------------------------


class TestParsePositionals:
    def test_skips_non_statement_next_arg(self) -> None:
        """When next_arg after Cmd is not Statement/str, loop continues."""
        from cmd2.decorators import _parse_positionals

        app = cmd2.Cmd()
        # Two Cmd-like objects: first has non-str next, second has str next
        result_cmd, result_stmt = _parse_positionals((app, 42, app, 'hello'))
        assert result_cmd is app
        assert result_stmt == 'hello'

    def test_matches_statement_type(self) -> None:
        """When next_arg is a Statement, it is accepted."""
        from cmd2.decorators import _parse_positionals
        from cmd2.parsing import Statement

        app = cmd2.Cmd()
        stmt = Statement('hello')
        result_cmd, result_stmt = _parse_positionals((app, stmt))
        assert result_cmd is app
        assert result_stmt is stmt


# ---------------------------------------------------------------------------
# Runtime coverage
# ---------------------------------------------------------------------------


class _Sport(str, enum.Enum):
    football = "football"
    basketball = "basketball"
    tennis = "tennis"


class _RuntimeAnnotatedApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self._items = ["apple", "banana", "cherry"]

    def item_choices(self) -> list[cmd2.CompletionItem]:
        return [cmd2.CompletionItem(item) for item in self._items]

    @cmd2.with_annotated
    def do_greet(self, name: str, count: int = 1) -> None:
        for _ in range(count):
            self.poutput(f"Hello {name}")

    @cmd2.with_annotated
    def do_add(self, a: int, b: int = 0) -> None:
        self.poutput(str(a + b))

    @cmd2.with_annotated
    def do_paint(
        self,
        item: str,
        color: Annotated[_Color, Option("--color", "-c", help_text="Color")] = _Color.blue,
        verbose: bool = False,
    ) -> None:
        msg = f"Painting {item} {color.value}"
        if verbose:
            msg += " (verbose)"
        self.poutput(msg)

    @cmd2.with_annotated
    def do_pick(self, item: Annotated[str, Argument(choices_provider=item_choices)]) -> None:
        self.poutput(f"Picked: {item}")

    @cmd2.with_annotated
    def do_open(self, path: Path) -> None:
        self.poutput(f"Opening: {path}")

    @cmd2.with_annotated
    def do_sport(self, sport: _Sport) -> None:
        self.poutput(f"Playing: {sport.value}")

    @cmd2.with_annotated(preserve_quotes=True)
    def do_raw(self, text: str) -> None:
        self.poutput(f"raw: {text}")


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
        ],
    )
    def test_command_execution(self, runtime_app, command, expected) -> None:
        out, _err = run_cmd(runtime_app, command)
        assert out == expected

    def test_help_shows_arguments(self, runtime_app) -> None:
        out, _ = run_cmd(runtime_app, "help greet")
        assert "name" in "\n".join(out).lower()

    def test_help_shows_option_help(self, runtime_app) -> None:
        out, _ = run_cmd(runtime_app, "help paint")
        help_text = "\n".join(out)
        assert "Color" in help_text or "color" in help_text


class TestRuntimeCompletion:
    def test_enum_completion(self, runtime_app) -> None:
        assert sorted(_complete_cmd(runtime_app, "paint wall --color ", "")) == ["blue", "green", "red"]

    def test_enum_completion_partial(self, runtime_app) -> None:
        assert _complete_cmd(runtime_app, "paint wall --color r", "r") == ["red"]

    def test_choices_provider_completion(self, runtime_app) -> None:
        assert sorted(_complete_cmd(runtime_app, "pick ", "")) == ["apple", "banana", "cherry"]

    def test_positional_enum_completion(self, runtime_app) -> None:
        assert _complete_cmd(runtime_app, "sport foot", "foot") == ["football"]


class _InferColor(str, enum.Enum):
    red = "red"
    green = "green"


class _RuntimeTypeInferenceApp(cmd2.Cmd):
    enum_override_choices: ClassVar[list[str]] = ["amber", "violet"]
    path_override_values: ClassVar[list[str]] = ["override-a", "override-b"]

    path_parser = Cmd2ArgumentParser()
    path_parser.add_argument("filepath", type=Path)

    @cmd2.with_argparser(path_parser)
    def do_read(self, args: argparse.Namespace) -> None:
        self.poutput(str(args.filepath))

    native_path_parser = Cmd2ArgumentParser()
    native_path_parser.add_argument("filepath", type=type(Path(".")))

    @cmd2.with_argparser(native_path_parser)
    def do_read_native(self, args: argparse.Namespace) -> None:
        self.poutput(str(args.filepath))

    enum_parser = Cmd2ArgumentParser()
    enum_parser.add_argument("color", type=_InferColor)

    @cmd2.with_argparser(enum_parser)
    def do_pick_color(self, args: argparse.Namespace) -> None:
        self.poutput(args.color.value)

    def enum_choices_override(self) -> list[cmd2.CompletionItem]:
        return [cmd2.CompletionItem(value) for value in self.enum_override_choices]

    enum_override_parser = Cmd2ArgumentParser()
    enum_override_parser.add_argument("color", type=_InferColor, choices_provider=enum_choices_override)

    @cmd2.with_argparser(enum_override_parser)
    def do_pick_color_override(self, args: argparse.Namespace) -> None:
        self.poutput(str(args.color))

    enum_converter_parser = Cmd2ArgumentParser()
    enum_converter_parser.add_argument("color", type=_make_enum_type(_InferColor))

    @cmd2.with_argparser(enum_converter_parser)
    def do_pick_color_converter(self, args: argparse.Namespace) -> None:
        self.poutput(args.color.value)

    bool_parser = Cmd2ArgumentParser()
    bool_parser.add_argument("enabled", type=_parse_bool)

    @cmd2.with_argparser(bool_parser)
    def do_set_flag(self, args: argparse.Namespace) -> None:
        self.poutput(str(args.enabled))

    def path_completer_override(self, text: str, line: str, begidx: int, endidx: int) -> cmd2.Completions:
        return self.basic_complete(text, line, begidx, endidx, self.path_override_values)

    path_override_parser = Cmd2ArgumentParser()
    path_override_parser.add_argument("filepath", type=Path, completer=path_completer_override)

    @cmd2.with_argparser(path_override_parser)
    def do_read_override(self, args: argparse.Namespace) -> None:
        self.poutput(str(args.filepath))


@pytest.fixture
def infer_app() -> _RuntimeTypeInferenceApp:
    app = _RuntimeTypeInferenceApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestTypeInferenceCompletion:
    """Runtime completion tests for type-inferred argparse argument types."""

    def test_enum_type_inference(self, infer_app) -> None:
        assert sorted(_complete_cmd(infer_app, "pick_color ", "")) == ["green", "red"]

    def test_enum_converter_type_inference(self, infer_app) -> None:
        assert sorted(_complete_cmd(infer_app, "pick_color_converter ", "")) == ["green", "red"]

    def test_path_type_inference(self, infer_app, tmp_path) -> None:
        test_file = tmp_path / "testfile.txt"
        test_file.touch()
        text = str(tmp_path) + "/"
        result_strings = _complete_cmd(infer_app, f"read {text}", text)
        assert len(result_strings) > 0
        assert any("testfile.txt" in item for item in result_strings)

    def test_native_path_subclass_type_inference(self, infer_app, tmp_path) -> None:
        test_file = tmp_path / "native-test.txt"
        test_file.touch()
        text = str(tmp_path) + "/"
        result_strings = _complete_cmd(infer_app, f"read_native {text}", text)
        assert len(result_strings) > 0
        assert any("native-test.txt" in item for item in result_strings)

    def test_bool_parser_type_inference(self, infer_app) -> None:
        assert sorted(_complete_cmd(infer_app, "set_flag ", "")) == sorted(
            ["true", "false", "yes", "no", "on", "off", "1", "0"]
        )

    def test_choices_provider_takes_precedence_over_enum_inference(self, infer_app) -> None:
        assert sorted(_complete_cmd(infer_app, "pick_color_override ", "")) == sorted(
            _RuntimeTypeInferenceApp.enum_override_choices
        )

    def test_completer_takes_precedence_over_path_inference(self, infer_app) -> None:
        assert sorted(_complete_cmd(infer_app, "read_override ", "")) == sorted(_RuntimeTypeInferenceApp.path_override_values)


class _AnnotatedCommandSet(cmd2.CommandSet):
    def __init__(self) -> None:
        super().__init__()
        self._sports = ["football", "baseball"]

    def sport_choices(self) -> list[cmd2.CompletionItem]:
        return [cmd2.CompletionItem(sport) for sport in self._sports]

    @cmd2.with_annotated
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

    @cmd2.with_annotated
    def do_greet(self, name: str, count: int = 1, loud: bool = False, *, keyword_arg: str | None = None) -> None:
        """Greet someone."""
        for _ in range(count):
            msg = f"Hello {name}"
            self.poutput(msg.upper() if loud else msg)
        if keyword_arg is not None:
            self.poutput(keyword_arg)

    @cmd2.with_annotated(with_unknown_args=True)
    def do_flex(self, name: str, _unknown: list[str] | None = None) -> None:
        self.poutput(f"name={name}")
        if _unknown:
            self.poutput(f"unknown={_unknown}")

    @cmd2.with_annotated(preserve_quotes=True)
    def do_raw(self, text: str) -> None:
        self.poutput(f"raw: {text}")

    @cmd2.with_annotated(ns_provider=namespace_provider)
    def do_ns_test(self, cmd2_statement=None) -> None:
        self.poutput("ok")

    @cmd2.with_annotated
    def do_prefixed(self, cmd2_mode: int = 1) -> None:
        self.poutput(f"cmd2_mode={cmd2_mode}")


class _GroupedParserApp(cmd2.Cmd):
    @cmd2.with_annotated(
        groups=(("local", "remote"), ("force", "dry_run")),
        mutually_exclusive_groups=(("local", "remote"), ("force", "dry_run")),
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
    return _IntegrationApp()


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
        assert any('error' in line.lower() or 'usage' in line.lower() for line in err)

    def test_no_args_raises_type_error(self, app) -> None:
        with pytest.raises(TypeError, match="Expected arguments"):
            app.do_greet()

    def test_with_unknown_args_requires_param(self) -> None:
        with pytest.raises(TypeError, match="_unknown"):

            @cmd2.with_annotated(with_unknown_args=True)
            def do_broken(self, name: str) -> None:
                pass

    def test_positional_only_unknown_rejected(self) -> None:
        with pytest.raises(TypeError, match="keyword-compatible"):

            @cmd2.with_annotated(with_unknown_args=True)
            def do_broken(self, _unknown: list[str], /) -> None:
                pass

    def test_ns_provider(self, app) -> None:
        out, _err = run_cmd(app, "ns_test")
        assert out == ["ok"]
        assert app.ns_calls == 1

    def test_cmd2_prefixed_param_is_preserved(self, app) -> None:
        out, _err = run_cmd(app, "prefixed --cmd2_mode 5")
        assert out == ["cmd2_mode=5"]

    def test_kwargs_passthrough(self, app) -> None:
        app.do_greet("Alice", keyword_arg="kwarg_value")

    def test_bare_call_decorator(self) -> None:
        """@with_annotated() with empty parens works same as @with_annotated."""

        class App(cmd2.Cmd):
            @cmd2.with_annotated()
            def do_echo(self, text: str) -> None:
                self.poutput(text)

        out, _err = run_cmd(App(), "echo hi")
        assert out == ["hi"]

    def test_missing_parser_raises(self, app) -> None:
        from unittest.mock import patch

        with (
            patch.object(app._command_parsers, 'get', return_value=None),
            pytest.raises(ValueError, match="No argument parser found"),
        ):
            app.do_greet("Alice")


class TestGroupedParserIntegration:
    def test_grouped_command_executes(self, grouped_app) -> None:
        out, _err = run_cmd(grouped_app, "transfer --local build.tar.gz --dry_run")
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
        assert "--dry_run" in help_text


# ---------------------------------------------------------------------------
# Subcommands: @with_annotated(base_command=True) + @with_annotated(subcommand_to=...)
# ---------------------------------------------------------------------------


class _SubcommandApp(cmd2.Cmd):
    # Level 1: base command
    @cmd2.with_annotated(base_command=True)
    def do_manage(self, cmd2_handler, verbose: bool = False) -> None:
        """Management command with subcommands."""
        if verbose:
            self.poutput("verbose mode")
        handler = cmd2_handler.get()
        if handler:
            handler()

    # Level 2: leaf subcommands
    @cmd2.with_annotated(subcommand_to='manage', help='add something')
    def manage_add(self, value: str) -> None:
        self.poutput(f"added: {value}")

    @cmd2.with_annotated(subcommand_to='manage', help='list things', aliases=['ls'])
    def manage_list(self) -> None:
        self.poutput("listing all")

    # Level 2: intermediate subcommand (also a base for level 3)
    @cmd2.with_annotated(subcommand_to='manage', base_command=True, help='manage members')
    def manage_member(self, cmd2_handler) -> None:
        handler = cmd2_handler.get()
        if handler:
            handler()

    # Level 3: nested subcommand
    @cmd2.with_annotated(subcommand_to='manage member', help='add a member')
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
        ],
    )
    def test_subcommand_executes(self, subcmd_app, command, expected) -> None:
        out, _err = run_cmd(subcmd_app, command)
        assert out == expected

    @pytest.mark.parametrize(
        "command",
        [
            pytest.param("manage", id="missing_subcmd"),
            pytest.param("manage delete", id="invalid_subcmd"),
            pytest.param("manage member", id="missing_nested_subcmd"),
        ],
    )
    def test_subcommand_errors(self, subcmd_app, command) -> None:
        _out, err = run_cmd(subcmd_app, command)
        assert any('error' in line.lower() or 'usage' in line.lower() or 'invalid' in line.lower() for line in err)

    def test_subcommand_help(self, subcmd_app) -> None:
        out, _err = run_cmd(subcmd_app, 'help manage')
        help_text = '\n'.join(out)
        assert 'add' in help_text
        assert 'list' in help_text
        assert 'member' in help_text


class TestSubcommandValidation:
    def test_base_command_positional_str_raises(self) -> None:
        """Positional str param conflicts with subcommand name."""
        with pytest.raises(TypeError, match="positional"):

            @cmd2.with_annotated(base_command=True)
            def do_bad(self, name: str, cmd2_handler) -> None:
                pass

    def test_base_command_positional_annotated_raises(self) -> None:
        """Explicit Argument() metadata forces positional -- conflict."""
        with pytest.raises(TypeError, match="positional"):

            @cmd2.with_annotated(base_command=True)
            def do_bad(self, a: Annotated[str, Argument(help_text="x")], cmd2_handler) -> None:
                pass

    def test_base_command_missing_handler_raises(self) -> None:
        with pytest.raises(TypeError, match="cmd2_handler"):

            @cmd2.with_annotated(base_command=True)
            def do_bad(self, verbose: bool = False) -> None:
                pass

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param({"help": "not allowed"}, id="help_only"),
            pytest.param({"aliases": ["x"]}, id="aliases_only"),
        ],
    )
    def test_subcmd_only_params_without_subcommand_to_raises(self, kwargs) -> None:
        with pytest.raises(TypeError, match="subcommand_to"):

            @cmd2.with_annotated(**kwargs)
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

            @cmd2.with_annotated(subcommand_to='team', **kwargs)
            def team_add(self, name: str, _unknown: list[str] | None = None) -> None:
                pass

    def test_subcommand_with_mutually_exclusive_groups(self) -> None:
        """mutually_exclusive_groups should work on subcommands."""

        class App(cmd2.Cmd):
            @cmd2.with_annotated(base_command=True)
            def do_fmt(self, cmd2_handler) -> None:
                handler = cmd2_handler.get()
                if handler:
                    handler()

            @cmd2.with_annotated(subcommand_to='fmt', help='output', mutually_exclusive_groups=(("json", "csv"),))
            def fmt_out(self, msg: str, json: bool = False, csv: bool = False) -> None:
                self.poutput(f"json={json} csv={csv} {msg}")

        app = App()
        out, _err = run_cmd(app, "fmt out hello --json")
        assert out == ["json=True csv=False hello"]
        _out, err = run_cmd(app, "fmt out hello --json --csv")
        assert any("not allowed" in line.lower() for line in err)

    def test_intermediate_base_command_positional_raises(self) -> None:
        with pytest.raises(TypeError, match="positional"):

            @cmd2.with_annotated(subcommand_to='team', base_command=True)
            def team_member(self, name: str, cmd2_handler) -> None:
                pass

    def test_intermediate_base_command_missing_handler_raises(self) -> None:
        with pytest.raises(TypeError, match="cmd2_handler"):

            @cmd2.with_annotated(subcommand_to='team', base_command=True)
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
            cmd2.with_annotated(subcommand_to=subcommand_to)(ns[func_name])

    def test_subcommand_attributes_set(self) -> None:
        from cmd2 import constants

        @cmd2.with_annotated(subcommand_to='team', help='create', aliases=['c'])
        def team_create(self, name: str) -> None: ...

        assert getattr(team_create, constants.SUBCMD_ATTR_COMMAND) == 'team'
        assert getattr(team_create, constants.SUBCMD_ATTR_NAME) == 'create'
        assert getattr(team_create, constants.SUBCMD_ATTR_ADD_PARSER_KWARGS) == {'help': 'create', 'aliases': ['c']}
        parser = getattr(team_create, constants.CMD_ATTR_ARGPARSER)()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_subcommand_without_help(self) -> None:
        """Subcommand with no help or aliases -- covers the None/empty branches."""
        from cmd2 import constants

        @cmd2.with_annotated(subcommand_to='team')
        def team_delete(self) -> None: ...

        assert getattr(team_delete, constants.SUBCMD_ATTR_ADD_PARSER_KWARGS) == {}
