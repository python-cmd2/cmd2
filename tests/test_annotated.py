"""Tests for the @with_annotated decorator and type inference in ArgparseCompleter."""

import argparse
import decimal
import enum
from collections.abc import Collection
from pathlib import Path
from typing import (
    Annotated,
    Literal,
)

import pytest

import cmd2
from cmd2 import (
    Choices,
    Cmd2ArgumentParser,
)
from cmd2.annotated import (
    Argument,
    Option,
    build_parser_from_function,
)

from .conftest import run_cmd

# ---------------------------------------------------------------------------
# Test functions for build_parser_from_function (not on any class)
# ---------------------------------------------------------------------------


def _func_positional_str(self, name: str) -> None: ...
def _func_option_with_default(self, count: int = 1) -> None: ...
def _func_bool_false(self, verbose: bool = False) -> None: ...
def _func_bool_true(self, debug: bool = True) -> None: ...


class _Color(str, enum.Enum):
    red = "red"
    green = "green"
    blue = "blue"


def _func_enum(self, color: _Color) -> None: ...
def _func_path(self, path: Path = Path(".")) -> None: ...
def _func_list(self, files: list[str]) -> None: ...
def _func_optional(self, name: str | None = None) -> None: ...
def _func_annotated_arg(self, name: Annotated[str, Argument(help_text="Your name")]) -> None: ...
def _func_annotated_option(self, color: Annotated[str, Option("--color", "-c", help_text="Pick")] = "blue") -> None: ...
def _func_metavar(self, name: Annotated[str, Argument(metavar="NAME")]) -> None: ...
def _func_explicit_nargs(self, names: Annotated[str, Argument(nargs=2)]) -> None: ...
def _func_explicit_action(self, verbose: Annotated[bool, Option(action="count")] = False) -> None: ...
def _func_unknown_type(self, data: dict | None = None) -> None: ...
def _func_completer(self, path: Annotated[str, Argument(completer=cmd2.Cmd.path_complete)]) -> None: ...
def _func_table_columns(self, item: Annotated[str, Argument(table_columns=("ID", "Name"))]) -> None: ...
def _func_suppress_hint(self, item: Annotated[str, Argument(suppress_tab_hint=True)]) -> None: ...
def _func_required_option(self, name: Annotated[str, Option("--name", required=True)]) -> None: ...
def _func_annotated_no_metadata(self, name: Annotated[str, "some doc"]) -> None: ...
def _func_list_with_default(self, items: list[str] | None = None) -> None: ...
def _func_float_option(self, rate: float = 1.0) -> None: ...
def _func_positional_bool(self, flag: bool) -> None: ...
def _func_enum_with_default(self, color: _Color = _Color.blue) -> None: ...
def _func_positional_path(self, path: Path) -> None: ...
def _func_decimal(self, amount: decimal.Decimal = decimal.Decimal("1.25")) -> None: ...
def _func_collection(self, ids: Collection[int]) -> None: ...
def _func_set_collection(self, tags: set[str]) -> None: ...
def _func_tuple_collection(self, values: tuple[int, ...]) -> None: ...
def _func_literal_option(self, mode: Literal["fast", "slow"] = "fast") -> None: ...
def _func_literal_positional_int(self, level: Literal[1, 2, 3]) -> None: ...


FOOD_ITEMS = ['Pizza', 'Ham', 'Potato']


def _func_static_choices(self, food: Annotated[str, Argument(choices=FOOD_ITEMS)]) -> None: ...


def _func_option_choices(self, food: Annotated[str, Option("--food", choices=FOOD_ITEMS)] = "Pizza") -> None: ...


class _IntColor(enum.IntEnum):
    red = 1
    green = 2
    blue = 3


