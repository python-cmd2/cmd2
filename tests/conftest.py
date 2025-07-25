"""Cmd2 unit/functional testing"""

import argparse
import sys
from contextlib import redirect_stderr
from typing import (
    Optional,
    Union,
)
from unittest import (
    mock,
)

import pytest

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


# Help text for the history command (Generated when terminal width is 80)
HELP_HISTORY = """Usage: history [-h] [-r | -e | -o FILE | -t TRANSCRIPT_FILE | -c] [-s] [-x]
               [-v] [-a]
               [arg]

View, run, edit, save, or clear previously entered commands.

Positional Arguments:
  arg                   empty               all history items
                        a                   one history item by number
                        a..b, a:b, a:, ..b  items by indices (inclusive)
                        string              items containing string
                        /regex/             items matching regular expression

Optional Arguments:
  -h, --help            show this help message and exit
  -r, --run             run selected history items
  -e, --edit            edit and then run selected history items
  -o, --output_file FILE
                        output commands to a script file, implies -s
  -t, --transcript TRANSCRIPT_FILE
                        create a transcript file by re-running the commands, implies both -r and -s
  -c, --clear           clear all history

Formatting:
  -s, --script          output commands in script format, i.e. without command numbers
  -x, --expanded        output fully parsed commands with shortcuts, aliases, and macros expanded
  -v, --verbose         display history and include expanded commands if they differ from the typed command
  -a, --all             display all commands, including ones persisted from previous sessions
"""

# Output from the shortcuts command with default built-in shortcuts
SHORTCUTS_TXT = """Shortcuts for other commands:
!: shell
?: help
@: run_script
@@: _relative_run_script
"""

# Output from the set command
SET_TXT = (
    "Name                    Value                           Description                                                 \n"
    "====================================================================================================================\n"
    "allow_style             Terminal                        Allow ANSI text style sequences in output (valid values:    \n"
    "                                                        Always, Never, Terminal)                                    \n"
    "always_show_hint        False                           Display tab completion hint even when completion suggestions\n"
    "                                                        print                                                       \n"
    "debug                   False                           Show full traceback on exception                            \n"
    "echo                    False                           Echo command issued into output                             \n"
    "editor                  vim                             Program used by 'edit'                                      \n"
    "feedback_to_output      False                           Include nonessentials in '|', '>' results                   \n"
    "max_completion_items    50                              Maximum number of CompletionItems to display during tab     \n"
    "                                                        completion                                                  \n"
    "quiet                   False                           Don't print nonessential feedback                           \n"
    "scripts_add_to_history  True                            Scripts and pyscripts add commands to history               \n"
    "timing                  False                           Report execution times                                      \n"
)


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

    # Only capture sys.stdout if it's the same stream as self.stdout
    stdouts_match = app.stdout == sys.stdout

    # This will be used to capture app.stdout and sys.stdout
    copy_cmd_stdout = StdSim(app.stdout)

    # This will be used to capture sys.stderr
    copy_stderr = StdSim(sys.stderr)

    try:
        app.stdout = copy_cmd_stdout
        if stdouts_match:
            sys.stdout = app.stdout
        with redirect_stderr(copy_stderr):
            app.onecmd_plus_hooks(cmd)
    finally:
        app.stdout = copy_cmd_stdout.inner_stream
        if stdouts_match:
            sys.stdout = app.stdout

    out = copy_cmd_stdout.getvalue()
    err = copy_stderr.getvalue()
    return normalize(out), normalize(err)


@pytest.fixture
def base_app():
    return cmd2.Cmd(include_py=True, include_ipy=True)


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
