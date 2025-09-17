"""Cmd2 unit/functional testing"""

import argparse
import sys
from collections.abc import Callable
from contextlib import redirect_stderr
from typing import (
    TYPE_CHECKING,
    ParamSpec,
    TextIO,
    TypeVar,
    cast,
)
from unittest import mock

import pytest

import cmd2
from cmd2 import rich_utils as ru
from cmd2.rl_utils import readline
from cmd2.utils import StdSim

# For type hinting decorators
P = ParamSpec('P')
T = TypeVar('T')


def verify_help_text(cmd2_app: cmd2.Cmd, help_output: str | list[str], verbose_strings: list[str] | None = None) -> None:
    """This function verifies that all expected commands are present in the help text.

    :param cmd2_app: instance of cmd2.Cmd
    :param help_output: output of help, either as a string or list of strings
    :param verbose_strings: optional list of verbose strings to search for
    """
    help_text = help_output if isinstance(help_output, str) else ''.join(help_output)
    commands = cmd2_app.get_visible_commands()
    for command in commands:
        assert command in help_text

    if verbose_strings:
        for verbose_string in verbose_strings:
            assert verbose_string in help_text


# Output from the shortcuts command with default built-in shortcuts
SHORTCUTS_TXT = """Shortcuts for other commands:
!: shell
?: help
@: run_script
@@: _relative_run_script
"""


def normalize(block: str) -> list[str]:
    """Normalize a block of text to perform comparison.

    Strip newlines from the very beginning and very end  Then split into separate lines and strip trailing whitespace
    from each line.
    """
    assert isinstance(block, str)
    block = block.strip('\n')
    return [line.rstrip() for line in block.splitlines()]


def run_cmd(app: cmd2.Cmd, cmd: str) -> tuple[list[str], list[str]]:
    """Clear out and err StdSim buffers, run the command, and return out and err"""

    # Only capture sys.stdout if it's the same stream as self.stdout
    stdouts_match = app.stdout == sys.stdout

    # This will be used to capture app.stdout and sys.stdout
    copy_cmd_stdout = StdSim(cast(TextIO, app.stdout))

    # This will be used to capture sys.stderr
    copy_stderr = StdSim(sys.stderr)

    try:
        app.stdout = cast(TextIO, copy_cmd_stdout)
        if stdouts_match:
            sys.stdout = app.stdout
        with redirect_stderr(cast(TextIO, copy_stderr)):
            app.onecmd_plus_hooks(cmd)
    finally:
        app.stdout = cast(TextIO, copy_cmd_stdout.inner_stream)
        if stdouts_match:
            sys.stdout = app.stdout

    out = copy_cmd_stdout.getvalue()
    err = copy_stderr.getvalue()
    return normalize(out), normalize(err)


@pytest.fixture
def base_app() -> cmd2.Cmd:
    return cmd2.Cmd(include_py=True, include_ipy=True)


def with_ansi_style(style: ru.AllowStyle) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator which sets ru.ALLOW_STYLE before a function runs and restores it when it's done."""

    def arg_decorator(func: Callable[P, T]) -> Callable[P, T]:
        import functools

        @functools.wraps(func)
        def cmd_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            old = ru.ALLOW_STYLE
            ru.ALLOW_STYLE = style
            try:
                retval = func(*args, **kwargs)
            finally:
                ru.ALLOW_STYLE = old
            return retval

        return cmd_wrapper

    return arg_decorator


# These are odd file names for testing quoting of them
odd_file_names = ['nothingweird', 'has   spaces', '"is_double_quoted"', "'is_single_quoted'"]


def complete_tester(text: str, line: str, begidx: int, endidx: int, app: cmd2.Cmd) -> str | None:
    """This is a convenience function to test cmd2.complete() since
    in a unit test environment there is no actual console readline
    is monitoring. Therefore we use mock to provide readline data
    to complete().

    :param text: the string prefix we are attempting to match
    :param line: the current input line with leading whitespace removed
    :param begidx: the beginning index of the prefix text
    :param endidx: the ending index of the prefix text
    :param app: the cmd2 app that will run completions
    :return: The first matched string or None if there are no matches
             Matches are stored in app.completion_matches
             These matches also have been sorted by complete()
    """

    def get_line() -> str:
        return line

    def get_begidx() -> int:
        return begidx

    def get_endidx() -> int:
        return endidx

    # Run the readline tab completion function with readline mocks in place
    with (
        mock.patch.object(readline, 'get_line_buffer', get_line),
        mock.patch.object(readline, 'get_begidx', get_begidx),
        mock.patch.object(readline, 'get_endidx', get_endidx),
    ):
        return app.complete(text, 0)


def find_subcommand(action: argparse.ArgumentParser, subcmd_names: list[str]) -> argparse.ArgumentParser:
    if not subcmd_names:
        return action
    cur_subcmd = subcmd_names.pop(0)
    for sub_action in action._actions:
        if isinstance(sub_action, argparse._SubParsersAction):
            for choice_name, choice in sub_action.choices.items():
                if choice_name == cur_subcmd:
                    return find_subcommand(choice, subcmd_names)
            break
    raise ValueError(f"Could not find subcommand '{subcmd_names}'")


if TYPE_CHECKING:
    _Base = cmd2.Cmd
else:
    _Base = object


class ExternalTestMixin(_Base):
    """A cmd2 plugin (mixin class) that exposes an interface to execute application commands from python"""

    def __init__(self, *args, **kwargs):
        """Initializes the ExternalTestMixin.

        This class is intended to be used in multiple inheritance alongside `cmd2.Cmd` for an application class.
        When doing this multiple inheritance, it is imperative that this mixin class come first.

        :type self: cmd2.Cmd
        :param args: arguments to pass to the superclass
        :param kwargs: keyword arguments to pass to the superclass
        """
        # code placed here runs before cmd2 initializes
        super().__init__(*args, **kwargs)
        if not isinstance(self, cmd2.Cmd):
            raise TypeError('The ExternalTestMixin class is intended to be used in multiple inheritance with cmd2.Cmd')
        # code placed here runs after cmd2 initializes
        self._pybridge = cmd2.py_bridge.PyBridge(self)

    def app_cmd(self, command: str, echo: bool | None = None) -> cmd2.CommandResult:
        """
        Run the application command

        :param command: The application command as it would be written on the cmd2 application prompt
        :param echo: Flag whether the command's output should be echoed to stdout/stderr
        :return: A CommandResult object that captures stdout, stderr, and the command's result object
        """
        try:
            self._in_py = True
            return self._pybridge(command, echo=echo)

        finally:
            self._in_py = False

    def fixture_setup(self):
        """Replicates the behavior of `cmdloop()` to prepare the application state for testing.

        This method runs all preloop hooks and the preloop method to ensure the
        application is in the correct state before running a test.

        :type self: cmd2.Cmd
        """

        for func in self._preloop_hooks:
            func()
        self.preloop()

    def fixture_teardown(self):
        """Replicates the behavior of `cmdloop()` to tear down the application after a test.

        This method runs all postloop hooks and the postloop method to clean up
        the application state and ensure test isolation.

        :type self: cmd2.Cmd
        """
        for func in self._postloop_hooks:
            func()
        self.postloop()


class WithCommandSets(ExternalTestMixin, cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


@pytest.fixture
def autoload_command_sets_app():
    return WithCommandSets(auto_load_commands=True)


@pytest.fixture
def manual_command_sets_app():
    return WithCommandSets(auto_load_commands=False)
