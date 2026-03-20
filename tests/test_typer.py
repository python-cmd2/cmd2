from __future__ import annotations

from typing import Annotated

import pytest

import cmd2
from cmd2 import utils

from .conftest import run_cmd

typer = pytest.importorskip("typer")


def _name_complete(incomplete: str):
    return [name for name in ["Alice", "Bob"] if name.startswith(incomplete)]


def _choice_complete(incomplete: str):
    return [item for item in ["alpha", "beta", "gamma"] if item.startswith(incomplete)]


def _second_choice_complete(incomplete: str):
    return [item for item in ["azure", "beige"] if item.startswith(incomplete)]


class TyperCommandSet(cmd2.CommandSet):
    @cmd2.with_typer
    def do_scale(
        self,
        value: int,
        factor: Annotated[int, typer.Option("--factor")] = 2,
    ) -> None:
        self._cmd.poutput(str(value * factor))


class TyperApp(cmd2.Cmd):
    @cmd2.with_typer
    def do_add(
        self,
        a: int,
        b: Annotated[int, typer.Option("--b")] = 2,
    ) -> None:
        self.poutput(str(a + b))

    @cmd2.with_typer
    def do_echo(self, text: Annotated[str, typer.Argument()]) -> None:
        self.poutput(text)

    @cmd2.with_typer(preserve_quotes=True)
    def do_wrap(self, text: Annotated[str, typer.Argument()]) -> None:
        self.poutput(text)

    @cmd2.with_typer
    def do_repeat(
        self,
        words: Annotated[list[str], typer.Argument()],
        shout: Annotated[bool, typer.Option("--shout")] = False,
    ) -> None:
        output = ' '.join(words)
        self.poutput(output.upper() if shout else output)

    @cmd2.with_typer
    def do_keyword(
        self,
        text: Annotated[str, typer.Argument()],
        *,
        keyword_arg: str | None = None,
    ) -> None:
        self.poutput(text)
        if keyword_arg is not None:
            print(keyword_arg)

    @cmd2.with_typer
    def do_documented(self, value: Annotated[str, typer.Argument()]) -> None:
        """Documented typer command."""
        self.poutput(value)

    @cmd2.with_typer
    def do_greet(
        self,
        name: Annotated[str, typer.Option("--name", autocompletion=_name_complete)] = "",
    ) -> None:
        self.poutput(f"hi {name}")

    @cmd2.with_typer
    def do_choose(
        self,
        item: Annotated[str, typer.Argument(autocompletion=_choice_complete)],
    ) -> None:
        self.poutput(item)

    @cmd2.with_typer
    def do_pair(
        self,
        first: Annotated[str, typer.Argument(autocompletion=_choice_complete)],
        second: Annotated[str, typer.Argument(autocompletion=_second_choice_complete)],
    ) -> None:
        self.poutput(f"{first} {second}")


@pytest.fixture
def typer_app() -> TyperApp:
    return TyperApp()


# ---------------------------------------------------------------------------
# Execution tests (parameterized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cmd_input", "expected"),
    [
        pytest.param('add 2 --b 3', ['5'], id="basic_execution"),
        pytest.param('add 2', ['4'], id="option_default"),
        pytest.param('echo "hello there"', ['hello there'], id="remove_quotes"),
        pytest.param('wrap "hello there"', ['"hello there"'], id="preserve_quotes"),
        pytest.param('repeat "hello  there" "rick & morty"', ['hello  there rick & morty'], id="multiple_quoted_args"),
        pytest.param("repeat 'This  is a' --shout test of the system", ['THIS  IS A TEST OF THE SYSTEM'], id="midline_option"),
    ],
)
def test_typer_execution(typer_app: TyperApp, cmd_input: str, expected: list[str]) -> None:
    out, _err = run_cmd(typer_app, cmd_input)
    assert out == expected


def test_typer_invalid_syntax(typer_app: TyperApp) -> None:
    _out, err = run_cmd(typer_app, 'add "')
    assert err[0] == 'Invalid syntax: No closing quotation'


def test_typer_with_no_args(typer_app: TyperApp) -> None:
    with pytest.raises(TypeError) as excinfo:
        typer_app.do_add()
    assert 'Expected arguments' in str(excinfo.value)


def test_typer_kwargs_passthrough(typer_app: TyperApp, capsys: pytest.CaptureFixture[str]) -> None:
    typer_app.do_keyword('hello', keyword_arg='foo')
    out, _err = capsys.readouterr()
    assert out == 'foo\n'


def test_typer_parse_error_stays_in_repl(typer_app: TyperApp, capsys: pytest.CaptureFixture[str]) -> None:
    stop = typer_app.onecmd_plus_hooks('add 2 3')

    assert stop is False
    assert 'Got unexpected extra argument (3)' in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Help tests
# ---------------------------------------------------------------------------


def test_typer_help_uses_app_stdout(typer_app: TyperApp, capsys: pytest.CaptureFixture[str]) -> None:
    typer_app.stdout = utils.StdSim(typer_app.stdout)

    typer_app.onecmd_plus_hooks('help add')

    out = typer_app.stdout.getvalue()
    assert 'Usage: add' in out
    assert '--b' in out
    assert capsys.readouterr().out == ''


def test_typer_help_uses_docstring(typer_app: TyperApp) -> None:
    out, _err = run_cmd(typer_app, 'help documented')
    assert any('Usage: documented' in line for line in out)
    assert any('Documented typer command.' in line for line in out)