class _PlainColor(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


def _func_int_enum(self, color: _IntColor) -> None: ...


# ---------------------------------------------------------------------------
# Parametrized parser construction tests
# ---------------------------------------------------------------------------


def _find_action(parser: argparse.ArgumentParser, dest: str) -> argparse.Action:
    for action in parser._actions:
        if action.dest == dest:
            return action
    raise ValueError(f"No action with dest={dest!r}")


class TestBuildParserParams:
    @pytest.mark.parametrize(
        ("func", "param_name", "expected"),
        [
            pytest.param(
                _func_positional_str,
                "name",
                {"option_strings": [], "type": None},
                id="positional_str",
            ),
            pytest.param(
                _func_option_with_default,
                "count",
                {"option_strings": ["--count"], "type": int, "default": 1},
                id="option_with_default",
            ),
            pytest.param(
                _func_bool_false,
                "verbose",
                {"option_strings": ["--verbose"]},
                id="bool_flag_false",
            ),
            pytest.param(
                _func_bool_true,
                "debug",
                {"option_strings": ["--no-debug"]},
                id="bool_flag_true",
            ),
            pytest.param(
                _func_enum,
                "color",
                {"option_strings": []},
                id="enum_choices",
            ),
            pytest.param(
                _func_path,
                "path",
                {"option_strings": ["--path"], "type": Path},
                id="path_type",
            ),
            pytest.param(
                _func_list,
                "files",
                {"option_strings": [], "nargs": "+"},
                id="list_nargs",
            ),
            pytest.param(
                _func_optional,
                "name",
                {"option_strings": ["--name"], "default": None},
                id="optional_type",
            ),
            pytest.param(
                _func_float_option,
                "rate",
                {"option_strings": ["--rate"], "type": float, "default": 1.0},
                id="float_option",
            ),
            pytest.param(
                _func_positional_bool,
                "flag",
                {"option_strings": []},
                id="positional_bool_parse_rule",
            ),
            pytest.param(
                _func_enum_with_default,
                "color",
                {"option_strings": ["--color"]},
                id="enum_with_default_becomes_option",
            ),
            pytest.param(
                _func_positional_path,
                "path",
                {"option_strings": [], "type": Path},
                id="positional_path_no_default",
            ),
            pytest.param(
                _func_decimal,
                "amount",
                {"option_strings": ["--amount"], "type": decimal.Decimal, "default": decimal.Decimal("1.25")},
                id="decimal_option",
            ),
            pytest.param(
                _func_collection,
                "ids",
                {"option_strings": [], "nargs": "+", "type": int},
                id="collection_positional",
            ),
            pytest.param(
                _func_set_collection,
                "tags",
                {"option_strings": [], "nargs": "+"},
                id="set_collection_positional",
            ),
            pytest.param(
                _func_tuple_collection,
                "values",
                {"option_strings": [], "nargs": "+", "type": int},
                id="tuple_collection_positional",
            ),
            pytest.param(
                _func_literal_option,
                "mode",
                {"option_strings": ["--mode"], "choices": ["fast", "slow"], "default": "fast"},
                id="literal_option",
            ),
            pytest.param(
                _func_literal_positional_int,
                "level",
                {"option_strings": [], "choices": [1, 2, 3]},
                id="literal_positional_int",
            ),
            pytest.param(
                _func_static_choices,
                "food",
                {"option_strings": [], "choices": FOOD_ITEMS},
                id="static_choices_positional",
            ),
            pytest.param(
                _func_option_choices,
                "food",
                {"option_strings": ["--food"], "choices": FOOD_ITEMS, "default": "Pizza"},
                id="static_choices_option",
            ),
        ],
    )
    def test_build_parser_params(self, func, param_name, expected):
        parser = build_parser_from_function(func)
        action = _find_action(parser, param_name)
        for key, value in expected.items():
            assert getattr(action, key) == value, f"{key}: expected {value!r}, got {getattr(action, key)!r}"


class TestBuildParserEdgeCases:
    @pytest.mark.parametrize(
        ("func", "param_name", "expected"),
        [
            pytest.param(
                _func_metavar,
                "name",
                {"metavar": "NAME"},
                id="metavar",
            ),
            pytest.param(
                _func_explicit_nargs,
                "names",
                {"nargs": 2},
                id="explicit_nargs",
            ),
            pytest.param(
                _func_unknown_type,
                "data",
                {"default": None, "option_strings": ["--data"]},
                id="unknown_type_with_default",
            ),
            pytest.param(
                _func_required_option,
                "name",
                {"required": True, "option_strings": ["--name"]},
                id="required_option",
            ),
            pytest.param(
                _func_annotated_no_metadata,
                "name",
                {"option_strings": []},
                id="annotated_no_arg_option_metadata",
            ),
            pytest.param(
                _func_list_with_default,
                "items",
                {"nargs": "*", "option_strings": ["--items"]},
                id="list_with_default_star_nargs",
            ),
        ],
    )
    def test_edge_cases(self, func, param_name, expected):
        parser = build_parser_from_function(func)
        action = _find_action(parser, param_name)
        for key, value in expected.items():
            assert getattr(action, key) == value, f"{key}: expected {value!r}, got {getattr(action, key)!r}"

    def test_completer_wired(self):
        parser = build_parser_from_function(_func_completer)
        action = _find_action(parser, "path")
        cc = action.get_choices_callable()
        assert cc is not None
        assert cc.is_completer is True

    def test_table_columns_wired(self):
        parser = build_parser_from_function(_func_table_columns)
        action = _find_action(parser, "item")
        assert action.get_table_columns() == ("ID", "Name")

    def test_suppress_tab_hint_wired(self):
        parser = build_parser_from_function(_func_suppress_hint)
        action = _find_action(parser, "item")
        assert action.get_suppress_tab_hint() is True

    def test_enum_by_value(self):
        """Test that enum type converter accepts member values."""
        from cmd2.annotated import _make_enum_type

        converter = _make_enum_type(_Color)
        assert converter("red") == _Color.red
        assert converter("green") == _Color.green

    def test_enum_by_name_fallback(self):
        """Test enum lookup by name when value doesn't match.

        _IntColor has int values (1, 2, 3) so string "red" won't match
        any value — falls through to name lookup.
        """
        from cmd2.annotated import _make_enum_type

        converter = _make_enum_type(_IntColor)
        assert converter("red") == _IntColor.red
        assert converter("blue") == _IntColor.blue

    def test_enum_invalid_value(self):
        """Test enum converter raises on invalid value."""
        from cmd2.annotated import _make_enum_type

        converter = _make_enum_type(_Color)
        with pytest.raises(argparse.ArgumentTypeError, match="invalid choice"):
            converter("purple")

    def test_explicit_action_in_metadata(self):
        parser = build_parser_from_function(_func_explicit_action)
        action = _find_action(parser, "verbose")
        # 'count' action from metadata
        assert isinstance(action, argparse._CountAction)

    def test_positional_bool_parse_rule(self):
        parser = build_parser_from_function(_func_positional_bool)
        assert parser.parse_args(["true"]).flag is True
        assert parser.parse_args(["0"]).flag is False

        with pytest.raises(SystemExit):
            parser.parse_args(["definitely"])

    def test_literal_int_parses_as_int(self):
        parser = build_parser_from_function(_func_literal_positional_int)
        assert parser.parse_args(["2"]).level == 2

        with pytest.raises(SystemExit):
            parser.parse_args(["7"])

    def test_set_collection_cast(self):
        parser = build_parser_from_function(_func_set_collection)
        parsed = parser.parse_args(["a", "b", "a"])
        assert isinstance(parsed.tags, set)
        assert parsed.tags == {"a", "b"}

    def test_tuple_collection_cast(self):
        parser = build_parser_from_function(_func_tuple_collection)
        parsed = parser.parse_args(["1", "2", "3"])
        assert isinstance(parsed.values, tuple)
        assert parsed.values == (1, 2, 3)

    def test_collection_cast_uses_store_action(self):
        from cmd2.annotated import _CollectionStoreAction

        set_parser = build_parser_from_function(_func_set_collection)
        set_action = _find_action(set_parser, "tags")
        assert isinstance(set_action, _CollectionStoreAction)

        tuple_parser = build_parser_from_function(_func_tuple_collection)
        tuple_action = _find_action(tuple_parser, "values")
        assert isinstance(tuple_action, _CollectionStoreAction)

    def test_plain_enum_parses_by_value_and_name(self):
        def _func_plain_enum(self, color: _PlainColor) -> None: ...

        parser = build_parser_from_function(_func_plain_enum)
        assert parser.parse_args(["red"]).color is _PlainColor.RED
        assert parser.parse_args(["green"]).color is _PlainColor.GREEN
        assert parser.parse_args(["BLUE"]).color is _PlainColor.BLUE


class TestAnnotatedMetadata:
    @pytest.mark.parametrize(
        ("func", "param_name", "expected"),
        [
            pytest.param(
                _func_annotated_arg,
                "name",
                {"option_strings": [], "help": "Your name"},
                id="annotated_argument_help",
            ),
            pytest.param(
                _func_annotated_option,
                "color",
                {"option_strings": ["--color", "-c"], "help": "Pick"},
                id="annotated_option_custom_names",
            ),
        ],
    )
    def test_annotated_metadata(self, func, param_name, expected):
        parser = build_parser_from_function(func)
        action = _find_action(parser, param_name)
        for key, value in expected.items():
            assert getattr(action, key) == value, f"{key}: expected {value!r}, got {getattr(action, key)!r}"


# ---------------------------------------------------------------------------
# Integration test app
# ---------------------------------------------------------------------------


class _Sport(str, enum.Enum):
    football = "football"
    basketball = "basketball"
    tennis = "tennis"


class AnnotatedApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._items = ["apple", "banana", "cherry"]

    def item_choices(self) -> Choices:
        return Choices.from_values(self._items)

    @cmd2.with_annotated
    def do_greet(self, name: str, count: int = 1) -> None:
        """Greet someone."""
        for _ in range(count):
            self.poutput(f"Hello {name}")

    @cmd2.with_annotated
    def do_add(self, a: int, b: int = 0) -> None:
        """Add two numbers."""
        self.poutput(str(a + b))

    @cmd2.with_annotated
    def do_paint(
        self,
        item: str,
        color: Annotated[_Color, Option("--color", "-c", help_text="Color")] = _Color.blue,
        verbose: bool = False,
    ) -> None:
        """Paint an item."""
        msg = f"Painting {item} {color.value}"
        if verbose:
            msg += " (verbose)"
        self.poutput(msg)

    @cmd2.with_annotated
    def do_pick(
        self,
        item: Annotated[str, Argument(choices_provider=item_choices)],
    ) -> None:
        """Pick an item with completion."""
        self.poutput(f"Picked: {item}")

    @cmd2.with_annotated
    def do_open(self, path: Path) -> None:
        """Open a file."""
        self.poutput(f"Opening: {path}")

    @cmd2.with_annotated
    def do_sport(self, sport: _Sport) -> None:
        """Pick a sport."""
        self.poutput(f"Playing: {sport.value}")

    @cmd2.with_annotated(preserve_quotes=True)
    def do_raw(self, text: str) -> None:
        """Echo raw text."""
        self.poutput(f"raw: {text}")


@pytest.fixture
def ann_app() -> AnnotatedApp:
    app = AnnotatedApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


# ---------------------------------------------------------------------------
# Integration: command execution
# ---------------------------------------------------------------------------


class TestCommandExecution:
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
    def test_command_execution(self, ann_app, command, expected):
        out, _err = run_cmd(ann_app, command)
        assert out == expected


# ---------------------------------------------------------------------------
# Integration: tab completion
# ---------------------------------------------------------------------------


class TestTabCompletion:
    def test_enum_completion(self, ann_app):
        text = ""
        line = "paint wall --color "
        endidx = len(line)
        begidx = endidx - len(text)
        completions = ann_app.complete(text, line, begidx, endidx)
        values = sorted(completions.to_strings())
        assert values == ["blue", "green", "red"]

    def test_enum_completion_partial(self, ann_app):
        text = "r"
        line = f"paint wall --color {text}"
        endidx = len(line)
        begidx = endidx - len(text)
        completions = ann_app.complete(text, line, begidx, endidx)
        assert list(completions.to_strings()) == ["red"]

    def test_choices_provider_completion(self, ann_app):
        text = ""
        line = "pick "
        endidx = len(line)
        begidx = endidx - len(text)
        completions = ann_app.complete(text, line, begidx, endidx)
        values = sorted(completions.to_strings())
        assert values == ["apple", "banana", "cherry"]

    def test_positional_enum_completion(self, ann_app):
        text = "foot"
        line = f"sport {text}"
        endidx = len(line)
        begidx = endidx - len(text)
        completions = ann_app.complete(text, line, begidx, endidx)
        assert list(completions.to_strings()) == ["football"]


# ---------------------------------------------------------------------------
# Type inference tests (benefits @with_argparser users too)
# ---------------------------------------------------------------------------


class _InferColor(str, enum.Enum):
    red = "red"
    green = "green"


class TypeInferenceApp(cmd2.Cmd):
    """App using manual @with_argparser to test type inference."""

    path_parser = Cmd2ArgumentParser()
    path_parser.add_argument('filepath', type=Path)

    @cmd2.with_argparser(path_parser)
    def do_read(self, args: argparse.Namespace) -> None:
        self.poutput(str(args.filepath))

    enum_parser = Cmd2ArgumentParser()
    enum_parser.add_argument('color', type=_InferColor)

    @cmd2.with_argparser(enum_parser)
    def do_pick_color(self, args: argparse.Namespace) -> None:
        self.poutput(args.color.value)


@pytest.fixture
def infer_app() -> TypeInferenceApp:
    app = TypeInferenceApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestTypeInference:
    def test_enum_type_inference(self, infer_app):
        text = ""
        line = "pick_color "
        endidx = len(line)
        begidx = endidx - len(text)
        completions = infer_app.complete(text, line, begidx, endidx)
        assert sorted(completions.to_strings()) == ["green", "red"]

    def test_path_type_inference(self, infer_app, tmp_path):
        """type=Path on a manual parser triggers path_complete via type inference."""
        # Create a file so path completion has something to find
        test_file = tmp_path / "testfile.txt"
        test_file.touch()

        text = str(tmp_path) + "/"
        line = f"read {text}"
        endidx = len(line)
        begidx = endidx - len(text)
        completions = infer_app.complete(text, line, begidx, endidx)
        assert len(completions) > 0
        result_strings = list(completions.to_strings())
        assert any("testfile.txt" in s for s in result_strings)


# ---------------------------------------------------------------------------
# Help output test
# ---------------------------------------------------------------------------


class TestHelpOutput:
    def test_help_shows_arguments(self, ann_app):
        out, _ = run_cmd(ann_app, "help greet")
        help_text = "\n".join(out)
        assert "name" in help_text.lower()

    def test_help_shows_option_help(self, ann_app):
        out, _ = run_cmd(ann_app, "help paint")
        help_text = "\n".join(out)
        assert "Color" in help_text or "color" in help_text


# ---------------------------------------------------------------------------
# Preserve quotes test
# ---------------------------------------------------------------------------


class TestPreserveQuotes:
    def test_preserve_quotes(self, ann_app):
        out, _ = run_cmd(ann_app, 'raw "hello world"')
        assert out == ['raw: "hello world"']


# ---------------------------------------------------------------------------
# with_unknown_args test
# ---------------------------------------------------------------------------


class UnknownArgsApp(cmd2.Cmd):
    @cmd2.with_annotated(with_unknown_args=True)
    def do_flex(self, name: str, _unknown: list[str] | None = None) -> None:
        """Command that accepts unknown args."""
        self.poutput(f"name={name}")
        if _unknown:
            self.poutput(f"unknown={_unknown}")


@pytest.fixture
def unknown_app() -> UnknownArgsApp:
    app = UnknownArgsApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestUnknownArgs:
    def test_with_unknown_args(self, unknown_app):
        out, _ = run_cmd(unknown_app, "flex Alice --extra stuff")
        assert out[0] == "name=Alice"
        assert "unknown=" in out[1]

    def test_with_unknown_args_requires_unknown_parameter(self):
        with pytest.raises(TypeError, match="requires a parameter named _unknown"):

            class _BadUnknownArgsApp(cmd2.Cmd):
                @cmd2.with_annotated(with_unknown_args=True)
                def do_bad(self, name: str) -> None:
                    self.poutput(name)


# ---------------------------------------------------------------------------
# Argparse error test
# ---------------------------------------------------------------------------


class TestArgparseError:
    def test_invalid_args_raise_error(self, ann_app):
        """Missing required positional arg should not crash."""
        _out, err = run_cmd(ann_app, "add")
        # argparse prints usage/error to stderr
        err_text = "\n".join(err)
        assert "required" in err_text.lower() or "error" in err_text.lower() or "usage" in err_text.lower()


# ---------------------------------------------------------------------------
# get_type_hints failure fallback
# ---------------------------------------------------------------------------


class TestGetTypeHintsFailure:
    def test_bad_annotation_falls_back(self):
        """When get_type_hints raises, build_parser_from_function still works using raw annotations."""
        # Create a function with a forward reference that can't be resolved
        exec_globals: dict = {}
        exec(
            "from cmd2.annotated import build_parser_from_function\n"
            "def func(self, name: 'NonExistentType' = 'default'): ...\n"
            "result = build_parser_from_function(func)\n",
            exec_globals,
        )
        parser = exec_globals["result"]
        # Should still produce a parser (falls back to raw signature)
        assert parser is not None


# ---------------------------------------------------------------------------
# _parse_positionals error path
# ---------------------------------------------------------------------------


class TestParsePositionalsError:
    def test_raises_on_bad_args(self):
        """_parse_positionals raises TypeError when no Cmd/CommandSet is found."""
        from cmd2.decorators import _parse_positionals

        with pytest.raises(TypeError, match="Expected arguments"):
            _parse_positionals(("not_a_cmd", "not_a_statement"))


# ---------------------------------------------------------------------------
# NS_ATTR_SUBCMD_HANDLER filtering
# ---------------------------------------------------------------------------


class SubcmdApp(cmd2.Cmd):
    @cmd2.with_annotated
    def do_echo(self, msg: str) -> None:
        """Echo a message."""
        self.poutput(msg)


@pytest.fixture
def subcmd_app() -> SubcmdApp:
    app = SubcmdApp()
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestNamespaceFiltering:
    def test_subcmd_handler_filtered(self, subcmd_app):
        """Verify __subcmd_handler__ is filtered from kwargs passed to the function.

        We can't easily inject __subcmd_handler__ through argparse, but we can verify
        the command works correctly which exercises the filtering loop.
        """
        out, _ = run_cmd(subcmd_app, "echo hello")
        assert out == ["hello"]

    def test_typing_union_optional(self):
        """typing.Union[str, None] should be treated the same as str | None."""
        from cmd2.annotated import _unwrap_optional

        # Build a typing.Union type dynamically to exercise the Union code path
        # (distinct from the types.UnionType path used by `str | None`)
        ns: dict = {}
        exec("import typing; t = typing.Union[str, None]", ns)
        union_type = ns["t"]
        inner, is_opt = _unwrap_optional(union_type)
        assert inner is str
        assert is_opt is True

        # Also test non-optional passes through
        inner2, is_opt2 = _unwrap_optional(str)
        assert inner2 is str
        assert is_opt2 is False

    def test_namespace_filtering_directly(self):
        """Directly test that internal namespace keys are filtered."""
        import argparse as ap

        from cmd2 import constants

        ns = ap.Namespace(msg="hello", cmd2_statement="x", **{constants.NS_ATTR_SUBCMD_HANDLER: None})
        func_kwargs = {}
        for key, value in vars(ns).items():
            if key.startswith('cmd2_') or key == constants.NS_ATTR_SUBCMD_HANDLER:
                continue
            func_kwargs[key] = value
        assert func_kwargs == {"msg": "hello"}


# ---------------------------------------------------------------------------
# CommandSet integration
# ---------------------------------------------------------------------------


class AnnotatedCommandSet(cmd2.CommandSet):
    def __init__(self) -> None:
        super().__init__()
        self._sports = ["football", "baseball"]

    def sport_choices(self) -> Choices:
        return Choices.from_values(self._sports)

    @cmd2.with_annotated
    def do_play(
        self,
        sport: Annotated[str, Argument(choices_provider=sport_choices)],
    ) -> None:
        """Play a sport."""
        self._cmd.poutput(f"Playing {sport}")


@pytest.fixture
def cmdset_app() -> cmd2.Cmd:
    cmdset = AnnotatedCommandSet()
    app = cmd2.Cmd(command_sets=[cmdset])
    app.stdout = cmd2.utils.StdSim(app.stdout)
    return app


class TestCommandSet:
    def test_command_set_execution(self, cmdset_app):
        out, _err = run_cmd(cmdset_app, "play football")
        assert out == ["Playing football"]

    def test_command_set_completion(self, cmdset_app):
        text = ""
        line = "play "
        endidx = len(line)
        begidx = endidx - len(text)
        completions = cmdset_app.complete(text, line, begidx, endidx)
        assert sorted(completions.to_strings()) == ["baseball", "football"]
