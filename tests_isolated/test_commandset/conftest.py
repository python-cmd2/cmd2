"""Cmd2 unit/functional testing"""

import sys
from contextlib import (
    redirect_stderr,
    redirect_stdout,
)
from typing import (
    Optional,
    Union,
)
from unittest import (
    mock,
)

import pytest
from cmd2_ext_test import (
    ExternalTestMixin,
)

import cmd2
from cmd2.rl_utils import (
    readline,
)
from cmd2.utils import (
    StdSim,
)


def verify_help_text(
    cmd2_app: cmd2.Cmd, help_output: Union[str, list[str]], verbose_strings: Optional[list[str]] = None
) -> None:
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


# Help text for the history command
HELP_HISTORY = """Usage: history [-h] [-r | -e | -o FILE | -t TRANSCRIPT_FILE | -c] [-s] [-x]
               [-v] [-a]
               [arg]

View, run, edit, save, or clear previously entered commands

positional arguments:
  arg                   empty               all history items
                        a                   one history item by number
                        a..b, a:b, a:, ..b  items by indices (inclusive)
                        string              items containing string
                        /regex/             items matching regular expression

optional arguments:
  -h, --help            show this help message and exit
  -r, --run             run selected history items
  -e, --edit            edit and then run selected history items
  -o, --output_file FILE
                        output commands to a script file, implies -s
  -t, --transcript TRANSCRIPT_FILE
                        output commands and results to a transcript file,
                        implies -s
  -c, --clear           clear all history

formatting:
  -s, --script          output commands in script format, i.e. without command
                        numbers
  -x, --expanded        output fully parsed commands with any shortcuts, aliases, and macros expanded
  -v, --verbose         display history and include expanded commands if they
                        differ from the typed command
  -a, --all             display all commands, including ones persisted from
                        previous sessions
"""

# Output from the shortcuts command with default built-in shortcuts
SHORTCUTS_TXT = """Shortcuts for other commands:
!: shell
?: help
@: run_script
@@: _relative_run_script
"""


def normalize(block):
    """Normalize a block of text to perform comparison.

    Strip newlines from the very beginning and very end  Then split into separate lines and strip trailing whitespace
    from each line.
    """
    assert isinstance(block, str)
    block = block.strip('\n')
    return [line.rstrip() for line in block.splitlines()]


def run_cmd(app, cmd):
    """Clear out and err StdSim buffers, run the command, and return out and err"""
    saved_sysout = sys.stdout
    sys.stdout = app.stdout

    # This will be used to capture app.stdout and sys.stdout
    copy_cmd_stdout = StdSim(app.stdout)

    # This will be used to capture sys.stderr
    copy_stderr = StdSim(sys.stderr)

    try:
        app.stdout = copy_cmd_stdout
        with redirect_stdout(copy_cmd_stdout), redirect_stderr(copy_stderr):
            app.onecmd_plus_hooks(cmd)
    finally:
        app.stdout = copy_cmd_stdout.inner_stream
        sys.stdout = saved_sysout

    out = copy_cmd_stdout.getvalue()
    err = copy_stderr.getvalue()
    return normalize(out), normalize(err)


@pytest.fixture
def base_app():
    return cmd2.Cmd()


# These are odd file names for testing quoting of them
odd_file_names = ['nothingweird', 'has   spaces', '"is_double_quoted"', "'is_single_quoted'"]


def complete_tester(text: str, line: str, begidx: int, endidx: int, app) -> Optional[str]:
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

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    # Run the readline tab completion function with readline mocks in place
    with (
        mock.patch.object(readline, 'get_line_buffer', get_line),
        mock.patch.object(readline, 'get_begidx', get_begidx),
        mock.patch.object(readline, 'get_endidx', get_endidx),
    ):
        return app.complete(text, 0)


class WithCommandSets(ExternalTestMixin, cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


@pytest.fixture
def command_sets_app():
    return WithCommandSets()


@pytest.fixture
def command_sets_manual():
    return WithCommandSets(auto_load_commands=False)