def test_typer_help_prog_name(typer_app: TyperApp) -> None:
    out, _err = run_cmd(typer_app, 'help add')
    usage_line = next(line for line in out if 'Usage: add' in line)
    assert usage_line.strip().startswith('Usage: add')


# ---------------------------------------------------------------------------
# Completion tests (parameterized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "text", "expected"),
    [
        pytest.param('greet --n', '--n', ('--name',), id="option_name"),
        pytest.param('greet --name A', 'A', ('Alice',), id="option_value"),
        pytest.param('greet --name ', '', ('Alice', 'Bob'), id="option_blank_value"),
        pytest.param('choose a', 'a', ('alpha',), id="positional"),
        pytest.param('pair alpha a', 'a', ('azure',), id="second_positional"),
        pytest.param('greet --name Z', 'Z', (), id="no_results"),
    ],
)
def test_typer_completion(typer_app: TyperApp, line: str, text: str, expected: tuple[str, ...]) -> None:
    endidx = len(line)
    begidx = endidx - len(text)
    completions = typer_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == expected


# ---------------------------------------------------------------------------
# CommandSet tests
# ---------------------------------------------------------------------------


def test_typer_commandset_binding() -> None:
    app = TyperApp(command_sets=[TyperCommandSet()])
    out, err = run_cmd(app, 'scale 3 --factor 4')
    assert out == ['12']
    assert err == []


def test_typer_commandset_help() -> None:
    app = TyperApp(command_sets=[TyperCommandSet()])
    out, _err = run_cmd(app, 'help scale')
    assert any('Usage: scale' in line for line in out)
    assert any('--factor' in line for line in out)


# ---------------------------------------------------------------------------
# Subcommand tests
# ---------------------------------------------------------------------------


class TyperSubcommandSet(cmd2.CommandSet):
    base_app = typer.Typer(help='Base command help')
    admin_app = typer.Typer(help='Admin command help')

    @base_app.command('foo')
    def base_foo(
        self,
        y: Annotated[float, typer.Argument()],
        x: Annotated[int, typer.Option('--x', '-x')] = 1,
    ) -> None:
        self._cmd.poutput(str(x * y))

    @admin_app.command('bar')
    def base_bar(self, z: Annotated[str, typer.Argument()]) -> None:
        self._cmd.poutput(f'(({z}))')

    @admin_app.command('lookup')
    def admin_lookup(
        self,
        name: Annotated[str, typer.Option('--name', autocompletion=_name_complete)] = '',
    ) -> None:
        self._cmd.poutput(name)

    base_app.add_typer(admin_app, name='admin')

    @cmd2.with_typer(base_app)
    def do_base(self) -> None:
        pass


@pytest.fixture
def subcmd_app() -> TyperApp:
    return TyperApp(command_sets=[TyperSubcommandSet()])


@pytest.mark.parametrize(
    ("cmd_input", "expected"),
    [
        pytest.param('base foo --x 2 5.0', ['10.0'], id="foo"),
        pytest.param('base admin bar baz', ['((baz))'], id="admin_bar"),
    ],
)
def test_typer_subcommand_execution(subcmd_app: TyperApp, cmd_input: str, expected: list[str]) -> None:
    out, err = run_cmd(subcmd_app, cmd_input)
    assert out == expected
    assert err == []


def test_typer_subcommand_invalid(subcmd_app: TyperApp) -> None:
    _out, err = run_cmd(subcmd_app, 'base baz')
    assert any(line.startswith('Usage: base') for line in err)
    assert any("No such command 'baz'" in line for line in err)


@pytest.mark.parametrize(
    ("cmd_input", "expected_strings"),
    [
        pytest.param('help base', ['Usage: base', 'Base command help', 'foo', 'admin'], id="base_help"),
        pytest.param('help base foo', ['Usage: base foo'], id="foo_help"),
        pytest.param('help base admin bar', ['Usage: base admin bar'], id="admin_bar_help"),
        pytest.param('help base baz', ['Usage: base', 'Base command help'], id="invalid_help_fallback"),
    ],
)
def test_typer_subcommand_help(subcmd_app: TyperApp, cmd_input: str, expected_strings: list[str]) -> None:
    out, _err = run_cmd(subcmd_app, cmd_input)
    for s in expected_strings:
        assert any(s in line for line in out)


def test_typer_subcommand_parse_error_stays_in_repl(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = TyperApp(command_sets=[TyperSubcommandSet()])

    stop = app.onecmd_plus_hooks('base foo --x 2')

    assert stop is False
    assert 'Missing argument' in capsys.readouterr().err


@pytest.mark.parametrize(
    ("line", "text", "expected_in"),
    [
        pytest.param('base a', 'a', ['admin'], id="subcommand_prefix"),
        pytest.param('base admin b', 'b', ['bar'], id="nested_subcommand_prefix"),
        pytest.param('base ', '', ['foo', 'admin'], id="blank_subcommand"),
        pytest.param('base admin ', '', ['bar', 'lookup'], id="blank_nested_subcommand"),
        pytest.param('base admin lookup --n', '--n', ['--name'], id="subcmd_option_name"),
        pytest.param('base admin lookup --name A', 'A', ['Alice'], id="subcmd_option_value"),
    ],
)
def test_typer_subcommand_completion(subcmd_app: TyperApp, line: str, text: str, expected_in: list[str]) -> None:
    endidx = len(line)
    begidx = endidx - len(text)
    completions = subcmd_app.complete(text, line, begidx, endidx)
    completion_strings = completions.to_strings()
    for item in expected_in:
        assert item in completion_strings
